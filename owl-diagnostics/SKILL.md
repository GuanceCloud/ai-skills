---
name: owl-diagnostics
description: 用 owl CLI 统一处理观测云查询、诊断、排障、根因分析、影响评估和结构化报告，覆盖意图路由、DQL 校验和跨域取证。适用于最近 15 分钟、1 小时、24 小时发生了什么，`errors` 分类，`event`、`APM`、`metric`、`network`、日志、前端监测、性能剖析、基础设施、Pipeline、LLM 应用查询，以及顾问式诊断分析。先看真实工具参数，再按意图路由；优先只读，DQL 先校验，查询类任务默认落盘。
---

# Owl Diagnostics

统一使用 `owl` 回答观测云相关问题：既覆盖“最近发生了什么”的时间窗摘要，也覆盖诊断、排障、根因分析、影响评估和必要的结构化报告。

本 skill 统一覆盖时间窗摘要、诊断分析、DQL 规范和跨域取证要求。

## 硬规则

- 每个任务先执行一次：`owl -h`
- 如需校验环境或工具清单，再执行：`owl version`、`owl list -f json`
- 调用具体 tool 前，先执行 `owl show <tool>`；需要精确参数时优先 `owl show <tool> -f json`
- 先按用户意图选择最贴近的数据域 tool，不要默认把“平台链路”缩窄成 trace
- 优先只读工具；`create/replace/update/add/upsert/receive` 一类写工具必须有明确用户意图
- 结果可能分页；命中 `page_size`、`limit`、`SLIMIT` 或明显裁剪时，先说明再决定是否翻页
- DQL 必须先 `check_dql`，确认 `valid=true` 后再 `query`
- 回答里先写事实，再写推断；没有跨域证据时，只能写 `suspected`，不能写成已确认根因
- 只要任务涉及查询结果交付，最终必须输出结构化报告，不能只给零散原始输出
- 对查询类任务，最终报告默认必须落盘；只有纯写操作回执可以不落盘

## 模式判断

先判断任务属于哪一类，再决定查询深度和最终格式。

### 1. 快速查询摘要

适用于：

- 最近 15 分钟 / 1 小时 / 24 小时发生了什么
- 某服务有没有错误
- 最新 fatal event 是什么
- 某类错误有多少、按服务怎么分布

规则：

- 输出仍然是结构化报告，只是比完整诊断短
- 可优先包含：`范围`、`结论`、`证据`
- 如果窄问题暴露出更大问题面，明确指出，并建议切到深入诊断
- 仍然需要落盘

### 2. 分析与诊断

适用于：

- analyze / troubleshoot / investigate
- root cause analysis
- classify / summarize / compare
- impact assessment
- diagnosis / judgment / advisory

规则：

- 最终回复必须是简洁报告，不能停在原始计数
- 复杂问题同时写出：已确认事实、尚未证实部分、下一步建议
- 根因判断至少要有跨域证据：例如 errors/traces 与 logs、metrics、events、infrastructure 中至少一个域互相印证
- 最终报告必须落盘

### 3. 操作或变更

适用于用户明确要求修改对象，例如：

- create / replace dashboard
- update monitor
- add / update error comment
- send external monitor event

规则：

- 先确认这确实是写操作需求，不要把查询任务误做成变更
- 最终输出是执行回执，不是诊断报告
- 必须说明：目标对象、执行动作、结果、验证状态、风险或回滚点
- 若用户同时要求附带报告，再额外落盘

如果任务同时包含查询和诊断，按“分析与诊断”处理。

## 选路顺序

1. 初始化：`owl -h`；必要时补 `owl version`、`owl list -f json`
2. 判断模式：快速查询摘要 / 分析与诊断 / 操作或变更
3. 按意图选择最贴近的数据域 tool
4. 调用前先看 `owl show <tool>`
5. 如需 DQL，先做 namespace / source discovery，再 `check_dql`，最后 `query`
6. 结果不足以支持结论时，再跨域补证据，不要一开始就把所有域都扫一遍
7. 先生成最终报告，再落盘，再回复摘要和路径

## 默认选路

