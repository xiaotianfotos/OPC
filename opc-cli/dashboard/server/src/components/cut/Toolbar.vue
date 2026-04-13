<template>
  <div class="toolbar">
    <div class="logo">
      <i class="fas fa-scissors"></i>
      <span>Cutx</span>
    </div>
    <div class="toolbar-actions">
      <button class="btn btn-secondary" :disabled="!canUndo" @click="undo">
        <i class="fas fa-undo"></i>
        撤销
      </button>
      <button class="btn btn-secondary" :disabled="!canRedo" @click="redo">
        <i class="fas fa-redo"></i>
        重做
      </button>
      <div style="width: 1px; height: 24px; background: var(--border, #2a2a2a); margin: 0 4px;"></div>

      <!-- Export / Download button -->
      <button v-if="!lastDownloadUrl" class="btn btn-primary" @click="handleExport" :disabled="!canExport || isExporting">
        <i class="fas" :class="isExporting ? 'fa-spinner fa-spin' : 'fa-download'"></i>
        {{ isExporting ? exportStatus : '导出视频' }}
      </button>
      <button v-else class="btn btn-success" @click="handleDownload">
        <i class="fas fa-file-download"></i>
        下载视频
      </button>
    </div>

    <!-- Progress Modal -->
    <div class="progress-container" :class="{ active: isExporting }">
      <div class="progress-box">
        <div class="progress-spinner"></div>
        <p>{{ exportStatus }}</p>
        <div class="progress-bar" v-if="exportProgress > 0">
          <div class="progress-fill" :style="{ width: exportProgress + '%' }"></div>
          <span class="progress-text">{{ exportProgress }}%</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { useCutStore } from '../../stores/cut';
import * as cutApi from '../../api/cut';

const cutStore = useCutStore();

const isExporting = ref(false);
const exportStatus = ref('正在导出视频...');
const exportProgress = ref(0);
const canUndo = ref(false);
const canRedo = ref(false);
const lastDownloadUrl = ref(null);

// Reset download button when edits change
watch(() => cutStore.deletedWords, () => {
  lastDownloadUrl.value = null;
}, { deep: true });

// Computed - access store state directly to maintain reactivity
const canExport = computed(() => {
  return cutStore.currentFile && cutStore.keptWords > 0;
});

async function handleExport() {
  if (!cutStore.currentFile) {
    alert('请先上传视频');
    return;
  }

  isExporting.value = true;
  exportStatus.value = '正在导出视频...';
  exportProgress.value = 0;
  lastDownloadUrl.value = null;

  try {
    // Use SSE for real-time progress
    const result = await cutApi.exportVideoWithProgress({
      file_id: cutStore.currentFile.file_id,
      cuts: cutStore.buildCutRanges(),
      format: 'mp4',
      apply_valley_correction: false,
      energy_threshold: cutStore.config.energyThreshold,
      search_ms: cutStore.config.searchRange
    }, (event) => {
      if (event.type === 'start') {
        exportStatus.value = event.message;
      } else if (event.type === 'progress') {
        exportProgress.value = event.progress || 0;
        exportStatus.value = event.message || '导出中...';
      } else if (event.type === 'complete') {
        exportProgress.value = 100;
        exportStatus.value = '导出完成！';
      }
    });

    if (result.success && result.download_url) {
      lastDownloadUrl.value = result.download_url;
    } else {
      alert('导出失败：未知错误');
    }
  } catch (error) {
    alert('导出失败：' + (error.message || '未知错误'));
  } finally {
    isExporting.value = false;
  }
}

function handleDownload() {
  if (lastDownloadUrl.value) {
    window.open(lastDownloadUrl.value, '_blank');
  }
}

function undo() {
  console.log('Undo not yet implemented');
}

function redo() {
  console.log('Redo not yet implemented');
}
</script>

<script>
export default {
  name: 'Toolbar'
};
</script>

<style scoped>
.toolbar {
  height: 52px;
  background: var(--bg-secondary, #141414);
  border-bottom: 1px solid var(--border, #2a2a2a);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
}

:root {
  --bg-primary: #0a0a0a;
  --bg-secondary: #141414;
  --bg-tertiary: #1f1f1f;
  --bg-hover: #2a2a2a;
  --text-primary: #ffffff;
  --text-secondary: #a0a0a0;
  --text-muted: #666666;
  --accent: #00d4ff;
  --accent-hover: #00b8e6;
  --danger: #ff4757;
  --success: #2ed573;
  --warning: #ffa502;
  --border: #2a2a2a;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  font-size: 16px;
}

.logo i {
  color: var(--accent, #00d4ff);
  font-size: 20px;
}

.toolbar-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.btn {
  padding: 8px 14px;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  gap: 6px;
}

.btn-primary {
  background: var(--accent, #00d4ff);
  color: #000;
}

.btn-primary:hover {
  background: var(--accent-hover, #00b8e6);
}

.btn-success {
  background: var(--success, #2ed573);
  color: #000;
}

.btn-success:hover {
  opacity: 0.85;
}

.btn-secondary {
  background: var(--bg-tertiary, #1f1f1f);
  color: var(--text-primary, #ffffff);
  border: 1px solid var(--border, #2a2a2a);
}

.btn-secondary:hover {
  background: var(--bg-hover, #2a2a2a);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Progress Modal */
.progress-container {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.85);
  display: none;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.progress-container.active {
  display: flex;
}

.progress-box {
  background: var(--bg-secondary, #141414);
  padding: 32px 48px;
  border-radius: 12px;
  text-align: center;
  border: 1px solid var(--border, #2a2a2a);
}

.progress-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border, #2a2a2a);
  border-top-color: var(--accent, #00d4ff);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 16px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.progress-box p {
  color: var(--text-primary, #ffffff);
  margin: 0;
}

/* Progress Bar */
.progress-bar {
  position: relative;
  width: 100%;
  height: 24px;
  background: var(--bg-tertiary, #1f1f1f);
  border-radius: 12px;
  overflow: hidden;
  margin-top: 16px;
}

.progress-fill {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: linear-gradient(90deg, var(--accent, #00d4ff), var(--accent-hover, #00b8e6));
  transition: width 0.3s ease;
}

.progress-text {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-primary, #ffffff);
  font-size: 12px;
  font-weight: 600;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.8);
}
</style>
