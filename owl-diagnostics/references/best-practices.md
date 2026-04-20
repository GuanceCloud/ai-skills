# Owl Diagnostics Best Practices

本文档给出使用 `owl-diagnostics` 进行观测查询、生成报告、保存报告的最佳实践。

## 目标

使用 `owl` 查询观测数据时，优先做到：

1. 选对数据域 tool，而不是一上来就写 DQL。
2. 输出最终报告，而不是只给中间查询结果。
3. 报告必须可追溯，包含生成信息、时间范围、证据和落盘路径。
4. 报告必须落盘为 Markdown 文件。

## 总体原则

### 1. 先确认 CLI 与 tool 用法

不要凭记忆调用 `owl`。

固定先做两步：

```bash
owl -h
owl show <tool>
```

这样可以避免：

- 参数名写错
- 分页参数遗漏
- 把错误域问题误查成 trace / metric / event

### 2. 先选最贴近问题的数据域

默认优先顺序：

- 错误分类、异常归类：`owl.errors.list`
- APM 字段、source、链路上下文：`owl.apm.list`
- 事件：`owl.event.list`
- 指标：`owl.metric.list`
- 网络：`owl.network.list`
- 只有现成 tool 不够时，才使用 `owl.data.query`

不要把“平台链路异常”机械地理解成只能查 trace。

### 3. 绝对时间优先

报告中不要只写“最近 1 小时”“最近 15 分钟”。

建议流程：

```bash
date +%s%3N
date -d '1 hour ago' +%s%3N
```

同时在报告中写清：

- 查询开始时间
- 查询结束时间
- 报告生成时间

### 4. 分页结果必须处理完整

当查询结果存在分页时：

- 不要只看第一页
- 如果当前页接近或达到 `page_size`，继续翻页
- 汇总结论时以所有页面的结果为准

否则会出现：

- 错误类型统计不全
- 服务分布判断偏差
- 结论和真实情况不一致

## 推荐工作流

### 场景一：最近 1 小时错误分类

1. 查看帮助和 tool：

```bash
owl -h
owl show owl.errors.list
```

2. 计算时间窗：

```bash
date +%s%3N
date -d '1 hour ago' +%s%3N
```

3. 查询错误：

```bash
owl exec owl.errors.list --start_time <START_MS> --end_time <END_MS> --page_size 100
```

4. 必要时分类辅助：

```bash
owl exec owl.errors.list --start_time <START_MS> --end_time <END_MS> --page_size 100 \
  | python3 scripts/classify_owl_errors.py
```

5. 生成完整 Markdown 报告。

6. 落盘保存：

```bash
cat /tmp/owl-report.md | python3 scripts/save_report.py --output-dir ./owl-reports
```

### 场景二：最近 15 分钟链路异常

1. 优先确认 APM 能提供什么：

```bash
owl -h
owl show owl.apm.list
owl exec owl.apm.list
owl exec owl.apm.list --mode field
```

2. 如果 APM discovery 不足以回答问题，再进入 DQL 路径：

```bash
owl show owl.data.show_dql_namespace
owl show owl.data.query
owl show owl.data.check_dql
owl show owl.data.search_dql_docs
```

3. 先 discovery，再查文档，再校验，再执行：

```bash
owl exec owl.data.show_dql_namespace
owl exec owl.data.search_dql_docs --query '<关键词>'
owl exec owl.data.check_dql --query_text '<DQL>'
owl exec owl.data.query ...
```

最佳实践是：

- 不要跳过 `owl show`
- 不要跳过 `check_dql`
- 不要在没有 source / field 发现的情况下直接猜字段

## 报告最佳实践

### 1. 报告必须是最终交付物

不要只给：

- 原始 JSON
- 命令输出片段
- 零散结论

必须产出结构化报告。

### 2. 报告默认必须带的元数据

- 生成时间
- 主机名
- 用户
- 问题分析开始时间
- 报告生成完成时间
- 总耗时

其中：

- `总耗时` 指从开始分析问题到报告生成完成的整个耗时
- 不是单独的查询耗时

### 3. 报告必须包含的主体内容

- 时间范围
- 查询方式
- 总体结论
- 分类结果
- 代表性证据
- 判断 / 推断
- 后续建议

### 4. 报告必须落盘

不要只在对话里输出。

默认保存目录：

```bash
./owl-reports/
```

推荐文件名格式：

```text
owl-report-YYYYMMDD-HHMMSS-<hostname>-<user>.md
```

### 5. 回复用户时必须说明

- 已生成报告
- 报告保存路径
- 文件格式为 Markdown

## 常见错误

### 1. 未先 `owl show <tool>`

问题：

- 参数猜错
- 错误使用 tool

修正：

```bash
owl show <tool>
```

### 2. 默认把问题缩窄到 trace

问题：

- 用户问的是平台异常，不一定只看 trace

修正：

- 先判断问题类型
- 先选最贴近的数据域

### 3. 只有结论，没有证据

问题：

- 报告不可追溯
- 用户无法复核

修正：

- 附至少一组代表性 `service/resource/trace_id/error_message`

### 4. 报告没落盘

问题：

- 对话结束后不可复用

修正：

```bash
python3 scripts/save_report.py --output-dir ./owl-reports < /tmp/owl-report.md
```

### 5. 只统计第一页

问题：

- 分类结果失真

修正：

- 继续翻页直到取完

## 最小执行清单

每次执行前确认：

- 已执行 `owl -h`
- 已执行 `owl show <tool>`
- 已确定绝对时间范围
- 已选择最贴近问题的数据域 tool
- 已处理分页
- 已生成完整报告
- 已保存 Markdown 报告到磁盘
- 已在回复中给出保存路径

## 推荐短提示词

- `用 owl-diagnostics 查最近1小时错误并分类`
- `用 owl-diagnostics 看最近15分钟平台链路异常`
- `用 owl-diagnostics 出一份最近1小时错误报告`
- `用 owl-diagnostics 查最近24小时 event 并输出报告`
