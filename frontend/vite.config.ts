import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // Where the dev server forwards API calls. Docker Compose sets this to http://backend:8000.
  const backendTarget = env.BACKEND_PROXY_TARGET || 'http://localhost:8000'

  return {
    plugins: [react(), tailwindcss()],
    server: {
      host: true,
      port: 5173,
      strictPort: true,
      // Same-origin API calls in development: no CORS involved.
      proxy: {
        '/api': backendTarget,
        '/health': backendTarget,
      },
    },
  }
})
