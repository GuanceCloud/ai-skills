# Guance Browser RUM SDK 严格类型复测

结论：既有 3.3.5 组合确有 SDK 声明错误；升级到官方同主版本最新 3.3.21 后，相同最小配置通过完整严格类型检查。

| browser-rum | browser-core | browser-worker | TypeScript | tsc 退出码 |
|---|---|---|---|---|
| 3.3.5 | 3.3.4 | 3.3.4 | 7.0.2 | 1 |
| 3.3.21 | 3.3.21 | 3.3.21 | 7.0.2 | 0 |

Node 为 v24.19.0。查询公开官方 npm registry（https://registry.npmjs.org），latest 与 3.x 最新均为 3.3.21。registry.json 保留完整查询结果。

## 验证边界

- 仅在此临时目录安装公开 npm SDK；未修改主仓库、本机 Skill 或 node_modules 声明。
- 两个版本的 src.ts 和 tsconfig.json 完全相同。
- 最小 init 使用 applicationId 和 datakitOrigin，均由 SDK 的 RumInitConfiguration 声明支持。
- strict: true、skipLibCheck: false、noEmit: true，没有 any 强制转换、声明补丁或错误忽略。
- TypeScript 只检查源码，没有执行 SDK，没有上报，没有真实账号或凭据；域名为保留测试域 example.invalid。
- 结果仅证明该版本组合的最小初始化可完成严格类型检查；不单独证明浏览器运行与数据接收效果。

## 旧版本真实错误

```text
node_modules/@cloudcare/browser-core/types/index.d.ts(2,16): error TS2304: Cannot find name 'ContextValue'.
node_modules/@cloudcare/browser-core/types/index.d.ts(121,33): error TS1254: A 'const' initializer in an ambient context must be a string or numeric literal or literal enum reference.
```

这些错误位于 SDK 声明文件，不在初始化配置中。3.3.21 的完整严格检查无诊断。

## 可复现命令

查询版本：

```sh
/Users/oneandonly/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node /usr/local/lib/node_modules/npm/bin/npm-cli.js view @cloudcare/browser-rum versions dist-tags --json --registry=https://registry.npmjs.org
```

在每个版本目录安装（package.json 已精确固定 SDK 与 TypeScript 版本）：

```sh
/Users/oneandonly/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node /usr/local/lib/node_modules/npm/bin/npm-cli.js ci --ignore-scripts --no-audit --no-fund --registry=https://registry.npmjs.org
```

在每个版本目录编译：

```sh
/Users/oneandonly/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node node_modules/typescript/bin/tsc --project tsconfig.json --pretty false
```

一键重跑两组：

```sh
python3 /private/tmp/rum-sdk-types-retest/run_checks.py
```

每个版本目录包含 package.json、package-lock.json、src.ts、tsconfig.json、effective-tsconfig.json、install.log、tsc.log、declaration-evidence.txt。results.json 记录编译命令、依赖真实版本、UTC 时间、退出码与锁文件 SHA-256。

## 原 Web 场景补测

已将上一轮 `/var/folders/8x/2_sfyjt11tb3y7_n0m9l53lc0000gn/T/rum-full-eval-fsgyxvww/web/project` 原文件复制至 `original-web-app`，初始复制排除 node_modules 与 .git。随后复用原有 Vue 3.5.0 依赖，并用此前下载的 3.3.21 browser-rum/core/worker 替换隔离副本的 SDK 包。唯一修改的原项目文件为 package.json 中 SDK 版本；新增离线锁文件。

全体应用 TypeScript 源码只有 src/main.ts 和 src/rum.ts，两者与原文件 SHA-256 完全相同。完整人工检查没有 `as`/尖括号/非空类型断言、显式 `any`、`@ts-ignore` 或 `@ts-expect-error`。rum.ts 现有 `declare global` 仅扩展 Window 配置和启动 Promise 属性，没有修改 SDK 声明。

| 检查 | 退出码 | 结论 |
|---|---|---|
| TS 7.0.2 完整严格检查，skipLibCheck:false | 0 | 所有原应用 TS 源码及加载的 SDK 声明通过，无诊断 |
| 原 esbuild 0.28.2 打包参数 | 0 | 原 main.ts/rum.ts 入口与真实 SDK 打包成功 |

严格检查实际参数：

```sh
--noEmit --strict --skipLibCheck false --target ES2020 --module ESNext --moduleResolution bundler --lib ES2020,DOM src/main.ts src/rum.ts
```

打包复用原 esbuild 执行文件及 `--bundle --format=esm --splitting` 参数，仅输入/输出路径改为隔离副本。

完整绝对命令、工具版本和退出码见 `original-web-app-results.json`；日志及打包依赖元信息见 `original-web-app-logs/`；源码一致性见 `original-web-app-copy-manifest.json`；SDK 全包与声明未修改证据见 `original-web-app-sdk-integrity.json`。重跑命令为 `python3 /private/tmp/rum-sdk-types-retest/run_original_app_checks.py`。

边界：原夹具没有 package scripts、tsconfig 或完整 Vue 挂载应用，此处证明原失败场景的全源码类型检查与同一 esbuild 验证成功，不扩大为完整生产 Vue 应用验证。未运行 SDK、浏览器、测试接收器或任何上报。

隔离副本的锁文件由 `npm install --package-lock-only --offline --ignore-scripts --no-audit --no-fund` 从实际依赖树生成，退出码 0。旧 npm 对未缓存的 Vue 间接依赖元数据产生警告，全部保留于 `original-web-app-lock.log`；随后已完成下面记录的独立安装验证，消除了该复现边界。两个最小 SDK 对照组仍保留从官方 registry 正常安装生成的独立锁文件。

### 独立 npm ci 复现确认

将此前复制的 node_modules 完整移到 original-web-app-borrowed-node_modules 保留后，对空依赖目录执行公开 registry 的 npm ci：

```sh
/Users/oneandonly/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node /usr/local/lib/node_modules/npm/bin/npm-cli.js ci --ignore-scripts --no-audit --no-fund --registry=https://registry.npmjs.org
```

退出码 **0**，独立安装 26 个包。没有依赖不可获取或离线元数据警告；仅有旧 npm 在 Node 24 下的 DEP0174 提醒。package.json 和原 package-lock.json SHA-256 均未改变。安装后的 rum/core/worker 仍为 3.3.21，Vue 仍为 3.5.0，与锁文件一致。

独立安装后再次执行完全相同的完整 strict tsc（skipLibCheck:false）与 esbuild：两者均退出 **0**。没有改源码、声明或检查参数，没有执行应用或上报。

安装证据：original-web-app-logs/npm-ci-result.json、npm-ci.log；后续编译与构建证据更新在 original-web-app-results.json 与 original-web-app-logs/。复用依赖阶段的结果保留为 original-web-app-results-before-npm-ci.json。
