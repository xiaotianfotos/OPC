/**
 * OPC Dashboard Server
 * 技能注册式架构，每个 skill 提供：
 * - API: 技能相关的 REST API
 * - 前端路由：展示结果界面
 */

import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
app.use(cors());
// Parse JSON bodies (as sent by API clients)
app.use(express.json());
// Parse URL-encoded bodies (as sent by HTML forms)
app.use(express.urlencoded({ extended: true }));

// ============ Import Skill Routes ============

import cutRouter from './api/cut.js';

// Mount Cut API routes
app.use('/api/skill/cut', cutRouter);

// ============ General API ============

/**
 * 获取所有可用技能
 */
app.get('/api/skills', (req, res) => {
  res.json({
    skills: [
      {
        name: 'cut',
        route: 'cut',
        status: 'available',
        description: '智能口播剪辑 - 基于 ASR 字级时间戳的视频编辑工具'
      }
    ]
  });
});

// ============ 静态文件服务 (Vue 前端) ============

const vueDistPath = path.join(__dirname, 'dist');
app.use(express.static(vueDistPath));

// 所有未知路由返回 Vue 前端
app.get('*', (req, res) => {
  res.sendFile(path.join(vueDistPath, 'index.html'));
});

// ============ 启动服务器 ============

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => {
  console.log(`[Dashboard] Server running at http://localhost:${PORT}`);
  console.log(`[Dashboard] Available skills: cut`);
});
