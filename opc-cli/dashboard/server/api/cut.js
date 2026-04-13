/**
 * Cut API Routes
 * Express routes for the Cut video editing feature
 */

import express from 'express';
import multer from 'multer';
import path from 'path';
import fs from 'fs';

import {
  saveUploadedFile,
  getVideoPath,
  getFileMetadata,
  saveMetadata,
  loadMetadata,
  fileExists
} from '../services/cut/file.service.js';

import {
  runAsrPipeline,
  wrapAsrForFrontend
} from '../services/cut/asr.service.js';

import {
  loadAudioForValley,
  findValleyBoundaries
} from '../services/cut/valley.service.js';

import {
  exportVideo,
  exportVideoWithProgress,
  getDownloadInfo
} from '../services/cut/export.service.js';

import { ensureWorkspaceDirs } from '../services/cut/config.js';

const router = express.Router();

// Configure multer for file uploads
const { uploadsDir, outputsDir } = ensureWorkspaceDirs();
const upload = multer({
  dest: uploadsDir,
  limits: {
    fileSize: 500 * 1024 * 1024 // 500MB max
  }
});

// ============ Upload & Init Endpoints ============

/**
 * POST /api/skill/cut/upload
 * Upload video file and run ASR
 * Body: multipart/form-data with 'file' field and optional 'language' field
 */
