# 独立 Web forward-test

最新 Skill 成功安装至隔离目录，并按发现、准备、计划、真实 SDK 验证流程执行。应用基础 RUM 接入未完成：Browser RUM 3.3.21 无法通过公开 beforeSend 清除派生 URL 查询字段。官方 npm latest 查询仍为 3.3.21，没有已验证的兼容修复版本。

- 补问 0 次，常规确认 0 次。
- 首次计划校验 exit 1：评估者沿用示例 approved，同时将目标标为 blocked；校验器正确拒绝。保留原始计划后改为 pending + 具体 blocker，第二次及最终校验 exit 0。
- 实施门禁 exit 1，拒绝受阻目标；未尝试绕过。
- 新增隔离诊断文件及内部计划，应用受维护源码、依赖、启动入口均未改变；git diff 为空。
- 实际官方 SDK bundle + 无头 Chrome 捕获 3 次上报，含 View、Resource、Error、Long Task；非空载荷中初始 query/hash、资源 query、history query canary 泄漏，probe exit 1。按钮、请求和导航行为保持。
- 无真实授权码、控制面调用、SDK 修改、远程上传或部署。Replay 关闭；DataKit 仅由浏览器测试路由模拟，未证明远端入库。

产物哈希见 logs/installed-source-sha256.json；安装回执见 logs/install-receipt.json；原始失败及修正计划校验、浏览器命令退出码、原始合成载荷全部保留在 logs。

模拟交付结论：当前接入因 SDK URL 隐私兼容性限制受阻，未启用采集。需要官方支持的过滤修复通过真实载荷验证后继续，不要求用户提供更多连接字段或批准绕过限制。
