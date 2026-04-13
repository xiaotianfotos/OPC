import { createApp } from 'vue';
import { createPinia } from 'pinia';
import { createRouter, createWebHistory } from 'vue-router';
import App from './App.vue';
import Landing from './views/Landing.vue';
import Docs from './views/Docs.vue';
import Home from './views/Home.vue';
import CutEditor from './views/CutEditor.vue';
import CutEditorView from './views/CutEditorView.vue';

const routes = [
  { path: '/', name: 'Landing', component: Landing },
  { path: '/docs', name: 'Docs', component: Docs },
  { path: '/dashboard', name: 'Home', component: Home },
  { path: '/skill/cut', name: 'Cut', component: CutEditor },
  { path: '/skill/cut/editor', name: 'CutEditor', component: CutEditorView },
  { path: '/skill/cut/editor/:fileId', name: 'CutEditorFile', component: CutEditorView }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

const pinia = createPinia();
const app = createApp(App);
app.use(pinia);
app.use(router);
app.mount('#app');
