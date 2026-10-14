# RUM 全平台验收补充报告

> 后续更新：用户授权测试站 TLS 例外并开启微信服务端口后的真实续验收见 [最新报告](../2026-10-13-live-continuation/report.md)。下文的证书/端口阻塞为当时状态，原证据保留。

日期：2026-10-13。基于当前仓库工作区的最新 Skill；没有使用或覆盖本机已安装 Skill，没有提交、推送或发布。

## 本轮结论

完整 Vue 工程的生产构建及真实 Chrome 运行、Android 完整 APK 的构建及模拟器运行已经补齐。两者均取得官方 SDK 的真实非空 View、Resource、Error 载荷。小程序已补齐完整工程和官方编译，平台运行仍未通过。**尚不能宣称“全平台端到端验收完成”或“远端入库成功”。**

本轮以当前仓库运行态文件直接执行独立 Agent 接入测试，文件指纹见 [skill-source-sha256.json](skill-source-sha256.json)。它不等于线上发布版本；此前安装器全流程的证据仍见 [修复报告](../2026-10-13-fixes/report.md)。本轮补的是完整应用与实际平台验证，没有重计一次 Skill 安装。

| 验收对象 | 本轮新增证据 | 结论与边界 |
|---|---|---|
| Vue 3 / Vite / TypeScript | 干净 npm ci、严格 vue-tsc、production build、真实 Chrome 16/16 断言；6 View、10 Resource、1 Error | 本机 SDK 链路通过；接收器为本地协议模拟服务 |
| Android | Java 17 / Gradle 8.7 / AGP 8.5.2 构建和 lint；Android 34 arm64 模拟器安装、两次冷启动；16/16 载荷断言 | 官方 ft-sdk 1.7.5 真实运行通过；View/Error 使用手动 API，Resource 使用真实 OkHttp interceptor；不代表 Gradle 插件自动插桩或真机 |
| 微信小程序 | 完整 App + Page 工程；官方 miniprogram-ci NPM 构建零警告；官方 wcc/wcsc 编译；13 项 JSON/JS/页面检查 | 编译通过；实际平台运行和载荷断言尚未完成，不能沿用 Node 平台替身结果冒充 |
| Skill 脚本 | 本轮重新执行 170 项 unittest | 全部通过；不替代设备和远端入库验收 |
| 真实测试接收端 | 私网接收端只读 TCP/HTTP 探测；测试 DataWay 和 AI API 只读探测 | 私网超时；新 DataWay 可达，但 AI API 证书校验失败，未消费新授权码 |

## 可审查证据与复跑工程

- Web：[完整报告](web/evidence/report.md)、[机器汇总](web/evidence/summary.json)、[Chrome 断言](web/evidence/browser-results.json)、[实际载荷](web/evidence/payloads.json)、[相对基线补丁](web/evidence/source.patch)。`web/` 保存完整源文件、package-lock、Vite/TS 配置及测试脚本；不保存 node_modules/dist。归档副本的 .gitignore 仅增加保留 evidence 的规则，以便提交原始证据。
- Android：[构建和运行说明](android/README.md)、[命令退出码](android/evidence/commands.json)、[载荷断言](android/evidence/payload-verification.json)、[真实 SDK 载荷](android/evidence/payloads.jsonl)。`android/project/` 保存源文件和 Gradle wrapper，`collector.py`/`verify_payload.py` 保存接收与验收脚本；不保存 JDK、Android SDK、AVD 数据、APK 和缓存。
- MiniApp：[机器报告](miniapp/report.json)、[官方 NPM 结果](miniapp/logs/npm-build-result.json)、[页面检查](miniapp/logs/static-results.json)、[CLI 结果](miniapp/logs/cli-results.json)。`miniapp/project/` 保存完整源工程及 lockfile；不保存第三方 SDK 构建产物或 npm 缓存。
- [本轮回归结果](regression.json)、[环境探测](environment.json)。部分原始日志含本机绝对路径，它们记录本次运行地点，不是通用安装要求。

复跑请复制归档工程到独立目录。Web 按工程 README 执行 `npm ci`、`npm run build`，浏览器脚本需现代 Node、Chrome 与 Playwright。Android 需 Java 17、Android SDK 34、可用模拟器；将 `rum.properties.example` 复制为被忽略的 `rum.properties`。MiniApp 将配置示例复制为被忽略的 `config/rum.local.js` 并填写合成本地 App ID/接收端，然后安装锁定依赖并使用官方工具构建。MiniApp 的 `validate.py` 保留本次临时目录路径，复跑时须按新目录调整；任何真实 Token 都不应写入本归档。历史 JSONL 和日志属于固定证据，重新运行须使用独立副本，避免把多次载荷混为同一次测试。

