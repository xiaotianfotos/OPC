<template>
  <div class="compare-page">
    <!-- Header -->
    <header class="compare-header">
      <h1>模型评估</h1>
      <p class="subtitle">{{ modelList.map(m => modelName(m)).join(' · ') }}</p>
    </header>

    <!-- Stats Panel -->
    <div class="stats-panel" v-if="statsLoaded">
      <div
        v-for="model in modelList"
        :key="model"
        class="stat-card"
        :class="`stat-${statusFor(model)}`"
      >
        <div class="stat-name">{{ modelName(model) }}</div>
        <div class="stat-main">
          <span class="stat-ok">{{ statFor(model).ok }}</span>
          <span class="stat-sep">/</span>
          <span class="stat-total">{{ statFor(model).total }}</span>
        </div>
        <div class="stat-label">{{ statusLabel(model) }}</div>
        <div class="stat-time" v-if="statFor(model).elapsed">
          {{ formatTime(statFor(model).elapsed) }}
        </div>
      </div>
    </div>

    <!-- Filters -->
    <div class="filter-bar">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="搜索 prompt 标题..."
        class="search-input"
      />
      <select v-model="categoryFilter" class="filter-select">
        <option value="">全部分类</option>
        <option v-for="cat in allCategories" :key="cat" :value="cat">{{ cat }}</option>
      </select>
      <select v-model="statusFilter" class="filter-select">
        <option value="all">全部状态</option>
        <option value="complete">已完成</option>
        <option value="partial">部分完成</option>
        <option value="pending">等待中</option>
      </select>
      <span class="filter-count">
        {{ filteredGroups.length }} / {{ groupedResults.length }}
      </span>
    </div>

    <!-- Results Grid -->
    <div class="compare-grid" v-if="groupedResults.length > 0">
      <div
        v-for="group in filteredGroups"
        :key="group.promptId"
        class="compare-card"
        :class="{ 'card-pending': groupStatus(group) === 'pending' }"
      >
        <div class="card-header">
          <div class="card-title-row">
            <h3>{{ group.title }}</h3>
            <span class="category-tag" v-if="group.category">{{ group.category }}</span>
          </div>
          <span class="prompt-id">{{ group.promptId }}</span>
        </div>

        <div class="tags-row" v-if="group.tags && group.tags.length">
          <span v-for="tag in group.tags.slice(0, 5)" :key="tag" class="tag">{{ tag }}</span>
        </div>

        <div class="prompt-section">
          <button class="prompt-toggle" @click="togglePrompt(group.promptId)">
            {{ expandedPrompts[group.promptId] ? '收起提示词' : '展开提示词' }}
          </button>
          <div v-if="expandedPrompts[group.promptId]" class="prompt-full">
            <div class="prompt-block">
              <label>Positive</label>
              <pre>{{ group.prompt }}</pre>
            </div>
            <div class="prompt-block" v-if="group.negative">
              <label>Negative</label>
              <pre>{{ group.negative }}</pre>
            </div>
          </div>
          <p class="prompt-preview" v-else>
            {{ group.prompt ? group.prompt.substring(0, 120) + '...' : '' }}
          </p>
        </div>

        <div class="model-row">
          <div
            v-for="model in modelList"
            :key="model"
            class="model-col"
            :class="{ 'model-ok': group[model]?.status === 'ok' }"
            @click="openLightbox(group, model)"
          >
            <div class="model-label">{{ modelName(model) }}</div>
            <div class="image-wrapper">
              <img
                v-if="group[model]?.status === 'ok'"
                :src="imageUrl(group[model].file, model)"
                :alt="model"
                loading="lazy"
              />
              <div v-else-if="group[model]?.status === 'error'" class="error-box">
                <span class="error-icon">!</span>
                <span class="error-text">{{ group[model]?.error || '生成失败' }}</span>
              </div>
              <div v-else class="loading-box">
                <div class="spinner"></div>
                <span>等待中</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="empty-state" v-else-if="results.length === 0">
      <div class="spinner large"></div>
      <p>正在加载测试结果...</p>
    </div>

    <div class="empty-state" v-else>
      <p>没有匹配的结果</p>
    </div>

    <!-- Lightbox Modal -->
    <div v-if="lightboxOpen" class="lightbox-overlay" @click.self="closeLightbox">
      <div class="lightbox-container">
        <button class="lightbox-close" @click="closeLightbox">&times;</button>
        <button class="lightbox-nav prev" @click="prevImage" v-if="lightboxIndex > 0">
          &lsaquo;
        </button>
        <button
          class="lightbox-nav next"
          @click="nextImage"
          v-if="lightboxIndex < lightboxAvailableModels.length - 1"
        >
          &rsaquo;
        </button>

        <div class="lightbox-content">
          <div class="lightbox-header">
            <span class="lightbox-badge">{{ modelName(lightboxModel) }}</span>
            <span class="lightbox-title-inline">{{ lightboxTitle }}</span>
          </div>
          <img
            v-if="lightboxImage"
            :src="lightboxImage"
            :alt="lightboxModel"
          />
          <div class="lightbox-meta">
            <div class="lightbox-prompt" v-if="lightboxPrompt">
              <pre>{{ lightboxPrompt }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      prompts: [],
      results: [],
      metaByModel: {},
      refreshTimer: null,
      searchQuery: '',
      categoryFilter: '',
      statusFilter: 'all',
      expandedPrompts: {},
      lightboxOpen: false,
      lightboxGroup: null,
      lightboxModel: null,
      lightboxIndex: 0,
      modelList: [],
    };
  },

  computed: {
    statsLoaded() {
      return Object.keys(this.metaByModel).length > 0;
    },

    allCategories() {
      const cats = new Set();
      for (const p of this.prompts) {
        if (p.category) cats.add(p.category);
      }
      return [...cats].sort();
    },

    groupedResults() {
      const map = {};
      for (const p of this.prompts) {
        map[p.id] = {
          promptId: p.id,
          title: p.title,
          category: p.category,
          tags: p.tags,
          prompt: p.prompt,
          negative: p.negative,
        };
      }
      for (const r of this.results) {
        if (map[r.prompt_id]) {
          map[r.prompt_id][r.model] = r;
        }
      }
      return Object.values(map);
    },

    filteredGroups() {
      return this.groupedResults.filter(g => {
        if (this.searchQuery) {
          const q = this.searchQuery.toLowerCase();
          const match =
            g.title.toLowerCase().includes(q) ||
            g.promptId.toLowerCase().includes(q) ||
            (g.category && g.category.toLowerCase().includes(q)) ||
            (g.tags && g.tags.some(t => t.toLowerCase().includes(q)));
          if (!match) return false;
        }
        if (this.categoryFilter && g.category !== this.categoryFilter) {
          return false;
        }
        const status = this.groupStatus(g);
        if (this.statusFilter === 'complete' && status !== 'done') return false;
        if (this.statusFilter === 'partial' && status !== 'partial') return false;
        if (this.statusFilter === 'pending' && status !== 'pending') return false;
        return true;
      });
    },

    lightboxImage() {
      if (!this.lightboxGroup || this.lightboxIndex < 0) return null;
      const model = this.lightboxAvailableModels[this.lightboxIndex];
      const item = this.lightboxGroup[model];
      if (!item || item.status !== 'ok') return null;
      return this.imageUrl(item.file, model);
    },

    lightboxTitle() {
      return this.lightboxGroup?.title || '';
    },

    lightboxAvailableModels() {
      if (!this.lightboxGroup) return [];
      return this.modelList.filter(m => this.lightboxGroup[m]?.status === 'ok');
    },

    lightboxPrompt() {
      return this.lightboxGroup?.prompt || '';
    },
  },

  mounted() {
    this.loadAll();
    this.refreshTimer = setInterval(() => this.loadResults(), 10000);
    document.addEventListener('keydown', this.handleKeydown);
  },

  beforeUnmount() {
    clearInterval(this.refreshTimer);
    document.removeEventListener('keydown', this.handleKeydown);
  },

  methods: {
    async loadAll() {
      await this.discoverModels();
      await this.loadPrompts();
      await this.loadResults();
    },

    async discoverModels() {
      try {
        const res = await fetch('/api/eval/models');
        if (res.ok) {
          this.modelList = await res.json();
        }
      } catch (e) {
        console.error('Failed to discover models:', e);
        this.modelList = ['ernie-full', 'ernie-turbo', 'z-image', 'qwen-image'];
      }
    },

    async loadPrompts() {
      try {
        const res = await fetch('/api/eval/prompts');
        if (res.ok) {
          this.prompts = await res.json();
        }
      } catch (e) {
        console.error('Failed to load prompts:', e);
      }
    },

    async loadResults() {
      for (const alias of this.modelList) {
        try {
          const res = await fetch(`/api/eval/results/${alias}`);
          if (res.ok) {
            const data = await res.json();
            if (data.results) {
              // Remove old results for this model
              this.results = this.results.filter(r => r.model !== alias);
              this.results.push(...data.results);
              if (data.meta) {
                this.metaByModel[alias] = data.meta;
              }
            }
          }
        } catch (e) {
          // silently ignore
        }
      }
    },

    modelName(alias) {
      const map = {
        'ernie-full': 'Ernie-Full',
        'ernie-turbo': 'Ernie-Turbo',
        'z-image': 'Z-Image',
        'qwen-image': 'Qwen-2512',
      };
      return map[alias] || alias;
    },

    imageUrl(filename, model) {
      return `/api/eval/image/${model}/${filename}`;
    },

    statusFor(alias) {
      const meta = this.metaByModel[alias];
      if (!meta || meta.total === 0) return 'pending';
      if (meta.ok === meta.total) return 'done';
      if (meta.ok > 0) return 'partial';
      return 'error';
    },

    statusClass(alias) {
      return `status-${this.statusFor(alias)}`;
    },

    statusLabel(alias) {
      const s = this.statusFor(alias);
      const labels = { done: '已完成', partial: '部分完成', error: '失败', pending: '等待中' };
      return labels[s] || s;
    },

    statFor(alias) {
      const meta = this.metaByModel[alias];
      if (!meta) return { ok: 0, total: 0, elapsed: 0 };
      return {
        ok: meta.ok || 0,
        total: meta.total || 0,
        elapsed: meta.elapsed_seconds || 0,
      };
    },

    groupStatus(group) {
      let ok = 0;
      let total = 0;
      for (const model of this.modelList) {
        if (group[model]) {
          total++;
          if (group[model].status === 'ok') ok++;
        }
      }
      if (total === 0) return 'pending';
      if (ok === total) return 'done';
      if (ok > 0) return 'partial';
      return 'pending';
    },

    formatTime(seconds) {
      if (!seconds) return '';
      const h = Math.floor(seconds / 3600);
      const m = Math.floor((seconds % 3600) / 60);
      if (h > 0) return `${h}h ${m}m`;
      return `${m}m`;
    },

    togglePrompt(pid) {
      this.expandedPrompts = {
        ...this.expandedPrompts,
        [pid]: !this.expandedPrompts[pid],
      };
    },

    openLightbox(group, model) {
      if (!group[model] || group[model].status !== 'ok') return;
      this.lightboxGroup = group;
      this.lightboxModel = model;
      const available = this.modelList.filter(m => group[m]?.status === 'ok');
      this.lightboxIndex = available.indexOf(model);
      this.lightboxOpen = true;
      document.body.style.overflow = 'hidden';
    },

    closeLightbox() {
      this.lightboxOpen = false;
      document.body.style.overflow = '';
    },

    handleKeydown(e) {
      if (!this.lightboxOpen) return;
      if (e.key === 'Escape') this.closeLightbox();
      if (e.key === 'ArrowLeft') this.prevImage();
      if (e.key === 'ArrowRight') this.nextImage();
    },

    prevImage() {
      if (this.lightboxIndex > 0) {
        this.lightboxIndex--;
        this.lightboxModel = this.lightboxAvailableModels[this.lightboxIndex];
      }
    },

    nextImage() {
      if (this.lightboxIndex < this.lightboxAvailableModels.length - 1) {
        this.lightboxIndex++;
        this.lightboxModel = this.lightboxAvailableModels[this.lightboxIndex];
      }
    },
  },
};
</script>

