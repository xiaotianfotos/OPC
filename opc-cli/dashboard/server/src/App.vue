<template>
  <div id="app">
    <nav class="nav" v-if="showNav">
      <h1 class="logo">OPC</h1>
      <div class="nav-links">
        <router-link to="/dashboard">首页</router-link>
      </div>
    </nav>
    <main class="main" :class="{ 'full-height': isEditor, 'no-padding': isFullPage }">
      <router-view />
    </main>
  </div>
</template>

<script>
export default {
  computed: {
    isEditor() {
      return this.$route.path.includes('/editor');
    },
    isFullPage() {
      const path = this.$route.path;
      return path === '/' || path === '/docs';
    },
    showNav() {
      const path = this.$route.path;
      return path !== '/' && path !== '/docs';
    }
  }
};
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #0a0a0a;
  color: #ffffff;
}

#app {
  min-height: 100vh;
}

.nav {
  height: 40px;
  background: #141414;
  border-bottom: 1px solid #2a2a2a;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 24px;
  position: relative;
}

.nav .logo {
  font-size: 14px;
  font-weight: 600;
  position: absolute;
  left: 24px;
}

.nav-links {
  display: flex;
  gap: 8px;
}

.nav-links a {
  color: #a0a0a0;
  text-decoration: none;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 13px;
  transition: all 0.15s;
}

.nav-links a:hover {
  background: #1f1f1f;
  color: #fff;
}

.nav-links a.router-link-active {
  background: #00d4ff;
  color: #000;
}

.main {
  padding: 24px;
}

.main.full-height {
  padding: 0;
  height: calc(100vh - 40px);
}

.main.no-padding {
  padding: 0;
  overflow: visible;
}
</style>
