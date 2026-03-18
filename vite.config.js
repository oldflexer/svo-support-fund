import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'path';

export default defineConfig({
  plugins: [vue()],
  root: path.resolve(__dirname, 'static'), // указываем корневую папку для статики
  base: '/static/',
  build: {
    outDir: path.resolve(__dirname, 'static/dist'), // куда собирать
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: {
        admin: path.resolve(__dirname, 'static/js/admin.js'),
        index: path.resolve(__dirname, 'static/js/index.js'),
      },
    },
  },
  server: {
    port: 3000,
    strictPort: true,
    proxy: {
      '/api': 'http://localhost:5000', // прокси на Flask бэкенд
    },
  },
});