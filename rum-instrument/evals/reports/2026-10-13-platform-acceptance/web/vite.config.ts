import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import pkg from './package.json'
export default defineConfig({ plugins: [vue()], define: { __APP_VERSION__: JSON.stringify(pkg.version), __APP_SERVICE__: JSON.stringify(pkg.name) } })
