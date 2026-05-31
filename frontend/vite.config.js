import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    // 把体积最大的 element-plus 和 vue 全家桶拆成独立 vendor chunk：
    // 业务代码改动频繁、vendor 很少变，拆开后用户回访能命中浏览器缓存，
    // 也让首屏 JS 能并行下载（配合 M4-2 的 PWA/移动端）。
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('element-plus') || id.includes('@element-plus')) return 'element-plus'
            if (id.includes('/vue/') || id.includes('/@vue/') || id.includes('vue-router') || id.includes('pinia')) return 'vue-vendor'
            return 'vendor'
          }
        },
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8901', changeOrigin: true },
      '/healthz': { target: 'http://127.0.0.1:8901', changeOrigin: true },
    },
  },
})
