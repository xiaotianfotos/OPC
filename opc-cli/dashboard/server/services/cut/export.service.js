/**
 * Cut Export Service
 * Handles video export using ffmpeg with valley correction support
 */

/**
 * Detect video bitrate from source file using ffprobe
 * @param {string} filePath - Path to video file
 * @returns {Promise<string>} Bitrate string like '40M'
 */
function detectVideoBitrate(filePath) {
  return new Promise((resolve, reject) => {
    ffmpeg.ffprobe(filePath, (err, metadata) => {
      if (err) {
        console.warn('[Export Service] ffprobe failed, defaulting to 20M:', err.message);
        resolve('20M');
        return;
      }
      // Try video stream bitrate first
      const videoStream = metadata.streams?.find(s => s.codec_type === 'video');
      if (videoStream?.bit_rate) {
        const bps = parseInt(videoStream.bit_rate);
        const mbps = Math.round(bps / 1_000_000);
        resolve(`${mbps}M`);
        return;
      }
      // Fallback to format bitrate
      if (metadata.format?.bit_rate) {
        const bps = parseInt(metadata.format.bit_rate);
        // Subtract ~200kbps for audio estimate
        const videoBps = bps - 200_000;
        const mbps = Math.max(1, Math.round(videoBps / 1_000_000));
        resolve(`${mbps}M`);
        return;
      }
      resolve('20M');
    });
  });
}

import ffmpeg from 'fluent-ffmpeg';
import fs from 'fs';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';
import { ensureWorkspaceDirs } from './config.js';
import { applyValleyCorrection } from './valley.service.js';

/**
 * Export video with specified cuts
 * @param {string} sourcePath - Source video path
 * @param {Array} cuts - Array of {start, end} cut boundaries
 * @param {string} outputPath - Output file path
 * @param {Object} options - Export options
 * @param {Function} onProgress - Progress callback
 * @returns {Promise<{success: boolean, outputPath: string, warning?: string}>}
 */
export async function exportVideoWithProgress(sourcePath, cuts, outputPath, options = {}, onProgress) {
  const {
    applyValleyCorrection: applyCorrection = false,
    energyThreshold = 0.7,
    searchMs = 100,
    format = 'mp4'
  } = options;

  // Detect source video bitrate via ffprobe
  const videoBitrate = await detectVideoBitrate(sourcePath);
  console.log(`[Export Service] Source video bitrate: ${videoBitrate}bps`);

  if (!fs.existsSync(sourcePath)) {
    throw new Error(`Source video not found: ${sourcePath}`);
  }

  if (!outputPath) {
    const { outputsDir } = ensureWorkspaceDirs();
    const outputId = uuidv4().substring(0, 8);
    outputPath = path.join(outputsDir, `export_${outputId}.${format}`);
  }

  let correctedCuts = cuts;

  // Apply valley correction if requested
  if (applyCorrection) {
    try {
      console.log('[Export Service] Applying valley correction...');
      correctedCuts = await applyValleyCorrection(
        cuts,
        sourcePath,
        energyThreshold,
        searchMs
      );
      console.log('[Export Service] Valley correction complete');
    } catch (error) {
      console.warn('[Export Service] Valley correction failed, using original cuts:', error.message);
      correctedCuts = cuts;
    }
  }

  // Perform export
  if (correctedCuts.length === 0) {
    throw new Error('No cuts specified for export');
  }

  const totalSegments = correctedCuts.length;

  if (totalSegments === 1) {
    await exportSingleSegmentWithProgress(sourcePath, correctedCuts[0], outputPath, videoBitrate, onProgress);
  } else {
    await exportMultipleSegmentsWithProgress(sourcePath, correctedCuts, outputPath, totalSegments, videoBitrate, onProgress);
  }

  return {
    success: true,
    outputPath,
    cuts: correctedCuts
  };
}

/**
 * Export video with specified cuts (no progress callback)
 * @param {string} sourcePath - Source video path
 * @param {Array} cuts - Array of {start, end} cut boundaries
 * @param {string} outputPath - Output file path
 * @param {Object} options - Export options
 * @returns {Promise<{success: boolean, outputPath: string, warning?: string}>}
 */
export async function exportVideo(sourcePath, cuts, outputPath, options = {}) {
  return exportVideoWithProgress(sourcePath, cuts, outputPath, options, () => {});
}

/**
 * Export a single video segment with progress callback
 * @param {string} sourcePath - Source video path
 * @param {Object} cut - {start, end} cut boundaries
 * @param {string} outputPath - Output file path
 * @param {Function} onProgress - Progress callback
 * @returns {Promise<void>}
 */
