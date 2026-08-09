import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/stream': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
      '/zones': 'http://localhost:8000',
      '/events': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
