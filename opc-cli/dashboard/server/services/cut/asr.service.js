/**
 * Cut ASR Service
 * Handles ASR (Automatic Speech Recognition) via opc CLI
 */

import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { v4 as uuidv4 } from 'uuid';
import { ensureWorkspaceDirs } from './config.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const OPC_CMD = 'uv';
const SKILL_DIR = path.resolve(__dirname, '../../..');

/**
 * Run ASR pipeline on audio file
 * @param {string} audioPath - Path to audio/video file
 * @param {string} language - Language code (e.g., 'Chinese', 'English')
 * @returns {Promise<Object>} ASR result with language, text, duration, words
 */
export async function runAsrPipeline(audioPath, language = 'Chinese') {
  const { outputsDir } = ensureWorkspaceDirs();
  const tempFile = path.join(outputsDir, `temp_${uuidv4().substring(0, 8)}.json`);

  const args = ['run', 'opc', 'asr', audioPath, '--format', 'json', '-o', tempFile];

  if (language) {
    args.push('--language', language);
  }

  console.log(`[ASR Service] Running: uv run opc asr "${audioPath}"`);

  try {
    const result = await spawnProcess(OPC_CMD, args, SKILL_DIR);

    // Read output JSON
    if (fs.existsSync(tempFile)) {
      const content = fs.readFileSync(tempFile, 'utf-8');
      const data = JSON.parse(content);

      // Clean up temp file
      fs.unlinkSync(tempFile);

      return {
        language: data.language || language,
        text: data.text || '',
        duration: data.duration || 0,
        words: data.words || []
      };
    }

    throw new Error('ASR output file not created');

  } catch (error) {
    // Clean up temp file if exists
    if (fs.existsSync(tempFile)) {
      fs.unlinkSync(tempFile);
    }
    throw error;
  }
}

/**
 * Parse ASR result from JSON file
 * @param {string} jsonPath - Path to ASR JSON file
 * @returns {Object} Parsed ASR result
 */
export async function parseAsrResult(jsonPath) {
  if (!fs.existsSync(jsonPath)) {
    throw new Error(`ASR JSON file not found: ${jsonPath}`);
  }

  const content = await fs.promises.readFile(jsonPath, 'utf-8');
  return JSON.parse(content);
}

/**
 * Wrap ASR result for frontend compatibility
 * Converts word-level ASR to segment format expected by frontend
 * @param {Object} asrResult - Raw ASR result
 * @returns {Object} Frontend-compatible ASR result
 */
export function wrapAsrForFrontend(asrResult) {
  if (asrResult.words && !asrResult.segments) {
    return {
      language: asrResult.language || 'Chinese',
      text: asrResult.text || '',
      duration: asrResult.duration || 0,
      segments: [{ words: asrResult.words }]
    };
  }

  return asrResult;
}

/**
 * Spawn a child process and collect output
 * @param {string} command - Command to run
 * @param {Array<string>} args - Arguments
 * @param {string} cwd - Working directory
 * @returns {Promise<string>} stdout output
 */
function spawnProcess(command, args, cwd) {
  return new Promise((resolve, reject) => {
    let stdout = '';
    let stderr = '';

    const proc = spawn(command, args, {
      cwd,
      shell: true
    });

    proc.stdout.on('data', (data) => {
      const text = data.toString();
      stdout += text;
      console.log(`[ASR stdout] ${text.trim()}`);
    });

    proc.stderr.on('data', (data) => {
      const text = data.toString();
      stderr += text;
      console.error(`[ASR stderr] ${text.trim()}`);
    });

    proc.on('close', (code) => {
      if (code === 0) {
        resolve(stdout);
      } else {
        reject(new Error(stderr || `ASR process exited with code ${code}`));
      }
    });

    proc.on('error', (error) => {
      reject(new Error(`Failed to spawn ASR process: ${error.message}`));
    });
  });
}

/**
 * Run ASR with progress callback
 * @param {string} audioPath - Path to audio file
 * @param {string} language - Language code
 * @param {Function} onProgress - Progress callback (progress: number, message: string)
 * @returns {Promise<Object>} ASR result
 */
export async function runAsrWithProgress(audioPath, language, onProgress) {
  onProgress(10, 'Starting ASR processing...');

  try {
    const result = await runAsrPipeline(audioPath, language);
    onProgress(100, 'ASR processing complete');
    return result;
  } catch (error) {
    onProgress(0, `ASR failed: ${error.message}`);
    throw error;
  }
}
