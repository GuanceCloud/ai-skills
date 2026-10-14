# RUM Skill 多平台接入模拟测试报告

> **结论更正（2026-10-13）：** 本报告按当时额外设定的“所有查询参数均不得上报”规则判定 Web 失败。该规则不能作为普通 RUM 接入的统一前置条件，相关“一律阻塞 Web”的结论已撤回。原始载荷与失败记录保留，用于证明特定过滤能力的限制；明确过滤要求或真实敏感数据场景仍需满足相应检查。当前规则与重新验证见[URL 策略修正报告](../2026-10-13-url-policy/report.md)。

后续修复与复测见[修复报告](../2026-10-13-fixes/report.md)。本报告保留首次测试的原始失败证据。

测试日期：2026 年 10 月 13 日。结论：**安装、参数复用和减少补问的流程有效，但接入质量未通过整体验收。** 本轮实际执行了 6 类应用的安装与接入流程、每类的重复接入，以及 1 个已有配置的零输入复用场景。发现 Web／Flutter Web 的真实载荷隐私失败和 React Native 的错误处理链问题；原生平台的构建证据仍不足。

这不是只阅读 Skill 或检查生成文件的评审。独立 Agent 从本机分发镜像读取 `rum.md`，执行安装器、读取安装后的 Skill、分析项目、实施接入、尝试适用验证并重复请求。主代理另外复跑了关键 SDK 测试。每个项目和 Skill 安装均在隔离目录中，本机真实安装没有修改。

**版本与测试边界**

- 被测包来自仓库工作树的隔离 Git 发布快照，版本为 `ebaddc3a8c835cc3f046920b0595a782a34d6459`，不是主仓库的发布提交。
- RUM archive SHA-256：`10b90e3892689ffb47602a5f10e789c05a1e66b6549ee824794f866b7b11b29b`。7 个场景使用的 Skill、脚本、参考文档共 22 个文件与被测源码一致，见[逐场复核](control/parent-checks.json)。
- 安装经过真实 HTTP 下载与安装器校验；分发端是本机镜像。稳定入口、固定版本入口均实际安装成功。没有发布或验证线上 OSS 新入口。
- 6 类应用流程使用 DataKit 和明确标注为测试值的应用 ID。Public DataWay 单独使用真实 helper 加模拟控制面响应验证，未进行真实账号换码，也不把该脚本模拟算作完整的 DataWay Agent 对话测试。
- 原始输入是仓库现有精简 fixture。Web 增加了维护态 HTML 入口；其他场景保留骨架限制。它们不是完整的生产应用样板。
- 本轮在 macOS 执行。Linux、Windows 安装器只有已有 CI 矩阵配置，本轮没有这两个系统的运行结果。

**各类应用结果**

“补问”只计业务信息补齐，不包含宿主权限提示。下表各场景的常规二次确认均为 0。

| 场景 | 实际接入和验证 | 补问轮数 | 结论 |
|---|---|---:|---|
| Vue Web，保留 Browser RUM 3.3.5 | 真实 npm 依赖、esbuild、Chrome；配置读取、单次初始化、加载失败隔离及本机模拟上报 | 0 | **未通过**：query/hash 进入载荷；严格类型检查也失败 |
| 微信小程序，SDK 2.2.20 | 真实 npm SDK，在模拟 wx/App/Page 下产生 view/resource/error/action；启动、请求不变及载荷 canary 检查 | 0 | **本地模拟通过**；微信平台编译、真机未验证 |
| Android，SDK 1.7.5 | 真实 SDK AAR/POM/源码核对；Gradle 配置、Manifest、初始化及静态检查 | 0 | **部分完成**；没有 Gradle Wrapper、完整工程和 Android 工具链，未编译运行 |
| iOS 与 tvOS，GuanceSDK 1.6.7 | 识别 PhoneApp、TVApp；独立 xcconfig、Podfile 和入口代码；plist/Ruby/Shell 检查 | 1 | **部分完成**；缺 Xcode/CocoaPods，原始 pbxproj 不完整，未编译运行 |
| React Native，SDK 0.4.2 | 真实 SDK JavaScript + 原生桥接替身；双 ID 传递、单次初始化、部分失败续跑和缺桥接降级 | 0 | **未通过**：原有全局错误处理器未被调用；原生运行未验证 |
| Flutter Android/iOS/Web，插件 0.5.7、Browser SDK 3.3.21 | 三端独立配置、条件导入；移动端源码检查；Web 增补真实 Chrome + Browser SDK 测试 | 0 | **未通过**：Web 派生字段泄漏查询参数；无 Flutter/Dart，移动端未编译运行 |
| 额外场景：已有小程序配置，只说“帮我接入 RUM” | 自动发现并复用 ID、地址、初始化；安装锁定依赖后完成语法与 4 个启动模拟检查 | 0 | **复用行为通过**；源码零修改、Skill 安装/更新检查均为 0 |