## 失败及修正没有被隐藏

- Web 第一次计划缺 dependency decision 的 owner、compatibility、official_sources、verified_at，校验器拒绝；补齐后 plan/implement 均通过才改应用代码。首次计划和失败日志均保留。没有业务补问或常规二次确认，但内部首次计划并非一次通过。
- Android 首轮 lint 因测试工程的 debug 网络配置缺 includeSubdomains 失败；修正后构建与 lint 通过。首次接收器漏处理 chunked/deflate，捕获为空；修正本地接收器并再次冷启动后取得载荷。原失败均保留，没有把空上报算成功。
- Android `testDebugUnitTest` 为 NO-SOURCE，不计作单元测试通过。两次冷启动初始化各一次，也不替代完整“再次调用 Agent 修改应用”的幂等性测试；Web 则额外保存重复接入审计及前后哈希。
- 微信 CLI 的 65536 错误来自沙盒内端口探测连续失败。沙盒外使用明确端口后，真实问题是 IDE service port disabled，退出 255。官方静态构建通过不代表 CLI 自动运行成功。
- Web SDK 3.3.21 普通接入通过；普通 URL 参数不再被机械判成隐私阻塞。此次完整 Vue 工程使用 TypeScript 5.9.3，不声称此 Vue 组合已经通过 TS 7。SDK 加载超过 1500ms 时应用优先启动，最早期事件可能丢失。

## 真实环境与剩余缺口

用户最初提供的私网接收端 TCP、HTTP、/v1/ping 均超时，未向它上报；结果见 [HTTP 探测](receiver-probe.json)、[TCP 探测](receiver-tcp.json)。随后改用 `http://testing-openway.dataflux.cn`，该地址 HEAD 返回 404，说明 HTTP 可达，**不证明 RUM 接收成功**。

Skill 内置对应 AI API 为 `https://testing-ft2x-ai-api.dataflux.cn`。Python 默认证书校验失败；[curl 保留默认校验也退出 60](tls-verification.json)。用户明确选择保留校验，随后确认没有可信 CA。本轮没有关闭 TLS 校验、没有交换新临时码、没有得到真实 Client Token，也没有将授权码持久化到本报告。需要环境管理员提供可信 CA 链或修复服务证书后，才能继续真实换码。用户新提供的应用 ID 为 `new_skill_001`；更换接收端没有把同一个 ID 分配给所有平台。

真实 Public DataWay 的非敏感准备已完成：新应用 ID、Vite 原生 Token 读取路径、0600 且被 Git 忽略的空 Token 配置文件、独立状态路径、通过 plan 校验的 v3 计划和待实施初始化补丁。依赖干净安装及严格生产构建通过；implement 校验按预期拒绝缺凭据状态的执行。见 [准备报告](public-dataway/report.md)、[续跑说明](public-dataway/continuation.md) 和 [机器汇总](public-dataway/summary.json)。准备中首次 Token 映射格式错误与 SDK 配置类型错误均已修正并复验，原失败日志保留。CA 到位后继续，无需重新提交已知地址与 ID；若临时码届时失效，仅补新码。准备工程的旧本地测试脚本会打印完整 SDK 配置，不能直接用于真实 Token；续跑说明明确要求真实验证仅输出布尔比较，并排除含 Token 的构建产物。

小程序服务端口已获准临时开启并恢复，但 CUA 按应用路径、包标识和全局读取均超时，当前旧版官方 CLI 没有开启此设置的受支持命令。最新 `--auto` 仍退出 255，提示服务端口关闭。未发生设置修改，原状态仍关闭，无需恢复；接收器未启动。见 [GUI 失败记录](miniapp/logs/gui-attempts.json)、[复现说明](miniapp/REPRODUCE.txt)。下一步需要可用的原生界面自动化通道，或在开发者工具中手动开启“设置 → 安全设置 → 服务端口”后继续，不能用修改未知内部配置绕过。

仍未补齐：Apple iOS/tvOS/macOS 的 Xcode 构建与运行；React Native/Flutter 的完整原生应用链路（不能用原生 Android 验收替代）；HarmonyOS、UniApp 各目标、C++/Unity 的完整构建与运行；Linux/Windows 当前改动的真实安装执行；真实控制面换码、DataWay 上报及服务端查询证据。用户确认没有可提供的其他设备或 CI 环境。已有模拟/静态测试继续有效，但不升级为这些平台的真实验收结果。

所有本地 SDK 验证仅使用合成数据。验收产生的专用 Chrome、Android 模拟器和接收器均已关闭，没有停止用户已有设备或服务。本轮没有修改产品 Skill 行为；新增的是可复现工程、验收证据及 README 索引。
