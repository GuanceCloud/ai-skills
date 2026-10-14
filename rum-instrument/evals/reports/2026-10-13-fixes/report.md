# RUM Skill 问题修复与复测报告

> **结论更正（2026-10-13）：** 本报告按当时额外设定的“所有查询参数均不得上报”规则判定 Web 失败。该规则不能作为普通 RUM 接入的统一前置条件，相关“一律阻塞 Web”的结论已撤回。原始载荷与失败记录保留，用于证明特定过滤能力的限制；明确过滤要求或真实敏感数据场景仍需满足相应检查。当前规则与重新验证见[URL 策略修正报告](../2026-10-13-url-policy/report.md)。

测试日期：2026 年 10 月 13 日。**React Native 错误处理链、Web 严格类型检查、小程序误识别和计划格式指引已修复并复测。Web／Flutter Web 查询参数隐私问题仍受上游 SDK 限制；本次修复了 Skill 对该问题的识别、实施阻断和如实报告行为，没有将其记为接入成功。**

本次以仓库源码为准，重新构建发布快照并通过真实安装器安装到隔离目录。本机已安装 Skill 未修改，未使用真实授权码，未提交、推送或发布。原失败证据保留在[首次测试报告](../2026-10-13/report.md)，本报告不覆盖或抹除历史失败。

## 修复结果

| 原问题 | 修改与复测 | 结果 |
|---|---|---|
| React Native SDK 0.4.2 破坏原错误处理链 | 增加应用侧错误钩子资产及接入指导；关闭有缺陷的自动错误钩子，通过公开 `addError` 上报；保持原处理器同步执行 | 真实 SDK JavaScript + 模拟桥接 **24/24 通过**；原始严格基线 exit 1，修复后聚合 exit 0 |
| Browser RUM 3.3.5/Core 3.3.4 声明错误 | 指导必要的兼容升级；实际升级到 SDK/Core/Worker 3.3.21，保留严格检查 | 原完整 `main.ts`、`rum.ts` 不变；独立 `npm ci`、严格 tsc、原 esbuild 均 exit 0 |
| 小程序加入 SDK 后被误判为框架 | 将框架依赖与 SDK 标记分开识别，保留真实 Taro 等框架判定 | 原生类型保持 `native/high`；真实 MiniApp SDK 2.2.20 模拟上报、载荷及业务请求检查通过 |
| DataKit 计划嵌套、引用格式易错 | 提供通过校验的 v3 模板，明确 `value`/`source` 互斥及 readiness 嵌套；补充阻塞批次状态规则 | 新增模板与阻塞状态回归；React Native 首次计划、实施校验均通过 |
| Web／Flutter Web 最终载荷泄漏查询参数 | 要求读取 SDK 实际限制、检查非空最终载荷；不满足要求时在新初始化和换码前阻塞受影响目标 | **SDK 问题未修复**；3.3.21 实际浏览器探针仍 exit 1，Skill 正确停止新增初始化，未宣称接入完成 |

## 关键证据

**React Native：** [独立报告](react-native/report.md)、[逐命令结果](react-native/test-results.json)、[实际应用补丁](react-native/source.patch)。Android/iOS 标签各覆盖上报成功、拒绝、同步抛错、永不 resolve、配置失败后续跑及缺桥恢复，再分别覆盖原处理器返回/抛错，共 24 场景。验证 this、所有参数、调用时机与次数、返回值及抛出的异常对象保持；console.error 不变；重复启动和模块重载不重复配置；上报非空且敏感 canary 不进入桥接数据。真实 SDK 的 109 个文件哈希未变。缺桥时 SDK 缓存空桥对象，恢复测试明确重载 SDK 模块，不声称同进程动态恢复原生桥；配置失败后的重试可在同进程完成。

**Web 类型：** [对照结果](types/results.json)、[原应用结果](types/original-web-app-results.json)、[独立安装记录](types/original-web-app-logs/npm-ci-result.json)、[锁文件核验](types/original-web-app-logs/lock-verification.json)。同一 TypeScript 7.0.2 下旧组合复现 TS2304、TS1254，新组合通过 `strict`、`skipLibCheck:false`。没有编辑 SDK 声明、引入 any、类型断言或错误忽略。原应用锁文件同步后从空依赖目录独立安装 26 个包，再次编译和打包通过。该夹具仍不是完整生产 Vue 工程。

