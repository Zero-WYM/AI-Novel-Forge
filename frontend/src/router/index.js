import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'
import OutlineView from '../views/OutlineView.vue'
import ChapterView from '../views/ChapterView.vue'
import CharactersView from '../views/CharactersView.vue'
import WorldView from '../views/WorldView.vue'
import RAGDebugView from '../views/RAGDebugView.vue'
export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: DashboardView },
    { path: '/outline', component: OutlineView },
    { path: '/chapter', component: ChapterView },
    { path: '/characters', component: CharactersView },
    { path: '/world', component: WorldView },
    { path: '/rag', component: RAGDebugView },
  ],
})