<style scoped>
.compare-page {
  max-width: 1600px;
  margin: 0 auto;
  padding: 0 16px 60px;
}

/* Header */
.compare-header {
  text-align: center;
  padding: 24px 0 16px;
}

.compare-header h1 {
  font-size: 26px;
  font-weight: 700;
  margin-bottom: 4px;
  letter-spacing: -0.5px;
}

.subtitle {
  color: #888;
  font-size: 13px;
}

/* Stats Panel */
.stats-panel {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.stat-card {
  background: #111;
  border: 1px solid #222;
  border-radius: 10px;
  padding: 16px;
  text-align: center;
  transition: border-color 0.2s;
}

.stat-card.stat-done {
  border-color: rgba(0, 212, 100, 0.4);
}

.stat-card.stat-partial {
  border-color: rgba(255, 180, 0, 0.4);
}

.stat-card.stat-pending {
  border-color: #2a2a2a;
}

.stat-name {
  font-size: 12px;
  color: #888;
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.stat-main {
  font-size: 28px;
  font-weight: 700;
  margin-bottom: 4px;
}

.stat-ok {
  color: #00d464;
}

.stat-sep {
  color: #555;
  margin: 0 4px;
}

.stat-total {
  color: #aaa;
}

.stat-label {
  font-size: 12px;
  color: #666;
}

.stat-time {
  font-size: 11px;
  color: #444;
  margin-top: 4px;
}

/* Filter Bar */
.filter-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  flex-wrap: wrap;
  align-items: center;
}

.search-input {
  flex: 1;
  min-width: 200px;
  background: #111;
  border: 1px solid #2a2a2a;
  border-radius: 6px;
  padding: 8px 12px;
  color: #fff;
  font-size: 13px;
  outline: none;
}

.search-input:focus {
  border-color: #00d4ff;
}

.filter-select {
  background: #111;
  border: 1px solid #2a2a2a;
  border-radius: 6px;
  padding: 8px 10px;
  color: #ccc;
  font-size: 13px;
  outline: none;
  cursor: pointer;
}

.filter-count {
  font-size: 12px;
  color: #555;
  margin-left: auto;
}

/* Grid */
.compare-grid {
  display: grid;
  gap: 24px;
}

.compare-card {
  background: #111;
  border: 1px solid #222;
  border-radius: 12px;
  overflow: hidden;
  transition: border-color 0.2s;
}

.compare-card.card-pending {
  opacity: 0.7;
}

/* Card Header */
.card-header {
  padding: 14px 18px 10px;
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.card-title-row h3 {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
}

.category-tag {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(0, 212, 255, 0.1);
  color: #00d4ff;
  border: 1px solid rgba(0, 212, 255, 0.2);
}

.prompt-id {
  font-size: 11px;
  color: #555;
  font-family: 'Space Mono', monospace;
}

/* Tags */
.tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 0 18px 10px;
}

.tag {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 4px;
  background: #1a1a1a;
  color: #666;
  border: 1px solid #2a2a2a;
}

/* Prompt Section */
.prompt-section {
  padding: 0 18px 12px;
}

.prompt-toggle {
  background: none;
  border: none;
  color: #00d4ff;
  font-size: 12px;
  cursor: pointer;
  padding: 0;
  margin-bottom: 6px;
}

.prompt-toggle:hover {
  text-decoration: underline;
}

.prompt-full {
  background: #0a0a0a;
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 8px;
}

.prompt-block {
  margin-bottom: 8px;
}

.prompt-block:last-child {
  margin-bottom: 0;
}

.prompt-block label {
  display: block;
  font-size: 10px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 4px;
}

.prompt-block pre {
  margin: 0;
  font-size: 12px;
  color: #aaa;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
}

.prompt-preview {
  font-size: 12px;
  color: #555;
  line-height: 1.5;
  margin: 0;
}

/* Model Row */
.model-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 2px;
  background: #0a0a0a;
}

