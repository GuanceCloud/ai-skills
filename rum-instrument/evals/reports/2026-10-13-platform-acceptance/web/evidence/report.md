# 完整 Vue Web 基础 RUM forward-test

结果：完整 Vue 工程、公开依赖干净安装、严格类型检查、正式 production 构建及真实 Chrome 验收全部通过。当前只证明 localhost 模拟接收器收到真实 SDK 数据，不证明真实 DataKit 配置或远端入库。

## 验收工程

- 路径：`/private/tmp/rum-platform-acceptance/web`。
- 隔离基线 commit：`db9ef5a8ab3de741bdb2ecc2cf948f022475c8cd`；分支 `codex/vue-rum-acceptance`；无 remote、无 push。
- 未接入基线包含 package.json、公开 npm package-lock.json、index.html、App.vue、main.ts、两个 Router 页面、资源 JSON/SVG、错误按钮、完整 tsconfig 与 Vite 配置；基线正式构建成功。
- Vue 3.5.22、Vue Router 4.5.1、Vite 7.1.9、官方 Vue 插件 6.0.1、TypeScript 5.9.3、vue-tsc 3.1.1。Node 24.19.0，独立 npm 11.6.2。
- SDK：真实公开 npm `@cloudcare/browser-rum@3.3.21`，其 core/worker 同为 3.3.21；未修改 SDK 源码、声明或 node_modules。
- `npm run build` 实际执行 `vue-tsc --noEmit && vite build`；strict:true、skipLibCheck:false，未添加 ambient any 或声明补丁。

## 按 Skill 执行

模拟请求保存在 `simulated-user-request.txt`，使用最新主仓库 Skill 与 common/execution/contracts/privacy-security/web/validation 引用。

首次检测确认一个 Web 目标、一个 application ID 槽位，基线无 RUM。`first-plan.json` 是未经修订的首次计划；第一次结构验证明确失败，原因是 dependency decision 缺 owner、compatibility、official_sources、verified_at。原失败日志保留，没有把失败改写为通过。补齐事实后 `validated-plan.json` 通过 plan 和 implement 校验，之后才修改应用代码。

接入 `.env.production` 中的 `VITE_RUM_APP_ID=eval_vue_acceptance`、`VITE_RUM_DATAKIT_URL=http://127.0.0.1:19539`，构建时实际消费。service/version 来自 package.json，env 来自 Vite mode。未进行凭据交换、远程控制台修改、Replay 或 Trace 接入。

应用先尝试初始化，再挂载 Vue Router；共享 Promise 防止重复调用。SDK 加载异常输出通用警告，1500ms 超时允许应用启动。保留原应用 error listener。SDK 会话采样保持默认，Replay 采样为零且未启动录制。

## 真实浏览器结果

真实本机 Google Chrome headless 运行 `dist` 产物，localhost HTTP 接收器捕获 SDK 请求。验收脚本 `scripts/acceptance.mjs` 的每个必需断言聚合到 exit code，最终结果见 `browser-results.json`（16/16）。

- Vue 正常挂载；SDK `getInitConfiguration` 中 applicationId、datakitOrigin、service、version、env 与来源一致。
- Chrome 原生精确覆盖率显示初始化内部块执行 1 次；导出初始化函数总调用 4 次，额外 SDK init 调用为 0。证据 `rum-coverage.json`。
- `/` → `/details?page=2` → `/` SPA 导航正常，资源 JSON 成功，实际 Error 事件含测试错误，原应用错误处理器继续执行。
- 捕获非空真实 View、Resource、Error line protocol，详见 `payloads.json`；记录断言使用 measurement 行前缀，避免普通字符串命中冒充事件。
- 无害 `page=2` 正常保留。组件内本地草稿 canary 未被自定义采集；未强行把普通 URL 参数解释为隐私故障。
- 未开启 Replay/Trace；业务请求无 trace header。
- 中断 SDK chunk 与持续挂起 SDK chunk 两种故障下，应用可启动、资源请求成功、原错误处理器继续运行。
- 第二次 detector 识别既有 SDK/init；重复接入审计保留现有有效集成，文件哈希前后一致，无重复依赖、初始化或 CDN 注入。`reintegration-audit.json`。

## 官方兼容性证据

[Vue TypeScript 官方指南](https://vuejs.org/guide/typescript/overview.html) 要求以 vue-tsc 检查 SFC，Vite 转译不能代替类型检查。[Vite 指南](https://vite.dev/guide/) 提供 Vue TS 工程模板及 Node 要求。所选 Vite 和官方 Vue 插件的确切 npm engines/peerDependencies 结果另存 `compatibility-metadata.log`、`compatibility-plugin.log`，选择满足其兼容范围。

[观测云 Web 接入指南](https://docs.guance.com/real-user-monitoring/web/app-access/) 核对 NPM API 和 DataKit 字段；`sdk-metadata.log` 核对所选发布版本与完整性。完整来源映射见 `official-compatibility.json`。

## 复现

使用符合 Vite engines 的现代 Node 和 npm：

```sh
cd /private/tmp/rum-platform-acceptance/web
npm ci --registry=https://registry.npmjs.org
npm run build
npm run preview
```

浏览器验收需本机 Chrome 与 Playwright；脚本支持 `CHROME_PATH` 和 `PLAYWRIGHT_MODULE`，后者指向 Playwright 的 index.mjs：

```sh
node scripts/acceptance.mjs
```

该脚本自行监听 19538/19539，执行前停止 preview，避免端口冲突。未依赖真实账号或远端服务。替换 `.env.production` 中配置后重新 build，即可消费新接收端。

## 文件与限制

- `commands.jsonl`：必要命令、argv、exit code；对应日志记录安装、构建、校验和浏览器结果。
- `source.patch`：相对未接入基线的源码/依赖/README/测试脚本 patch。
- `.rum/plan.json`、首次计划、已校验计划、完整项目和 lockfile 均保留。
- 初始系统 npm 7 报 Rollup engines 警告，之后切换隔离 npm 11.6.2，基线与接入后的独立 npm ci、正式构建均成功；保留原日志。
- 使用 TypeScript 5.9.3 验收完整 Vue 工程；没有声称此 Vue 组合在 TS 7 上通过。
- SDK 延迟初始化超过 1500ms 的情况下，最早期事件可能丢失；应用启动优先且明确记录此限制。
- 尚未验证用户后来提供的真实接收端；本任务未访问它。远程验证为 false。
- 未修改主仓库、用户安装 Skill 或 SDK 源码。