- 错误追踪问题：`owl.errors.list`
- 告警、未恢复事件、监控事件：`owl.event.list`，必要时补 `owl.event.get`
- `APM`、链路、下游依赖、慢请求：`owl.apm.list`，再进命名空间 `T`
- 指标、`CPU`、内存、延迟、重启、趋势：`owl.metric.list`，再进命名空间 `M`
- 网络、`DNS`、丢包、端口、连接：`owl.network.list`，再进命名空间 `N`
- 日志或日志错误分类：`owl.data.query`，命名空间 `L`
- 前端监测、页面影响、页面报错、资源加载：`owl.rum.list`，再进命名空间 `R`
- 性能剖析、火焰图、`CPU` 热点：`owl.profile.list`，再进命名空间 `P`
- 主机、容器、进程：`owl.infrastructure.list` / `owl.infrastructure.get`；为空或超时时再交叉看 `O` 或 `M`
- Pipeline 解析、缺字段、脱敏、数据丢弃：`owl.pipeline.list`
- `LLM` 应用清单或总览：`owl.llm.list`，必要时进命名空间 `LLM`
- 复杂聚合或跨域查询：`owl.data.show_dql_namespace` -> discovery tool -> `owl.data.search_dql_docs` -> `owl.data.check_dql` -> `owl.data.query`

## DQL 路径

- 简单已知模式：必要时 `show_dql_namespace` -> 域或数据源发现 -> `check_dql` -> `query`
- 新语法、复杂过滤、函数、校验失败：`owl.data.show_dql_namespace` -> 发现工具 -> `owl.data.search_dql_docs` -> `owl.data.check_dql` -> `owl.data.query`
- 发现顺序优先 `source` / `index`，再看 `field`；不要把大段字段结构整块贴进答案
- `owl.data.query` 常返回数据文件路径；必须继续读取文件内容，并检查内部 `success` / `error`
- shell exit code 为 `0` 不代表查询成功

## DQL 规则

- 日志 index 必须是字符串：`L("index_name")`
- 日志数据源不确定时，从全 `source` 起步：`::*`
- `source` 名含特殊字符时加引号，例如 `T::"kodo-x"`
- 复杂日志 DQL 不要依赖 `owl.data.query --index <name>` 自动拼接，优先显式传 `query_text`
- DQL 聚合用 `BY`，不是 SQL `GROUP BY`
- 常用 trace 错误聚合：

```text
T::*:(count(*)) { status = "error" } [24h] BY service, resource, error_type
```

- 常用补样字段：`time, trace_id, service, resource, status, error_type, error_message, duration`
- 网络常见字段：`src_ip`, `dst_ip`, `dst_port`, `transport`, `retransmits`, `rtt`, `bytes_read`, `bytes_written`
- 前端监测常见字段：`app_id`, `app_name`, `view_name`, `error_message`, `resource_status`, `session_id`, `userid`, `browser`, `os`
- 空结果是有效结果；必须明确写出时间范围、查询域、空结果，不要硬编分类

## 时间范围

- 相对时间统一转换成绝对时间再汇报
- 最终答案必须写绝对时间，不只写“最近 15 分钟”
- 生成 13 位毫秒时间戳时优先用 Python，不用 `date -d` 和 `%s%3N`
- 对“recent”类问题，默认先查 `15m`、`1h` 或用户指定窗口；若无数据且问题允许扩窗，再查 `24h` 并明确说明

可直接用：

```bash
python3 - <<'PY'
import time
now = int(time.time() * 1000)
print(now)
print(now - 15 * 60 * 1000)
print(now - 60 * 60 * 1000)
print(now - 24 * 60 * 60 * 1000)
PY
```

## 输出规则

- 不在最终答案里粘贴大段 JSON、完整 query 文件或长命令输出
- 报告或摘要都必须先写事实，再写判断
- 需要推断时明确标注：`疑似` / `推断`
- 如果 tool 失败，明确写失败点和下一步，而不是基于失败数据硬下结论
- 如果结果被采样、分页或裁剪，必须说明

## 回复形态

可以参考下面的模板组织答案，但不是强制固定格式。如果更短、更直接的结构更清楚，可以调整；前提是不丢失事实、证据和结论。

