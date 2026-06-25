# Owl Diagnostics Report Example

Example。

## Example

```md
**Generation info**
- Generated at：`2026-04-17 12:08:30 CST`
- Hostname：`liurui`
- User：`liurui`
- Analysis started at：`2026-04-17 12:06:42 CST`
- Report completed at：`2026-04-17 12:08:30 CST`
- Total duration：`108s`

**Time range**
`2026-04-17 11:00:00 CST`  `2026-04-17 12:00:00 CST`

**Query method**
- CLI：`owl`
-  tool：`owl.errors.list`、`owl.apm.list`
- Notes：` 100 query；； APM  service/resource/error_type`

**Overall conclusion**
-  1  2 ， `grpc`  `mysqli` 。
- ，，。

**Classification results**
- `grpc._channel._MultiThreadedRendezvous`：`2`， `grpc /flagd.evaluation.v1.Service/EventStream`
- `mysqli_sql_exception`：`2`， `php-demo GET /containers/json`、`mysqli mysqli.__construct`

**Representative evidence**
- `service=grpc` `resource=/flagd.evaluation.v1.Service/EventStream` `trace_id=0e981c62edf5966b499511b360943208`：`StatusCode.DEADLINE_EXCEEDED / Deadline Exceeded`
- `service=php-demo` `resource=GET /containers/json` `trace_id=69e19b8000000000f53ded9ca6056ee8`：`Uncaught mysqli_sql_exception: Connection timed out`

**Judgment / **
-  1：`grpc`  `DEADLINE_EXCEEDED`，Notes 1 。
-  2：`php-demo`  `mysqli`  `trace_id`，Notes。

**Next steps**
1.  `flagd.evaluation.v1.Service/EventStream` 。
2. Check `php-demo`  MySQL 、。
3. ， `service/resource/error_type` 。
```

## Notes

- User“”，Output。
- ， `report-format.md` Template。
- query， event、metric、network ，，“Classification results”“Representative evidence”Content。

##

Markdown ，：

```bash
./owl-reports/
```

：

```bash
cat /tmp/owl-report.md | python3 scripts/save_report.py --output-dir ./owl-reports
```