router.post('/upload', upload.single('file'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded' });
    }

    const { originalname, path: tempPath } = req.file;
    const language = req.body.language || 'Chinese';

    console.log(`[Cut API] Uploading file: ${originalname}`);

    // Save uploaded file
    const { fileId, filePath, filename } = await saveUploadedFile(req.file, originalname);

    // Run ASR pipeline
    console.log(`[Cut API] Running ASR on ${filePath}`);
    const asrResult = await runAsrPipeline(filePath, language);

    // Wrap for frontend compatibility
    const asrResultForFrontend = wrapAsrForFrontend(asrResult);

    // Save metadata
    await saveMetadata(fileId, {
      original_filename: filename,
      file_path: filePath,
      asr_result: asrResult
    });

    res.json({
      success: true,
      file_id: fileId,
      filename: filename,
      asr_result: asrResultForFrontend
    });

  } catch (error) {
    console.error('[Cut API] Upload failed:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * POST /api/skill/cut/init
 * Initialize with existing video and optional ASR JSON
 * Body: { video: string, json?: string, language?: string }
 */
router.post('/init', async (req, res) => {
  try {
    const { video, json: jsonPath, language = 'Chinese' } = req.body;

    if (!video) {
      return res.status(400).json({ error: 'video parameter is required' });
    }

    // Check if video file exists
    if (!fileExists(video)) {
      return res.status(400).json({ error: `Video file not found: ${video}` });
    }

    // Generate file ID from video filename
    const filename = path.basename(video);
    const fileId = path.basename(video, path.extname(video));

    let asrResult;

    if (jsonPath && fileExists(jsonPath)) {
      // Load existing ASR result
      console.log(`[Cut API] Loading existing JSON: ${jsonPath}`);
      const existingMetadata = await loadMetadata(fileId);

      if (existingMetadata && existingMetadata.asr_result) {
        asrResult = existingMetadata.asr_result;
      } else {
        // Read JSON file directly
        const content = await fs.promises.readFile(jsonPath, 'utf-8');
        const data = JSON.parse(content);

        // Handle different JSON formats
        if (data.asr_result) {
          asrResult = data.asr_result;
        } else if (data.words || data.segments) {
          asrResult = data;
        } else {
          throw new Error('Invalid ASR JSON format');
        }
      }

      // Save metadata so editor can load it via /file/:fileId
      await saveMetadata(fileId, {
        original_filename: filename,
        file_path: video,
        asr_result: asrResult
      });
    } else {
      // Run ASR on video
      console.log(`[Cut API] Running ASR on: ${video}`);
      const rawAsrResult = await runAsrPipeline(video, language);
      asrResult = wrapAsrForFrontend(rawAsrResult);

      // Save metadata
      await saveMetadata(fileId, {
        original_filename: filename,
        file_path: video,
        asr_result: rawAsrResult
      });
    }

    // Ensure frontend compatibility
    const asrResultForFrontend = wrapAsrForFrontend(asrResult);

    res.json({
      success: true,
      file_id: fileId,
      filename: filename,
      asr_result: asrResultForFrontend
    });

  } catch (error) {
    console.error('[Cut API] Init failed:', error);
    res.status(500).json({ error: error.message });
  }
});

// ============ Video & Metadata Endpoints ============

/**
 * GET /api/skill/cut/video/:fileId
 * Stream video file
 */
router.get('/video/:fileId', async (req, res) => {
  try {
    const { fileId } = req.params;

    // Try to get video path from registry or metadata
    let videoPath = getVideoPath(fileId);

    if (!videoPath) {
      // Check metadata
      const metadata = await loadMetadata(fileId);
      if (metadata && metadata.file_path) {
        videoPath = metadata.file_path;
      }
    }

    if (!videoPath || !fileExists(videoPath)) {
      return res.status(404).json({ error: 'Video file not found' });
    }

    // Stream file
    res.sendFile(videoPath);

  } catch (error) {
    console.error('[Cut API] Get video failed:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /api/skill/cut/metadata/:fileId
 * Get ASR metadata JSON
 */
router.get('/metadata/:fileId', async (req, res) => {
  try {
    const { fileId } = req.params;
    const metadata = await loadMetadata(fileId);

    if (!metadata) {
      return res.status(404).json({ error: 'Metadata not found' });
    }

    res.json(metadata);

  } catch (error) {
    console.error('[Cut API] Get metadata failed:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /api/skill/cut/file/:fileId
 * Get file info with ASR result for editor
 */
router.get('/file/:fileId', async (req, res) => {
  try {
    const { fileId } = req.params;
    const metadata = await loadMetadata(fileId);

    if (!metadata) {
      return res.status(404).json({ error: 'File not found' });
    }

    // Get ASR result in frontend format
    const asrResult = wrapAsrForFrontend(metadata.asr_result || {});

    res.json({
      success: true,
      file: {
        file_id: fileId,
        filename: metadata.original_filename || path.basename(metadata.file_path || fileId),
        asr_result: asrResult
      }
    });

  } catch (error) {
    console.error('[Cut API] Get file failed:', error);
    res.status(500).json({ error: error.message });
  }
});

// ============ Valley Detection Endpoints ============

/**
 * POST /api/skill/cut/find-valley
 * Find energy valley for cut boundaries
 * Body: { audio_path, word_start_time, word_end_time, left_search_ms?, right_search_ms?, threshold? }
 */
router.post('/find-valley', async (req, res) => {
  try {
    const {
      audio_path,
      word_start_time: wordStartTime,
      word_end_time: wordEndTime,
      left_search_ms: leftSearchMs = 100,
      right_search_ms: rightSearchMs = 100,
      threshold = 0.7
    } = req.body;

    if (!audio_path) {
      return res.status(400).json({ error: 'audio_path is required' });
    }

    if (wordStartTime === undefined || wordEndTime === undefined) {
      return res.status(400).json({ error: 'word_start_time and word_end_time are required' });
    }

    if (!fileExists(audio_path)) {
      return res.status(404).json({ error: `Audio file not found: ${audio_path}` });
    }

    // Load audio and find valleys
    const { wav, sampleRate } = await loadAudioForValley(audio_path);

    const result = await findValleyBoundaries(
      wav,
      sampleRate,
      wordStartTime,
      wordEndTime,
      leftSearchMs,
      rightSearchMs,
      threshold
    );

    res.json(result);

  } catch (error) {
    console.error('[Cut API] Find valley failed:', error);
    res.status(500).json({ error: error.message });
  }
});

// ============ Export Endpoints ============

/**
 * POST /api/skill/cut/export-stream
 * Export video with cuts using SSE for progress updates
 * Body: { file_id, cuts[], format?, apply_valley_correction?, energy_threshold?, search_ms? }
 */
router.post('/export-stream', async (req, res) => {
  const {
    file_id: fileId,
    cuts = [],
    format = 'mp4',
    apply_valley_correction: applyValleyCorrection = false,
    energy_threshold: energyThreshold = 0.7,
    search_ms: searchMs = 100
  } = req.body;

  if (!fileId) {
    res.status(400).json({ error: 'file_id is required' });
    return;
  }

  if (!cuts || cuts.length === 0) {
    res.status(400).json({ error: 'cuts are required' });
    return;
  }

  // Get source video path
  const metadata = await loadMetadata(fileId);
  if (!metadata) {
    res.status(404).json({ error: 'File metadata not found' });
    return;
  }

  const sourcePath = metadata.file_path;
  if (!sourcePath || !fileExists(sourcePath)) {
    res.status(404).json({ error: 'Source video not found' });
    return;
  }

  // Set up SSE headers
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');

  const sendEvent = (data) => {
    res.write(`data: ${JSON.stringify(data)}\n\n`);
  };

  try {
    sendEvent({ type: 'start', message: '开始导出视频...' });

    // Export video with progress callback
    const result = await exportVideoWithProgress(
      sourcePath,
      cuts,
      null,
      {
        applyValleyCorrection,
        energyThreshold,
        searchMs,
        format
      },
      (progress) => {
        sendEvent({ type: 'progress', ...progress });
      }
    );

    // Generate download URL
    const downloadFilename = path.basename(result.outputPath);
    const downloadUrl = `/api/skill/cut/download/${downloadFilename}`;

    sendEvent({
      type: 'complete',
      success: true,
      download_url: downloadUrl,
      output_file: result.outputPath,
      cuts: result.cuts
    });

    res.end();
  } catch (error) {
    console.error('[Cut API] Export failed:', error);
    sendEvent({ type: 'error', message: error.message });
    res.end();
  }
});

/**
 * POST /api/skill/cut/export
 * Export video with cuts (legacy, returns JSON without progress)
 */
router.post('/export', async (req, res) => {
  try {
    const {
      file_id: fileId,
      cuts = [],
      format = 'mp4',
      apply_valley_correction: applyValleyCorrection = true,
      energy_threshold: energyThreshold = 0.7,
      search_ms: searchMs = 100
    } = req.body;

    if (!fileId) {
      return res.status(400).json({ error: 'file_id is required' });
    }

    if (!cuts || cuts.length === 0) {
      return res.status(400).json({ error: 'cuts are required' });
    }

    // Get source video path
    const metadata = await loadMetadata(fileId);
    if (!metadata) {
      return res.status(404).json({ error: 'File metadata not found' });
    }

    const sourcePath = metadata.file_path;
    if (!sourcePath || !fileExists(sourcePath)) {
      return res.status(404).json({ error: 'Source video not found' });
    }

    // Export video
    const result = await exportVideo(sourcePath, cuts, null, {
      applyValleyCorrection,
      energyThreshold,
      searchMs,
      format
    });

    // Generate download URL
    const downloadFilename = path.basename(result.outputPath);
    const downloadUrl = `/api/skill/cut/download/${downloadFilename}`;

    res.json({
      success: true,
      output_file: result.outputPath,
      download_url: downloadUrl,
      cuts: result.cuts
    });

  } catch (error) {
    console.error('[Cut API] Export failed:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /api/skill/cut/download/:filename
 * Download exported file
 */
router.get('/download/:filename', (req, res) => {
  try {
    const { filename } = req.params;

    // Sanitize filename to prevent path traversal attacks
    if (filename.includes('..') || filename.includes('/') || filename.includes('\\')) {
      return res.status(400).json({ error: 'Invalid filename' });
    }

    const filePath = path.join(outputsDir, filename);

    if (!fileExists(filePath)) {
      return res.status(404).json({ error: 'File not found' });
    }

    res.download(filePath);

  } catch (error) {
    console.error('[Cut API] Download failed:', error);
    res.status(500).json({ error: error.message });
  }
});

// ============ Status Endpoint ============

/**
 * GET /api/skill/cut/status
 * Get Cut service status
 */
router.get('/status', async (req, res) => {
  // Find the most recently saved metadata file as the active file
  let activeFileId = null;
  try {
    const files = await fs.promises.readdir(outputsDir);
    const jsonFiles = files.filter(f => f.endsWith('.json'));
    if (jsonFiles.length > 0) {
      // Pick the most recently modified file
      let latestTime = 0;
      for (const f of jsonFiles) {
        const stat = await fs.promises.stat(path.join(outputsDir, f));
        if (stat.mtimeMs > latestTime) {
          latestTime = stat.mtimeMs;
          activeFileId = f.replace('.json', '');
        }
      }
    }
  } catch (e) {
    // ignore
  }

  res.json({
    name: 'cut',
    status: activeFileId ? 'running' : 'idle',
    type: 'native',
    message: activeFileId
      ? `Cut service is running (active: ${activeFileId})`
      : 'Cut service is idle (no file loaded)',
    file_id: activeFileId
  });
});

export default router;
