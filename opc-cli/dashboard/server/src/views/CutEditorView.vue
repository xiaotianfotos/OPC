<template>
  <div class="cut-editor-view">
    <LoadingOverlay v-if="isLoading" :message="loadingMessage" />
    <div v-else-if="error" class="error-container">
      <p>{{ error }}</p>
      <button @click="goHome" class="btn primary">返回首页</button>
    </div>
    <CutEditor v-else-if="isReady" />
    <div v-else class="empty-state">
      <i class="fas fa-film"></i>
      <p>无视频数据</p>
      <button @click="goHome" class="btn primary">返回首页</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useCutStore } from '../stores/cut';
import CutEditor from '../components/cut/CutEditor.vue';
import LoadingOverlay from '../components/LoadingOverlay.vue';

const route = useRoute();
const router = useRouter();
const cutStore = useCutStore();

const isLoading = ref(false);
const loadingMessage = ref('');
const error = ref(null);
const isReady = ref(false);

// Check if we have file_id from route params or query
const fileId = computed(() => route.query.file_id || route.params.file_id);

onMounted(async () => {
  await initializeEditor();
});

async function initializeEditor() {
  if (fileId.value) {
    // Load from existing file_id
    await loadFromFile(fileId.value);
  } else {
    // Check if there's a running cut service
    await checkRunningService();
  }
}

async function loadFromFile(fileId) {
  isLoading.value = true;
  loadingMessage.value = '正在加载视频数据...';

  try {
    // Get file metadata from service
    const response = await fetch(`/api/skill/cut/file/${fileId}`);
    if (!response.ok) {
      throw new Error('Failed to load file');
    }

    const data = await response.json();

    if (data.success && data.file && data.file.asr_result) {
      // Initialize store with the file data
      cutStore.currentFile = {
        file_id: fileId,
        filename: data.file.filename || fileId,
        asr_result: data.file.asr_result
      };

      // Load words from ASR result
      cutStore.loadWordsFromASR(data.file.asr_result);

      isReady.value = true;
      console.log('[CutEditorView] File loaded:', fileId, 'Words:', cutStore.words.length);
    } else {
      throw new Error(data.error || 'Failed to load file');
    }
  } catch (err) {
    error.value = err.message || '加载失败';
    console.error('[CutEditorView] Load failed:', err);
  } finally {
    isLoading.value = false;
  }
}

async function checkRunningService() {
  isLoading.value = true;
  loadingMessage.value = '正在检查服务状态...';

  try {
    // Check if there's a file_id in query params first
    const queryParams = new URLSearchParams(window.location.search);
    const queryFileId = queryParams.get('file_id');

    if (queryFileId) {
      await loadFromFile(queryFileId);
      return;
    }

    // Otherwise check status for auto-loaded file
    const response = await fetch('/api/skill/cut/status');
    const data = await response.json();

    if (data.status === 'running' && data.file_id) {
      await loadFromFile(data.file_id);
    } else {
      isReady.value = false;
    }
  } catch (err) {
    error.value = '无法连接到服务';
    isReady.value = false;
  } finally {
    isLoading.value = false;
  }
}

function goHome() {
  router.push('/');
}

// Handle auto-file mode if no file_id
async function checkAutoFile() {
  try {
    const response = await fetch('/api/skill/cut/status');
    const data = await response.json();

    if (data.status === 'running' && data.file_id) {
      await loadFromFile(data.file_id);
    }
  } catch (err) {
    console.log('No auto-file configured');
  }
}
</script>

<script>
export default {
  name: 'CutEditorView',
  components: {
    CutEditor,
    LoadingOverlay
  }
};
</script>

<style scoped>
.cut-editor-view {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #0a0a0a;
  color: #ffffff;
}

.error-container,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 16px;
}

.error-container p {
  color: #ff6b6b;
  font-size: 14px;
}

.empty-state {
  color: #a0a0a0;
}

.empty-state i {
  font-size: 48px;
  margin-bottom: 8px;
}

.btn {
  padding: 10px 20px;
  background: #00d4ff;
  color: #000;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
}

.btn:hover {
  background: #00b8e6;
}

.btn.primary {
  background: #00d4ff;
  color: #000;
}
</style>
