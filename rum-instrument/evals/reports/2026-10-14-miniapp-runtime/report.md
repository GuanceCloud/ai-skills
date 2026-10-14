# MiniApp 运行时续验收

日期：2026-10-14。使用仓库工作区中的 RUM Skill；本轮只新增验收证据，没有修改运行脚本或本机安装的 Skill。

## 结论

**MiniApp 运行时验收仍被无 RUM 页面基线阻塞。** 新版微信开发者工具 `2.02.2609231` 下，灰度基础库 `3.17.4` 和非灰度基础库 `3.17.3` 均未建立可交互的首页。切换版本后的实际运行时返回 `SDKVersion: 3.17.3`，不是仅修改了配置文件。App 启动次数为 1，页面栈仍为 `[]`，`currentPage()` 继续报 `getPageMetaByWebviewId(...)` 返回 null 的 `rawPath` 错误。

本轮没有加载 RUM SDK，也没有启动模拟接收器。因此 SDK 初始化、View/Resource/Error/Action、重复接入及最终载荷隐私均为 **not_run**；不得把没有上报视为隐私通过。当前证据不能归因于 RUM SDK，也不能证明故障仅由灰度基础库引起。

| 检查 | 结果 | 证据 |
|---|---|---|
| 有效微信 AppID / IDE 服务 / 自动化端口 | 已识别已有有效 AppID，服务和端口可连接；启动命令发生超时，不能按端口存在宣称启动全部成功 | [启动日志](logs/baseline-launch.log)、[55 秒超时](logs/baseline-launch.json) |
| 3.17.4 首次运行 | 自动化 App 生命周期读取超时；测试总超时返回 124 | [首次结果](logs/baseline-result-before-recompile.json) |
| 3.17.4 重新编译 | 真实 GUI 编译后仍为空白页；页面读取出现 rawPath 异常；测试返回 1 | [结果](logs/gray-baseline-result.json)、[截图](logs/gray-baseline.png) |
| 非灰度版本选择依据 | 官方 IDE 自带版本目录将 3.17.3 列入 notGrayList，使用占比最高；先尝试 widelyUsed，再将隔离工程明确设为 3.17.3 | [版本目录摘录](logs/official-library-metadata.json) |
| 3.17.3 实际运行 | App 启动一次，页面栈为空、页面交互失败、截图超时；测试返回 1 | [实际运行结果](logs/baseline-result.json) |
| GUI 错误取证 | 已读取控制台 rawPath 错误和灰度提示；最终工具提示模拟器长时间无响应 | [GUI 观察记录](logs/gui-observations.json) |
| SDK / 信号 / 幂等 / 隐私 / 远端入库 | not_run / 未验证 | [汇总](result.json) |

## 执行范围与清理

此前临时工程已不存在。本轮从历史无 RUM 基线重建 `/private/tmp/rum-miniapp-acceptance-20261014/baseline`，复用已提供的微信 AppID，不重新索取或消费 RUM 授权码。仅在临时 `tooling/` 安装官方 `miniprogram-automator@0.12.1`；锁文件记录 registry 完整性。核对了已锁定 `@cloudcare/rum-miniapp@2.2.20` 的 registry 元数据，但因基线未通过，没有运行该 SDK。

测试脚本聚合检查并对失败返回非零。CLI 的进程超时单独保存在 JSON 中；包裹 CLI 的记录脚本正常退出不代表 CLI 验收通过。`widelyUsed` 启动调用在 45 秒内未结束，后续单工程 `close` 调用也超时。之后检测到自动化子进程已变化，最终通过运行时查询确认已进入 3.17.3，再判定其基线失败。

GUI 控制期间出现界面变化、无可用窗口等中断；用户明确表示可以继续操作隔离工程后继续。最后通过可见的“终止模拟器”按钮结束挂起运行，确认“模拟器处于终止状态”，再关闭该隔离窗口，返回 IDE 项目列表。未打开或修改列表中的其他用户项目，未改全局安全设置、登录状态或远端控制台，未上传发布。

清理后 `19529`、`19532`、`19534` 均无监听；IDE `20166` 保留运行，见[端口记录](logs/final-ports.json)。仓库证据中的微信 AppID 已替换为占位符；可复跑的临时工程保留本地有效配置。

## 下一步与提交边界

下一次先使用一个在该工具中已确认首页正常显示、按钮正常交互的原生微信工程做对照；在它的隔离副本上运行相同无 RUM 断言，通过后再进行真实 SDK、非空事件载荷和幂等验收。现有 AppID 无需再次提供。不要继续把静态编译、端口监听、App 启动或空载荷等同于完整接入通过。

本轮没有发现可定位到 RUM Skill 的新代码缺陷；先前修复的提交判断保持在原已验证范围内，**MiniApp 全流程“傻瓜式接入已验收”仍不成立**。

## 复跑入口

本目录 `baseline/` 只有原生 App/Page 与本地测试控件，没有 RUM 依赖。归档 `project.config.json` 中的微信 AppID 是占位符；直接继续使用上述临时目录可复用已有值。`baseline-acceptance.cjs` 从同级 `tooling/node_modules/miniprogram-automator` 加载官方客户端，连接 `ws://127.0.0.1:19534`；运行前须由官方 CLI 打开对应工程，输出保存在同级 `logs/`。复跑时使用新输出目录以保留历史失败。

参考：微信工具随安装包提供的 `references/project-config-fields.md` 说明 `libVersion` 支持版本号及 `latest` / `trial` / `widelyUsed`；[观测云官方 MiniApp 接入文档](https://docs.guance.com/en/real-user-monitoring/miniapp/app-access/)用于核对 SDK 来源和后续接入。Skill 源文件摘要见[来源记录](logs/source-manifest.json)。
