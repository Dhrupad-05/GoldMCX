import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev wiring: when VITE_API_BASE_URL is unset, `/api` requests fall back to the
// dev proxy so a fresh checkout talks to the backend with zero configuration.
const API_TARGET = process.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
      },
    },
  },
})