.model-col {
  background: #111;
  padding: 10px;
  cursor: pointer;
  transition: background 0.15s;
}

.model-col:hover {
  background: #161616;
}

.model-col.model-ok:hover .image-wrapper img {
  transform: scale(1.02);
}

.model-label {
  font-size: 11px;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 6px;
  text-align: center;
}

.image-wrapper {
  border-radius: 6px;
  overflow: hidden;
  background: #0a0a0a;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 180px;
}

.image-wrapper img {
  width: 100%;
  height: auto;
  object-fit: contain;
  display: block;
  transition: transform 0.3s ease;
}

.loading-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #444;
  font-size: 12px;
}

.error-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  color: #ff3c3c;
  padding: 20px;
}

.error-icon {
  font-size: 24px;
  font-weight: 700;
}

.error-text {
  font-size: 11px;
  text-align: center;
  max-width: 80%;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid #222;
  border-top-color: #00d4ff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.spinner.large {
  width: 40px;
  height: 40px;
  border-width: 3px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 80px 0;
  color: #555;
  font-size: 14px;
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
  padding: 20px;
}

.lightbox-container {
  position: relative;
  max-width: 90vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.lightbox-close {
  position: absolute;
  top: -40px;
  right: 0;
  background: none;
  border: none;
  color: #fff;
  font-size: 32px;
  cursor: pointer;
  z-index: 10;
}

.lightbox-nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(255, 255, 255, 0.1);
  border: none;
  color: #fff;
  font-size: 36px;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

.lightbox-nav:hover {
  background: rgba(255, 255, 255, 0.2);
}

.lightbox-nav.prev {
  left: -60px;
}

.lightbox-nav.next {
  right: -60px;
}

.lightbox-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  max-height: 85vh;
  overflow: hidden;
}

