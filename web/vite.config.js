import { defineConfig } from 'vite';
import preact from '@preact/preset-vite';

// The dev server proxies /api to the FastAPI backend (uvicorn on :8000),
// so the browser only ever talks to one origin — cookies and the PWA
// scope behave identically in dev and production, where FastAPI serves
// the built app itself (increment 10).
export default defineConfig({
  plugins: [preact()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  build: {
    outDir: 'dist',
  },
});
