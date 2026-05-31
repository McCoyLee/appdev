import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElIcons from '@element-plus/icons-vue'
import App from './App.vue'

const app = createApp(App)
app.use(createPinia())
app.use(ElementPlus)
for (const [name, comp] of Object.entries(ElIcons)) {
  app.component(name, comp)
}
app.mount('#app')

// PWA：注册 service worker（仅生产构建；dev 下没有 /sw.js 就跳过）
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((e) => {
      console.warn('SW 注册失败（不影响使用）：', e)
    })
  })
}
