import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    // === 新增以下完整的 proxy 配置 ===
    proxy: {
      '/api': {
        target: 'http://backend:8000', // Docker 环境用服务名 'backend'；本机裸跑前端时改成 http://localhost:8000
        changeOrigin: true,
        // 一键成书等重活会跑几分钟（多次 LLM 串行），proxy 超时必须长于客户端 axios timeout
        timeout: 600000,       // 10 分钟（proxy 层：Vite dev server → 后端）
        proxyTimeout: 600000   // 10 分钟（底层 socket 超时）
        // 注意：后端路由本身带 /api 前缀（如 /api/novel/create）。
        // 这里【不要】 rewrite 掉 /api，否则转发到后端会变成 /novel/create 而 404。
      }
    }
  }
})