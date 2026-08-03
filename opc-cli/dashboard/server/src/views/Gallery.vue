<template>
  <div class="gallery-page">
    <!-- Header -->
    <header class="gallery-header">
      <div class="header-left">
        <h1>Gallery</h1>
        <span class="stats-text" v-if="stats.total > 0">
          {{ stats.total }} 张图片 · {{ stats.totalSizeFormatted }}
        </span>
      </div>
      <div class="header-actions">
        <button class="btn btn-primary" @click="scanForImages" :disabled="scanning">
          {{ scanning ? '扫描中...' : '扫描新图片' }}
        </button>
        <button
          v-if="selectedIds.size > 0"
          class="btn btn-danger"
          @click="confirmBatchDelete"
        >
          删除选中 ({{ selectedIds.size }})
        </button>
        <button
          v-if="selectedIds.size > 0"
          class="btn btn-ghost"
          @click="selectedIds.clear()"
        >
          取消选择
        </button>
      </div>
    </header>

    <!-- Filters -->
    <div class="filter-bar">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="搜索 prompt、alias..."
        class="search-input"
      />
      <select v-model="aliasFilter" class="filter-select">
        <option value="">全部模型</option>
        <option v-for="(count, alias) in stats.aliases" :key="alias" :value="alias">
          {{ alias }} ({{ count }})
        </option>
      </select>
    </div>

    <!-- Grid -->
    <div class="gallery-grid" v-if="filteredImages.length > 0">
      <div
        v-for="img in filteredImages"
        :key="img.id"
        class="gallery-item"
        :class="{ selected: selectedIds.has(img.id) }"
      >
        <div class="thumb-wrapper" @click="openLightbox(img)">
          <img :src="`/api/gallery/image/${img.id}`" loading="lazy" />
          <div class="select-check" @click.stop="toggleSelect(img.id)">
            <span class="check-box" :class="{ checked: selectedIds.has(img.id) }">
              <span v-if="selectedIds.has(img.id)">&#10003;</span>
            </span>
          </div>
        </div>
        <div class="item-meta">
          <span class="item-alias">{{ img.alias || 'unknown' }}</span>
          <span class="item-time">{{ formatTime(img.created_at) }}</span>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div class="empty-state" v-else>
      <p v-if="images.length === 0">还没有图片。点击「扫描新图片」将已生成的图片加入画廊。</p>
      <p v-else>没有匹配的结果。</p>
    </div>

    <!-- Pagination -->
    <div class="pagination" v-if="totalPages > 1">
      <button class="btn btn-ghost" @click="prevPage" :disabled="page <= 1">上一页</button>
      <span class="page-info">{{ page }} / {{ totalPages }}</span>
      <button class="btn btn-ghost" @click="nextPage" :disabled="page >= totalPages">下一页</button>
    </div>

    <!-- Lightbox -->
    <div v-if="lightboxOpen" class="lightbox-overlay" @click.self="closeLightbox">
      <button class="lb-close" @click="closeLightbox">&times;</button>
      <button class="lb-nav lb-prev" @click="prevLightbox" v-if="lightboxIndex > 0">&lsaquo;</button>
      <button class="lb-nav lb-next" @click="nextLightbox" v-if="lightboxIndex < filteredImages.length - 1">&rsaquo;</button>
      <div class="lb-content">
        <div class="lb-image-wrap">
          <img :src="`/api/gallery/image/${lightboxImage.id}`" />
        </div>
        <div class="lb-meta">
          <div class="meta-row" v-if="lightboxImage.alias">
            <label>模型</label>
            <span>{{ lightboxImage.alias }}</span>
          </div>
          <div class="meta-row">
            <label>时间</label>
            <span>{{ formatTime(lightboxImage.created_at) }}</span>
          </div>
          <div class="meta-row" v-if="lightboxImage.width">
            <label>尺寸</label>
            <span>{{ lightboxImage.width }} x {{ lightboxImage.height }}</span>
          </div>
          <div class="meta-row" v-if="lightboxImage.file_size">
            <label>大小</label>
            <span>{{ formatBytes(lightboxImage.file_size) }}</span>
          </div>
          <div class="meta-row meta-prompt" v-if="lightboxImage.prompt">
            <label>Prompt</label>
            <pre>{{ lightboxImage.prompt }}</pre>
          </div>
          <div class="lb-actions">
            <button class="btn btn-danger" @click="deleteFromLightbox">删除</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Delete Confirmation -->
    <div v-if="deleteDialogOpen" class="dialog-overlay" @click.self="deleteDialogOpen = false">
      <div class="dialog-box">
        <h3>确认删除</h3>
        <p>{{ deleteDialogMessage }}</p>
        <div class="dialog-actions">
          <button class="btn btn-ghost" @click="deleteDialogOpen = false">取消</button>
          <button class="btn btn-danger" @click="executeDelete">删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      images: [],
      stats: { total: 0, totalSize: 0, totalSizeFormatted: '0 B', aliases: {} },
      page: 1,
      totalPages: 1,
      limit: 50,
      searchQuery: '',
      aliasFilter: '',
      selectedIds: new Set(),
      lightboxOpen: false,
      lightboxImage: null,
      lightboxIndex: 0,
      deleteDialogOpen: false,
      deleteDialogMessage: '',
      pendingDeleteIds: [],
      scanning: false,
    };
  },
  computed: {
    filteredImages() {
      let list = this.images;
      if (this.searchQuery) {
        const q = this.searchQuery.toLowerCase();
        list = list.filter(img =>
          (img.prompt && img.prompt.toLowerCase().includes(q)) ||
          (img.alias && img.alias.toLowerCase().includes(q)) ||
          img.filename.toLowerCase().includes(q)
        );
      }
      return list;
    },
  },
  watch: {
    aliasFilter() {
      this.page = 1;
      this.loadGallery();
    },
  },
  mounted() {
    this.loadGallery();
    this.loadStats();
    this._keyHandler = (e) => {
      if (e.key === 'Escape') this.closeLightbox();
      if (this.lightboxOpen && e.key === 'ArrowLeft') this.prevLightbox();
      if (this.lightboxOpen && e.key === 'ArrowRight') this.nextLightbox();
    };
    window.addEventListener('keydown', this._keyHandler);
  },
  beforeUnmount() {
    window.removeEventListener('keydown', this._keyHandler);
  },
  methods: {
    async loadGallery() {
      try {
        const params = new URLSearchParams({ page: this.page, limit: this.limit });
        if (this.aliasFilter) params.set('alias', this.aliasFilter);
        const res = await fetch(`/api/gallery?${params}`);
        const data = await res.json();
        this.images = data.images;
        this.totalPages = data.totalPages;
      } catch (e) {
        console.error('Failed to load gallery:', e);
      }
    },
    async loadStats() {
      try {
        const res = await fetch('/api/gallery/stats');
        this.stats = await res.json();
      } catch (e) {
        console.error('Failed to load stats:', e);
      }
    },
    async scanForImages() {
      this.scanning = true;
      try {
        const res = await fetch('/api/gallery/scan', { method: 'POST' });
        const data = await res.json();
        if (data.added > 0) {
          await this.loadGallery();
          await this.loadStats();
        }
        alert(data.added > 0 ? `新增 ${data.added} 张图片` : '没有发现新图片');
      } catch (e) {
        alert('扫描失败: ' + e.message);
      } finally {
        this.scanning = false;
      }
    },
    toggleSelect(id) {
      if (this.selectedIds.has(id)) {
        this.selectedIds.delete(id);
      } else {
        this.selectedIds.add(id);
      }
      // Force reactivity
      this.selectedIds = new Set(this.selectedIds);
    },
    openLightbox(img) {
      this.lightboxImage = img;
      this.lightboxIndex = this.filteredImages.findIndex(i => i.id === img.id);
      this.lightboxOpen = true;
    },
    closeLightbox() {
      this.lightboxOpen = false;
      this.lightboxImage = null;
    },
    prevLightbox() {
      if (this.lightboxIndex > 0) {
        this.lightboxIndex--;
        this.lightboxImage = this.filteredImages[this.lightboxIndex];
      }
    },
    nextLightbox() {
      if (this.lightboxIndex < this.filteredImages.length - 1) {
        this.lightboxIndex++;
        this.lightboxImage = this.filteredImages[this.lightboxIndex];
      }
    },
    confirmBatchDelete() {
      this.pendingDeleteIds = [...this.selectedIds];
      this.deleteDialogMessage = `确定要删除选中的 ${this.pendingDeleteIds.length} 张图片吗？文件将从磁盘删除，不可恢复。`;
      this.deleteDialogOpen = true;
    },
    deleteFromLightbox() {
      if (!this.lightboxImage) return;
      this.pendingDeleteIds = [this.lightboxImage.id];
      this.deleteDialogMessage = `确定要删除这张图片吗？文件将从磁盘删除，不可恢复。`;
      this.deleteDialogOpen = true;
    },
    async executeDelete() {
      this.deleteDialogOpen = false;
      try {
        if (this.pendingDeleteIds.length === 1) {
          await fetch(`/api/gallery/${this.pendingDeleteIds[0]}`, { method: 'DELETE' });
        } else {
          await fetch('/api/gallery/batch-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: this.pendingDeleteIds }),
          });
        }
        this.selectedIds = new Set();
        this.closeLightbox();
        await this.loadGallery();
        await this.loadStats();
      } catch (e) {
        alert('删除失败: ' + e.message);
      }
    },
    prevPage() {
      if (this.page > 1) { this.page--; this.loadGallery(); }
    },
    nextPage() {
      if (this.page < this.totalPages) { this.page++; this.loadGallery(); }
    },
    formatTime(iso) {
      if (!iso) return '';
      const d = new Date(iso);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
    },
    formatBytes(bytes) {
      if (!bytes) return '0 B';
      const k = 1024;
      const sizes = ['B', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    },
  },
};
</script>

