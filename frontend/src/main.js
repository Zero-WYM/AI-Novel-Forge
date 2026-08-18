import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia).use(router).use(ElementPlus)
for (const [key, comp] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, comp)
}
app.mount('#app')
