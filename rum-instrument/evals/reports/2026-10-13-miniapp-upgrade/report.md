# 微信开发者工具升级后复验

日期：2026-10-13。使用仓库最新 rum-instrument，运行态文件哈希与此前验收一致；未修改本机安装的 Skill。

## 有效微信 AppID 后的复验（当前结论）

用户提供实际微信 AppID 后，服务端口与 AppID 门槛均已通过。官方 `auto --project ... --auto-port 19534 --trust-project` 最终成功，自动化端口可连接。使用的仍是仓库当前 Skill，未修改本机已安装的 RUM Skill。只更新隔离基线及隔离 RUM 工程的微信 AppID，没有更换 RUM Application ID、消费授权码或上传发布。

| 检查 | 结果与证据 |
|---|---|
| 新版 IDE / 微信 AppID / 自动化连接 | 通过；官方 CLI 返回 `autoPort: 19534` |
| 不含 RUM 的 App 生命周期 | `App.onLaunch` 执行一次；真实基础库 `3.17.4` |
| 纯页面建立与交互 | **失败**；`getCurrentPages()` 返回空数组，截图为空白；`currentPage` 与 `reLaunch` 返回 `Cannot destructure property 'rawPath' of 't.getPageMetaByWebviewId(...)' as it is null.` |
| 页面配置 | 运行时包含 `pages/index/index` 和对应 WXML/JSON，仍未产生页面实例 |
| 官方诊断 CLI | 状态检查成功：未登录过期、Skill 版本一致、无需 CLI Token；实际读取 console 和打开页面的调用另行等待客户端授权，最终超时，未取得错误日志 |
| 显式打开完整项目窗口 | 命令最终退出 255：`wait IDE port timeout` |
| RUM 初始化、View/Resource/Error/Action、幂等及最终载荷隐私 | **not_run**；不得把空载荷计为隐私通过 |

当前已排除 AppID 无效这一前置阻塞；故障发生在无 RUM 的基线，因此没有证据将其归因于 RUM SDK。尚不能区分工具状态异常与页面运行时兼容问题，也不声称升级已修复全部旧版问题。另一次 CUA 连接等待约 802 秒后返回未找到运行中的应用，未发生 GUI 操作；后续停止使用该诊断路径。

保留了第一次 55 秒启动超时、过早连接失败、页面断言失败及各次 CLI 错误。测试脚本对断言失败返回非零；CLI 自身的成功退出码不会覆盖其错误输出。原始 `baseline-before-cli-ready.json` 是启动前连接失败，`baseline-result.json` 是就绪后的页面失败，不能混为同一次检查。

已停止挂起的测试 CLI 85670；另一个打开项目命令 87554 在清理前自行以 255 退出，没有终止 IDE。未启动接收器，19529/19532 无监听；保留隔离基线的 19534 自动化端口及 IDE 20166 供后续诊断。未改动服务端口设置、登录态或其他用户项目。

下一步建议先保存微信工具内的工作并重启工具，再重新打开该隔离基线、执行编译，确认首页可见；这是针对已观察到 IDE 连接超时的恢复尝试，并非已证实的根因修复。基线通过后再执行真实 SDK 事件、载荷和幂等验收，无需重新提供 AppID 或 RUM 参数。

证据：[启动成功日志](logs/authorized-appid/baseline-trusted-launch.log)、[页面断言结果](logs/authorized-appid/baseline-result.json)、[运行时诊断](logs/authorized-appid/baseline-diagnostic.json)、[页面配置](logs/authorized-appid/baseline-runtime-config.json)、[空白页截图](logs/authorized-appid/baseline-diagnostic.png)、[读取 console 失败](logs/authorized-appid/simulator-errors.json)、[项目窗口超时](logs/authorized-appid/open-baseline-window.log)、[清理记录](logs/authorized-appid/cleanup.json)。探针源文件同目录保存；复跑前按文件内依赖路径将其放回隔离测试目录。历史 Web 入库人工确认结论不变。

## 前次无效 AppID 复验（历史记录）

将用户提供的 `wx_skill_001` 仅写入隔离纯页面基线的微信工程配置，执行官方 `cli auto`。微信工具返回 **code 10：AppID 不合法，invalid appid**；这次仍是进程退出码 0、实际操作失败。未启动页面或 RUM，没有发送遥测或消耗授权码。

