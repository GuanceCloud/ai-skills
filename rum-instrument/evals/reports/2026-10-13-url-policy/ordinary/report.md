# 普通商品目录基础 RUM 接入 forward-test

结论：隔离项目完成接入，最终真实 SDK 浏览器测试通过（exit 0），无补问、无常规确认。首次计划校验 exit 0；实施前校验 exit 0。未修改主仓库、本机安装 Skill 或共享 SDK。

## 来源与范围

- 输入 Skill：`/private/tmp/rum-url-policy-eval/skills/rum-instrument/SKILL.md`
- Skill SHA-256：`6a1fdb1a23126b8045e4eafdde3529a2e1edbb9495cbe1a6ddd1329d2c53e6a1`，全部 Skill 文件哈希见 `skill-hashes.json`。
- 初始提交：`9e38996a36c0a7964119a05da567b3da81eba6a3`；初始工作树干净。
- 唯一目标 Web；已有官方 SDK `@cloudcare/browser-rum` 3.3.21，没有已有初始化。
- 官方文档已查询：https://docs.guance.com/real-user-monitoring/web/app-access/ 。SDK 的 receiver 字段、会话默认采样和 Replay 默认值另外核对了已安装官方源码。
- 未读取此前报告或其他 Agent 计划。DataKit 不走控制面；授权码消耗和控制面调用均为 0。

## 实施

新增 `src/bootstrap.js`、`src/rum.js`、`rum-config.js`、构建脚本、README 和 ignore 规则；HTML 改为加载公开运行时配置和 bootstrap；增加 esbuild 构建命令，保留 SDK 版本。完整补丁见 `applied.patch`。

bootstrap 先尝试初始化 RUM，再启动原有商品代码，SDK 模块加载失败时继续启动商品应用。Replay 采样显式为 0；没有新开 Trace、Logs、远程配置或自定义 context。`page`、`sort` 是代码中可核实的普通目录参数，保留标准采集，未加全局 URL 过滤。

## 浏览器证据

使用真实 Chrome 155、真实 npm SDK + esbuild，HTTP 服务仅监听本机临时端口。为避免与其他评估者抢占 19529，使用 Playwright route 对配置地址 `http://127.0.0.1:19529/**` 本地接收并响应。没有访问真实接收端。

最终非空载荷 2 个请求、17623 字节。`payloads.json` 保存最终序列化载荷，`coverage.json.gz`（原始覆盖率数据的无损压缩副本） 保存真实 Chrome 精确覆盖率。所有 15 个 smoke 断言通过：View、Resource、未处理 Error、console Error、SDK init 回调计数 1、运行时 appId/接收端/service、按钮 1→2、URL `/?page=2&sort=price`、原样商品请求、原有错误处理器调用一次、SDK 加载失败后仍可翻页、没有 Trace 请求头和 Replay 请求。

首次 smoke exit 1 原因是测试的脚本选择器误选 `rum-config.js`，只有 oneInit 断言失败，其余断言通过。保留 `smoke-results-first.json` / `payloads-first.json`；修正测试选择器后重跑 exit 0，没有修改接入代码。首次报告中自动生成的本机 Cookie 值已脱敏，失败断言和其余结果保持原样。

重复执行重新发现/校验/构建，维护源码哈希前后一致；唯一 SDK 依赖和初始化均为 1。见 `rerun.json`。没有使用失真的手造 callback 作为过滤证明。

## 限制与交付

模拟接收成功不能证明真实 DataKit、控制台或远程入库，远程验证为 false。项目没有版本/环境来源，公开运行时配置留下可填字段，未伪造生产版本。使用授权复用的本地依赖，未测试全新 npm install 或新增 lockfile。项目没有原有测试或 TypeScript 配置，因此验证范围是实际 bundle 与浏览器行为。

基础采集保持普通 URL query 字段；未发现适用的过滤禁止要求或实际敏感值流。本测试不能证明 SDK 支持清除派生 query 字段；Skill 中关于该能力的限制仍适用。

运行：`npm install` → `npm run build` → HTTP 发布 `dist/`，部署时更新 `rum-config.js` 的实际版本、环境及可达接收地址。外部 SDK 加载失败和应用错误行为已本机验证。

命令与退出码见 `commands.json`、`first-plan-validation.json`、`implement-validation.json`、`smoke-results.json` 和 `rerun.json`。补问 0、常规确认 0；2 次工具沙箱提权用于授权的本机服务/Chrome，没有追加用户业务确认。
