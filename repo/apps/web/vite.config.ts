import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

const apiProxyTarget = process.env.HH_WEB_API_PROXY_TARGET

const apiProxy = apiProxyTarget
  ? {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    }
  : undefined

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    allowedHosts: true,
    proxy: apiProxy,
  },
  preview: {
    host: true,
    port: 5173,
    proxy: apiProxy,
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
