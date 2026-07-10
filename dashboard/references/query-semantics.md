# 查询语义与可读性

## 1. 指标类型决策

先判断字段由谁聚合，再选择 DQL：

| 类型 | 典型字段 | 趋势查询 | `fieldFunc` |
| --- | --- | --- | --- |
| 原始计数器 | 请求累计数、错误累计数、字节累计数 | `rate(field)` 或兼容 rollup | `last` |
| 原始仪表值 | 当前连接、队列深度、使用率 | `AVG(field)` | `avg` |
| 云端预聚合平均值 | `*_average` | `fill(last(field), linear)` | `last` |
| 云端预聚合最大/最小值 | `*_max` / `*_min` | 仅在明确需要峰谷时使用 `fill(last(...), linear)` | `last` |

不要对云监控已聚合字段再次 `AVG()`，否则得到的是采样窗口和查询窗口叠加后的二次平均。

## 2. 概览跨系列聚合

概览卡片通常先按实例取最新值，再在实例之间聚合。

使用 `series_sum`：

- 当前连接数或连接总量。
- QPS/TPS 等需要展示整体吞吐的值。
- 队列长度、慢日志长度、阻塞客户端等可加总数量。

使用 `avg`：

- CPU、内存负载和使用率。
- 命中率、连接使用率、流量占比。
- 平均延迟、平均响应时间。

使用 `series_max` 仅用于明确的“最差实例”概览。不要把它伪装成整体平均。

容量规格、创建时间、架构和状态不是遥测总量，放在资源对象实例表。

## 3. 平均/最大/最小降噪

当同一指标存在 `_average/_max/_min`：

1. 普通趋势默认只展示 `_average`。
2. 不再为同一指标族生成“平均值图、最大值图、最小值图”三张兄弟图。
3. 只有容量规划、SLA 峰值或异常尖峰场景明确需要时，才增加 `_max`。
4. 只有明确观察下界时才增加 `_min`。

在 32 个实例场景中，三种统计值会把 32 条曲线扩成近百条，默认不可接受。

## 4. 一指标一查询

每个 `queries[]` 项只查询一个指标字段：

```dql
M::`service`:(fill(last(`read_qps_average`), linear) AS `读 QPS`) { `instance_name` = '#{instance_name}' } BY `instance_name`
```

```dql
M::`service`:(fill(last(`write_qps_average`), linear) AS `写 QPS`) { `instance_name` = '#{instance_name}' } BY `instance_name`
```

不要把多个字段塞进同一条 DQL。观测云编辑器按 query 展示配置；一条 DQL 含多个字段会让外层看见多系列、编辑器内却只看见一行查询，后续难以维护。

## 5. 分组与图例

- 过滤维度不等于展示维度。账号、实例名称和实例 ID 可以都用于过滤，但 `BY` 只放图例真正需要的维度。
- 普通多实例趋势优先使用可读 `instance_name`。
- 需要稳定 ID 时，把 `instance_id` 保留在过滤器或对象分组中。
- 不默认拼接 `node_id/node_name/shard_id`。节点级需求另建明细图或下钻。
- 若名称可能重名且会造成错误聚合，使用同时包含名称与 ID 的可读展示方案，或按产品能力提供单实例筛选后再展示节点。

## 6. 图表内颜色

当一条 query 通过 `BY instance_name` 返回多条系列时，固定 query 颜色会把所有实例锁成同色。

使用：

```json
{
  "queries": [{"color": ""}],
  "extend": {"settings": {"colors": []}}
}
```

多 query 图如果每条 query 表示不同指标，可以按指标配置颜色；同一 query 内的分组系列仍应由 UI 调色盘区分。

## 7. 查询结构一致性

每条 query 保持：

- 外层 `name/type/unit/color/qtype` 完整。
- `query.filters` 使用实际变量 code 和 `#{code}`。
- `query.groupBy` 与 DQL `BY` 一致。
- `funcList`、`queryFuncs`、`groupByTime` 与查询类型匹配。
- `fill` 与 DQL 实际填充策略一致。

不要用“所有查询必须包含第一个变量”这类单变量校验器。解析 DQL 中实际引用的变量，再与 `main.vars` 全量比对。
