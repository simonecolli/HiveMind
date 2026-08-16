import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss()
  ],
  server: {
    // Keeps the API on the same origin as the app: no CORS, and SSE with no
    // friction. The container image does the same job with nginx.
    proxy: {
      '/api': {
        target: process.env.HIVEMIND_API_URL ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
