/**
 * OPC Dashboard Server
 * 技能注册式架构
 *
 * API:
 * POST /api/skill/cut/init - 初始化 Cut 技能
 * GET  /api/skills - 获取所有技能
 *
 * 前端路由:
 * /skill/cut/editor - Cut 剪辑界面 (iframe 嵌入 cut server)
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
    dashboard_port: 12080
  };

  if (fs.existsSync(CONFIG_FILE)) {
    const userConfig = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
    return { ...defaultConfig, ...userConfig };
  }
  return defaultConfig;
}

const config = loadConfig();

// Use configured port and host
const DASHBOARD_PORT = process.env.PORT || config.dashboard_port || 12080;
const DASHBOARD_HOST = config.dashboard_host || '0.0.0.0';

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

// ============ 静态文件服务 (Vue 前端) ============

const vueDistPath = path.join(__dirname, 'dist');
if (fs.existsSync(vueDistPath)) {
  app.use(express.static(vueDistPath));
  console.log(`[Dashboard] Serving static files from ${vueDistPath}`);
}

// SPA 路由回退
app.get('*', (req, res) => {
  const indexPath = path.join(vueDistPath, 'index.html');
  if (fs.existsSync(indexPath)) {
    res.sendFile(indexPath);
  } else {
    res.json({
      message: 'OPC Dashboard API',
      endpoints: {
        skills: 'GET /api/skills',
        cutStatus: 'GET /api/skill/cut/status',
        cutInit: 'POST /api/skill/cut/init'
      }
    });
  }
});

// ============ 启动服务器 ============

app.listen(DASHBOARD_PORT, DASHBOARD_HOST, () => {
  const displayHost = DASHBOARD_HOST === '0.0.0.0' ? '0.0.0.0 (所有接口)' : DASHBOARD_HOST;
  console.log(`\n[OPC Dashboard] Server running at http://${displayHost}:${DASHBOARD_PORT}`);
  console.log(`[OPC Dashboard] API: http://${displayHost}:${DASHBOARD_PORT}/api/skills`);
  console.log(`[OPC Dashboard] Frontend: http://${displayHost}:${DASHBOARD_PORT}/skill/cut/editor\n`);
});