<style scoped>
.gallery-page {
  max-width: 1400px;
  margin: 0 auto;
}

.gallery-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.header-left h1 {
  font-size: 20px;
  font-weight: 600;
}

.stats-text {
  color: #888;
  font-size: 13px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.btn {
  padding: 6px 14px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.15s;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: #00d4ff;
  color: #000;
}

.btn-primary:hover:not(:disabled) {
  background: #33ddff;
}

.btn-danger {
  background: #ff4444;
  color: #fff;
}

.btn-danger:hover:not(:disabled) {
  background: #ff6666;
}

.btn-ghost {
  background: transparent;
  color: #aaa;
  border: 1px solid #333;
}

.btn-ghost:hover:not(:disabled) {
  background: #1f1f1f;
  color: #fff;
}

.filter-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.search-input {
  flex: 1;
  padding: 7px 12px;
  background: #141414;
  border: 1px solid #2a2a2a;
  border-radius: 6px;
  color: #fff;
  font-size: 13px;
  outline: none;
}

.search-input:focus {
  border-color: #00d4ff;
}

.filter-select {
  padding: 7px 12px;
  background: #141414;
  border: 1px solid #2a2a2a;
  border-radius: 6px;
  color: #fff;
  font-size: 13px;
  outline: none;
  cursor: pointer;
}

/* Grid */
.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 14px;
}

