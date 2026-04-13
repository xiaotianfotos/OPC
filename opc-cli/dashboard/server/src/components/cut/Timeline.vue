<template>
  <div class="timeline-container">
    <div class="timeline-header">
      <span>时间轴</span>
      <div class="zoom-control">
        <label for="timelineZoom">缩放:</label>
        <input
          type="range"
          id="timelineZoom"
          :value="zoomLevel"
          @input="handleZoomChange"
          min="1"
          max="10"
          step="0.5"
        />
        <span>{{ zoomLevel }}x</span>
      </div>
      <span id="timeDisplay">{{ timeDisplay }}</span>
    </div>
    <div class="timeline-track-wrapper">
      <div class="timeline-track" ref="trackRef" @click="handleTrackClick">
        <canvas ref="waveformCanvas" class="waveform-canvas"></canvas>
        <!-- Render gaps -->
        <div
          v-for="gap in gaps"
          :key="'gap-' + gap.index"
          class="timeline-gap"
          :class="{ deleted: deletedGaps.has(gap.index) }"
          :style="{
            left: (gap.start / duration * 100) + '%',
            width: Math.max(0.3, ((gap.end - gap.start) / duration * 100)) + '%'
          }"
          :title="`间隙 ${formatTime(gap.duration)}`"
          @click.stop="handleGapClick(gap)"
        ></div>
        <!-- Render words -->
        <div
          v-for="(word, index) in words"
          :key="'word-' + index"
          class="timeline-word"
          :class="{ deleted: deletedWords.has(index) }"
          :style="{
            left: (word.start_time / duration * 100) + '%',
            width: Math.max(0.5, ((word.end_time - word.start_time) / duration * 100)) + '%'
          }"
          :title="word.text"
          @click.stop="handleWordClick(word)"
        ></div>
        <!-- Timeline cursor -->
        <div
          class="timeline-cursor"
          :style="{ left: (currentTime / duration * 100) + '%' }"
        ></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue';
import { useCutStore } from '../../stores/cut';

const cutStore = useCutStore();
const { words, gaps, deletedWords, deletedGaps, currentTime, duration } = cutStore;

const trackRef = ref(null);
const waveformCanvas = ref(null);
const zoomLevel = ref(1);

// Computed
const timeDisplay = computed(() => {
  return `${formatTime(currentTime.value)} / ${formatTime(duration.value)}`;
});

// Methods
function formatTime(seconds) {
  if (!seconds) return '00:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function handleZoomChange(event) {
  zoomLevel.value = parseFloat(event.target.value);
}

function handleTrackClick(event) {
  const rect = trackRef.value.getBoundingClientRect();
  const percent = (event.clientX - rect.left) / rect.width;
  const time = percent * duration.value;
  cutStore.setCurrentTime(time);
}

function handleGapClick(gap) {
  cutStore.setCurrentTime(gap.start);
}

function handleWordClick(word) {
  cutStore.setCurrentTime(word.start_time);
}

// Render waveform
function renderWaveform() {
  if (!waveformCanvas.value || !duration.value || words.value.length === 0) return;

  const canvas = waveformCanvas.value;
  const ctx = canvas.getContext('2d');
  const width = canvas.offsetWidth;
  const height = canvas.offsetHeight;

  // Set canvas resolution
  canvas.width = width * 2;
  canvas.height = height * 2;
  ctx.scale(2, 2);

  // Clear canvas
  ctx.fillStyle = '#1f1f1f';
  ctx.fillRect(0, 0, width, height);

  // Draw center line
  ctx.strokeStyle = '#2a2a2a';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, height / 2);
  ctx.lineTo(width, height / 2);
  ctx.stroke();

  // Create gradient for waveform
  const gradient = ctx.createLinearGradient(0, 0, 0, height);
  gradient.addColorStop(0, '#00d4ff');
  gradient.addColorStop(1, '#00b8e6');
  ctx.fillStyle = gradient;

  // Draw simulated waveform
  const barWidth = 2;
  const bars = Math.floor(width / barWidth);

  for (let i = 0; i < bars; i++) {
    const t = (i / bars) * duration.value;
    // Simulate amplitude based on word density
    let amplitude = 0.2 + Math.random() * 0.3;

    // Find if there's a word at this time
    const word = words.value.find(w => Math.abs((w.start_time + w.end_time) / 2 - t) < 0.5);
    if (word && !deletedWords.value.has(words.value.indexOf(word))) {
      amplitude = 0.6 + Math.random() * 0.3;
    }

    const barHeight = amplitude * height * 0.4;
    ctx.fillRect(
      i * barWidth,
      (height - barHeight) / 2,
      barWidth - 1,
      barHeight
    );
  }
}

// Watch for changes and re-render
watch([duration, words, deletedWords], () => {
  nextTick(() => {
    renderWaveform();
  });
});

onMounted(() => {
  renderWaveform();

  // Re-render on window resize
  window.addEventListener('resize', renderWaveform);
});
</script>

<script>
export default {
  name: 'Timeline'
};
</script>

<style scoped>
.timeline-container {
  height: 100px;
  background: var(--bg-secondary, #141414);
  border-top: 1px solid var(--border, #2a2a2a);
  display: flex;
  flex-direction: column;
}

:root {
  --bg-primary: #0a0a0a;
  --bg-secondary: #141414;
  --bg-tertiary: #1f1f1f;
  --text-secondary: #a0a0a0;
  --accent: #00d4ff;
  --accent-hover: #00b8e6;
  --danger: #ff4757;
  --warning: #ffa502;
  --border: #2a2a2a;
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  font-size: 12px;
  color: var(--text-secondary, #a0a0a0);
}

.zoom-control {
  display: flex;
  align-items: center;
  gap: 8px;
}

.zoom-control label {
  color: var(--text-secondary, #a0a0a0);
}

.zoom-control input[type="range"] {
  width: 100px;
  cursor: pointer;
}

.zoom-control span {
  color: var(--accent, #00d4ff);
  font-weight: 500;
  min-width: 30px;
  text-align: right;
}

.timeline-track-wrapper {
  flex: 1;
  padding: 0 16px 12px;
  position: relative;
}

.timeline-track {
  height: 100%;
  background: var(--bg-tertiary, #1f1f1f);
  border-radius: 6px;
  position: relative;
  overflow: hidden;
  cursor: pointer;
}

.waveform-canvas {
  width: 100%;
  height: 100%;
  position: absolute;
  top: 0;
  left: 0;
}

.timeline-word {
  position: absolute;
  top: 4px;
  height: 20px;
  background: var(--accent, #00d4ff);
  border-radius: 2px;
  min-width: 2px;
  cursor: pointer;
  transition: all 0.15s;
  z-index: 10;
}

.timeline-word:hover {
  background: var(--accent-hover, #00b8e6);
}

.timeline-word.deleted {
  background: var(--danger, #ff4757);
}

.timeline-gap {
  position: absolute;
  top: 4px;
  height: 20px;
  background: var(--warning, #ffa502);
  opacity: 0.6;
  cursor: pointer;
  z-index: 10;
  border-radius: 2px;
}

.timeline-gap:hover {
  opacity: 0.9;
  background: var(--accent, #00d4ff);
}

.timeline-gap.deleted {
  opacity: 0.2;
  background: var(--danger, #ff4757);
}

.timeline-cursor {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: white;
  pointer-events: none;
  z-index: 10;
}
</style>
