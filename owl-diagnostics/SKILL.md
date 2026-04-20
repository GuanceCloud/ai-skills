---
name: owl-diagnostics
description: 用 owl CLI 处理观测云查询、诊断、根因分析与结构化报告。先看真实工具参数，按意图选择数据域，优先只读；涉及 DQL 先校验；查询类任务默认生成并落盘 Markdown 报告。
---

# Owl Diagnostics

用 `owl` 统一处理观测云查询、诊断、排障、影响评估和报告输出。目标不是堆原始结果，而是给出可复核的事实、必要推断和落盘报告。

## 核心规则

- 每个任务先执行 `owl -h`
- 需要确认环境或工具清单时，再执行 `owl version`、`owl list -f json`
- 调用具体 tool 前，先执行 `owl show <tool>`；参数不明确时优先 `owl show <tool> -f json`
- 先选最贴近问题的数据域，不要默认把“平台链路”缩窄成 trace
- 优先只读；`create`、`replace`、`update`、`add`、`upsert`、`receive` 一类写操作必须有明确用户意图
- 涉及 DQL 时，必须先 `check_dql`，确认 `valid=true` 后再 `query`
- 命中分页、采样或裁剪时要说明，必要时继续翻页
- 先写事实，再写推断；没有跨域证据时只能写“疑似”
- 只要交付查询结果，就必须输出结构化结论；查询类任务默认还要落盘报告

## 工作流

1. 初始化：`owl -h`
2. 判断任务类型：快速摘要、诊断分析、操作回执
3. 选最贴近的数据域 tool，并先 `owl show <tool>`
4. 取数；需要 DQL 时走校验链路
5. 证据不足时再跨域补查，不要一开始全域扫描
6. 先整理最终报告，再落盘，再回复摘要和路径

## 任务类型

### 快速摘要

适用于“最近 15 分钟 / 1 小时 / 24 小时发生了什么”“某服务有没有错误”“最新 fatal event 是什么”这类问题。

要求：

- 结果仍然要结构化，至少包含 `范围`、`结论`、`证据`
- 问题面明显扩大时，要明确提示切到深入诊断
- 仍然需要落盘

### 诊断分析

适用于 classify、summarize、compare、troubleshoot、investigate、root cause analysis、impact assessment 等问题。

要求：

- 不能停在原始计数，必须形成结论
- 同时写出已确认事实、尚未证实部分、下一步建议
- 根因判断至少要有跨域证据，例如 errors/traces 与 logs、metrics、events、infrastructure 中至少一个域互相印证
- 必须落盘

### 操作回执

适用于用户明确要求执行变更，例如 create/replace dashboard、update monitor、add error comment、send external monitor event。

要求：

- 先确认这是写操作，不要把查询任务误做成变更
- 最终交付执行回执，不是诊断报告
- 必须说明目标对象、执行动作、结果、验证状态、风险或回滚点
- 如果用户同时要求分析，再额外生成并落盘报告

## 默认选路

- 错误分类、错误追踪：`owl.errors.list`
- 告警事件、未恢复事件、监控事件：`owl.event.list`，必要时补 `owl.event.get`
- `APM`、链路、下游依赖、慢请求：`owl.apm.list`
- 指标、`CPU`、内存、延迟、重启、趋势：`owl.metric.list`
- 网络、`DNS`、丢包、端口、连接：`owl.network.list`
- 日志或复杂日志查询：`owl.data.query`，命名空间 `L`
- 前端监测、页面影响、页面报错、资源加载：`owl.rum.list`
- 性能剖析、火焰图、`CPU` 热点：`owl.profile.list`
- 主机、容器、进程：`owl.infrastructure.list` / `owl.infrastructure.get`
- Pipeline 解析、缺字段、脱敏、数据丢弃：`owl.pipeline.list`
- `LLM` 应用清单或总览：`owl.llm.list`
- 复杂聚合或跨域查询：`owl.data.show_dql_namespace` -> discovery -> `owl.data.search_dql_docs` -> `owl.data.check_dql` -> `owl.data.query`

