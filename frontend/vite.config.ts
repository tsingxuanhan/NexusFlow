import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8900',
      '/upload': 'http://localhost:8900',
      '/agentos': 'http://localhost:8900',
      '/ws': { target: 'ws://localhost:8900', ws: true },
    },
  },
})