六个首次安装场景均成功安装；重复同一请求均复用已安装 Skill，无重复初始化、依赖声明或配置改动，文件指纹保持不变。iOS 的一次补问有实际必要：初始只给了一个 ID，工程中却有两个独立应用。补充 TVApp 的 ID 后继续，重跑没有重复索要。参数已经明确或可从项目确定的另外 6 个场景均没有业务补问。

这些是 7 次具体观察，不代表统计上的成功率。只有小程序的本地 SDK 模拟验收通过；**不能将“没有提问”或“安装成功”视作接入质量已经通过。**

**需要处理的问题**

1. **P1：Web 载荷隐私规则没有可靠落到代码和验收。** Vue 场景中 `CANARY_QUERY`、`CANARY_HASH` 进入真实 SDK 载荷。Flutter Web 虽然清洗了 `event.view.url` 等字段，真实 SDK 仍通过派生字段 `view_url_query` 输出 `CANARY_FLUTTER_QUERY`。其桩测试原本通过，说明只检查构造的事件对象不足以证明真实上报安全。主代理使用实际 Chrome 和 SDK 复现，两次验收断言均返回失败。应覆盖最终导出字段，在真实 SDK 载荷上检查 canary，并将失败作为未完成条件。[Web 证据](web/logs/parent-verification.json)、[Flutter Web 证据](flutter/logs/parent-browser-smoke.json)、[实际派生字段载荷](flutter/logs/parent-local-payloads.json)。

2. **P1：React Native 自动错误采集改变原有错误处理行为。** SDK 0.4.2 的 JavaScript 代码保存了 `ErrorUtils.getGlobalHandler` 方法本身，而不是调用它取得的当前处理器。触发模拟错误后，上报方法被调用，原处理器调用次数却为 0。Android/iOS 标签的桥接替身测试均观察到该问题，主代理也独立复现；这不是原生真机验证。Skill 的兼容性验证需要覆盖错误处理链，在证明兼容前不能将该接入认定为完成。[独立复核](react-native/logs/parent-verification.json)、[调用记录](react-native/logs/smoke-android-normal.json)。

3. **P2：计划格式仍有 Agent 自行试错成本。** 小程序场景首次计划校验因 DataKit readiness 缺少 `status/checks` 嵌套失败，Agent 阅读校验器源码后修正；已有配置复用场景又因同一引用同时包含 `source` 和 `value` 首次校验失败。两者都未向用户补问，但增加了执行步骤。应提供可直接使用的 v3 DataKit 示例，明确 readiness 和引用结构。[首次失败](miniapp/logs/plan-validation.log)、[修正后结果](miniapp/logs/plan-validation-fixed.log)、[复用场景记录](reuse-existing/result.json)。

4. **P2：既有 SDK 与所用 TypeScript 的严格类型检查不通过。** Browser RUM 3.3.5、browser-core 3.3.4 与测试工具 TypeScript 7.0.2 组合出现 `ContextValue` 缺失和 ambient const 声明错误。`skipLibCheck` 后业务源码检查通过，esbuild 打包也通过，但不能将它表述为完整严格类型检查通过。本轮保留原依赖，没有编辑第三方 SDK。[编译错误](web/logs/typecheck.log)。

