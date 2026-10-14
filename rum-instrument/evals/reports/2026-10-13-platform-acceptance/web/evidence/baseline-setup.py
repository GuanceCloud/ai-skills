from pathlib import Path
import json
r=Path('/private/tmp/rum-platform-acceptance/web')
files={
'package.json':json.dumps({'name':'vue-rum-acceptance','version':'1.2.3','private':True,'type':'module','scripts':{'dev':'vite','typecheck':'vue-tsc --noEmit','build':'vue-tsc --noEmit && vite build','preview':'vite preview --host 127.0.0.1 --port 19538'},'dependencies':{'vue':'3.5.22','vue-router':'4.5.1'},'devDependencies':{'vite':'7.1.9','@vitejs/plugin-vue':'6.0.1','typescript':'5.9.3','vue-tsc':'3.1.1','@types/node':'22.18.10'}},indent=2)+'\n',
'.gitignore':'node_modules/\ndist/\n.rum/\nevidence/\n.env*.local\n',
'index.html':'<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Vue RUM 验收</title></head><body><div id="app"></div><script type="module" src="/src/main.ts"></script></body></html>\n',
'vite.config.ts':"import { defineConfig } from 'vite'\nimport vue from '@vitejs/plugin-vue'\nimport pkg from './package.json'\nexport default defineConfig({ plugins: [vue()], define: { __APP_VERSION__: JSON.stringify(pkg.version), __APP_SERVICE__: JSON.stringify(pkg.name) } })\n",
 'tsconfig.json':json.dumps({'compilerOptions':{'target':'ES2022','useDefineForClassFields':True,'module':'ESNext','lib':['ES2022','DOM','DOM.Iterable'],'moduleResolution':'Bundler','resolveJsonModule':True,'isolatedModules':True,'verbatimModuleSyntax':True,'noEmit':True,'strict':True,'skipLibCheck':False,'types':['vite/client','node']},'include':['src/**/*.ts','src/**/*.vue','vite.config.ts']},indent=2)+'\n',
'src/env.d.ts':'/// <reference types="vite/client" />\ndeclare const __APP_VERSION__: string\ndeclare const __APP_SERVICE__: string\n',
'src/main.ts':"import { createApp } from 'vue'\nimport App from './App.vue'\nimport { router } from './router'\nwindow.addEventListener('error', () => { document.documentElement.dataset.appErrors = String(Number(document.documentElement.dataset.appErrors || '0') + 1) })\ncreateApp(App).use(router).mount('#app')\n",
'src/router.ts':"import { createRouter, createWebHistory } from 'vue-router'\nimport HomePage from './pages/HomePage.vue'\nimport DetailsPage from './pages/DetailsPage.vue'\nexport const router = createRouter({ history: createWebHistory(), routes: [{ path: '/', component: HomePage }, { path: '/details', component: DetailsPage }] })\n",
'src/App.vue':'<template><main><h1>Vue RUM 验收</h1><nav><RouterLink to="/">首页</RouterLink> · <RouterLink to="/details?page=2">详情</RouterLink></nav><RouterView /></main></template>\n<style>body{font-family:system-ui;margin:3rem;background:#f5f7fa;color:#24314a}main{max-width:760px;margin:auto;background:white;padding:2rem;border-radius:16px}button,input{padding:.7rem;margin:.5rem}nav{margin:1rem 0}</style>\n',
'src/pages/HomePage.vue':'''<script setup lang="ts">
import { ref } from 'vue'
const response = ref('尚未请求')
const draft = ref('')
async function loadResource() { const result = await fetch('/sample.json'); response.value = (await result.json()).message }
function triggerError() { setTimeout(() => { throw new Error('acceptance-unhandled-error') }, 0) }
</script>
<template><section><h2>首页</h2><label>本地草稿<input aria-label="本地草稿" v-model="draft"></label><button @click="loadResource">请求资源</button><output>{{ response }}</output><button @click="triggerError">触发错误</button></section></template>
''',
'src/pages/DetailsPage.vue':'<script setup lang="ts">\nimport { useRoute } from \'vue-router\'\nconst route = useRoute()\n</script>\n<template><section><h2>详情页</h2><p>当前页码：{{ route.query.page }}</p><img src="/mark.svg" alt="资源图标" width="48" height="48"></section></template>\n',
'public/sample.json':'{"message":"资源请求成功"}\n',
'public/mark.svg':'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><circle cx="24" cy="24" r="22" fill="#3275d4"/></svg>\n',
'README.md':'# Vue RUM 验收工程\n\nVue 3 + Vue Router + Vite + TypeScript，包含两个页面、资源请求与可触发错误。\n\n运行 `npm ci`，`npm run build`，`npm run preview`。正式 build 同时执行 vue-tsc 严格类型检查（skipLibCheck: false）和 Vite production build。\n',
'scripts/run.py':'''import subprocess,sys,json,os,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
label=sys.argv[1]; args=sys.argv[2:]
env=os.environ.copy();env['PATH']='/Users/oneandonly/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:'+env['PATH']
p=subprocess.run(args,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
(root/'evidence'/f'{label}.log').write_text(p.stdout)
with (root/'evidence/commands.jsonl').open('a') as f:f.write(json.dumps({'label':label,'argv':args,'exit_code':p.returncode,'time':time.time()})+'\\n')
print(p.stdout);sys.exit(p.returncode)
'''
}
for name,content in files.items():
 p=r/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