**Web 隐私：** [独立行为结果](web/report.json)、[实际浏览器结果](web/logs/browser-probe-result.json)、[合成载荷](web/logs/local-synthetic-payloads.json)。真实 SDK 3.3.21 + Chrome 捕获 3 次请求，包含 View、Resource、Error 等非空事件；初始 URL、资源 URL 和 history query 的 canary 仍出现。`beforeSend` 的修改白名单不能修改 `view.url_query`，View 事件也不能通过返回 false 取消。仅清洗可见 URL 或仅让类型检查通过均不足以解决问题。独立 Agent 补问与常规确认均为 0；保持应用代码无接入修改，实施校验拒绝该目标。浏览器测试在隔离探针运行，未向真实接收端上报。Flutter Web 使用同一 Browser SDK，原报告的 Dart/Flutter 原生验证缺口仍然存在。

**小程序：** [检测输出](miniapp/logs/detect-after.json)、[实际 SDK 烟测](miniapp/logs/real-sdk-smoke.log)。保持单次初始化；最终载荷不含查询、认证及请求体 canary，原业务请求保持。这里仍是 Node 中的 wx/App/Page 替身，不是开发者工具编译或真机测试。

## 独立复测引出的二次修正

Web 评估者第一次把模板的 `approved` 批次与 `blocked` 目标一起使用，校验器正确拒绝。原始失败记录保存在 [first-plan-validation.json](web/logs/first-plan-validation.json)。已补充明确规则：受阻批次使用 `pending + blockers`；这是技术阻塞，不应重新索要用户确认；无关的就绪批次保留批准状态。新增用例验证阻塞计划可记录、不可实施。最终快照另由未参与该计划的 Agent 从零编写阻塞计划，结果见 [最终计划复测](blocked-plan/result.json)。

RN 首次评估 harness 也出现过假绿：失败诊断调用了被 SDK 修改的 console.error，在设置失败退出码前再次抛错。已保留原日志，改为默认失败退出码、独立诊断输出、全部断言完成后才设置成功；重新取得 exit 1 的失败基线和 24/24 的修复结果，详见 RN 报告。不把退出码 0 与 JSON 内失败断言混为通过。

## 自动回归与版本核对

| 检查 | 结果 |
|---|---:|
| 仓库 RUM 回归 | **170/170** |
| 安装器／发布回归，本机 macOS | **5/5** |
| 可移植性、注册表 | **2/2** |
| 最终安装包内 RUM 回归 | **170/170**，与工作树同一套用例，不重复累计 |
| Skill 格式校验、git diff 检查 | 通过 |

独立自动回归合计 **177 项**通过，真实 SDK 验证另列，不能用回归总数掩盖 Web 隐私失败。[命令结果](control/checks.json)、[工作树日志](control/workspace-tests.log)、[最终安装包日志](control/installed-tests.log)。

RN/Web 独立行为测试的首轮快照为 `97bff6dd3ab0fb1601b41aadbc1a47847811b99b`；之后只调整阻塞计划指引并新增该回归。最终重新构建、安装的快照为 `8e68e5828349590d1ae4695c10d588341222953c`，归档 SHA-256 为 `f9401018aef594ddabd9cf91cced89f072b61c5346db4c75c599434739d1aedb`。这些都是隔离测试快照，并非主仓库提交或线上发布版本。[最终安装回执](control/final-install-receipt.json)与[24 个运行态文件逐一比对](control/source-install-comparison.json)证明最终源码与安装包一致。测试工具、依赖及文件路径详见各场景记录；临时目录可能被系统清理，仓库保存可审查的持久证据。

## 尚未通过的验收

- Browser SDK 查询参数过滤能力仍需官方支持或受验证的兼容版本。当前不能把 Web／Flutter Web 接入标记为完整通过；也不能通过关闭所有采集、修改第三方 SDK 或拦截全局传输伪造通过。
- Android、iOS/tvOS、React Native 原生和 Flutter 的完整平台构建、设备运行，以及小程序开发者工具／真机验证，未在本轮补齐。本次修改集中在已证实的 Skill 与 JavaScript 问题。
- 无真实控制面换码、远程入库、Linux/Windows 实机安装或线上发布验证。以上均保持“未验证”，本机模拟 HTTP 成功不代表服务端入库。