5. **P3：小程序检测标签漂移。** 只加入 SDK 的普通 `package.json` 后，detector 从 `native/high` 变成 `framework+native/medium`，没有实际新增框架。当前没有导致重复目标或额外补问，但值得修正框架判定证据。[接入前](miniapp/logs/detect-first.json)、[接入后](miniapp/logs/detect-rerun.json)。

本轮保留了上述失败的原始接入代码，未通过临时修改源码、SDK 或测试预期来掩盖发现。部分子测试程序退出码为 0，但 JSON 中的隐私或处理器布尔值为 false；本报告按实际断言判定失败，并保存了主代理的独立失败断言。

**脚本与恢复验证**

| 验证组 | 结果 | 证据 |
|---|---:|---|
| 安装包内原有 RUM 脚本测试 | 164/164 | [日志](control/unit-tests.log) |
| 工作树 RUM 脚本测试，含本轮新增混合平台恢复用例 | 165/165 | [日志](control/workspace-tests.log) |
| 发布及安装器测试，macOS 本地执行 | 5/5 | [日志](control/installer-tests.log) |
| Skill 包可移植性 | 1/1 | [日志](control/portability.log) |
| Skill 注册表 | 1/1 | [日志](control/registry.log) |

164 与 165 是同一套测试在安装包和工作树中的两个执行版本，不能相加。工作树回归合计 172 项通过，**与上表真实 SDK 接入失败并不矛盾**。

新增用例直接调用安装版 helper，使用模拟控制面响应：一次换码依次处理 Web JSON、小程序 dotenv、Android properties、iOS xcconfig；让 Android 查询失败，Web、小程序和 iOS 已保存结果保留。续跑只查询 Android，先前文件内容不变；随后修改本地验证命令再次续跑，网络调用和授权码读取均为 0。状态及计划不包含模拟凭据值。该用例也已保存到仓库 `rum-instrument/tests/test_onboarding.py`。[恢复证据](control/cross-platform-recovery.json)。已有回归另覆盖检查点写入失败回滚、旧状态迁移、配置身份变化、脏文件冲突、只读请求和独立目标选择。

**仍需补齐的验收**

- 将以上 P1 问题修复并用相同真实 SDK 测试重跑，不能只修桩断言。
- 使用完整、可构建的代表应用补跑 Android、iOS/tvOS、React Native、Flutter；小程序补跑开发者工具和真机。本机 Swift 解析的 `SwiftBridging` 错误在原始未改骨架上也复现，不能归因于接入修改。
- 使用测试账号及实际 DataKit/Public DataWay 完成受控的服务端验证。本轮没有任何真实控制面换码或远程入库证据；本机拦截的 HTTP 成功不代表入库。
- 在线上分发入口发布后，再运行 Linux、Windows 和真实宿主首次加载验证。本轮用 `--dest` 隔离安装，未覆盖默认用户目录实际写入或其他 Agent 产品的宿主加载行为。

**证据和复跑说明**

每个场景目录保存 `result.json`、非敏感 `plan.json`、安装回执、关键日志及 `source.patch`；Web、小程序、React Native、Flutter 另保存烟测脚本。完整临时工程保留在本机 `/var/folders/8x/2_sfyjt11tb3y7_n0m9l53lc0000gn/T/rum-full-eval-fsgyxvww`，证据中用 `${EVAL_ROOT}` 代替该路径。该临时目录可能被系统清理，仓库内证据为持久副本。复制的脚本依赖各场景 SDK、测试工具及临时工程，不是零依赖通用测试运行器。

本轮只新增混合平台恢复回归、测试证据和 README 测试入口。应用接入改动全部位于隔离工程；没有改本机真实 Skill，没有提交、推送或发布。临时 HTTP 分发服务已关闭。
