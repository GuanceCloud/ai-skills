# Web URL 策略修正与复测

本次修正的是 Skill 的适用条件，并未修改 SDK。**普通 Web／Flutter Web 接入不再因为标准 URL/query/fragment 字段存在而被阻塞，也不再要求用户额外确认或证明所有 URL 都无风险。**

## 修正范围

- `SKILL.md` 和 `references/web.md`：按官方标准行为完成基础接入。只有明确的项目过滤要求无法满足、已确认的敏感数据暴露或实际构建/应用行为故障，才阻塞受影响范围。
- `references/privacy-security.md`：区分 SDK 标准字段与自行添加的自定义采集。仍禁止把凭据、请求体等加入自定义上下文，并检查维护态认证/路由代码中的具体风险。
- `references/validation.md`：每条隐私断言必须关联实际要求或具体敏感数据流；普通分页、排序参数出现不算失败。需要过滤时仍必须验证非空最终载荷和派生字段。
- `evals/evals.json` 与两个新 Web fixture：保留普通接入、明确禁止 query 值、授权回调保留令牌三个长期评估场景。
- README 及两份历史报告/摘要：加上明确的结论更正。原载荷、退出码和失败断言保持不变。

## 为什么更正之前的结论

之前的探针验证了：3.3.21 中仅清洗 `view.url` 不能清洗 `view_url_query` 等派生字段。这是过滤能力的限制；它不足以证明基础 RUM 不能接入。先前将“所有原始查询参数不得出现”额外设为统一验收条件，造成对全部 Web 应用的过度阻塞，该结论已撤回。

更正不等于声称 SDK 已具备原先缺失的过滤能力，也不把旧测试的失败改成通过。当前分别验证普通接入，以及较严格条件真正适用时的处理。

## 独立 Agent 与真实 SDK 验证

两名独立评估者使用相同的最新运行态 Skill，未读取旧测试结论或彼此计划。三种场景都未向用户补问或要求常规确认。

| 场景 | 实际结果 | 证据 |
|---|---|---|
| 普通商品目录，分页/排序参数 | 首次计划与实施校验均 exit 0；实际完成接入；真实 SDK 3.3.21 + Chrome 的 15 项断言通过，2 个非空载荷、17,623 字节；重复执行源码不变 | [报告](ordinary/report.md)、[浏览器结果](ordinary/smoke-results.json)、[补丁](ordinary/applied.patch) |
| 项目明确禁止所有 query 值 | 计划可以记录，实施门禁拒绝；实际载荷证明清洗可见 URL 后派生字段仍保留禁止值；应用未新增初始化 | [A 决策](restricted/A-first-decision.json)、[门禁](restricted/A-implement-gate.json) |
| 认证回调将 access_token 留在 URL | 根据维护态代码确认具体凭据流，使用合成令牌验证派生字段行为；应用未新增初始化，受影响范围仍阻塞 | [B 源码流证据](restricted/B-auth-source-flow.json)、[门禁](restricted/B-implement-gate.json) |

普通场景验证了单次初始化、View/Resource/Error、按钮分页、原样资源请求、原错误处理器调用、SDK 加载失败降级，以及没有额外启用 Replay/Trace。第一次 smoke 因测试选择器选错脚本失败，保留原始记录；只修正选择器，应用接入代码未变，重跑通过。依赖复用已下载的官方包，未在本轮重新做 fresh npm install。

限制场景有 4 轮真实浏览器探针，每轮捕获 8–9 个事件，均含非空 View/Resource/Error，导航和业务请求不变。**过滤断言仍 exit 1，阻塞决策验证 exit 0**，没有把过滤失败算作接入成功。[原始断言](restricted/evidence/assertions.json)、[完整说明](restricted/report.txt)。B 的浏览器探针隔离验证 URL 字段行为，认证函数另外用维护态源码和独立合成调用验证；没有声称执行完整真实认证系统。

## 回归与测试边界

工作树 RUM 回归 170/170、可移植性 1/1、注册表 1/1，共 **172 项通过**。新增最后一个评估 fixture 后，又重跑了包含 fixture 路径检查的 13 项 Skill 契约用例；它们是上述回归的子集，不重复计数。Skill 格式校验及 `git diff --check` 通过。

运行态 Skill、引用、脚本、资产共 24 个文件从当前仓库复制到隔离评估目录，逐文件 SHA-256 一致，见 [source-sha256.json](source-sha256.json)。本次没有更改安装器，不重复声称执行了跨操作系统安装验收。没有修改本机已安装 Skill、第三方 SDK，没有使用真实授权码或真实接收端，没有提交或发布。

真实 SDK + Chrome 的本机模拟上报与实际服务端入库分别报告；本次不新增原生平台构建或远程入库结论。
