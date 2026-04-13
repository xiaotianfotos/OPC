/**
 * Cut Video Editor Pinia Store
 *
 * Manages state for the Cut video editing feature
 * - Word and gap management
 * - Selection and deletion
 * - Video playback
 * - Export functionality
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import * as cutApi from '../api/cut';

export const useCutStore = defineStore('cut', () => {
  // State
  const words = ref([]);
  const gaps = ref([]);
  const deletedWords = ref(new Set());
  const deletedGaps = ref(new Set());
  const selectedWords = ref(new Set());
  const selectedGaps = ref(new Set());
  const currentFile = ref(null);
  const config = ref({
    gapThreshold: 0.5,
    energyThreshold: 0.7,
    searchRange: 100
  });
  const isPlaying = ref(false);
  const currentTime = ref(0);
  const duration = ref(0);
  const currentWordIndex = ref(-1);
  const isLoading = ref(false);
  const error = ref(null);

  // Computed
  const totalWords = computed(() => words.value.length);
  const deletedWordCount = computed(() => deletedWords.value.size);
  const deletedGapCount = computed(() => deletedGaps.value.size);
  const keptWords = computed(() => totalWords.value - deletedWordCount.value);
  const hasSelection = computed(() => selectedWords.value.size > 0 || selectedGaps.value.size > 0);

  const totalGapDuration = computed(() => {
    return gaps.value.reduce((sum, g) => sum + g.duration, 0);
  });

  const deletedGapDuration = computed(() => {
    return gaps.value
      .filter(g => deletedGaps.value.has(g.index))
      .reduce((sum, g) => sum + g.duration, 0);
  });

  /**
   * Initialize from video upload with ASR
   */
  async function initFromUpload(formData) {
    isLoading.value = true;
    error.value = null;
    try {
      const result = await cutApi.uploadVideo(formData);
      currentFile.value = {
        file_id: result.file_id,
        filename: result.filename,
        asr_result: result.asr_result
      };
      loadWordsFromASR(result.asr_result);
      return result;
    } catch (err) {
      error.value = err.message || 'Upload failed';
      throw err;
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Initialize with existing ASR JSON
   */
  async function initFromJson(params) {
    isLoading.value = true;
    error.value = null;
    try {
      const result = await cutApi.initCut(params);
      return result;
    } catch (err) {
      error.value = err.message || 'Init failed';
      throw err;
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Load metadata from server
   */
  async function loadMetadata(fileId) {
    try {
      const result = await cutApi.getMetadata(fileId);
      if (result.success && result.metadata) {
        // Load saved state
        if (result.metadata.deletedWords) {
          deletedWords.value = new Set(result.metadata.deletedWords);
        }
        if (result.metadata.deletedGaps) {
          deletedGaps.value = new Set(result.metadata.deletedGaps);
        }
        if (result.metadata.config) {
          config.value = { ...config.value, ...result.metadata.config };
        }
      }
      return result;
    } catch (err) {
      console.error('Failed to load metadata:', err);
    }
  }

  /**
   * Save current metadata to server
   */
  async function saveMetadata() {
    if (!currentFile.value) return;
    try {
      await cutApi.saveMetadata(currentFile.value.file_id, {
        deletedWords: Array.from(deletedWords.value),
        deletedGaps: Array.from(deletedGaps.value),
        config: config.value
      });
    } catch (err) {
      console.error('Failed to save metadata:', err);
    }
  }

  /**
   * Load words and detect gaps from ASR result
   */
  function loadWordsFromASR(asrResult) {
    // Merge words from all segments into a flat array
    if (asrResult.segments && asrResult.segments.length > 0) {
      words.value = asrResult.segments.flatMap(seg => seg.words || []);
    } else if (asrResult.words) {
      words.value = asrResult.words;
    } else {
      words.value = [];
    }
    if (asrResult.duration) {
      duration.value = asrResult.duration;
    }
    detectGaps();
    deletedWords.value.clear();
    deletedGaps.value.clear();
    selectedWords.value.clear();
    selectedGaps.value.clear();
  }

  /**
   * Detect silence gaps between words based on threshold
   */
  function detectGaps() {
    const detectedGaps = [];
    const threshold = config.value.gapThreshold;

    for (let i = 0; i < words.value.length - 1; i++) {
      const currentEnd = words.value[i].end_time;
      const nextStart = words.value[i + 1].start_time;
      const gapDuration = nextStart - currentEnd;

      if (gapDuration >= threshold) {
        detectedGaps.push({
          index: i,
          start: currentEnd,
          end: nextStart,
          duration: gapDuration,
          afterWord: i,
          beforeWord: i + 1
        });
      }
    }

    gaps.value = detectedGaps;
  }

  /**
   * Select a range of words (no auto-expansion, just the exact range)
   */
  function selectWordRange(startIdx, endIdx) {
    const min = Math.min(startIdx, endIdx);
    const max = Math.max(startIdx, endIdx);

    // Clear previous selection and set new range (exact range, no auto-expansion)
    selectedWords.value.clear();
    selectedGaps.value.clear();
    for (let i = min; i <= max; i++) {
      selectedWords.value.add(i);
    }

    // Also select gaps within the range
    for (let i = min; i < max; i++) {
      const gapAfter = gaps.value.find(g => g.afterWord === i && g.beforeWord <= max);
      if (gapAfter) {
        selectedGaps.value.add(gapAfter.index);
      }
    }
  }

  /**
   * Toggle word selection (with shift/meta support)
   */
  function toggleWordSelection(index, shiftKey, metaKey, ctrlKey) {
    if (!shiftKey && !metaKey && !ctrlKey) {
      selectedWords.value.clear();
      selectedGaps.value.clear();
    }
    selectedWords.value.add(index);
  }

  /**
   * Toggle gap selection
   */
  function toggleGapSelection(gapIndex, shiftKey, metaKey, ctrlKey) {
    if (!shiftKey && !metaKey && !ctrlKey) {
      selectedWords.value.clear();
      selectedGaps.value.clear();
    }
    selectedGaps.value.add(gapIndex);
  }

  /**
   * Delete selected words and gaps
   */
  function deleteSelected() {
    selectedWords.value.forEach(index => {
      deletedWords.value.add(index);
    });
    selectedGaps.value.forEach(gapIndex => {
      deletedGaps.value.add(gapIndex);
    });
    selectedWords.value.clear();
    selectedGaps.value.clear();

    // Recalculate gaps after word deletion
    detectGaps();
    // Clear deletedGaps that no longer exist
    const validGapIndices = new Set(gaps.value.map(g => g.index));
    deletedGaps.value = new Set([...deletedGaps.value].filter(i => validGapIndices.has(i)));
  }

  /**
   * Restore selected words and gaps
   */
  function restoreSelected() {
    selectedWords.value.forEach(index => {
      deletedWords.value.delete(index);
    });
    selectedGaps.value.forEach(gapIndex => {
      deletedGaps.value.delete(gapIndex);
    });
    selectedWords.value.clear();
    selectedGaps.value.clear();

    // Recalculate gaps after word restoration
    detectGaps();
  }

  /**
   * Toggle delete state of a single word
   */
  function toggleDeleteWord(index) {
    if (deletedWords.value.has(index)) {
      deletedWords.value.delete(index);
    } else {
      deletedWords.value.add(index);
    }
    detectGaps();
  }

  /**
   * Toggle delete state of a single gap
   */
  function toggleDeleteGap(gapIndex) {
    if (deletedGaps.value.has(gapIndex)) {
      deletedGaps.value.delete(gapIndex);
    } else {
      deletedGaps.value.add(gapIndex);
    }
  }

  /**
   * Clear all deleted items permanently
   */
  function clearDeleted() {
    // Filter out deleted words
    words.value = words.value.filter((_, i) => !deletedWords.value.has(i));
    // Recalculate gaps after filtering
    detectGaps();
    deletedWords.value.clear();
    deletedGaps.value.clear();
    selectedWords.value.clear();
    selectedGaps.value.clear();
  }

  /**
   * Clear selection
   */
  function clearSelection() {
    selectedWords.value.clear();
    selectedGaps.value.clear();
  }

  /**
   * Find energy valley at boundary for smooth cuts
   */
  async function findValley(startTime, endTime) {
    if (!currentFile.value) {
      throw new Error('No file loaded');
    }

    try {
      const result = await cutApi.findValley({
        file_id: currentFile.value.file_id,
        start_time: startTime,
        end_time: endTime,
        energy_threshold: config.value.energyThreshold,
        search_ms: config.value.searchRange
      });
      return result.valley_time;
    } catch (err) {
      console.error('Failed to find valley:', err);
      return null;
    }
  }

  /**
   * Build cut ranges from kept words.
   * Groups contiguous kept words into segments.
   * Deleted words split the video into N+1 segments.
   */
  function buildCutRanges() {
    // If selected words exist, export only those as one segment
    if (selectedWords.value.size > 0) {
      const selected = words.value
        .map((w, i) => ({ ...w, index: i }))
        .filter(w => selectedWords.value.has(w.index));
      if (selected.length === 0) return [];
      return [{
        start: selected[0].start_time,
        end: selected[selected.length - 1].end_time
      }];
    }

    // Find contiguous groups of kept words by original index
    const allWords = words.value.map((w, i) => ({ ...w, index: i }));
    const cuts = [];
    let segStart = null;

    for (let i = 0; i < allWords.length; i++) {
      const kept = !deletedWords.value.has(allWords[i].index);
      if (kept) {
        if (segStart === null) segStart = i;
      } else {
        if (segStart !== null) {
          cuts.push({
            start: allWords[segStart].start_time,
            end: allWords[i - 1].end_time
          });
          segStart = null;
        }
      }
    }
    // Trailing kept group
    if (segStart !== null) {
      cuts.push({
        start: allWords[segStart].start_time,
        end: allWords[allWords.length - 1].end_time
      });
    }

    console.log('[Cut Store] buildCutRanges:', JSON.stringify(cuts), 'deletedWords:', [...deletedWords.value]);
    return cuts;
  }

  /**
   * Export video with current cut ranges
   * @param {Object} options - Export options
   * @param {boolean} options.applyValleyCorrection - Apply energy valley correction (default: false for speed)
   * @param {number} options.energyThreshold - Energy threshold for valley detection
   * @param {number} options.searchMs - Search range in milliseconds
   */
  async function exportVideo(options = {}) {
    if (!currentFile.value) {
      throw new Error('No file loaded');
    }

    const cuts = buildCutRanges();
    if (cuts.length === 0) {
      throw new Error('No words selected or all deleted');
    }

    try {
      const result = await cutApi.exportVideo({
        file_id: currentFile.value.file_id,
        cuts: cuts,
        format: 'mp4',
        apply_valley_correction: options.applyValleyCorrection || false,
        energy_threshold: options.energyThreshold || config.value.energyThreshold,
        search_ms: options.searchMs || config.value.searchRange
      });
      return result;
    } catch (err) {
      error.value = err.message || 'Export failed';
      throw err;
    }
  }

  /**
   * Update video playback time
   */
  function setCurrentTime(time) {
    currentTime.value = time;
    updateCurrentWordIndex();
  }

  /**
   * Update current word index based on time
   */
  function updateCurrentWordIndex() {
    const newIndex = words.value.findIndex(w =>
      currentTime.value >= w.start_time && currentTime.value <= w.end_time
    );
    currentWordIndex.value = newIndex;
  }

  /**
   * Get video URL for playback
   */
  function getVideoUrl() {
    if (!currentFile.value) return null;
    return cutApi.getVideoUrl(currentFile.value.file_id);
  }

  /**
   * Update config value
   */
  function updateConfig(key, value) {
    config.value[key] = value;
    if (key === 'gapThreshold') {
      detectGaps();
    }
    saveMetadata();
  }

  /**
   * Reset store to initial state
   */
  function reset() {
    words.value = [];
    gaps.value = [];
    deletedWords.value.clear();
    deletedGaps.value.clear();
    selectedWords.value.clear();
    selectedGaps.value.clear();
    currentFile.value = null;
    isPlaying.value = false;
    currentTime.value = 0;
    duration.value = 0;
    currentWordIndex.value = -1;
    error.value = null;
  }

  return {
    // State
    words,
    gaps,
    deletedWords,
    deletedGaps,
    selectedWords,
    selectedGaps,
    currentFile,
    config,
    isPlaying,
    currentTime,
    duration,
    currentWordIndex,
    isLoading,
    error,

    // Computed
    totalWords,
    deletedWordCount,
    deletedGapCount,
    keptWords,
    hasSelection,
    totalGapDuration,
    deletedGapDuration,

    // Actions
    initFromUpload,
    initFromJson,
    loadMetadata,
    saveMetadata,
    selectWordRange,
    toggleWordSelection,
    toggleGapSelection,
    deleteSelected,
    restoreSelected,
    toggleDeleteWord,
    toggleDeleteGap,
    clearDeleted,
    clearSelection,
    findValley,
    buildCutRanges,
    exportVideo,
    setCurrentTime,
    updateCurrentWordIndex,
    getVideoUrl,
    updateConfig,
    loadWordsFromASR,
    reset
  };
});
