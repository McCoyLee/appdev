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