补充约束：

- `owl.monitor.list` 不是事件列表，查告警事件优先 `owl.event.list`
- 基础设施工具为空或超时时，可以回退检查 `O` 或 `M`，但要明确说明
- 网络域没数据时要直接说明，不要偷偷拿日志顶替

## DQL 规则

- 典型链路：discovery -> `check_dql` -> `query`
- 新语法、复杂过滤、函数不确定、校验失败时，再补 `owl.data.search_dql_docs`
- `owl.data.query` 返回文件路径时，必须继续读取文件内容，并检查内部 `success` / `error`
- shell exit code 为 `0` 不代表查询成功
- 日志 index 必须是字符串：`L("index_name")`
- 日志数据源不确定时，从全 `source` 起步：`::*`
- `source` 含特殊字符时加引号，例如 `T::"kodo-x"`
- 复杂日志查询优先显式传 `query_text`，不要依赖 `--index` 自动拼接
- 聚合用 `BY`，不是 SQL `GROUP BY`

常用 trace 错误聚合：

```text
T::*:(count(*)) { status = "error" } [24h] BY service, resource, error_type
```

常用补样字段：

```text
time, trace_id, service, resource, status, error_type, error_message, duration
```

## 时间范围

- 相对时间统一换算成绝对时间再汇报
- 最终答案必须写绝对时间，不只写“最近 15 分钟”
- 13 位毫秒时间戳优先用 Python 生成，不用 `date -d` 和 `%s%3N`
- 对 recent 类问题，默认先查 `15m`、`1h` 或用户指定窗口；无数据且问题允许扩窗时，再查 `24h`

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

## 输出要求

- 不要在最终答案里粘贴大段 JSON、完整 query 文件或长命令输出
- 报告或摘要都要先事实、后判断
- 需要推断时明确标注“疑似”或“推断”
- 如果 tool 失败，要写清失败点和下一步，不能基于失败数据硬下结论
- 空结果是有效结果，必须明确写出时间范围、查询域和空结果

### 快速摘要模板

```md
**时间范围**
- 时间范围：`<绝对开始时间>` 到 `<绝对结束时间>`
- 数据域 / 工具：`<数据域>` / `<tool>`

**结论**
- `<直接结论>`

**证据**
- `<关键证据>`
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

**证据**
- `<维度>`：`<数量 / 趋势 / 代表性信息>`

**判断**
- 事实：`<仅写事实>`
- 推断：`<疑似原因或已确认原因>`
- 置信度：`<高 / 中 / 低>`

**后续建议**
1. `<下一步>`
2. `<下一步>`

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

## Errors 分类

当主要数据来自 `owl.errors.list` 时，至少回答：

- 有几类错误
- 每类多少条
- 集中在哪些服务 / 资源
- 最近一次出现时间
- 代表性报错
- 是否有共享 `trace_id`，从而可能属于同一条链路

```bash
owl exec owl.errors.list --start_time <START_MS> --end_time <END_MS> --page_size 100 \
  | python3 scripts/classify_owl_errors.py
```

## 报告落盘

参考格式：

- `references/report-format.md`
- `references/best-practices.md`
- `references/report-example.md`

查询类任务默认保存到：

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

回复时必须说明：

- 已生成报告
- 报告保存路径
- 是否为 Markdown 文件

## Guardrails

- 用 `owl help exec`，不要用 `owl exec -h`
- 工具缺失、参数不匹配、输出异常，或用户明确提到最新、同步、更新时，执行 `owl sync`，再 `owl list -f json`

## 触发示例

- `用 owl-diagnostics 看最近15分钟发生了什么`
- `用 owl-diagnostics 查最近1小时 errors 并分类`
- `用 owl-diagnostics 排查 frontend-proxy 为什么 5xx 上升`
- `用 owl-diagnostics 做一次 root cause analysis`
- `用 owl-diagnostics 比较今天和昨天的服务错误影响`
- `用 owl-diagnostics 导出一份最近1小时故障报告`
