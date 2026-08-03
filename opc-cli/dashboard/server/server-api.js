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

// ============ Knowledge Graph API ============

const KG_DATA_PATH = path.join(__dirname, '..', '..', 'scripts', 'image', 'examples', 'prompt_graph.json');
const TEMPLATES_DIR = path.join(__dirname, '..', '..', 'scripts', 'image', 'templates');

// Map template style keywords to KG entities
const STYLE_ENTITY_MAP = {
  '手绘': 'style:hand_drawn', '手账': 'style:hand_drawn', '水彩': 'style:hand_drawn',
  '漫画': 'genre:comic', '贴纸': 'genre:sticker',
  '扁平': 'style:flat_design', '矢量': 'style:flat_design',
  '等距': 'style:isometric', '蓝图': 'genre:blueprint', '工程': 'genre:blueprint',
  '波普': 'style:pop_art',
  '温暖': 'mood:warm', '柔和': 'mood:warm',
  '活泼': 'mood:playful', '童趣': 'mood:playful',
  '戏剧': 'mood:dramatic', '高饱和': 'mood:dramatic',
  '宁静': 'mood:serene',
  '信息图': 'genre:infographic', '海报': 'genre:poster',
  '暗色': 'mood:dark', '霓虹': 'lighting:neon',
  '3D': 'style:3d_render', '微缩': 'style:miniature',
  '莫兰迪': 'style:vintage_ledger', '绘本': 'style:vintage_ledger',
  '墨水': 'style:hand_drawn', '做旧': 'style:vintage', '复古': 'style:vintage',
  '怀旧': 'mood:nostalgic',
};

// Map scene types to relevant KG entities by content analysis
const SCENE_ENTITY_MAP = {
  'title': ['composition:horizontal', 'mood:playful'],
  'hype': ['mood:dramatic', 'genre:poster'],
  'debunk': ['mood:playful', 'genre:comic'],
  'timeline': ['composition:horizontal', 'genre:infographic'],
  'comparison': ['composition:horizontal', 'genre:infographic'],
  'architecture': ['style:isometric', 'subject:architecture', 'genre:blueprint'],
  'pipeline': ['composition:horizontal', 'genre:infographic'],
  'danger_vs_safe': ['composition:horizontal', 'mood:dramatic'],
  'verdict': ['mood:warm', 'composition:horizontal'],
  'sandbox': ['style:isometric', 'subject:architecture'],
  'stages': ['composition:horizontal', 'genre:infographic', 'mood:warm'],
  'stages_3col': ['composition:horizontal', 'genre:infographic', 'style:vintage_ledger'],
  'summary': ['mood:serene', 'composition:horizontal', 'genre:infographic'],
};

function loadTemplates() {
  const templates = [];
  if (!fs.existsSync(TEMPLATES_DIR)) return templates;

  for (const dir of fs.readdirSync(TEMPLATES_DIR, { withFileTypes: true })) {
    if (!dir.isDirectory()) continue;
    const tplPath = path.join(TEMPLATES_DIR, dir.name, 'template.json');
    if (!fs.existsSync(tplPath)) continue;
    try {
      const tpl = JSON.parse(fs.readFileSync(tplPath, 'utf-8'));
      templates.push({ ...tpl, dirName: dir.name });
    } catch (e) { /* skip invalid */ }
  }
  return templates;
}

app.get('/api/kg/data', (req, res) => {
  if (!fs.existsSync(KG_DATA_PATH)) {
    return res.status(404).json({ error: 'Knowledge graph data not found' });
  }
  const raw = JSON.parse(fs.readFileSync(KG_DATA_PATH, 'utf-8'));

  // Transform KG entities
  const entities = [];
  const catSet = new Set();
  for (const [id, info] of Object.entries(raw.entities)) {
    entities.push({ id, name: info.name, category: info.category, count: info.count });
    catSet.add(info.category);
  }
  const entityIds = new Set(entities.map(e => e.id));

  // KG co-occurrence edges
  const edges = [];
  for (const [src, neighbors] of Object.entries(raw.co_occurrence)) {
    for (const [tgt, weight] of Object.entries(neighbors)) {
      if (entityIds.has(src) && entityIds.has(tgt)) {
        edges.push({ source: src, target: tgt, weight });
      }
    }
  }

  // Load templates as new nodes + edges
  catSet.add('template');
  catSet.add('scene');
  const templates = loadTemplates();
  for (const tpl of templates) {
    // Template node
    const tplId = `template:${tpl.name}`;
    entities.push({
      id: tplId, name: tpl.name, category: 'template',
      count: Object.keys(tpl.scenes).length,
      _template: true, _desc: tpl.description, _scenes: Object.keys(tpl.scenes),
    });

    // Find style entities from style_prefix
    const prefix = tpl.style_prefix || '';
    for (const [keyword, entityId] of Object.entries(STYLE_ENTITY_MAP)) {
      if (prefix.includes(keyword) && entityIds.has(entityId)) {
        edges.push({ source: tplId, target: entityId, weight: 15, _template: true });
      }
    }

    // Find entities from source field
    const source = tpl.source || '';
    for (const [id, info] of Object.entries(raw.entities)) {
      if (source.includes(id) || source.includes(info.name)) {
        edges.push({ source: tplId, target: id, weight: 12, _template: true });
      }
    }

    // Scene nodes
    for (const [sceneKey, sceneDef] of Object.entries(tpl.scenes)) {
      const sceneId = `scene:${tpl.name}:${sceneKey}`;
      entities.push({
        id: sceneId, name: sceneKey, category: 'scene',
        count: 5, _scene: true, _desc: sceneDef.desc, _params: sceneDef.params,
      });
      // Edge: template → scene
      edges.push({ source: tplId, target: sceneId, weight: 20, _template: true });

      // Edge: scene → related KG entities
      const relatedEntities = SCENE_ENTITY_MAP[sceneKey] || [];
      for (const eid of relatedEntities) {
        if (entityIds.has(eid)) {
          edges.push({ source: sceneId, target: eid, weight: 8, _template: true });
        }
      }
    }
  }

  res.json({ entities, edges, categories: [...catSet] });
});

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

