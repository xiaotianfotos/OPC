<template>
  <div class="subtitle-editor">
    <div class="editor-header">
      <span class="panel-title">字幕编辑</span>
      <span class="panel-stats">{{ keptWords }}/{{ totalWords }} 字</span>
    </div>

    <div v-if="words.length === 0" class="upload-area">
      <i class="fas fa-cloud-upload-alt"></i>
      <p>拖拽视频文件到此处，或点击上传</p>
      <p style="font-size: 12px; margin-top: 8px; opacity: 0.6;">支持 MP4, MOV, MP3, WAV 格式</p>
    </div>

    <template v-else>
      <div class="editor-toolbar">
        <button
          class="editor-btn danger"
          :disabled="!hasSelection"
          @click="deleteSelected"
          title="删除选中 (Delete/Backspace)"
        >
          <i class="fas fa-trash"></i>
          删除
        </button>
        <button
          class="editor-btn"
          :disabled="!hasSelection"
          @click="restoreSelected"
          title="恢复选中"
        >
          <i class="fas fa-undo"></i>
          恢复
        </button>
        <div class="toolbar-divider"></div>
        <button class="editor-btn danger" @click="confirmClearDeleted">
          <i class="fas fa-broom"></i>
          清除已删除
        </button>
        <div class="toolbar-divider"></div>
        <div class="config-item">
          <label for="gapThreshold">间隙阈值 (秒):</label>
          <input
            id="gapThreshold"
            type="number"
            :value="config.gapThreshold"
            @change="updateGapThreshold"
            step="0.1"
            min="0.1"
            max="5"
            style="width: 60px;"
          />
        </div>
        <div class="toolbar-divider"></div>
        <div class="config-item">
          <label for="energyThreshold">能量阈值:</label>
          <input
            id="energyThreshold"
            type="number"
            :value="config.energyThreshold"
            @change="updateEnergyThreshold"
            step="0.1"
            min="0.1"
            max="1.0"
            style="width: 60px;"
          />
        </div>
        <div class="config-item">
          <label for="searchMs">搜索范围 (ms):</label>
          <input
            id="searchMs"
            type="number"
            :value="config.searchRange"
            @change="updateSearchRange"
            step="10"
            min="10"
            max="500"
            style="width: 60px;"
          />
        </div>
      </div>

      <div class="editor-container" ref="editorContainer" @mousedown="handleContainerMouseDown">
        <div class="text-content">
          <template v-for="(word, index) in words" :key="index">
            <span
              class="word"
              :class="{
                deleted: isWordDeleted(index),
                selected: isWordSelected(index),
                current: index === currentWordIndex
              }"
              :data-index="index"
              :data-start="word.start_time"
              :data-end="word.end_time"
              @mousedown="handleWordMouseDown($event, index)"
              @mouseenter="handleWordMouseEnter($event, index)"
              @mouseup="handleWordMouseUp($event, index)"
              @dblclick="toggleDeleteWord(index)"
            >
              {{ word.text }}
              <span class="time-hint">{{ formatTime(word.start_time) }}</span>
            </span>

            <!-- Render gap after this word if exists -->
            <span
              v-if="getGapAfterWord(index)"
              class="gap"
              :class="{
                deleted: isGapDeleted(getGapAfterWord(index).index),
                selected: isGapSelected(getGapAfterWord(index).index)
              }"
              :data-gap-index="getGapAfterWord(index).index"
              :title="`间隙 ${formatTime(getGapAfterWord(index).duration)}`"
              @mousedown="handleGapMouseDown($event, getGapAfterWord(index).index)"
              @click="handleGapClick($event, getGapAfterWord(index))"
              @dblclick="toggleDeleteGap(getGapAfterWord(index).index)"
            >
              <span class="gap-line"></span>
              <span class="gap-label">{{ getGapAfterWord(index).duration.toFixed(1) }}s</span>
            </span>
          </template>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { useCutStore } from '../../stores/cut';

const cutStore = useCutStore();

// Helper functions to check if a word/gap is deleted or selected
// Access store properties directly to preserve reactivity
function isWordDeleted(index) {
  return cutStore.deletedWords.has(index);
}

function isWordSelected(index) {
  return cutStore.selectedWords.has(index);
}

function isGapDeleted(gapIndex) {
  return cutStore.deletedGaps.has(gapIndex);
}

function isGapSelected(gapIndex) {
  return cutStore.selectedGaps.has(gapIndex);
}

// Use computed for currentWordIndex to preserve reactivity
const currentWordIndex = computed(() => cutStore.currentWordIndex);

// Destructure refs (words, gaps are refs, Set properties are accessed via helper functions)
const { words, gaps, config } = cutStore;

