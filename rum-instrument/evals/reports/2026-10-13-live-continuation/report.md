# RUM 真实测试站与微信平台续验收

日期：2026-10-13。继续使用仓库当前 rum-instrument；没有覆盖本机已安装 Skill、提交或发布。本报告续接 [全平台验收报告](../2026-10-13-platform-acceptance/report.md)，此前的证书和服务端口阻塞记录保留为历史。

最新结论：用户于 2026-10-13 自行核对后台并确认“我验证了数据存在”。本次 Web 基础 RUM 的真实换码、接入、上报与后台数据存在性已完成验证，其中后台环节为用户人工确认，非 Agent 自动查询。小程序及其他平台的未完成项不因此变更。

## 已完成的真实链路

用户明确授权仅内置测试站绕过 CA 校验后，schema v3 计划记录 testing-site/disabled-TLS 授权，plan 校验通过。helper 经隐藏 stdin 消费一次临时码，成功解析 `new_skill_001`，Client Token 直接保存到临时工程被 Git 忽略的 0600 配置文件，服务端 API Key 仅存于 helper 内存。随后实施状态校验通过，应用初始化补丁已落地；再次 `--resume` 返回 reused，没有重新换码。

完整 Vue 工程的严格 vue-tsc / Vite production build 通过。第一次构建因 npm 子进程继承系统旧 Node 而失败；为构建进程指定既有 Node 24 PATH 后通过，没有修改系统默认 Node。见 [控制面回执](web/control-plane-receipt.json)、[构建日志](web/real-build.log)。真实 Token、授权码、状态完整性数据和包含 Token 的 dist 不归档。

真实 Chrome 对该测试 DataWay 的最终一轮观察：4 次 POST `/v1/write/rum` 均收到 HTTP 200；请求内含 4 View、7 Resource、1 Error，应用 ID 正确，本地草稿 canary 未进入载荷。配置、Vue 挂载、SPA、业务请求及原错误处理器等 10 项应用检查通过。Replay 和 Trace 未开启。详见 [安全浏览器记录](web/remote-browser-results.json)、[复核结论](web/assessment.json)。这些事件数表示浏览器发出的数据，不表示已从后台查询到这些数据。

## 没有抹除失败或夸大 HTTP 200

首轮测试误用对象引用比较 SDK getInitConfiguration 的两次返回值，SDK 实际返回 deepClone；改为比较对应配置值后通过。首轮 Error 未检出，延长受控错误后的等待后真实上报中检出 Error。各轮失败记录保留。

最终浏览器脚本仍因“HTTP 成功必须没有任何 requestfailed”这个合并断言退出 1：收到 HTTP 200 后 Playwright 记录 ERR_ABORTED，无法读取响应体。不能直接忽略它，也不能机械判全部上传失败。

独立本地调查做了 12 个 SDK/原生 fetch 对照及 2 个主动读 body 对照：未消费的空 HTTP 200 可精确复现相同 ERR_ABORTED；主动读取同一空响应体则正常完成。SDK 没有在收到 200 后主动 abort/cancel，各回调报告 200、传输状态 UP。带 body 与真实断连的对照结果不同。完整证据见 [传输调查](transport/report.md)、[结果](transport/results.json)、[主动读取对照](transport/native-read-results.json)。远端响应体长度未确认，此对照是有力解释而非“远端必为空”的证明。

因此将结果分别记为：接收端 HTTP 2xx=4/4、响应体完成情况未确认、后续 ERR_ABORTED=4；远端数据存在性随后由用户人工确认。保留原始 exit 1 和当时未验证入库的浏览器记录，另存复核及人工确认结果；未修改 SDK 或强行让原断言变绿。

## 后台入库核对

目标为用户指定测试控制台工作空间 `wksp_4b57c7bab38e4a2d9630f675dc20015d`，应用 `new_skill_001`。本机 Owl 杭州测试站账号返回 5 个可访问工作空间，其中不含目标；没有查询其他空间的 RUM 数据，见 [访问检查](owl-access.json)。

浏览器控制台跳转到 `testing-ft2x-auth.dataflux.cn` 时，自动审批以认证域尚未获明确授权为由拒绝访问。用户随后选择自行核对，Agent 未继续访问认证站或绕过拦截。

用户于 2026-10-13 明确反馈“我验证了数据存在”，据此将目标应用的后台数据存在性标记为人工确认通过，见 [人工核对回执](web/manual-ingestion-confirmation.json)。用户未提供逐类事件数量、查询时间范围或截图，因此不声称后台数量与浏览器发送数量逐条一致，也不将该结果标为 Agent 自动查询通过。

## 微信运行验证

用户开启服务端口并登录后，官方 CLI 已成功打开隔离项目，真实 miniprogram-automator 返回工具版本 1.02.1911180、基础库 3.17.4。已从“服务端口关闭”推进到“工具运行兼容性”问题。

模拟器页面空白，调试器出现 Unexpected token . / wx is not defined，App.getCurrentPage 超时；完全不含 RUM 的纯页面对照也失败。仅写本地 libVersion=2.11.1 及换新隔离项目路径未改变实际加载基础库。不能将其归因为 SDK 故障，更不能以编译通过代替真实页面与事件验证。见 [平台报告](miniapp/report.json) 和 runtime 日志。

本地接收器已实际启动但收到 0 POST，View/Resource/Error/Action、重复初始化和隐私测试均未执行。进一步尝试通过项目级 GUI 选择兼容基础库时，CLI 停在 starting ide，CUA 两次连接超时，无法进入设置页面；只读检查表明工具主进程未运行。该次修复没有实际执行，不能认定基础库切换成功；需可正常启动的兼容开发者工具环境后继续。测试不上传预览、不切换账号、不修改用户项目；用户自行开启的服务端口与登录状态保持原状。

## 当前边界

本次关闭证书校验只作用于已授权的内置测试 AI API 调用，没有修改全局 TLS、安装系统证书或关闭其他站点校验。真实链路是用户指定测试环境，测试数据为合成事件。Apple/跨端原生/其他平台及 Linux/Windows 的缺口仍按前报告保留，本次结果不替代其验收。