// ============ Image Model Evaluation API ============

const EVAL_DIR = path.join(__dirname, '..', '..', 'scripts', 'image', 'eval', 'results');

app.get('/api/eval/models', (req, res) => {
  const defaultOrder = ['ernie-full', 'z-image', 'qwen-image'];
  try {
    if (!fs.existsSync(EVAL_DIR)) return res.json(defaultOrder);
    const dirs = fs.readdirSync(EVAL_DIR).filter(d => {
      return fs.existsSync(path.join(EVAL_DIR, d, 'results.json'));
    });
    // Merge: default order first, then any extras
    const ordered = defaultOrder.filter(m => dirs.includes(m));
    const extras = dirs.filter(m => !defaultOrder.includes(m)).sort();
    res.json([...ordered, ...extras]);
  } catch (e) {
    res.json(defaultOrder);
  }
});

app.get('/api/eval/results/:alias', (req, res) => {
  const alias = req.params.alias;
  const safeAlias = path.basename(alias);
  const resultsFile = path.join(EVAL_DIR, safeAlias, 'results.json');
  if (!fs.existsSync(resultsFile)) {
    return res.json({ meta: { alias: safeAlias, total: 0 }, results: [] });
  }
  try {
    const data = JSON.parse(fs.readFileSync(resultsFile, 'utf-8'));
    res.json(data);
  } catch (e) {
    res.status(500).json({ error: 'Failed to parse results file' });
  }
});

app.get('/api/eval/image/:alias/:filename', (req, res) => {
  const alias = req.params.alias;
  const filename = req.params.filename;
  const safeAlias = path.basename(alias);
  const safeName = path.basename(filename);
  const filePath = path.join(EVAL_DIR, safeAlias, safeName);
  if (!fs.existsSync(filePath)) {
    return res.status(404).json({ error: 'Image not found' });
  }
  res.sendFile(filePath);
});

const EVAL_PROMPTS_DIR = path.join(__dirname, '..', '..', 'scripts', 'image', 'eval', 'prompts');

app.get('/api/eval/prompts', (req, res) => {
  const prompts = [];
  if (!fs.existsSync(EVAL_PROMPTS_DIR)) {
    return res.json([]);
  }
  const files = fs.readdirSync(EVAL_PROMPTS_DIR).filter(f => f.endsWith('.json'));
  // Get mtime for each file for sorting
  const filesWithTime = files.map(f => ({
    fname: f,
    mtime: fs.statSync(path.join(EVAL_PROMPTS_DIR, f)).mtimeMs,
  }));
  // Sort newest first
  filesWithTime.sort((a, b) => b.mtime - a.mtime);

  for (const { fname } of filesWithTime) {
    try {
      const data = JSON.parse(fs.readFileSync(path.join(EVAL_PROMPTS_DIR, fname), 'utf-8'));
      const pid = fname.slice(0, -5);
      prompts.push({
        id: pid,
        title: data.meta?.template_name || data.meta?.title || pid,
        category: data.meta?.category || '',
        tags: data.meta?.tags || [],
        description: data.meta?.description || '',
        prompt: data.prompt || '',
        negative: data.negative || '',
      });
    } catch (e) { /* skip invalid */ }
  }
  res.json(prompts);
});

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
      },
      {
        name: 'image',
        displayName: '图像生成',
        description: '多模型图像生成评估',
        route: '/evaluate',
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
