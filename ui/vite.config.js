import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: resolve(__dirname, '../extension/sidepanel-dist'),
    rollupOptions: {
      input: resolve(__dirname, 'index.html'),
    },
    emptyOutDir: true,
  },
  base: './',
})
