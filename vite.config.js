import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'path';

export default defineConfig({
    plugins: [vue()],
    root: path.resolve(__dirname, 'static'),
    base: '/static/',
    resolve: {
        alias: {
            vue: 'vue/dist/vue.esm-bundler.js'
        }
    },
    build: {
        outDir: path.resolve(__dirname, 'static/dist'),
        emptyOutDir: true,
        manifest: true,
        rollupOptions: {
            input: {
                index: path.resolve(__dirname, 'static/js/src/index/main.js'),
                admin: path.resolve(__dirname, 'static/js/src/admin/main.js'),
            },
        },
    },
    server: {
        port: 3000,
        strictPort: true,
        proxy: {
            '/api': 'http://localhost:5000',
        },
    },
});