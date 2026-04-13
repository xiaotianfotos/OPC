/**
 * Cut Video Editor API Client
 *
 * API endpoints for the Cut video editing feature
 */

import axios from 'axios';

const API_BASE = '/api/skill/cut';

/**
 * Upload video file and run ASR
 * @param {FormData} formData - File data with 'file' field
 * @returns {Promise<{success: boolean, file_id: string, filename: string, asr_result: object}>}
 */
export async function uploadVideo(formData) {
  const response = await axios.post(`${API_BASE}/upload`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });
  return response.data;
}

/**
 * Initialize Cut with existing ASR JSON
 * @param {Object} params - {video: string, json?: string}
 * @returns {Promise<{success: boolean, serverUrl: string}>}
 */
export async function initCut(params) {
  const response = await axios.post(`${API_BASE}/init`, params);
  return response.data;
}

/**
 * Get video URL for playback
 * @param {string} fileId - File identifier
 * @returns {string} Video URL
 */
export function getVideoUrl(fileId) {
  return `${API_BASE}/video/${fileId}`;
}

/**
 * Get saved metadata for a file
 * @param {string} fileId - File identifier
 * @returns {Promise<{success: boolean, metadata?: object}>}
 */
export async function getMetadata(fileId) {
  const response = await axios.get(`${API_BASE}/metadata/${fileId}`);
  return response.data;
}

/**
 * Export video with cut ranges (legacy, no progress)
 * @param {Object} params - Export parameters
 * @param {string} params.file_id - File identifier
 * @param {Array<{start: number, end: number}>} params.cuts - Cut ranges
 * @param {string} params.format - Output format (mp4, etc)
 * @param {boolean} params.apply_valley_correction - Apply energy valley correction
 * @param {number} params.energy_threshold - Energy threshold for valley detection
 * @param {number} params.search_ms - Search range in milliseconds
 * @returns {Promise<{success: boolean, download_url?: string, error?: string}>}
 */
export async function exportVideo(params) {
  const response = await axios.post(`${API_BASE}/export`, params);
  return response.data;
}

/**
 * Export video with SSE progress streaming
 * @param {Object} params - Export parameters
 * @param {string} params.file_id - File identifier
 * @param {Array<{start: number, end: number}>} params.cuts - Cut ranges
 * @param {string} params.format - Output format (mp4, etc)
 * @param {boolean} params.apply_valley_correction - Apply energy valley correction
 * @param {number} params.energy_threshold - Energy threshold for valley detection
 * @param {number} params.search_ms - Search range in milliseconds
 * @param {Function} onProgress - Progress callback: (event) => void
 * @returns {Promise<{success: boolean, download_url?: string, error?: string}>}
 */
export async function exportVideoWithProgress(params, onProgress) {
  const response = await fetch(`${API_BASE}/export-stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(params)
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Export failed' }));
    throw new Error(error.error || 'Export failed');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let downloadUrl = null;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Parse SSE events
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';

      for (const event of events) {
        const lines = event.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'progress' && onProgress) {
              onProgress(data);
            } else if (data.type === 'complete') {
              downloadUrl = data.download_url;
            } else if (data.type === 'error') {
              throw new Error(data.message);
            }
          }
        }
      }
    }
  } finally {
    reader.cancel();
  }

  return { success: true, download_url: downloadUrl };
}

/**
 * Find energy valley at cut boundary
 * @param {Object} params - Valley detection parameters
 * @param {string} params.file_id - File identifier
 * @param {number} params.start_time - Start time to search
 * @param {number} params.end_time - End time to search
 * @param {number} params.energy_threshold - Energy threshold (0-1)
 * @param {number} params.search_ms - Search range in milliseconds
 * @returns {Promise<{success: boolean, valley_time?: number, error?: string}>}
 */
export async function findValley(params) {
  const response = await axios.post(`${API_BASE}/find-valley`, params);
  return response.data;
}

/**
 * Get download URL for exported file
 * @param {string} filename - Exported filename
 * @returns {string} Download URL
 */
export function getDownloadUrl(filename) {
  return `${API_BASE}/download/${filename}`;
}

/**
 * Check cut service status
 * @returns {Promise<{status: string, serverUrl?: string}>}
 */
export async function getCutStatus() {
  const response = await axios.get(`${API_BASE}/status`);
  return response.data;
}

/**
 * Save metadata for a file
 * @param {string} fileId - File identifier
 * @param {Object} metadata - Metadata to save
 * @returns {Promise<{success: boolean}>}
 */
export async function saveMetadata(fileId, metadata) {
  const response = await axios.post(`${API_BASE}/metadata/${fileId}`, metadata);
  return response.data;
}
