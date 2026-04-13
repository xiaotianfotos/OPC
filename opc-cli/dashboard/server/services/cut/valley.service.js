/**
 * Cut Valley Service
 * Energy valley detection algorithm for clean video cuts
 * Ported from Python: scripts/cut/valley_finder.py
 */

import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';
import os from 'os';
import { v4 as uuidv4 } from 'uuid';
import { ensureWorkspaceDirs } from './config.js';

// Constants matching Python implementation
const WINDOW_SIZE_MS = 20; // 20ms window for energy calculation
const STEP_MS = 5; // 5ms step for valley searching
const DEFAULT_SEARCH_MS = 100; // Default search range in milliseconds
const DEFAULT_THRESHOLD = 0.7; // Default energy ratio threshold

/**
 * Load audio from video file for valley analysis
 * Extracts audio as 16kHz mono WAV and parses into Float32Array
 * @param {string} audioPath - Path to audio/video file
 * @returns {Promise<{wav: Float32Array, sampleRate: number}>}
 */
export async function loadAudioForValley(audioPath) {
  const { outputsDir } = ensureWorkspaceDirs();
  const tempWav = path.join(outputsDir, `temp_audio_${uuidv4().substring(0, 8)}.wav`);

  // Extract audio using ffmpeg: 16kHz, mono, PCM 16-bit
  await extractAudio(audioPath, tempWav);

  try {
    const { wavData, sampleRate } = await parseWavFile(tempWav);
    return { wav: wavData, sampleRate };
  } finally {
    // Clean up temp WAV file
    if (fs.existsSync(tempWav)) {
      fs.unlinkSync(tempWav);
    }
  }
}

/**
 * Extract audio from video file using ffmpeg
 * @param {string} inputPath - Input file path
 * @param {string} outputPath - Output WAV path
 * @returns {Promise<void>}
 */
function extractAudio(inputPath, outputPath) {
  return new Promise((resolve, reject) => {
    const args = [
      '-y', // Overwrite output
      '-i', inputPath,
      '-vn', // No video
      '-acodec', 'pcm_s16le', // PCM 16-bit signed little-endian
      '-ar', '16000', // 16kHz sample rate
      '-ac', '1', // Mono
      outputPath
    ];

    console.log(`[Valley Service] Extracting audio: ffmpeg ${args.join(' ')}`);

    const proc = spawn('ffmpeg', args);
    let stderr = '';

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`ffmpeg failed: ${stderr}`));
      }
    });

    proc.on('error', (error) => {
      reject(new Error(`Failed to spawn ffmpeg: ${error.message}`));
    });
  });
}

/**
 * Parse WAV file and extract audio data as Float32Array
 * @param {string} wavPath - Path to WAV file
 * @returns {Promise<{wavData: Float32Array, sampleRate: number}>}
 */
async function parseWavFile(wavPath) {
  const buffer = await fs.promises.readFile(wavPath);

  // WAV file header parsing
  const view = new DataView(buffer.buffer, buffer.byteOffset);

  // Verify RIFF header
  const riffId = String.fromCharCode(
    view.getUint8(0),
    view.getUint8(1),
    view.getUint8(2),
    view.getUint8(3)
  );
  if (riffId !== 'RIFF') {
    throw new Error('Invalid WAV file: missing RIFF header');
  }

  // Get format chunk info
  const numChannels = view.getUint16(22, true); // Little-endian
  const sampleRate = view.getUint32(24, true);
  const bitsPerSample = view.getUint16(34, true);

  // Find data chunk
  let dataOffset = 36;
  while (dataOffset < buffer.length - 8) {
    const chunkId = String.fromCharCode(
      view.getUint8(dataOffset),
      view.getUint8(dataOffset + 1),
      view.getUint8(dataOffset + 2),
      view.getUint8(dataOffset + 3)
    );
    const chunkSize = view.getUint32(dataOffset + 4, true);

    if (chunkId === 'data') {
      dataOffset += 8;
      break;
    }
    dataOffset += 8 + chunkSize;
  }

  // Calculate samples per channel
  const bytesPerSample = bitsPerSample / 8;
  const blockAlign = numChannels * bytesPerSample;
  const numSamples = (buffer.length - dataOffset) / blockAlign;

  // Convert to Float32Array normalized to [-1, 1]
  const wavData = new Float32Array(numSamples);

  if (bitsPerSample === 16) {
    const int16View = new Int16Array(buffer.buffer, buffer.byteOffset + dataOffset);
    for (let i = 0; i < numSamples; i++) {
      // Interleaved channels - just take first channel
      wavData[i] = int16View[i * numChannels] / 32768.0;
    }
  } else {
    throw new Error(`Unsupported bits per sample: ${bitsPerSample}`);
  }

  return { wavData, sampleRate };
}

/**
 * Calculate RMS energy for a window of audio samples
 * @param {Float32Array} wav - Audio waveform data
 * @param {number} startIdx - Start sample index
 * @param {number} windowSize - Window size in samples
 * @returns {number} RMS energy value
 */
export function calcEnergy(wav, startIdx, windowSize) {
  const endIdx = Math.min(startIdx + windowSize, wav.length);

  if (endIdx <= startIdx) {
    return 0.0;
  }

  let sumSquares = 0;
  for (let i = startIdx; i < endIdx; i++) {
    sumSquares += wav[i] * wav[i];
  }

  const meanSquare = sumSquares / (endIdx - startIdx);
  return Math.sqrt(meanSquare);
}

