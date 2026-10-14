# Vue RUM 验收工程

Vue 3 + Vue Router + Vite + TypeScript，包含两个页面、资源请求与可触发错误。

运行 `npm ci`，`npm run build`，`npm run preview`。正式 build 同时执行 vue-tsc 严格类型检查（skipLibCheck: false）和 Vite production build。

基础 RUM 使用 `.env.production` 的非密钥 Vite 变量。更换接收端或 appId 后重新 `npm run build`；版本和服务读取 package.json，环境读取 Vite 构建 mode。默认 session 采样保持 SDK 默认；Replay 采样设为 0 且不启动 Replay，不配置 Trace/Logs。

初始化通过共享 Promise 只运行一次。通常先完成初始化再挂载路由；SDK 失败或超过 1500ms 时应用仍挂载。

本地验收：`python3 scripts/run.py acceptance node scripts/acceptance.mjs`。需安装 Playwright 并设置 `PLAYWRIGHT_MODULE`，默认复用本机测试工具；`CHROME_PATH` 可覆盖 Chrome 路径。测试启动 localhost 模拟接收器，不代表真实 DataKit 或远端入库。
