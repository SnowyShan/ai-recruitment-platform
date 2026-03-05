import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import legacy from '@vitejs/plugin-legacy'
export default defineConfig({
  plugins: [
    react(),
    legacy({ targets: ['safari >= 13', 'ios >= 13'] }),
  ],
  build: {
    minify: false,
    rollupOptions: {
      output: {
        inlineDynamicImports: false,
        manualChunks: undefined,
      },
    },
  },
  server: {
    port: 5174,
    host: true,
    allowedHosts: ['all', '.trycloudflare.com'],
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      }
    }
  },
  preview: {
    port: 5174,
    host: true,
    allowedHosts: ['all', '.trycloudflare.com'],
  }
})