/**
 * Find energy valley near a time point
 * @param {Float32Array} wav - Audio waveform data
 * @param {number} sampleRate - Sample rate in Hz
 * @param {number} centerTime - Center time in seconds
 * @param {number} searchMs - Search range in milliseconds
 * @param {string} direction - 'left' or 'right'
 * @returns {Promise<{bestTime: number, energyRatio: number}>}
 */
export async function findEnergyValley(wav, sampleRate, centerTime, searchMs = DEFAULT_SEARCH_MS, direction = 'left') {
  const centerIdx = Math.floor(centerTime * sampleRate);
  const searchSamples = Math.floor((searchMs / 1000) * sampleRate);
  const windowSize = Math.floor((WINDOW_SIZE_MS / 1000) * sampleRate);

  let startIdx, endIdx, step;

  if (direction === 'left') {
    startIdx = Math.max(0, centerIdx - searchSamples);
    endIdx = centerIdx;
    step = Math.floor((STEP_MS / 1000) * sampleRate);
  } else { // right
    startIdx = centerIdx;
    endIdx = Math.min(wav.length, centerIdx + searchSamples);
    step = Math.floor((STEP_MS / 1000) * sampleRate);
  }

  if (endIdx - startIdx < windowSize) {
    return { bestTime: centerTime, energyRatio: 1.0 };
  }

  // Calculate max energy in search range for normalization
  let maxEnergy = 0;
  for (let i = startIdx; i < endIdx - windowSize; i += step) {
    const energy = calcEnergy(wav, i, windowSize);
    if (energy > maxEnergy) {
      maxEnergy = energy;
    }
  }

  if (maxEnergy === 0) {
    return { bestTime: centerTime, energyRatio: 0.0 };
  }

  // Find minimum energy point
  let minEnergy = Infinity;
  let bestIdx = centerIdx;

  for (let i = startIdx; i < endIdx - windowSize; i += step) {
    const energy = calcEnergy(wav, i, windowSize);
    if (energy < minEnergy) {
      minEnergy = energy;
      bestIdx = i;
    }
  }

  const energyRatio = minEnergy / maxEnergy;
  const bestTime = bestIdx / sampleRate;

  return { bestTime, energyRatio };
}

/**
 * Find valley boundaries for a word segment
 * @param {Float32Array} wav - Audio waveform data
 * @param {number} sampleRate - Sample rate in Hz
 * @param {number} wordStartTime - First word start time
 * @param {number} wordEndTime - Last word end time
 * @param {number} leftSearchMs - Left search range in ms
 * @param {number} rightSearchMs - Right search range in ms
 * @param {number} threshold - Energy ratio threshold
 * @returns {Promise<Object>} Valley boundaries with quality assessment
 */
export async function findValleyBoundaries(
  wav,
  sampleRate,
  wordStartTime,
  wordEndTime,
  leftSearchMs = DEFAULT_SEARCH_MS,
  rightSearchMs = DEFAULT_SEARCH_MS,
  threshold = DEFAULT_THRESHOLD
) {
  // Find left valley (search left from wordStartTime)
  const { bestTime: leftCut, energyRatio: leftRatio } = await findEnergyValley(
    wav, sampleRate, wordStartTime, leftSearchMs, 'left'
  );

  // Find right valley (search right from wordEndTime)
  const { bestTime: rightCut, energyRatio: rightRatio } = await findEnergyValley(
    wav, sampleRate, wordEndTime, rightSearchMs, 'right'
  );

  // Assess quality
  const maxRatio = Math.max(leftRatio, rightRatio);
  let quality;
  let warning;

  if (maxRatio < 0.3) {
    quality = 'good';
    warning = null;
  } else if (maxRatio < threshold) {
    quality = 'fair';
    warning = `边界能量比较高 (左=${leftRatio.toFixed(2)}, 右=${rightRatio.toFixed(2)})，剪切可能有轻微爆音`;
  } else {
    quality = 'poor';
    warning = `警告：边界不在能量谷底 (左=${leftRatio.toFixed(2)}, 右=${rightRatio.toFixed(2)})，剪切可能有明显爆音`;
  }

  return {
    cut_start: leftCut,
    cut_end: rightCut,
    left_ratio: leftRatio,
    right_ratio: rightRatio,
    quality,
    warning
  };
}

/**
 * Apply valley correction to cut boundaries
 * @param {Array} cuts - Array of {start, end} cut boundaries
 * @param {string} audioPath - Path to audio file
 * @param {number} threshold - Energy ratio threshold
 * @param {number} searchMs - Search range in ms
 * @returns {Promise<Array>} Corrected cuts with quality info
 */
export async function applyValleyCorrection(cuts, audioPath, threshold = DEFAULT_THRESHOLD, searchMs = DEFAULT_SEARCH_MS) {
  const { wav, sampleRate } = await loadAudioForValley(audioPath);

  const correctedCuts = [];

  for (const cut of cuts) {
    const result = await findValleyBoundaries(
      wav,
      sampleRate,
      cut.start,
      cut.end,
      searchMs,
      searchMs,
      threshold
    );

    correctedCuts.push({
      start: result.cut_start,
      end: result.cut_end,
      left_ratio: result.left_ratio,
      right_ratio: result.right_ratio,
      quality: result.quality,
      warning: result.warning
    });
  }

  return correctedCuts;
}
