<template>
  <div class="home">
    <h2>技能列表</h2>
    <div class="skill-cards">
      <div class="card" v-for="skill in skills" :key="skill.name">
        <h3>{{ skill.name }}</h3>
        <p>路由：{{ skill.route }}</p>
        <p>状态：{{ skill.status }}</p>
        <router-link :to="skill.route" class="btn">打开</router-link>
      </div>
    </div>

    <div class="init-section">
      <h3>启动 Cut 剪辑服务</h3>
      <form @submit.prevent="startCut">
        <div class="form-group">
          <label>视频文件路径</label>
          <input v-model="cutForm.video" type="text" placeholder="/path/to/video.mp4" required />
        </div>
        <div class="form-group">
          <label>ASR JSON 文件 (可选)</label>
          <input v-model="cutForm.json" type="text" placeholder="/path/to/result.json" />
        </div>
        <button type="submit" class="btn primary" :disabled="cutLoading">
          {{ cutLoading ? '启动中...' : '启动剪辑服务' }}
        </button>
      </form>
      <div v-if="cutResult" class="result">
        <p>初始化成功！文件: {{ cutResult.filename }}</p>
        <button @click="openEditor" class="btn primary">打开编辑器</button>
      </div>
      <div v-if="cutError" class="error">{{ cutError }}</div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  data() {
    return {
      skills: [],
      cutForm: { video: '', json: '' },
      cutLoading: false,
      cutResult: null,
      cutError: null
    };
  },
  async mounted() {
    await this.fetchSkills();
  },
  methods: {
    async fetchSkills() {
      try {
        const res = await axios.get('/api/skills');
        this.skills = res.data.skills;
      } catch (e) {
        console.error('Failed to fetch skills:', e);
      }
    },
    async startCut() {
      this.cutLoading = true;
      this.cutError = null;
      this.cutResult = null;
      try {
        const res = await axios.post('/api/skill/cut/init', this.cutForm);
        this.cutResult = res.data;
        // 自动跳转到编辑页面，传递 file_id
        setTimeout(() => {
          if (res.data.file_id) {
            this.$router.push(`/skill/cut/editor?file_id=${res.data.file_id}`);
          } else {
            this.$router.push('/skill/cut/editor');
          }
        }, 1000);
      } catch (e) {
        this.cutError = e.response?.data?.error || e.message;
      } finally {
        this.cutLoading = false;
      }
    },
    openEditor() {
      this.$router.push('/skill/cut/editor');
    }
  }
};
</script>

<style scoped>
.home {
  max-width: 960px;
  margin: 0 auto;
}

h2 {
  font-size: 24px;
  margin-bottom: 24px;
}

.skill-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  margin-bottom: 40px;
}

.card {
  background: #141414;
  border: 1px solid #2a2a2a;
  border-radius: 12px;
  padding: 20px;
}

.card h3 {
  font-size: 18px;
  margin-bottom: 8px;
}

.card p {
  color: #a0a0a0;
  font-size: 14px;
  margin-bottom: 4px;
}

.card .btn {
  display: inline-block;
  margin-top: 12px;
  padding: 8px 16px;
  background: #00d4ff;
  color: #000;
  text-decoration: none;
  border-radius: 6px;
  font-weight: 500;
}

.init-section {
  background: #141414;
  border: 1px solid #2a2a2a;
  border-radius: 12px;
  padding: 24px;
}

.init-section h3 {
  font-size: 18px;
  margin-bottom: 16px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-size: 14px;
  color: #a0a0a0;
  margin-bottom: 6px;
}

.form-group input {
  width: 100%;
  padding: 10px 12px;
  background: #0a0a0a;
  border: 1px solid #2a2a2a;
  border-radius: 6px;
  color: #fff;
  font-size: 14px;
}

.form-group input:focus {
  outline: none;
  border-color: #00d4ff;
}

.btn {
  padding: 10px 20px;
  background: #1f1f1f;
  border: 1px solid #2a2a2a;
  color: #fff;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
}

.btn.primary {
  background: #00d4ff;
  color: #000;
  border: none;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.result {
  margin-top: 16px;
  padding: 12px;
  background: #1a3a2a;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}

.result p {
  margin: 0;
}

.result .url {
  color: #00d4ff;
  font-size: 12px;
}

.error {
  margin-top: 16px;
  padding: 12px;
  background: #3a1a1a;
  color: #ff6b6b;
  border-radius: 6px;
}
</style>