.lightbox-content img {
  max-width: 95vw;
  max-height: 80vh;
  object-fit: contain;
  border-radius: 8px;
}

.lightbox-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.lightbox-badge {
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 6px;
  padding: 4px 12px;
  font-size: 13px;
  font-weight: 700;
  color: #00d4ff;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.lightbox-title-inline {
  font-size: 15px;
  color: #ccc;
}

.lightbox-meta {
  margin-top: 16px;
  text-align: center;
  max-width: 600px;
}

.lightbox-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 4px;
}

.lightbox-model {
  font-size: 12px;
  color: #888;
  margin-bottom: 8px;
}

.lightbox-prompt {
  background: #1a1a1a;
  border-radius: 6px;
  padding: 10px 14px;
  max-height: 150px;
  overflow: auto;
}

.lightbox-prompt pre {
  margin: 0;
  font-size: 11px;
  color: #999;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  text-align: left;
}

@media (max-width: 900px) {
  .stats-panel {
    grid-template-columns: 1fr;
  }

  .model-row {
    grid-template-columns: 1fr;
  }

  .filter-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-count {
    margin-left: 0;
  }

  .lightbox-nav.prev {
    left: 10px;
  }

  .lightbox-nav.next {
    right: 10px;
  }

  .lightbox-content img {
    max-width: 85vw;
  }
}
</style>