// Computed from store
const totalWords = computed(() => cutStore.totalWords);
const keptWords = computed(() => cutStore.keptWords);
const hasSelection = computed(() => cutStore.hasSelection);

const editorContainer = ref(null);

// Drag selection state
const isDragging = ref(false);
const dragStartIndex = ref(-1);
const isGapDrag = ref(false);

// Methods
function formatTime(seconds) {
  if (!seconds) return '00:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function getGapAfterWord(index) {
  if (!cutStore.gaps || cutStore.gaps.length === 0) return null;
  return cutStore.gaps.find(g => g.afterWord === index);
}

function handleWordMouseDown(event, index) {
  event.preventDefault();
  isDragging.value = true;
  isGapDrag.value = false;
  dragStartIndex.value = index;

  // Don't select on mousedown - wait for mouseup or drag
  // This prevents the initial selection from conflicting with drag selection
}

function handleWordMouseEnter(event, index) {
  if (isDragging.value && !isGapDrag.value) {
    // If dragging started from empty area (-1), start selection from this word
    const startIdx = dragStartIndex.value === -1 ? index : dragStartIndex.value;
    cutStore.selectWordRange(startIdx, index);
  }
}

function handleWordMouseUp(event, index) {
  // End of drag - selection is already set by mouseEnter
  isDragging.value = false;

  // If not dragging (just a click), seek to this word
  if (dragStartIndex.value === index) {
    emit('seekTo', words[index].start_time);
  }
}

function handleContainerMouseDown(event) {
  // Click on empty area - clear selection and prepare for drag selection
  if (event.target === editorContainer.value || event.target.classList.contains('text-content')) {
    cutStore.clearSelection();
    // Set up for drag selection from this point
    isDragging.value = true;
    isGapDrag.value = false;
    dragStartIndex.value = -1; // -1 means dragging started from empty area
  }
}

function handleGapMouseDown(event, gapIndex) {
  event.preventDefault();
  event.stopPropagation();
  isDragging.value = false;
  isGapDrag.value = true;

  const { shiftKey, metaKey, ctrlKey } = event;
  cutStore.toggleGapSelection(gapIndex, shiftKey, metaKey, ctrlKey);
}

function handleGapClick(event, gap) {
  event.stopPropagation();
  // Seek to gap start - handled by parent component
}

function toggleDeleteWord(index) {
  cutStore.toggleDeleteWord(index);
}

function toggleDeleteGap(gapIndex) {
  cutStore.toggleDeleteGap(gapIndex);
}

function deleteSelected() {
  cutStore.deleteSelected();
}

function restoreSelected() {
  cutStore.restoreSelected();
}

function confirmClearDeleted() {
  if (confirm('确定要清除所有已删除的字和间隙吗？此操作不可撤销。')) {
    cutStore.clearDeleted();
  }
}

function updateGapThreshold(event) {
  const value = parseFloat(event.target.value) || 0.5;
  cutStore.updateConfig('gapThreshold', value);
}

function updateEnergyThreshold(event) {
  const value = parseFloat(event.target.value) || 0.7;
  cutStore.updateConfig('energyThreshold', value);
}

function updateSearchRange(event) {
  const value = parseInt(event.target.value) || 100;
  cutStore.updateConfig('searchRange', value);
}

// Global mouse events for drag selection
function handleMouseUp() {
  isDragging.value = false;
  isGapDrag.value = false;
  dragStartIndex.value = -1;
}

// Keyboard shortcuts
function handleKeyDown(event) {
  if (event.key === 'Delete' || event.key === 'Backspace') {
    if (hasSelection.value) {
      event.preventDefault();
      deleteSelected();
    }
  } else if (event.key === 'Escape') {
    cutStore.clearSelection();
  }
}

onMounted(() => {
  document.addEventListener('mouseup', handleMouseUp);
  document.addEventListener('keydown', handleKeyDown);
});

onUnmounted(() => {
  document.removeEventListener('mouseup', handleMouseUp);
  document.removeEventListener('keydown', handleKeyDown);
});

// Emit current word click for video seeking
const emit = defineEmits(['seekTo']);

function seekToWord(word) {
  emit('seekTo', word.start_time);
}
</script>

<script>
export default {
  name: 'SubtitleEditor',
  emits: ['seekTo']
};
</script>

