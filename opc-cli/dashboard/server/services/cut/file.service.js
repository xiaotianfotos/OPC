/**
 * Cut File Service
 * Handles video file uploads, retrieval, and metadata storage
 */

import fs from 'fs';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';
import { ensureWorkspaceDirs } from './config.js';

// In-memory file tracking (could be replaced with database)
const fileRegistry = new Map();

/**
 * Save uploaded video file
 * @param {File} file - Uploaded file object (from multer)
 * @param {string} originalFilename - Original filename
 * @returns {Promise<{fileId: string, filePath: string, filename: string}>}
 */
export async function saveUploadedFile(file, originalFilename) {
  const { uploadsDir } = ensureWorkspaceDirs();

  const fileId = uuidv4().substring(0, 8);
  const ext = path.extname(originalFilename);
  const filename = `${fileId}${ext}`;
  const filePath = path.join(uploadsDir, filename);

  // Move uploaded file to destination
  await fs.promises.rename(file.path, filePath);

  // Register file
  fileRegistry.set(fileId, {
    fileId,
    originalFilename,
    filePath,
    uploadedAt: new Date().toISOString()
  });

  return { fileId, filePath, filename: originalFilename };
}

/**
 * Get video file path by ID
 * @param {string} fileId - File ID
 * @returns {string|null} File path or null if not found
 */
export function getVideoPath(fileId) {
  const fileData = fileRegistry.get(fileId);
  if (fileData) {
    return fileData.filePath;
  }

  // Try to find file in uploads directory
  const { uploadsDir } = ensureWorkspaceDirs();
  const files = fs.readdirSync(uploadsDir);
  const matchingFile = files.find(f => f.startsWith(fileId));

  if (matchingFile) {
    return path.join(uploadsDir, matchingFile);
  }

  return null;
}

/**
 * Get file metadata
 * @param {string} fileId - File ID
 * @returns {Object|null} File metadata or null
 */
export function getFileMetadata(fileId) {
  return fileRegistry.get(fileId) || null;
}

/**
 * Save ASR metadata to workspace
 * @param {string} fileId - File ID
 * @param {Object} metadata - ASR result metadata
 * @returns {Promise<string>} Path to saved metadata file
 */
export async function saveMetadata(fileId, metadata) {
  const { outputsDir } = ensureWorkspaceDirs();
  const metadataPath = path.join(outputsDir, `${fileId}.json`);

  const fullMetadata = {
    file_id: fileId,
    original_filename: metadata.original_filename || fileId,
    file_path: metadata.file_path,
    asr_result: metadata.asr_result,
    saved_at: new Date().toISOString()
  };

  await fs.promises.writeFile(
    metadataPath,
    JSON.stringify(fullMetadata, null, 2),
    'utf-8'
  );

  return metadataPath;
}

/**
 * Load ASR metadata from workspace
 * @param {string} fileId - File ID
 * @returns {Promise<Object|null>} Parsed metadata or null
 */
export async function loadMetadata(fileId) {
  const { outputsDir } = ensureWorkspaceDirs();
  const metadataPath = path.join(outputsDir, `${fileId}.json`);

  try {
    const content = await fs.promises.readFile(metadataPath, 'utf-8');
    return JSON.parse(content);
  } catch (error) {
    return null;
  }
}

/**
 * Check if file exists
 * @param {string} filePath - File path
 * @returns {boolean} True if file exists
 */
export function fileExists(filePath) {
  return fs.existsSync(filePath);
}

/**
 * Delete file by ID
 * @param {string} fileId - File ID
 * @returns {Promise<boolean>} True if deleted
 */
export async function deleteFile(fileId) {
  const fileData = fileRegistry.get(fileId);
  if (!fileData) return false;

  try {
    await fs.promises.unlink(fileData.filePath);
    fileRegistry.delete(fileId);

    // Also delete metadata if exists
    const { outputsDir } = ensureWorkspaceDirs();
    const metadataPath = path.join(outputsDir, `${fileId}.json`);
    if (fs.existsSync(metadataPath)) {
      await fs.promises.unlink(metadataPath);
    }

    return true;
  } catch (error) {
    console.error(`[File Service] Failed to delete file ${fileId}:`, error.message);
    return false;
  }
}

/**
 * Get all registered files
 * @returns {Array} Array of file metadata
 */
export function getAllFiles() {
  return Array.from(fileRegistry.values());
}
