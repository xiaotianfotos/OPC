<template>
  <div class="cut-editor">
    <div class="editor-header">
      <h2>智能剪辑</h2>
      <span class="status" :class="status">{{ statusText }}</span>
    </div>

    <div class="editor-frame" v-if="status === 'running' && serverUrl">
      <iframe ref="iframe" :src="serverUrl" frameborder="0" class="iframe"></iframe>
    </div>
    <div class="editor-frame" v-else>
      <div class="loading">
        <p>{{ statusMessage }}</p>
        <button @click="checkStatus" class="btn">刷新状态</button>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  data() {
    return {
      serverUrl: null,
      status: 'idle',
      pollingInterval: null
    };
  },
  computed: {
    statusMessage() {
      if (this.status === 'idle') return '服务未启动，请先在首页启动剪辑服务';
      if (this.status === 'starting') return '服务启动中...';
      if (this.status === 'error') return '服务启动失败';
      return '正在连接...';
    },
    statusText() {
      if (this.status === 'running') return '运行中';
      if (this.status === 'idle') return '未启动';
      if (this.status === 'starting') return '启动中';
      if (this.status === 'error') return '错误';
      return this.status;
    }
  },
  mounted() {
    this.checkStatus();
    this.pollingInterval = setInterval(this.checkStatus, 3000);
  },
  beforeUnmount() {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
    }
  },
  methods: {
    async checkStatus() {
      try {
        const res = await axios.get('/api/skill/cut/status');
        this.status = res.data.status;
        this.serverUrl = res.data.serverUrl;
      } catch (e) {
        console.error('Failed to fetch status:', e);
      }
    }
  }
};
</script>

<style scoped>
.cut-editor {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.editor-header {
  height: 40px;
  background: #141414;
  border-bottom: 1px solid #2a2a2a;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 24px;
  gap: 12px;
  position: relative;
}

.editor-header h2 {
  font-size: 14px;
  font-weight: 500;
}

.status {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 4px;
  background: #2a2a2a;
  color: #a0a0a0;
}

.status.running {
  background: #1a3a2a;
  color: #2ed573;
}

.status.error {
  background: #3a1a1a;
  color: #ff6b6b;
}

.editor-frame {
  flex: 1;
  background: #141414;
  overflow: hidden;
}

.iframe {
  width: 100%;
  height: 100%;
  border: none;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 16px;
}

.loading p {
  color: #a0a0a0;
  font-size: 14px;
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
</style>