.gallery-item {
  background: #141414;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid transparent;
  transition: border-color 0.15s;
}

.gallery-item.selected {
  border-color: #00d4ff;
}

.thumb-wrapper {
  position: relative;
  aspect-ratio: 1;
  overflow: hidden;
  cursor: pointer;
  background: #0a0a0a;
}

.thumb-wrapper img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.select-check {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 2;
}

.check-box {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.5);
  font-size: 13px;
  color: #fff;
  cursor: pointer;
  transition: all 0.15s;
}

.check-box:hover {
  border-color: rgba(255, 255, 255, 0.7);
}

.check-box.checked {
  background: #00d4ff;
  border-color: #00d4ff;
  color: #000;
}

.item-meta {
  padding: 8px 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.item-alias {
  font-size: 12px;
  color: #00d4ff;
  font-weight: 500;
}

.item-time {
  font-size: 11px;
  color: #666;
}

/* Empty */
.empty-state {
  text-align: center;
  padding: 80px 0;
  color: #666;
}

/* Pagination */
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  margin-top: 24px;
  padding-bottom: 24px;
}

.page-info {
  color: #888;
  font-size: 13px;
}

/* Lightbox */
.lightbox-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.92);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.lb-close {
  position: absolute;
  top: 16px;
  right: 20px;
  background: none;
  border: none;
  color: #fff;
  font-size: 32px;
  cursor: pointer;
  z-index: 1001;
  line-height: 1;
}

.lb-nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(255, 255, 255, 0.1);
  border: none;
  color: #fff;
  font-size: 28px;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  cursor: pointer;
  z-index: 1001;
  display: flex;
  align-items: center;
  justify-content: center;
}

.lb-prev { left: 16px; }
.lb-next { right: 16px; }
.lb-nav:hover { background: rgba(255, 255, 255, 0.2); }

.lb-content {
  display: flex;
  gap: 24px;
  max-width: 90vw;
  max-height: 90vh;
  align-items: flex-start;
}

.lb-image-wrap {
  flex-shrink: 0;
  max-width: 70vw;
  max-height: 85vh;
  display: flex;
  align-items: center;
}

.lb-image-wrap img {
  max-width: 100%;
  max-height: 85vh;
  border-radius: 6px;
}

.lb-meta {
  min-width: 240px;
  max-width: 300px;
  color: #ccc;
  font-size: 13px;
  padding: 16px 0;
}

.meta-row {
  margin-bottom: 12px;
}

.meta-row label {
  display: block;
  color: #666;
  font-size: 11px;
  text-transform: uppercase;
  margin-bottom: 2px;
}

.meta-prompt pre {
  background: #1a1a1a;
  padding: 8px 10px;
  border-radius: 4px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
  color: #aaa;
}

.lb-actions {
  margin-top: 16px;
}

/* Dialog */
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.dialog-box {
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
  border-radius: 10px;
  padding: 24px;
  min-width: 320px;
}

.dialog-box h3 {
  font-size: 16px;
  margin-bottom: 12px;
}

.dialog-box p {
  color: #aaa;
  font-size: 13px;
  margin-bottom: 20px;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