### 快速查询摘要模板

```md
**范围**
- 时间范围：`<绝对开始时间>` 到 `<绝对结束时间>`
- 数据域：`<数据域>`

**结论**
- `<直接结论>`

**证据**
- `<关键证据>`

**说明**
- `<采样 / 限制 / 空结果 / 建议进一步诊断>`
```

### 诊断分析模板

```md
**范围**
- 时间范围：`<绝对开始时间>` 到 `<绝对结束时间>`
- 数据域：`<日志 / 错误 / 事件 / APM / 指标 / ...>`
- 使用工具：`<工具1>`、`<工具2>`
- 说明：`<分页 / DQL / 空结果 / 截断结果>`

**发现**
- `<发现 1>`
- `<发现 2>`
- `<发现 3>`

**证据**
- `<维度>`：`<数量 / 趋势 / 代表性信息>`
- `<维度>`：`<数量 / 趋势 / 代表性信息>`

**判断**
- 事实：`<仅写事实>`
- 相关性：`<看起来有关联的内容>`
- 推断原因：`<疑似原因或已确认原因>`
- 置信度：`<高 / 中 / 低>`，并说明原因

**后续建议**
1. `<下一步>`
2. `<下一步>`
3. `<下一步>`

**缺口**
- `<缺失证据 / 工具失败 / 未验证假设>`
```

### 操作回执模板

```md
**目标**
- `<对象>`

**动作**
- `<执行了什么变更>`

**结果**
- `<成功 / 失败 / 部分完成>`

**验证**
- `<如何验证>`

**风险**
- `<回滚说明或剩余风险>`
```

### 空结果模板

```md
**范围**
- 时间范围：`<绝对开始时间>` 到 `<绝对结束时间>`
- 数据域：`<数据域>`
- 使用工具：`<工具列表>`

**发现**
- 该时间范围内未查询到匹配数据。

**说明**
- `<是否扩窗 / 是否分页 / 是否做了备选域检查>`
```

## Errors 分类

当主要数据来自 `owl.errors.list` 时，至少回答：

- 有几类错误
- 每类多少条
- 集中在哪些服务 / 资源
- 最近一次出现时间
- 代表性报错
- 是否有共享 `trace_id`，从而可能属于同一条链路

可直接使用：

```bash
owl exec owl.errors.list --start_time <START_MS> --end_time <END_MS> --page_size 100 \
  | python3 scripts/classify_owl_errors.py
```

## 报告输出与落盘

默认报告格式见：

- `references/report-format.md`
- `references/best-practices.md`
- `references/report-example.md`

生成报告时，默认补充以下元数据：

- 生成时间
- 主机名
- 当前用户
- 问题分析开始时间
- 报告生成完成时间
- 总耗时

查询类任务的最终报告默认保存到当前工作目录下：

```bash
./owl-reports/
```

推荐文件名格式：

```text
owl-report-YYYYMMDD-HHMMSS-<user>.md
```

保存脚本：

```bash
python3 scripts/save_report.py --output-dir ./owl-reports < /tmp/owl-report.md
```

完成后必须在回复里说明：

- 已生成报告
- 报告保存路径
- 是否为 Markdown 文件

## Guardrails

- 用 `owl help exec`，不要用 `owl exec -h`
- 工具缺失、参数不匹配、输出异常，或用户明确提到最新、同步、更新时，执行：`owl sync`，再 `owl list -f json`
- `owl.monitor.list` 不是事件列表；查告警事件优先 `owl.event.list`
- 网络域没数据时要明确说没数据，不要偷偷拿日志顶替
- 基础设施工具为空时，可以交叉验证 `O` 或 `M`，但要说明这是回退检查

## 触发示例

- `用 owl-diagnostics 看最近15分钟发生了什么`
- `用 owl-diagnostics 查最近1小时 errors 并分类`
- `用 owl-diagnostics 排查 frontend-proxy 为什么 5xx 上升`
- `用 owl-diagnostics 做一次 root cause analysis`
- `用 owl-diagnostics 比较今天和昨天的服务错误影响`
- `用 owl-diagnostics 导出一份最近1小时故障报告`
