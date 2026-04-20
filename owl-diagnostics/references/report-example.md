# Owl Diagnostics Report Example

下面是一份可直接参考的标准报告示例。

## 示例

```md
**生成信息**
- 生成时间：`2026-04-17 12:08:30 CST`
- 主机名：`liurui`
- 用户：`liurui`
- 问题分析开始时间：`2026-04-17 12:06:42 CST`
- 报告生成完成时间：`2026-04-17 12:08:30 CST`
- 总耗时：`108s`

**时间范围**
`2026-04-17 11:00:00 CST` 到 `2026-04-17 12:00:00 CST`

**查询方式**
- CLI：`owl`
- 主要 tool：`owl.errors.list`、`owl.apm.list`
- 说明：`错误问题按单页 100 条查询；未命中分页上限；补充查看了 APM 字段用于确认 service/resource/error_type`

**总体结论**
- 最近 1 小时共发现 2 类链路错误，主要集中在 `grpc` 超时和 `mysqli` 连接超时。
- 从错误分布看，当前更像是下游依赖超时问题，而不是单一入口请求异常。

**分类结果**
- `grpc._channel._MultiThreadedRendezvous`：`2`，主要在 `grpc /flagd.evaluation.v1.Service/EventStream`
- `mysqli_sql_exception`：`2`，主要在 `php-demo GET /containers/json`、`mysqli mysqli.__construct`

**代表性证据**
- `service=grpc` `resource=/flagd.evaluation.v1.Service/EventStream` `trace_id=0e981c62edf5966b499511b360943208`：`StatusCode.DEADLINE_EXCEEDED / Deadline Exceeded`
- `service=php-demo` `resource=GET /containers/json` `trace_id=69e19b8000000000f53ded9ca6056ee8`：`Uncaught mysqli_sql_exception: Connection timed out`

**判断 / 推断**
- 推断 1：`grpc` 相关错误集中为 `DEADLINE_EXCEEDED`，说明该链路在最近 1 小时存在稳定的下游响应超时现象。
- 推断 2：`php-demo` 与 `mysqli` 共用同一个 `trace_id`，说明应用请求与数据库连接失败属于同一条链路上的级联报错。

**后续建议**
1. 优先排查 `flagd.evaluation.v1.Service/EventStream` 对应下游服务的延迟和可用性。
2. 检查 `php-demo` 所连接 MySQL 的连接池、网络连通性和超时配置。
3. 若同类问题持续出现，补充按 `service/resource/error_type` 的周期性报告并落盘归档。
```

## 适用说明

- 当用户要求“给我一份报告”时，优先按这个结构输出。
- 当结果为空时，改用 `report-format.md` 中的空结果模板。
- 当查询目标不是错误，而是 event、metric、network 时，保留结构不变，只替换“分类结果”和“代表性证据”的内容。

## 落盘建议

生成最终 Markdown 后，保存到：

```bash
./owl-reports/
```

例如：

```bash
cat /tmp/owl-report.md | python3 scripts/save_report.py --output-dir ./owl-reports
```
