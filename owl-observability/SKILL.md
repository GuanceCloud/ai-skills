---
name: owl-observability
description: 用 owl CLI 查询观测云数据并整理结论。适用于“查最近 15 分钟/1 小时/24 小时的链路、错误、事件、APM、指标、网络异常”“按错误类型、服务、资源、状态分类汇总”“需要一份简洁报告输出”。先执行 owl -h，再用 owl show <tool> 确认具体 tool 用法；优先选择最贴近问题的数据域 tool，不要默认缩窄到 trace。
---

# Owl Observability Skill

用于通过 `owl` 查询观测数据，并输出简洁结论或报告。

## 硬规则

- 先执行 `owl -h`。
- 具体 tool 先执行 `owl show <tool>`，不要猜参数。
- 先选最贴近问题的数据域 tool，不够时再用 `owl.data.query`。
- 不要默认把“平台链路”缩窄成 trace。
- 结果可能分页，命中 `page_size` 时继续翻页。
- 只要任务涉及查询结果交付，最终必须输出报告，不能只给零散结论。
- 最终报告必须落盘，不能只在对话里展示。

## 默认选路

- 错误分类、异常归类：`owl.errors.list`
- APM source / field / 链路上下文：`owl.apm.list`
- 事件：`owl.event.list`
- 指标：`owl.metric.list`
- 网络：`owl.network.list`
- 复杂聚合或跨域查询：`owl.data.show_dql_namespace` -> discovery tool -> `owl.data.search_dql_docs` -> `owl.data.check_dql` -> `owl.data.query`

## 最小工作流

1. 先看 CLI 和目标 tool：

```bash
owl -h
owl show <tool>
```

2. 计算时间窗：

```bash
date +%s%3N
date -d '15 minutes ago' +%s%3N
date -d '1 hour ago' +%s%3N
date -d '24 hours ago' +%s%3N
```

3. 取数并汇总。

4. 先生成最终报告。

5. 将最终报告落盘。

6. 回复时同时给出报告摘要和落盘路径。

## 错误分类

当数据来自 `owl.errors.list` 时，默认按以下字段汇总：

- `error_type`
- `service`
- `resource`
- `status`
- `time`
- `error_message`
- `trace_id`

至少回答：

- 有几类错误
- 每类多少条
- 集中在哪些服务 / 资源
- 最近一次出现时间
- 代表性报错

如果多个 issue 共用同一个 `trace_id`，指出它们可能属于同一条链路。

可直接使用脚本：

```bash
owl exec owl.errors.list --start_time <START_MS> --end_time <END_MS> --page_size 100 \
  | python3 scripts/classify_owl_errors.py
```

## 报告输出

默认报告格式见 `references/report-format.md`。
最佳实践见 `references/best-practices.md`。
标准报告示例见 `references/report-example.md`。

报告是默认必交付物，不是可选项。

生成报告时，默认补充以下元数据：

- 生成时间
- 主机名
- 当前用户
- 问题分析开始时间
- 报告生成完成时间
- 总耗时

可直接通过以下命令获取：

```bash
date '+%F %T %Z'
hostname
whoami
```

总耗时指“从开始分析用户问题，到报告最终生成完成”的整个耗时。

建议按秒统计：

```bash
START_TS=$(date +%s)
# 从开始分析用户问题时记录
# ...查询、分析、整理、生成报告...
END_TS=$(date +%s)   # 在报告生成完成时记录
echo "$((END_TS-START_TS))s"
```

## 报告落盘

最终报告默认保存到当前工作目录下：

```bash
./owl-reports/
```

推荐文件名格式：

```text
owl-report-YYYYMMDD-HHMMSS-<user>.md
```

生成最终报告后，必须执行落盘。

可直接使用脚本：

```bash
python3 scripts/save_report.py --output-dir ./owl-reports < /tmp/owl-report.md
```

如果已经有完整 Markdown 内容，也可以：

```bash
cat /tmp/owl-report.md | python3 scripts/save_report.py --output-dir ./owl-reports
```

完成后必须在回复里说明：

- 已生成报告
- 报告保存路径
- 是否为 Markdown 文件

如果用户没有指定风格，优先输出：

- 一段简短结论
- 一组分类结果
- 一组代表性证据
- 一组后续建议
- 一条明确的落盘路径

## 简短触发示例

- `用 owl-observability 查最近1小时错误并分类`
- `用 owl-observability 看最近15分钟平台链路异常`
- `用 owl-observability 查最近1小时 event`
- `用 owl-observability 看 apm 里有哪些字段`
- `用 owl-observability 出一份最近1小时错误报告`