当前需要微信平台实际签发、当前登录账号有开发权限的测试 AppID，或本机已有可运行项目的路径。RUM Application ID 与微信 AppID 是独立字段；仅给自定义名称加上 wx 前缀不能建立微信应用。用户无需重新提供 RUM 连接参数。

证据：[实际 CLI 错误](logs/supplied-appid/baseline-launch.log)、[结构化结果](logs/supplied-appid/launch-result.json)。

## 服务端口开启后的复验

用户已开启新版服务端口。官方 CLI 能连接 IDE，启动日志确认服务监听在本机；此前的 `IDE service port disabled` 阻塞已解除。

不含 RUM 的隔离基线仍未进入页面执行。新版工具对工程的 `touristappid` 返回 **APPID_ERROR：不存在此 AppID 请检查后重新输入**。只读核对安装包内 `formatProject` 实现，确认它在启动前明确拒绝空 AppID 与游客 AppID；未修改工具代码或绕过该检查。该结果不能归因于 RUM SDK，也不能据此判定升级是否已解决旧版的基础库语法错误。

注意：此次官方 CLI **退出码为 0，但输出包含 APPID_ERROR**，且自动化端口没有监听；因此不能把零退出码当作成功。纯页面、SDK 初始化、View/Resource/Error/Action、重复初始化与最终载荷隐私检查均为 **not_run**，不能用零上报通过隐私断言。

下一步仅需当前登录账号有开发权限的微信小程序测试 AppID（wx 开头），或本机已有可运行测试项目路径。它与观测云 RUM Application ID `new_skill_001` 不同。后续只在隔离工程中进行本地模拟器测试，不上传或发布，也无需再次提供 RUM 授权码。运行顺序：纯页面行为基线 → SDK 初始化和真实信号 → 聚合断言及最终载荷检查 → 幂等复验。

本轮未启动接收器，未发送 RUM 数据、消费凭据或更改 IDE 设置；19529、19532、19534 均无监听，保留用户开启的 IDE。先前 Web 后台数据存在性的人工确认不受影响。

证据：[开启后的 CLI 日志](logs/service-enabled/baseline-launch.log)、[启动结果](logs/service-enabled/launch-result.json)、[官方 AppID 校验片段与哈希](logs/service-enabled/appid-validation-evidence.json)、[端口检查](logs/service-enabled/ports.json)、[此前状态](result-before-service-enabled.json)。

## 服务端口开启前的历史记录

升级已识别：官方 CLI 改用 `auto --project <path> --auto-port <port>`，不再使用旧版 `--auto`。安装元数据确认新版产品版本为 2.02.2609231；Info.plist 的 36.6.0 是运行时版本，不能混为产品版本。尚未取得新的 Tool.getInfo。

第一次打开不含 RUM 的隔离基线时，CLI 因用户配置目录下 Default/.cli 缺失而退出 255。随后官方应用进程已运行，Default 目录也已生成；没有手工创建或改写该内部目录。

再次执行新版官方 CLI，返回 **246：IDE service port disabled**。以 TTY 再试也得到同样结果；虽然错误提示写了可输入 y，实际进程直接退出，没有等待输入，不能据此声称服务端口已开启。

当前卡点已变为新版工具的服务端口关闭；这次尚未进入纯页面生命周期，因此无法重新验证此前基础库语法错误是否解决，也没有执行 RUM 初始化、View/Resource/Error/Action、幂等或隐私检查。不把上轮编译结果当成本轮运行成功。

两次 GUI 连接未能取得可操作界面，其中一次长时间等待后被 Agent 中断；没有点击、改动开关或登录状态，没有启动接收器或新的自动化服务。已启动的官方 IDE 保持运行。

需要在新版微信开发者工具的“设置 → 安全设置 → 服务端口”开启服务端口，再继续纯页面和完整 RUM 工程验收。这是实际 CLI 返回的必要设置，不是再次索要接入参数。没有消耗授权码或向远端发送数据。

证据：[机器结果](result.json)、[初次启动日志](logs/baseline-launch.log)、[初始化后重试日志](logs/baseline-launch-after-init.log)、[新版 CLI 帮助](logs/auto-help.log)、[Skill 来源](skill-source.json)。此前真实 Web 入库的人工确认不受此次小程序环境阻塞影响。
