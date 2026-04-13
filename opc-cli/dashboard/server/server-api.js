/**
 * OPC Dashboard API Server (Pure API, no static files)
 * Port: 12081
 *
 * API:
 * GET  /api/skills - 获取所有技能
 * GET  /api/skill/cut/status - 获取 Cut 技能状态
 * POST /api/skill/cut/init - 初始化 Cut 技能
 */

import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';
import os from 'os';
import cutRouter from './api/cut.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();

// 启用 CORS，允许远程访问
app.use(cors({
  origin: true,
  credentials: true
}));
app.use(express.json());

// Mount Cut API routes
app.use('/api/skill/cut', cutRouter);

// Load configuration for server settings
const CONFIG_DIR = path.join(os.homedir(), '.opc_cli', 'opc');
const CONFIG_FILE = path.join(CONFIG_DIR, 'config.json');

function loadConfig() {
  const defaultConfig = {
    dashboard_host: '0.0.0.0',
    dashboard_port: 12080,
    api_port: 12081
  };

  if (fs.existsSync(CONFIG_FILE)) {
    const userConfig = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
    return { ...defaultConfig, ...userConfig };
  }
  return defaultConfig;
}

const config = loadConfig();

// Use configured port and host
const API_PORT = process.env.PORT || config.api_port || 12081;
const API_HOST = config.dashboard_host || '0.0.0.0';

// ============ API Routes ============

/**
 * 获取所有技能状态
 */
app.get('/api/skills', (req, res) => {
  res.json({
    skills: [
      {
        name: 'cut',
        displayName: '智能剪辑',
        description: '基于 ASR 字词级时间戳的视频剪辑',
        route: '/skill/cut/editor',
        status: 'running'
      }
    ]
  });
});

// ============ 启动服务器 ============

app.listen(API_PORT, API_HOST, () => {
  const displayHost = API_HOST === '0.0.0.0' ? '0.0.0.0 (所有接口)' : API_HOST;
  console.log(`\n[OPC Dashboard API] Server running at http://${displayHost}:${API_PORT}`);
  console.log(`[OPC Dashboard API] Endpoints:`);
  console.log(`  GET  /api/skills`);
  console.log(`  GET  /api/skill/cut/status`);
  console.log(`  POST /api/skill/cut/init`);
  console.log(`  GET  /api/skill/cut/file/:fileId`);
  console.log(`  GET  /api/skill/cut/video/:fileId`);
  console.log(`  POST /api/skill/cut/export`);
  console.log(`\n`);
});