<style scoped>
.subtitle-editor {
  width: 50%;
  min-width: 400px;
  background: var(--bg-secondary, #141414);
  border-right: 1px solid var(--border, #2a2a2a);
  display: flex;
  flex-direction: column;
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
  --selected: rgba(0, 212, 255, 0.3);
  --deleted: rgba(255, 71, 87, 0.3);
}

.editor-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border, #2a2a2a);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-tertiary, #1f1f1f);
}

.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary, #a0a0a0);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.panel-stats {
  font-size: 12px;
  color: var(--text-muted, #666666);
}

.upload-area {
  padding: 60px 40px;
  border: 2px dashed var(--border, #2a2a2a);
  border-radius: 12px;
  margin: 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
}

.upload-area:hover {
  border-color: var(--accent, #00d4ff);
  background: rgba(0, 212, 255, 0.05);
}

.upload-area i {
  font-size: 48px;
  color: var(--text-secondary, #a0a0a0);
  margin-bottom: 16px;
}

.upload-area p {
  color: var(--text-secondary, #a0a0a0);
  font-size: 14px;
}

.editor-toolbar {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  background: var(--bg-tertiary, #1f1f1f);
  border-bottom: 1px solid var(--border, #2a2a2a);
  align-items: center;
  flex-wrap: wrap;
}

.toolbar-divider {
  width: 1px;
  height: 20px;
  background: var(--border, #2a2a2a);
  margin: 0 4px;
}

.editor-btn {
  padding: 6px 12px;
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-secondary, #a0a0a0);
  cursor: pointer;
  border-radius: 4px;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.15s;
}

.editor-btn:hover {
  background: var(--bg-hover, #2a2a2a);
  color: var(--text-primary, #ffffff);
}

.editor-btn.danger:hover {
  background: var(--danger, #ff4757);
  color: white;
}

.editor-btn.active {
  background: var(--accent, #00d4ff);
  color: #000;
}

.editor-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.config-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 8px;
}

.config-item label {
  font-size: 12px;
  color: var(--text-secondary, #a0a0a0);
}

.config-item input {
  padding: 4px 8px;
  background: var(--bg-primary, #0a0a0a);
  border: 1px solid var(--border, #2a2a2a);
  border-radius: 4px;
  color: var(--text-primary, #ffffff);
  font-size: 12px;
}

.config-item input:focus {
  outline: none;
  border-color: var(--accent, #00d4ff);
}

.editor-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  user-select: none;
}

.text-content {
  line-height: 2.2;
  font-size: 16px;
  white-space: pre-wrap;
  word-wrap: break-word;
  user-select: none;
}

.word {
  display: inline;
  padding: 2px 1px;
  margin: 0 1px;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.1s;
  position: relative;
}

.word:hover:not(.selected) {
  background: var(--bg-hover, #2a2a2a);
}

.word.selected {
  background: var(--selected, rgba(0, 212, 255, 0.3)) !important;
  box-shadow: 0 0 0 1px var(--accent, #00d4ff);
}

.word.deleted {
  background: var(--deleted, rgba(255, 71, 87, 0.3));
  text-decoration: line-through;
  opacity: 0.5;
}

.word.current:not(.selected) {
  background: rgba(0, 212, 255, 0.15);
  border-bottom: 2px solid var(--accent, #00d4ff);
}

.word .time-hint {
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  background: var(--bg-tertiary, #1f1f1f);
  color: var(--text-secondary, #a0a0a0);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s;
  z-index: 100;
  border: 1px solid var(--border, #2a2a2a);
}

.word:hover .time-hint {
  opacity: 1;
}

.gap {
  display: inline-flex;
  align-items: center;
  vertical-align: middle;
  margin: 0 4px;
  padding: 2px 6px;
  background: var(--bg-tertiary, #1f1f1f);
  border-radius: 4px;
  cursor: pointer;
  user-select: none;
  transition: all 0.15s;
  border: 1px dashed var(--border, #2a2a2a);
}

.gap:hover {
  background: var(--bg-hover, #2a2a2a);
  border-color: var(--accent, #00d4ff);
}

.gap.selected {
  background: var(--selected, rgba(0, 212, 255, 0.3));
  border-color: var(--accent, #00d4ff);
  border-style: solid;
}

.gap.deleted {
  opacity: 0.3;
  background: var(--danger, #ff4757);
  border-color: var(--danger, #ff4757);
}

.gap-line {
  width: 20px;
  height: 2px;
  background: var(--text-muted, #666666);
  margin-right: 4px;
}

.gap.selected .gap-line {
  background: var(--accent, #00d4ff);
}

.gap.deleted .gap-line {
  background: var(--danger, #ff4757);
}

.gap-label {
  font-size: 10px;
  color: var(--text-muted, #666666);
  font-variant-numeric: tabular-nums;
}

.gap:hover .gap-label {
  color: var(--accent, #00d4ff);
}
</style>