function exportSingleSegmentWithProgress(sourcePath, cut, outputPath, videoBitrate, onProgress) {
  return new Promise((resolve, reject) => {
    const duration = cut.end - cut.start;

    console.log(`[Export Service] Exporting single segment: ${cut.start}s - ${cut.end}s (duration: ${duration.toFixed(3)}s)`);

    ffmpeg(sourcePath)
      .setStartTime(cut.start)
      .setDuration(duration)
      .outputOptions([
        '-c:v hevc_nvenc',
        '-c:a aac',
        `-b:v ${videoBitrate}`
      ])
      .output(outputPath)
      .on('start', (commandLine) => {
        console.log('[Export Service] FFmpeg command:', commandLine);
        onProgress({ segment: 1, totalSegments: 1, message: '开始导出...', progress: 0 });
      })
      .on('progress', (progress) => {
        const percent = Math.round(progress.percent || 0);
        onProgress({ segment: 1, totalSegments: 1, progress: percent, message: `导出中... ${percent}%` });
      })
      .on('end', () => {
        console.log('[Export Service] Single segment export complete');
        onProgress({ segment: 1, totalSegments: 1, progress: 100, message: '导出完成!' });
        resolve();
      })
      .on('error', (error) => {
        console.error('[Export Service] Export failed:', error.message);
        reject(new Error(`FFmpeg error: ${error.message}`));
      })
      .run();
  });
}

/**
 * Export multiple video segments with progress callback
 * @param {string} sourcePath - Source video path
 * @param {Array} cuts - Array of cut boundaries
 * @param {string} outputPath - Output file path
 * @param {number} totalSegments - Total number of segments
 * @param {Function} onProgress - Progress callback
 * @returns {Promise<void>}
 */
async function exportMultipleSegmentsWithProgress(sourcePath, cuts, outputPath, totalSegments, videoBitrate, onProgress) {
  console.log(`[Export Service] Exporting ${totalSegments} segments in single pass`);

  // Build filter_complex for trim + concat in one ffmpeg pass
  const filterParts = [];
  const mapArgs = [];
  for (let i = 0; i < cuts.length; i++) {
    const cut = cuts[i];
    filterParts.push(`[0:v]trim=start=${cut.start}:end=${cut.end},setpts=PTS-STARTPTS[v${i}]`);
    filterParts.push(`[0:a]atrim=start=${cut.start}:end=${cut.end},asetpts=PTS-STARTPTS[a${i}]`);
    mapArgs.push(`[v${i}]`, `[a${i}]`);
  }
  const concatFilter = `${mapArgs.join('')}concat=n=${cuts.length}:v=1:a=1[outv][outa]`;
  const filterComplex = [...filterParts, concatFilter].join(';');

  console.log(`[Export Service] Filter: ${filterComplex}`);

  return new Promise((resolve, reject) => {
    ffmpeg(sourcePath)
      .complexFilter(filterComplex)
      .outputOptions([
        '-map', '[outv]',
        '-map', '[outa]',
        '-c:v', 'hevc_nvenc',
        '-c:a', 'aac',
        `-b:v`, videoBitrate
      ])
      .output(outputPath)
      .on('start', (commandLine) => {
        console.log('[Export Service] FFmpeg command:', commandLine);
        onProgress({ segment: 1, totalSegments, progress: 0, message: '正在导出...' });
      })
      .on('progress', (progress) => {
        const percent = Math.round(progress.percent || 0);
        onProgress({ segment: 1, totalSegments, progress: percent, message: `导出中... ${percent}%` });
      })
      .on('end', () => {
        console.log('[Export Service] Single pass export complete');
        onProgress({ segment: 1, totalSegments, progress: 100, message: '导出完成!' });
        resolve();
      })
      .on('error', (error) => {
        console.error('[Export Service] Export failed:', error.message);
        reject(new Error(`FFmpeg error: ${error.message}`));
      })
      .run();
  });
}

/**
 * Export a single video segment
 * @param {string} sourcePath - Source video path
 * @param {Object} cut - {start, end} cut boundaries
 * @param {string} outputPath - Output file path
 * @returns {Promise<void>}
 */
function exportSingleSegment(sourcePath, cut, outputPath) {
  return exportSingleSegmentWithProgress(sourcePath, cut, outputPath, () => {});
}

