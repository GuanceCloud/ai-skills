# MiniApp 真机预览验收

日期：2026-10-14。延续此前模拟器验收，使用临时隔离工程、微信真机预览与真实 `@cloudcare/rum-miniapp@2.2.20`。用户操作手机，Agent 检查局域网接收器保存的最终 SDK 载荷。

## 结论与提交边界

**本轮 MiniApp 核心信号及指定隐私 canary 检查通过，可以作为当前 Skill 修复提交的验收证据。** 先前模拟器失败仍保留，真机路线没有修复模拟器。

这不等于所有平台、生产环境或完全无人值守接入已验收。MiniApp 的真实观测云入库、生产合法域名校验与重复实施接入的真机幂等测试尚未完成；SDK 初始化顺序及模块 guard 已从源文件确认，但没有真机 init 调用次数探针。此前脚本回归与本轮真机证据应分别理解。未执行 Git 提交、推送或发布。

## 实际证据

| 检查 | 结果 |
|---|---|
| 无 RUM 手机基线 | 用户确认页面点击计数正常 |
| 构建与预览 | 官方 `build-npm` 返回 0，无构建 warnings；SDK 工程预览返回 success，包体 311156 字节 |
| 首次网络 | `request:fail url not in domain list`；接收器无手机健康请求、无 RUM 数据 |
| 恢复 | 用户在隔离预览开启手机调试、重新进入并完成步骤，反馈网络正常 |
| 真实 SDK 载荷 | 3 批：Action 25、Resource 1、Error 1、View 3 |
| View / Action 身份 | 3 条 View 为同一 view ID 的更新；25 条 Action 对应 25 个唯一 ID，不把周期 View 更新误判为重复初始化 |
| 资源 | 手机健康请求 1 次，载荷资源状态 200；URL 的查询 canary 被过滤 |
| 错误与交互 | 受控测试错误及错误栈存在，错误后还有交互事件 |
| 隐私 | 非空最终载荷均未出现 `RUM_PHONE_QUERY_CANARY`、`RUM_PHONE_INPUT_CANARY`；输入步骤完成依赖用户反馈，没有采集原始输入作证明 |
| 追踪头 | 接收器检查到的 trace / x-datadog / x-b3 / uber-trace 前缀请求头为空；只覆盖该测试请求 |
| 配置 | 载荷 SDK 2.2.20、service miniapp、env develop、合成 application ID 符合隔离工程配置 |

[机器结果](result.json)、[载荷字段摘录](logs/events-selected.json)、[首次域名拦截](logs/phone-network-result.json)、[用户基线反馈](logs/phone-baseline-result.json)、[构建预览摘要](logs/build-and-preview.json)。原始抓包保留在本机临时目录，仓库仅归档必要字段；设备信息和用户标识未归档，session/view/action ID 只保留摘要，局域网 IP 已替换。机器结果保留原始文件 SHA-256，摘要不替代原始抓包。

Action 包含 SDK 的启动、启动尝试、脚本注入和按钮点击，25 条不能解释为用户点击恰好 25 次。接收器启动后的第一次健康请求来自电脑自检，已经从手机请求数量中扣除。SDK 前一次被域名拦截产生的空载荷没有被计为隐私通过。

## 修复与复跑

MiniApp 适配指引现已明确：模拟器基线失败时可以使用已获授权的手机预览；先做无 RUM 基线，再验证网络。桌面 `urlCheck: false` 不代表手机可访问，出现域名拒绝时，在隔离开发预览开启手机调试并重新进入后先重试网络。该例外不能替代生产 HTTPS 接收域名与白名单设置。

归档 [工程](project/app.js) 保留真实初始化与测试页面，配置样例不含凭据。复跑需要填写自己的微信 AppID，并创建本地 `config/rum.local.js`，将 applicationId 设为隔离标识、datakitOrigin 设为手机可达的测试接收器；本轮接收器仅模拟 DataKit 的接收接口，不是真实 DataKit 服务。执行锁定依赖安装与官方 npm 构建，生成手机预览码，依次请求资源、点击交互、触发错误、输入页面 canary、再次交互并停留 30 秒后退出。接收器需记录非空最终载荷和业务请求追踪头，再做上述检查。

本轮验收结束后已关闭临时接收器。测试工程保留在本机 `/private/tmp/rum-miniapp-phone-20261014`，未修改用户业务工程、远端白名单或全局安全设置。用户可关闭该预览的手机调试模式。微信预览服务仅用于生成预览版本，没有上传体验版或正式发布。

## 本轮文档检查

新增真机指引后，Skill 契约测试 13 项通过，归档 11 个 JSON 文件可解析，报告和索引本地链接有效，`git diff --check` 通过。首次文档检查发现品牌中立措辞不符合契约，改为 backend 后复跑通过；未修改既有业务脚本，因此没有重复执行先前全部 233 项回归。

Skill 格式校验器最初缺少 PyYAML；仅在临时目录补充 PyYAML 6.0.3 后重跑，结果为 `Skill is valid!`，未更改仓库依赖或全局 Python 环境。
