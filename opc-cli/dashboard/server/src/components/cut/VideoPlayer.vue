<template>
  <div class="video-player">
    <div class="video-container">
      <div class="video-wrapper">
        <video
          v-if="videoUrl"
          ref="videoRef"
          :src="videoUrl"
          controls
          @loadedmetadata="handleLoadedMetadata"
          @timeupdate="handleTimeUpdate"
          @play="handlePlay"
          @pause="handlePause"
        ></video>
        <div v-else class="video-placeholder">
          <i class="fas fa-film"></i>
          <p>上传视频开始剪辑</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { useCutStore } from '../../stores/cut';

const cutStore = useCutStore();
// Use store state directly to maintain reactivity
const words = computed(() => cutStore.words);
const gaps = computed(() => cutStore.gaps);
const deletedWords = computed(() => cutStore.deletedWords);
const deletedGaps = computed(() => cutStore.deletedGaps);
const { currentFile, currentTime, currentWordIndex } = cutStore;

const videoRef = ref(null);
const isPlaying = ref(false);
const videoDuration = ref(0);
const skipCheckInterval = ref(null);

// Computed
const videoUrl = computed(() => cutStore.getVideoUrl());

// Watch current word index to scroll to it
watch(currentWordIndex, (newIndex) => {
  if (newIndex >= 0) {
    scrollToWord(newIndex);
  }
});

// Methods
function handleLoadedMetadata() {
  if (videoRef.value) {
    videoDuration.value = videoRef.value.duration;
  }
}

function handlePlay() {
  isPlaying.value = true;
  startSkipCheck();
}

function handlePause() {
  isPlaying.value = false;
  stopSkipCheck();
}

// Track last skip target to avoid infinite loops
let lastSkipTarget = -1;
let lastSkipCheckTime = 0;

function handleTimeUpdate() {
  if (videoRef.value) {
    const time = videoRef.value.currentTime;
    cutStore.setCurrentTime(time);
  }
}

// Use requestAnimationFrame for responsive skipping
function startSkipCheck() {
  stopSkipCheck(); // Clear any existing loop
  lastSkipTarget = -1; // Reset on start

  function check() {
    if (!videoRef.value || !isPlaying.value) {
      skipCheckInterval.value = null;
      return;
    }

    const time = videoRef.value.currentTime;
    skipDeletedSegments(time);
    skipCheckInterval.value = requestAnimationFrame(check);
  }

  skipCheckInterval.value = requestAnimationFrame(check);
}

function stopSkipCheck() {
  if (skipCheckInterval.value) {
    cancelAnimationFrame(skipCheckInterval.value);
    skipCheckInterval.value = null;
  }
}

function skipDeletedSegments(time) {
  // Avoid infinite loops: check at most once per 50ms
  const now = Date.now();
  if (now - lastSkipCheckTime < 50) return;
  lastSkipCheckTime = now;

  // Check if we recently skipped to this position (within 0.2s)
  if (lastSkipTarget > 0 && Math.abs(time - lastSkipTarget) < 0.2) {
    return;
  }

  // Check if we're in a deleted gap
  const currentGap = gaps.value.find(g =>
    time >= g.start && time <= g.end
  );

  if (currentGap && deletedGaps.value.has(currentGap.index)) {
    // Skip to the word after this gap
    const nextWordIdx = currentGap.beforeWord;
    if (nextWordIdx < words.value.length) {
      const targetTime = words.value[nextWordIdx].start_time;
      lastSkipTarget = targetTime;
      seekTo(targetTime);
    }
    return;
  }

  // Find which word we're currently in
  const currentWordIdx = words.value.findIndex(w =>
    time >= w.start_time && time <= w.end_time
  );

  // If we're in a deleted word, skip to the next kept word
  if (currentWordIdx !== -1 && deletedWords.value.has(currentWordIdx)) {
    skipToNextKeptWord(currentWordIdx, time);
  }
}

function skipToNextKeptWord(fromIndex, currentTime) {
  // Check if we recently skipped (within 0.2s of target)
  if (lastSkipTarget > 0 && Math.abs(currentTime - lastSkipTarget) < 0.2) {
    return;
  }

  // Find the next kept word after fromIndex
  let nextKeptIndex = -1;
  for (let i = fromIndex + 1; i < words.value.length; i++) {
    if (!deletedWords.value.has(i)) {
      nextKeptIndex = i;
      break;
    }
  }

  if (nextKeptIndex !== -1) {
    const targetTime = words.value[nextKeptIndex].start_time;
    lastSkipTarget = targetTime;
    seekTo(targetTime);
  } else {
    // No more kept words, pause the video
    videoRef.value?.pause();
  }
}

function seekTo(time) {
  if (videoRef.value) {
    videoRef.value.currentTime = time;
    // Force play after seek
    videoRef.value.play().catch(e => console.error('[VideoPlayer] Play failed:', e));
  }
}

function scrollToWord(index) {
  // Find the word element and scroll into view
  const wordEl = document.querySelector(`.word[data-index="${index}"]`);
  if (wordEl) {
    wordEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

function play() {
  videoRef.value?.play();
}

function pause() {
  videoRef.value?.pause();
}

// Expose methods
defineExpose({
  seekTo,
  play,
  pause
});

// Emit seek events
const emit = defineEmits(['wordChange']);

// Auto-scroll to current word
watch(currentWordIndex, (newIndex) => {
  emit('wordChange', newIndex);
});

// Cleanup on unmount
onUnmounted(() => {
  stopSkipCheck();
});
</script>

<script>
export default {
  name: 'VideoPlayer'
};
</script>

<style scoped>
.video-player {
  flex: 1;
  background: var(--bg-primary, #0a0a0a);
  display: flex;
  flex-direction: column;
}

:root {
  --bg-primary: #0a0a0a;
  --bg-secondary: #141414;
  --bg-tertiary: #1f1f1f;
  --text-secondary: #a0a0a0;
  --accent: #00d4ff;
}

.video-container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: #000;
}

.video-wrapper {
  position: relative;
  width: 100%;
  max-width: 720px;
  aspect-ratio: 16/9;
  background: var(--bg-secondary, #141414);
  border-radius: 8px;
  overflow: hidden;
}

video {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.video-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary, #a0a0a0);
  gap: 12px;
}

.video-placeholder i {
  font-size: 48px;
}
</style>
