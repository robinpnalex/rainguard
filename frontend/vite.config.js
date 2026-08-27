import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dashboard talks to the FastAPI backend through a dev proxy, so the
// browser only ever sees one origin. No CORS, and the /images/... URLs the
// API returns work unchanged.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/images': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
