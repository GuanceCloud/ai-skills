# RUM 接入验收索引

这里集中保存测试范围和历次证据。运行包不包含 `evals/`；历史日志的失败、临时路径和当时结论保持原样，不作为当前运行配置。

## 当前验证范围

| 范围 | 已有证据 | 仍需区分的边界 |
|---|---|---|
| 脚本与发布包 | 本地回归；真实构建 tar/zip 后校验文件、哈希及解包后的探测、草稿、实施校验、配置解析和恢复 | 控制面使用合成凭据与网络替身，不代表本轮真实换码 |
| Web | 完整 Vue 工程构建、真实浏览器 SDK、测试 DataWay HTTP 上报；用户人工确认后台有数据 | 后台未做自动逐事件核对；不代表全部框架和生产环境 |
| Android | 完整 APK 构建/lint、模拟器与本地接收器载荷 | 不代表全部自动插桩、真机或远端入库 |
| MiniApp | 官方 npm 构建、手机预览基线通过；真实 SDK 向局域网接收器上报 View/Resource/Error/Action，非空载荷中的两类隐私 canary 均未命中 | 模拟器仍故障；真机使用调试模式，生产域名校验、远端入库、重复接入幂等未验收 |
| Apple、跨端原生、HarmonyOS、C++、Unity | 平台适配指引及静态/模拟证据 | 完整平台构建与运行仍有缺口 |
| 执行宿主 | RUM 完整脚本 CI 覆盖 macOS/Linux；安装器及宿主限制测试含 Windows | 原生 Windows 不执行 Public DataWay 凭据落盘；需 WSL/Linux 文件系统或受支持宿主 |

## 本地复验

2026-10-22 [地址解析修复验证](reports/2026-10-22-site-resolution/report.md)：普通/RUM OpenWay 共用目录识别，支持有依据的部署配置与命名约定，DataWay 探测改为非阻塞，内置测试站默认端口覆盖保护已修复。RUM 257 项、发布包 1 项、注册表 1 项，共 **259 项通过**；包含 23 项新增边界回归。未消费真实授权码或执行发布。

2026-10-14 自动更新策略调整：新接入任务检查已发布版本，无本地修改时自动升级；任务续跑固定版本。安装器回归覆盖同版本校验且不下载包、生成缓存不阻塞升级、本地修改保护、固定版本、索引不可用时保留安装，以及恢复索引后的升级。本轮 macOS 实测 RUM 234 项、安装器 7 项、发布包冒烟 1 项、注册表 1 项，共 **243 项通过**；Skill 格式、Shell 语法和差异检查通过。Windows 安装器同步修改，待现有三系统 CI 验证；未执行新的真实 Agent 对话、设备验收或公共发布，也未修改本机已安装 Skill。

最新整体评审修复见 [交付修复与收敛](reports/2026-10-14-delivery-fixes/report.md)：嵌套 JSON 配置写入、旧入口换码前格式检查、UniApp H5 目标归属共三个 P2 问题已关闭。新增 9 项行为回归，最终 RUM 234 项、安装器 6 项、发布包冒烟 1 项、注册表 1 项，共 **242 项通过**。同时统一原生隐私规则及逐目标交付结果口径；未重新进行设备或后台入库验收。

2026-10-14 本轮恢复流程修复后的检查：RUM 225 项、安装器 6 项、真实发布包冒烟 1 项、注册表 1 项，共 233 项通过。新增 16 项回归覆盖规划后用户修改、配置准备前后摘要、无凭据准备校验、宿主限制、父路径冲突和落盘预检查。发布包冒烟增加了脏 `.gitignore` 准备、配置解析、重复执行及后续用户修改拦截。原有地址规范化、分批恢复和失败回滚继续通过。 Skill 格式、36 处运行文档本地链接、CI YAML 和 `git diff --check` 均通过。宿主限制已加入三系统 CI；本轮实际执行宿主为 macOS，Windows 分支以受控模拟验证，未声称完成 Windows 设备验收。

上述恢复流程修复回归没有消费真实授权码、重跑设备或后台入库验收，也没有执行公共发布。随后进行的 [MiniApp 运行时续验收](reports/2026-10-14-miniapp-runtime/report.md)确认：非灰度基础库 3.17.3 已实际生效，但无 RUM 基线仍出现空页面栈和 rawPath 异常。已结束挂起模拟器并关闭隔离窗口；不将此环境阻塞计为 SDK 或隐私通过。

后续 [MiniApp 真机验收](reports/2026-10-14-miniapp-phone/report.md)绕过模拟器，用户完成手机操作，接收器收到真实 SDK 的 3 批数据。确认核心事件、200 资源请求、测试错误、查询参数与输入 canary 过滤以及未注入追踪头；保留首次手机域名拦截证据。已将真机预览的调试模式要求补入 MiniApp 适配指引，结论限于报告列出的验证范围。

```sh
python3 -B -m unittest discover -s rum-instrument/tests -q
python3 -B -m unittest discover -s tests -p 'test_*rum*' -q
python3 -B -m unittest discover -s tests -p test_skill_registry.py -q
python3 -B tests/test_installers.py
git diff --check
```

发布包测试在临时 Git 快照中使用实际 manifest 和构建器，核对 tar/zip 一致性和白名单，删除快照后运行解包脚本。它不再复制源码测试套件冒充发布包验证。安装器测试需要允许本机回环 HTTP 监听。

## 历史报告

| 报告 | 内容 |
|---|---|
| [首次接入评估](reports/2026-10-13/report.md) | 安装、真实 SDK 与模拟平台的初始结果 |
| [首次修复验证](reports/2026-10-13-fixes/report.md) | React Native 错误处理、类型检查、配置恢复 |
| [URL 策略](reports/2026-10-13-url-policy/report.md) | 区分普通 SDK 字段和实际敏感信息暴露 |
| [完整工程验收](reports/2026-10-13-platform-acceptance/report.md) | Vue、Android、MiniApp 工程与平台边界 |
| [真实测试站续验收](reports/2026-10-13-live-continuation/report.md) | 换码、HTTP 上报、人工确认入库及微信运行调查 |
| [微信升级复查](reports/2026-10-13-miniapp-upgrade/report.md) | 服务端口恢复和无 RUM 页面基线 |
| [MiniApp 运行时续验收](reports/2026-10-14-miniapp-runtime/report.md) | 真实 GUI 控制台、非灰度基础库对照、页面基线失败与清理证据 |
| [MiniApp 真机验收](reports/2026-10-14-miniapp-phone/report.md) | 手机预览基线、域名拦截恢复、真实 SDK 核心事件及非空载荷隐私检查 |
| [Skill 收敛评估](reports/2026-10-14-slim/report.md) | 按需读取、运行包白名单、五类使用场景 |
| [第一轮评审修复](reports/2026-10-14-review-fixes/report.md) | 依赖阻塞、地址规范化、按批次外部配置授权 |
| [交付修复与收敛](reports/2026-10-14-delivery-fixes/report.md) | JSON 路径消费、旧入口预检查、UniApp 归属与统一交付口径 |

历史测试数量只对应各报告当时的源码。公共发布以发布流程成功及入口回读为准，不能由本地测试结果推断。
