import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Local backend address for live mode. Keep it on localhost: README section 10
// forbids exposing the unauthenticated API.
const apiTarget = process.env.ALETHEIA_API_URL ?? 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