/**
 * Export multiple video segments and concatenate
 * @param {string} sourcePath - Source video path
 * @param {Array} cuts - Array of cut boundaries
 * @param {string} outputPath - Output file path
 * @returns {Promise<void>}
 */
async function exportMultipleSegments(sourcePath, cuts, outputPath) {
  const { outputsDir } = ensureWorkspaceDirs();
  const segmentFiles = [];

  try {
    console.log(`[Export Service] Exporting ${cuts.length} segments`);

    // Export each segment
    for (let i = 0; i < cuts.length; i++) {
      const cut = cuts[i];
      const segmentPath = path.join(outputsDir, `segment_${uuidv4().substring(0, 8)}.mp4`);
      const duration = cut.end - cut.start;

      console.log(`[Export Service] Exporting segment ${i + 1}/${cuts.length}: ${cut.start}s - ${cut.end}s`);

      await new Promise((resolve, reject) => {
        ffmpeg(sourcePath)
          .setStartTime(cut.start)
          .setDuration(duration)
          // Use GPU acceleration for decoding and encoding
          .inputOptions(['-hwaccel cuda', '-hwaccel_output_format cuda'])
          .outputOptions([
            '-c:v hevc_nvenc',  // NVIDIA GPU encoding
            '-c:a aac',         // AAC audio encoding
            '-preset p1',       // Fastest preset
            '-rc:v vbr',        // Variable bitrate
            '-qmin 18',
            '-qmax 28'
          ])
          .output(segmentPath)
          .on('start', (commandLine) => {
            console.log(`[Export Service] Segment ${i + 1} FFmpeg command:`, commandLine);
          })
          .on('progress', (progress) => {
            const percent = Math.round((progress.percent || 0));
            const fps = progress.fps || 0;
            console.log(`[Export Service] Segment ${i + 1}/${cuts.length} Progress: ${percent}% (fps: ${fps})`);
          })
          .on('end', () => {
            console.log(`[Export Service] Segment ${i + 1}/${cuts.length} complete`);
            resolve();
          })
          .on('error', (error) => {
            console.error(`[Export Service] Segment ${i + 1} failed:`, error.message);
            reject(new Error(`FFmpeg error: ${error.message}`));
          })
          .run();
      });

      segmentFiles.push(segmentPath);
    }

    // Create concat list file
    const concatListPath = path.join(outputsDir, `concat_${uuidv4().substring(0, 8)}.txt`);
    const concatContent = segmentFiles.map(f => `file '${f}'`).join('\n');
    await fs.promises.writeFile(concatListPath, concatContent);

    // Concatenate segments
    await new Promise((resolve, reject) => {
      ffmpeg()
        .input(concatListPath)
        .inputOptions(['-f', 'concat', '-safe', '0'])
        .outputOptions(['-c', 'copy'])
        .output(outputPath)
        .on('start', (commandLine) => {
          console.log('[Export Service] Concat command:', commandLine);
        })
        .on('end', resolve)
        .on('error', reject)
        .run();
    });

    console.log('[Export Service] Multiple segments export complete');

  } finally {
    // Clean up segment files
    for (const file of segmentFiles) {
      if (fs.existsSync(file)) {
        fs.unlinkSync(file);
      }
    }

    // Clean up concat list (use the same variable from try block)
    if (concatListPath && fs.existsSync(concatListPath)) {
      fs.unlinkSync(concatListPath);
    }
  }
}

/**
 * Get download info for exported file
 * @param {string} outputPath - Path to exported file
 * @returns {{filename: string, path: string, size: number}}
 */
export function getDownloadInfo(outputPath) {
  if (!fs.existsSync(outputPath)) {
    throw new Error('Exported file not found');
  }

  const stats = fs.statSync(outputPath);

  return {
    filename: path.basename(outputPath),
    path: outputPath,
    size: stats.size
  };
}

/**
 * Clean up temporary export files
 * @param {Array} filePaths - Array of file paths to delete
 */
export async function cleanupFiles(filePaths) {
  for (const filePath of filePaths) {
    try {
      if (fs.existsSync(filePath)) {
        await fs.promises.unlink(filePath);
      }
    } catch (error) {
      console.warn(`[Export Service] Failed to cleanup ${filePath}:`, error.message);
    }
  }
}

/**
 * Generate safe filename for export
 * @param {string} fileId - Original file ID
 * @param {string} format - Output format
 * @returns {string} Safe filename
 */
export function generateExportFilename(fileId, format = 'mp4') {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').substring(0, 19);
  return `${fileId}_exported_${timestamp}.${format}`;
}
