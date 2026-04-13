/**
 * Cut Service Configuration
 * Loads configuration from ~/.opc_cli/opc/config.json
 */

import fs from 'fs';
import path from 'path';
import os from 'os';

const CONFIG_DIR = path.join(os.homedir(), '.opc_cli', 'opc');
const CONFIG_FILE = path.join(CONFIG_DIR, 'config.json');

const DEFAULT_CONFIG = {
  tts_engine: 'edge-tts',
  output_dir: os.tmpdir(),
  workspace_dir: path.join(os.homedir(), '.opc_cli', 'workspace'),
  dashboard_host: '0.0.0.0',
  dashboard_port: 12080,
  cut_server_port: 12082,
  asr_model_size: '1.7B',
  asr_language: '',
};

/**
 * Load OPC configuration
 * @returns {Object} Configuration object
 */
export function loadConfig() {
  const config = { ...DEFAULT_CONFIG };

  if (fs.existsSync(CONFIG_FILE)) {
    try {
      const userConfig = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
      Object.assign(config, userConfig);
    } catch (error) {
      console.error('[Cut Config] Failed to load config, using defaults:', error.message);
    }
  }

  return config;
}

/**
 * Get workspace directory for Cut operations
 * @returns {string} Absolute path to workspace directory
 */
export function getWorkspaceDir() {
  const config = loadConfig();
  const workspaceDir = config.workspace_dir || DEFAULT_CONFIG.workspace_dir;
  return path.resolve(workspaceDir.replace('~', os.homedir()));
}

/**
 * Ensure workspace directories exist
 * @returns {Object} Object with paths to uploads and outputs directories
 */
export function ensureWorkspaceDirs() {
  const workspaceDir = getWorkspaceDir();
  const uploadsDir = path.join(workspaceDir, 'uploads');
  const outputsDir = path.join(workspaceDir, 'outputs');

  fs.mkdirSync(uploadsDir, { recursive: true });
  fs.mkdirSync(outputsDir, { recursive: true });

  return { uploadsDir, outputsDir, workspaceDir };
}
