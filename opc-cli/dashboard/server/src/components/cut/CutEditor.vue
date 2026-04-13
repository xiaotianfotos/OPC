<template>
  <div class="cut-editor">
    <Toolbar @export="handleExport" />
    <div class="main-container">
      <SubtitleEditor @seek-to="handleSeekTo" />
      <div class="right-panel">
        <VideoPlayer ref="videoPlayerRef" />
        <Timeline />
        <div class="status-bar">
          <div class="status-left">
            <div class="status-item">
              <i class="fas fa-mouse-pointer" style="font-size: 10px;"></i>
              <span>拖拽选择文字</span>
            </div>
            <div class="status-item">
              <i class="fas fa-keyboard" style="font-size: 10px;"></i>
              <span>Delete 删除选中</span>
            </div>
          </div>
          <div class="status-right">
            <div class="status-item" id="statusWords">
              <span>总字数: {{ totalWords }}</span>
            </div>
            <div class="status-item" id="statusDeleted">
              <span>已删: {{ deletedWordCount }}字 + {{ formatTime(deletedGapDuration) }}静音</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useCutStore } from '../../stores/cut';
import Toolbar from './Toolbar.vue';
import SubtitleEditor from './SubtitleEditor.vue';
import VideoPlayer from './VideoPlayer.vue';
import Timeline from './Timeline.vue';

const cutStore = useCutStore();
const videoPlayerRef = ref(null);

// Use computed wrappers to maintain reactivity
const totalWords = computed(() => cutStore.totalWords);
const deletedWordCount = computed(() => cutStore.deletedWordCount);
const deletedGapDuration = computed(() => cutStore.deletedGapDuration);
const duration = computed(() => cutStore.duration);

function formatTime(seconds) {
  if (!seconds) return '00:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function handleSeekTo(time) {
  videoPlayerRef.value?.seekTo(time);
}

function handleExport() {
  // Export is handled by Toolbar component
}
</script>

<script>
export default {
  name: 'CutEditor'
};
</script>

<style scoped>
.cut-editor {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary, #0a0a0a);
  color: var(--text-primary, #ffffff);
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

.main-container {
  display: flex;
  height: calc(100vh - 52px);
}

.right-panel {
  flex: 1;
  background: var(--bg-primary, #0a0a0a);
  display: flex;
  flex-direction: column;
}

.status-bar {
  height: 28px;
  background: var(--bg-tertiary, #1f1f1f);
  border-top: 1px solid var(--border, #2a2a2a);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  font-size: 11px;
  color: var(--text-muted, #666666);
}

.status-left,
.status-right {
  display: flex;
  gap: 16px;
  align-items: center;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>
