/**
 * Gallery API Routes
 * Image gallery browsing, scanning, and management
 */

import express from 'express';
import path from 'path';
import fs from 'fs';
import os from 'os';
import { v4 as uuidv4 } from 'uuid';

const router = express.Router();

const GALLERY_DIR = path.join(os.homedir(), '.opc_cli', 'opc');
const GALLERY_FILE = path.join(GALLERY_DIR, 'gallery.json');
const CONFIG_FILE = path.join(GALLERY_DIR, 'config.json');

// ============ Helpers ============

function resolveOutputDir() {
  try {
    if (fs.existsSync(CONFIG_FILE)) {
      const cfg = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
      return cfg.image_output_dir || cfg.output_dir || os.tmpdir();
    }
  } catch (e) { /* fall through */ }
  return os.tmpdir();
}

function ensureGalleryFile() {
  if (!fs.existsSync(GALLERY_DIR)) {
    fs.mkdirSync(GALLERY_DIR, { recursive: true });
  }
  if (!fs.existsSync(GALLERY_FILE)) {
    fs.writeFileSync(GALLERY_FILE, JSON.stringify({ images: [] }));
  }
}

function readGallery() {
  ensureGalleryFile();
  return JSON.parse(fs.readFileSync(GALLERY_FILE, 'utf-8'));
}

function writeGallery(data) {
  ensureGalleryFile();
  const tmp = GALLERY_FILE + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2));
  fs.renameSync(tmp, GALLERY_FILE);
}

function readPngDimensions(filepath) {
  try {
    const buf = Buffer.alloc(24);
    const fd = fs.openSync(filepath, 'r');
    fs.readSync(fd, buf, 0, 24, 0);
    fs.closeSync(fd);
    if (buf.slice(0, 8).toString('ascii') !== '\x89PNG\r\n\x1a\n') return null;
    return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
  } catch (e) {
    return null;
  }
}

function resolveImagePath(entry) {
  const outputDir = resolveOutputDir();
  return path.join(outputDir, entry.filepath);
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// ============ Routes ============

// GET /api/gallery — paginated list
router.get('/', (req, res) => {
  const page = Math.max(1, parseInt(req.query.page) || 1);
  const limit = Math.min(200, Math.max(1, parseInt(req.query.limit) || 50));
  const alias = req.query.alias || '';

  const data = readGallery();
  let images = [...data.images].reverse(); // newest first

  if (alias) {
    images = images.filter(img => img.alias === alias);
  }

  const total = images.length;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const start = (page - 1) * limit;
  const pageImages = images.slice(start, start + limit);

  res.json({ images: pageImages, total, page, totalPages });
});

// GET /api/gallery/stats
router.get('/stats', (req, res) => {
  const data = readGallery();
  let totalSize = 0;
  const aliases = {};
  for (const img of data.images) {
    totalSize += img.file_size || 0;
    if (img.alias) {
      aliases[img.alias] = (aliases[img.alias] || 0) + 1;
    }
  }
  res.json({
    total: data.images.length,
    totalSize,
    totalSizeFormatted: formatBytes(totalSize),
    aliases,
  });
});

// GET /api/gallery/image/:id — serve image file
router.get('/image/:id', (req, res) => {
  const id = req.params.id;
  const data = readGallery();
  const entry = data.images.find(img => img.id === id);
  if (!entry) return res.status(404).json({ error: 'Image not found' });

  const fullPath = resolveImagePath(entry);
  if (!fs.existsSync(fullPath)) return res.status(404).json({ error: 'File not found on disk' });

  res.sendFile(fullPath);
});

// POST /api/gallery/scan — scan output dir for new images
router.post('/scan', (req, res) => {
  const outputDir = resolveOutputDir();
  if (!fs.existsSync(outputDir)) {
    return res.json({ added: 0, total: 0, error: 'Output directory not found' });
  }

  const data = readGallery();
  const existing = new Set(data.images.map(img => img.filename));

  const exts = new Set(['.png', '.jpg', '.jpeg', '.webp']);
  let added = 0;

  const files = fs.readdirSync(outputDir).sort();
  for (const fname of files) {
    const ext = path.extname(fname).toLowerCase();
    if (!exts.has(ext)) continue;
    if (existing.has(fname)) continue;

    const fullPath = path.join(outputDir, fname);
    const stat = fs.statSync(fullPath);
    if (!stat.isFile()) continue;

    const parts = path.basename(fname, ext).split('_');
    const alias = parts.length > 1 ? parts[0] : '';

    const entry = {
      id: `g_${uuidv4().replace(/-/g, '').slice(0, 12)}`,
      filename: fname,
      filepath: fname,
      prompt: '',
      alias,
      created_at: stat.mtime.toISOString(),
      file_size: stat.size,
    };

    const dims = readPngDimensions(fullPath);
    if (dims) {
      entry.width = dims.width;
      entry.height = dims.height;
    }

    data.images.push(entry);
    added++;
  }

  if (added) writeGallery(data);

  res.json({ added, total: data.images.length });
});

// DELETE /api/gallery/:id — delete single image
router.delete('/:id', (req, res) => {
  const id = req.params.id;
  const data = readGallery();
  const idx = data.images.findIndex(img => img.id === id);
  if (idx === -1) return res.status(404).json({ error: 'Not found' });

  const entry = data.images[idx];

  // Delete file from disk
  const fullPath = resolveImagePath(entry);
  try {
    if (fs.existsSync(fullPath)) fs.unlinkSync(fullPath);
  } catch (e) { /* ignore file delete errors */ }

  data.images.splice(idx, 1);
  writeGallery(data);

  res.json({ success: true });
});

// POST /api/gallery/batch-delete — batch delete
router.post('/batch-delete', (req, res) => {
  const ids = req.body.ids || [];
  if (!Array.isArray(ids) || ids.length === 0) {
    return res.status(400).json({ error: 'ids array required' });
  }

  const idSet = new Set(ids);
  const data = readGallery();
  const outputDir = resolveOutputDir();
  let deleted = 0;

  const remaining = data.images.filter(img => {
    if (!idSet.has(img.id)) return true;

    // Delete file from disk
    try {
      const fullPath = path.join(outputDir, img.filepath);
      if (fs.existsSync(fullPath)) fs.unlinkSync(fullPath);
    } catch (e) { /* ignore */ }

    deleted++;
    return false;
  });

  data.images = remaining;
  writeGallery(data);

  res.json({ deleted });
});

export default router;
