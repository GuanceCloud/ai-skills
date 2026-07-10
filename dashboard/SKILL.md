---
name: dashboard
description: 生成、修复或评审观测云 Dashboard 仪表板。根据真实指标 CSV、标签信息和资源目录/自定义对象 JSON 或 CSV 生成 Dashboard JSON；用于设计可读变量与对象实例列表、选择 DQL 聚合语义、查询官方资料确认枚举和单位、控制高基数趋势图可读性，并在交付前逐条校验全部 DQL。
---

# 观测云 Dashboard 生成技能

## 技能描述

根据用户提供的真实指标 CSV 生成观测云 Dashboard JSON 配置。标准资源型 Dashboard 同时使用资源目录或自定义对象数据生成实例属性表；已有人工修改 JSON 时，将其作为反馈样本继续修复未完成图表。

核心数据职责：

- 指标 CSV 和标签信息生成概览与趋势图。
- 对象 JSON/CSV 生成实例属性表和对象实例数量。
- 官方资料只用于确认单位、枚举和字段语义，不用于补造 CSV 中不存在的指标。

### 按需读取参考

- 生成或修复 JSON 字段、单位、布局和样式时，读取 [Dashboard JSON 契约](references/dashboard-json-contract.md)。
- 判断计数器、仪表值、预聚合字段、概览聚合和趋势分组时，读取 [查询语义与可读性](references/query-semantics.md)。
- 输入包含资源目录/自定义对象，或需要实例属性表和值映射时，读取 [资源对象实例表](references/resource-object-tables.md)。
- 单位、状态、模式、计费、容量或布尔字段含义不明确时，读取 [官方字段研究流程](references/official-field-research.md)，并查询当前服务的第一方资料。

## 工作流程

```text
输入：csv/{{type}}*.csv + 标签信息
      标准资源型 Dashboard：对象 JSON/CSV
      可选：人工修改 Dashboard JSON
        ↓
   [检查真实输入] ← 指标 CSV 缺失则拒绝生成
        ↓             对象缺失则停止标准资源版
   [解析指标、tag 与对象顶层字段]
        ↓
   [查询官方单位和枚举资料]
        ↓
   [专业运维基线设计]
        ↓
     [生成 JSON]
        ↓
   [样式自动修正] ← 分组、布局、概览色盘、系列颜色
        ↓
   [静态验证 + DQL 逐条验证]
        ↓
输出：output/dashboard/{{type}}/{{type}}.json
```

### 第四步：样式自动修正（强制）

生成 Dashboard JSON 后，必须先执行样式归一化并回写，再进入静态检查和 DQL 验证。

自动修正项：

1. `dashboardExtend.groupUnfoldStatus` 中所有分组设为 `true`。
2. `概览` 固定第一，列表分组固定第二，其他分组按业务排障顺序排列。
3. 移除 `dashboardExtend.groupColor` 和 `main.groups[].extend.colorKey`，为每个分组补充 `rgba(...)` 背景。
4. 概览 `singlestat` 使用多彩色盘，补齐 `valueColor`、对应透明 `bgColor` 和 `borderColor: "#E5E7EB"`。
5. 一条 grouped query 返回多个实例系列时，设置 query `color: ""` 和 `settings.colors: []`，让 UI 在图表内部按系列分配颜色。
6. 不用固定 query 颜色解决“不同图表颜色不同”；用户需要的是同一图表内不同实例可区分。

```python
def to_alpha_bg(hex_color, alpha):
    value = hex_color.lstrip("#")
    red, green, blue = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({red}, {green}, {blue}, {alpha})"


def autofix_dashboard_style(dashboard):
    groups = [g["name"] for g in dashboard["main"]["groups"]]
    dashboard["dashboardExtend"]["groupUnfoldStatus"] = {name: True for name in groups}
    dashboard["dashboardExtend"].pop("groupColor", None)

    list_groups = [name for name in groups if "列表" in name and name != "概览"]
    other_groups = [name for name in groups if name not in (["概览"] + list_groups)]
    ordered = (["概览"] if "概览" in groups else []) + list_groups + other_groups
    order_index = {name: index for index, name in enumerate(ordered)}
    dashboard["main"]["groups"].sort(key=lambda group: order_index[group["name"]])
    dashboard["main"]["charts"].sort(
        key=lambda chart: order_index[chart.get("group", {}).get("name")]
    )

    multi = ["#06B6D4", "#10B981", "#EAB308", "#F97316", "#EF4444", "#8B5CF6", "#EC4899"]
    group_palette = ["#3B82F6", "#94A3B8", "#22C55E", "#F59E0B", "#06B6D4", "#EF4444", "#8B5CF6", "#EC4899"]
    stat_index = 0
    for chart in dashboard["main"]["charts"]:
        settings = chart.setdefault("extend", {}).setdefault("settings", {})
        if chart.get("type") == "singlestat" and chart.get("group", {}).get("name") == "概览":
            settings["valueColor"] = multi[stat_index % len(multi)]
            settings["bgColor"] = to_alpha_bg(settings["valueColor"], 0.66)
            settings["borderColor"] = "#E5E7EB"
            stat_index += 1
        if chart.get("type") == "sequence":
            for item in chart.get("queries", []):
                if item.get("query", {}).get("groupBy"):
                    item["color"] = ""
                    settings["colors"] = []

    for index, group in enumerate(dashboard["main"]["groups"]):
        extension = group.setdefault("extend", {})
        extension["bgColor"] = to_alpha_bg(group_palette[index % len(group_palette)], 0.10)
        extension.pop("colorKey", None)
```

### 第五步：DQL 验证（强制）

从 `main.charts[].queries[].query.q` 提取所有 DQL，逐条执行 `dqlcheck`：

```bash
./dql/bin/dqlcheck -q 'M::`service`:(fill(last(`cpu_average`), linear) AS `CPU 使用率`) { `instance_name` = "#{instance_name}" } BY `instance_name`'
```

若 skill 独立安装，先查找可用的 `dqlcheck`。失败查询必须按错误位置修复并重新验证；无法通过的 DQL 不得保留在最终 Dashboard 中。交付时报告校验总数、成功数和失败数。

### 第六步：变量与维度验证（强制）

不再只读取 `main.vars[0]`。遍历全部变量并验证：

- 每个变量 `code` 都来自真实 tag 或对象字段，不做名称强制转换。
- DQL 中的 `#{code}` 必须在 `main.vars` 中存在。
- `filters[].name/value` 与实际变量和 `#{code}` 一致。
- `query.groupBy` 与 DQL 的 `BY` 展示维度一致。
- 过滤维度不要求全部进入 `BY`；账号、名称、ID 可以共同过滤，但趋势图例只保留可读维度。
- 稳定 ID 用于过滤和对象分组，不强迫用户只看 ID 图例。

## 执行规则（重要）

### 第一步：强制检查 CSV 文件

开始生成前，搜索以下路径：

- `csv/{{type}}.csv`
- `csv/{{type}} 指标.csv`
- `csv/{{type}}*.csv`
- `csv/{{type}}/*.csv`

指标 CSV 必须包含指标名，且能从标签 CSV 或指标行中取得完整 tag 信息。没有指标 CSV 时停止生成并请求真实导出。

禁止行为：

- 不从互联网、示例或其他产品文档补造指标。
- 不在没有 CSV 时根据组件常识猜测指标。
- 不生成缺少 `extend.settings.units` 的图表。

允许上网查询当前产品的官方指标说明、API 文档或 SDK，以确认用户 CSV 中已有字段的单位和含义。

### 第一步补充：检查对象数据

标准资源型 Dashboard 的实例列表必须使用对象 JSON/CSV。对象输入至少包含：

- 对象 measurement/class。
- 至少一条真实对象记录。
- 可查询顶层字段及其真实类型和值。
- 账号、可读实例名称和稳定实例 ID，或当前产品的等价字段。

对象缺失时：

1. 不生成或修改实例属性表。
2. 不用指标 tag 降级拼接“实例属性列表”。
3. 停止标准资源型 Dashboard 生成并请求对象导出。
4. 只有用户明确接受“不含实例属性表的遥测版”时才继续，并在交付说明中标记例外。

仅评审已有 JSON 且不改对象表时，可以不要求对象输入；一旦新增对象字段、单位或枚举映射，仍必须提供真实对象样本。

### 第二步：解析真实数据

从指标 CSV 提取：

- `指标名` / `metric_name`。
- `字段类型` / `data_type`。
- `单位` / `unit`。
- `操作` / `tag_key` / `Tag` / `标签`。

同时识别：

- 原始计数器、原始仪表值和云端预聚合值。
- 同源 `_average/_max/_min` 指标族。
- 可加总数量、百分比、负载、延迟、容量和状态类字段。
- 账号、实例名称、实例 ID、节点和分片等真实维度。

从对象样本提取 class、顶层字段、样本值、字段类型、单位元数据和低基数枚举候选。嵌套 `message` 只用于查证来源，不假设其中字段一定可被 `CO::` 直接查询。

若提供人工修改 JSON，比较查询、变量、聚合、分组、颜色、单位、`fieldMapping` 和 `valMappings`，把可复用修正应用到未完成图表。

### 第三步：从真实 tag 设计变量

变量 `code` 严格使用实际 tag。常见云资源在字段真实存在时采用：

1. 可见账号名称，如 `account_name`。
2. 可见实例名称，如 `instance_name`。
3. 隐藏稳定实例 ID，如 `instance_id`。

若产品只提供 `instanceId`、`host` 或其他字段，沿用原名，不强制转换。只有一个 tag 时保留原 skill 的单变量兼容行为。

每个变量使用：

```text
SHOW_TAG_VALUE(from=['service'],keyin=['actual_tag'])[10m]
```

所有变量默认支持多选和 `*`。可读名称用于筛选和图例，稳定 ID 用于过滤或对象 `BY` 分组。

### 第三步补充：专业运维覆盖基线（强制）

默认至少提供：

- 1 行 `singlestat` 概览，包含 4 到 8 个关键 KPI。
- 1 个实例级 `table`；标准资源型 Dashboard 必须来自对象数据。
- 6 个以上按资源、请求、延迟、错误、网络、日志等业务主题分组的 `sequence` 趋势图。

覆盖所有有运维价值的指标族，并记录未落图原因。不要为了“CSV 每个字段都落图”机械生成 `_average/_max/_min` 三套图，也不要把静态容量、架构、状态和创建时间放进遥测求和卡片。

产品特定覆盖范围由当前 CSV、对象样本和官方资料决定，不在通用 skill 中维护某个云厂商或组件的数据字典。

### 第四步：生成 Dashboard JSON

按照下面的核心规范生成，详细字段契约读取 [Dashboard JSON 契约](references/dashboard-json-contract.md)。

## 核心规范

### 1. 基础结构

```json
{
  "title": "服务监控",
  "dashboardType": "CUSTOM",
  "dashboardExtend": {"groupUnfoldStatus": {"概览": true, "实例列表": true}},
  "dashboardMapping": [],
  "dashboardOwnerType": "node",
  "iconSet": {"url": "", "icon": "database"},
  "dashboardBindSet": [],
  "thumbnail": "",
  "tagInfo": [],
  "summary": "服务资源属性和遥测监控",
  "main": {"vars": [], "charts": [], "groups": [], "type": "template"}
}
```

`main.groups` 必须存在，`main` 不包含 `chartGroupPos`。每张 chart 必须包含 `uuid`、`chartGroupUUID`、`group`、`prevGroupName` 和不重叠的 `pos`。

### 2. 变量配置

```json
{
  "name": "实例名称",
  "seq": 1,
  "datasource": "dataflux",
  "code": "instance_name",
  "type": "QUERY",
  "definition": {
    "tag": "",
    "field": "",
    "value": "SHOW_TAG_VALUE(from=['service'],keyin=['instance_name'])[10m]",
    "metric": "",
    "object": ""
  },
  "valueSort": "default",
  "hide": 0,
  "isHiddenAsterisk": 0,
  "multiple": true,
  "includeStar": true,
  "extend": {}
}
```

变量可共同进入 filters，但 `BY/groupBy` 只放图表展示维度。普通多实例趋势优先 `BY instance_name` 等可读字段；对象实例表优先按稳定 ID 分组。

### 3. 分组配置（必需）

```json
{
  "main": {
    "groups": [
      {"name": "概览", "extend": {"bgColor": "rgba(59, 130, 246, 0.10)"}},
      {"name": "实例列表", "extend": {"bgColor": "rgba(148, 163, 184, 0.10)"}},
      {"name": "性能", "extend": {"bgColor": "rgba(34, 197, 94, 0.10)"}}
    ]
  }
}
```

- 所有分组展开，概览第一，列表第二。
- 分组背景使用克制且有区分度的 `rgba(...)`，不要求所有分组都属于同一蓝色族。
- 概览卡片按多彩色盘轮换。
- 趋势图内部的实例系列由 UI 调色盘区分，不用固定 query 颜色锁成同色。

### 4. 图表公共结构（必须配置单位）

每个 `queries[]` 外层包含 `name/type/unit/color/qtype/query/datasource`。每个 filter 包含 `id/op/name/type/logic/value`。默认 `op` 使用 `=`，除非当前产品语义明确需要其他操作符。

```json
{
  "extend": {"settings": {"units": [], "colors": [], "showTitle": true}},
  "group": {"name": "性能"},
  "chartGroupUUID": "chtg_xxx",
  "name": "CPU 使用率趋势",
  "pos": {"h": 10, "w": 8, "x": 0, "y": 0},
  "type": "sequence",
  "queries": [],
  "prevGroupName": "性能",
  "uuid": "chrt_xxx"
}
```

### 5. 单位配置（强制要求）

每张图的每个查询字段都有对应 `extend.settings.units`：

| 输入单位 | `units` 配置 |
| --- | --- |
| 无单位 / `-` | `["custom", ""]` |
| `%` / percent | `["percent", "percent"]` |
| `B`、`KB`、`MB`、`GB` | `["digital", "B/KB/MB/GB"]` |
| `B/S`、`KB/S`、`MB/S` | `["traffic", "B/S/KB/S/MB/S"]` |
| `ms`、`s` | `["time", "ms/s"]` |
| `iops` | `["throughput", "iops"]` |
| `ops` | `["throughput", "ops"]` |
| `reqps` | `["throughput", "reqps"]` |

CSV 或对象 schema 未给单位时，先按 [官方字段研究流程](references/official-field-research.md) 查询当前服务资料。只有无法确认时才使用 custom 原始显示并标记 `UNVERIFIED`。区分 `GB` 与 `Gb`、比例与百分数、累计值与每秒速率、实例总量与节点/分片值。

### 6. 实例属性表

标准资源型 Dashboard 使用对象数据：

```dql
CO::service_object:(last(`account_name`), last(`instance_name`), last(`region_id`), last(`status`), last(`size`)) { `account_name` = '#{account_name}' and `instance_id` = '#{instance_id}' } BY `instance_id`
```

查询元数据使用：

```json
{
  "namespace": "custom_object",
  "dataSource": "service_object",
  "groupBy": ["instance_id"],
  "fieldFunc": "last"
}
```

- 只查询真实对象样本存在的顶层字段。
- 优先展示账号、区域、项目、名称、架构、版本、规格、状态、网络、容量、功能开关和时间等静态属性。
- 遥测值放在概览和趋势图，不重复塞进实例表。
- 使用 `alias`/`fieldMapping` 提供可读列名。
- 数值、布尔和低基数枚举按当前产品官方资料生成 `valMappings`；仅观察或未知值保留原值。
- 不把嵌套 `message` 的节点/分片数组当成顶层字段；确需节点排障时另建明细表。

详细要求读取 [资源对象实例表](references/resource-object-tables.md)。

### 7. 概览图（singlestat）

概览先按稳定实例维度取最新值，再按语义跨实例聚合：

| 指标语义 | 外层聚合 |
| --- | --- |
| 连接数、QPS/TPS、队列长度等可加总值 | `series_sum` |
| CPU/内存使用率、命中率、占比、平均延迟 | `avg` |
| 明确展示最差实例 | `series_max` |
| 实例数量 | 优先对象 `count` |

```dql
series_sum("M::`service`:(last(`connections_average`) AS `连接数`) { `instance_id` = '#{instance_id}' } BY `instance_id`")
```

```dql
avg("M::`service`:(last(`cpu_average`) AS `CPU 使用率`) { `instance_id` = '#{instance_id}' } BY `instance_id`")
```

规则：

- `fill: null`、`funcList: []`、`fieldFunc: "last"`。
- 不使用 rollup。
- `queryFuncs` 与外层聚合函数一致。
- 容量规格、状态、架构和创建时间放入对象实例表，不做遥测求和。
- 不把所有概览机械设为 `series_sum`。

### 8. 时序图（sequence）

先判断字段由谁聚合：

| 指标类型 | 趋势 DQL | `fieldFunc` |
| --- | --- | --- |
| 原始计数器 | `rate(field)` 或兼容 rollup | `last` |
| 原始仪表值 | `AVG(field)` | `avg` |
| 云端预聚合 `_average` | `fill(last(field), linear)` | `last` |
| 云端预聚合 `_max/_min` | 仅明确需要峰谷时使用 | `last` |

```dql
M::`service`:(fill(last(`cpu_average`), linear) AS `CPU 使用率平均值`) { `account_name` = '#{account_name}' and `instance_name` = '#{instance_name}' and `instance_id` = '#{instance_id}' } BY `instance_name`
```

规则：

- 普通 `_average/_max/_min` 指标族默认只展示 `_average`。
- 不对云端预聚合 `_average` 再做二次 `AVG()`。
- 一个 `queries[]` 项只查询一个指标字段。
- `fill: "linear"`、`currentChartType: "area"`、`chartType: "areaLine"`。
- `funcList: []`、`queryFuncs: []`、`groupByTime: ""`。
- 普通多实例趋势优先 `BY instance_name` 等可读维度，不默认拼接 `node_id/node_name/shard_id`。
- grouped query 的外层 `color` 和 `settings.colors` 保持空。
- 不添加无依据的 `showLine/openStack/stackType/xAxisShowType/timeInterval/legendPostion`。

详细决策读取 [查询语义与可读性](references/query-semantics.md)。

### 9. 图表位置规则

概览高度默认 `h=6`：

| 每行数量 | `w` | `x` 位置 |
| --- | --- | --- |
| 8 | 3 | 0,3,6,9,12,15,18,21 |
| 6 | 4 | 0,4,8,12,16,20 |
| 4 | 6 | 0,6,12,18 |
| 3 | 8 | 0,8,16 |

趋势图高度默认 `h=10`：

| 每行数量 | `w` | `x` 位置 |
| --- | --- | --- |
| 4 | 6 | 0,6,12,18 |
| 3 | 8 | 0,8,16 |
| 2 | 12 | 0,12 |
| 1 | 24 | 0 |

表格默认 `w=24`、`h=10`。同一分组内图表位置不得重叠。

## 验证清单

### 输入验证

- [ ] 指标 CSV 和完整 tag 信息存在。
- [ ] 标准资源型 Dashboard 具有对象 class 和至少一条真实对象记录。
- [ ] 人工 JSON、官方资料和对象样本来源已记录。
- [ ] 未从互联网或示例补造指标。

### 基础验证

- [ ] JSON 可解析，`main.groups` 存在，`main.chartGroupPos` 不存在。
- [ ] 样式自动修正结果已回写。
- [ ] 所有分组展开，概览第一，列表第二。
- [ ] 所有图表 UUID、分组、位置和公共字段完整。
- [ ] 所有图表和查询字段具有正确 units。

### 变量验证

- [ ] 遍历了全部 `main.vars`，变量 code 来自真实 tag/对象字段。
- [ ] DQL 变量引用和 filters 均能对应到变量定义。
- [ ] `groupBy` 与 DQL `BY` 一致，且只包含展示维度。
- [ ] 可读名称用于图例，稳定 ID 用于过滤或对象分组。

### 实例表验证

- [ ] 标准资源实例表 DQL 使用 `CO::`，namespace 为 `custom_object`。
- [ ] dataSource 为真实对象 measurement/class，字段来自对象顶层。
- [ ] `BY` 使用稳定实例 ID，不混入指标粒度 tag。
- [ ] 列别名、单位、`fieldMapping` 和 `valMappings` 引用正确返回字段。
- [ ] 未确认枚举保留原值并在交付中说明。

### singlestat 验证

- [ ] 外层聚合符合指标语义，不是全部 `series_sum`。
- [ ] 保留稳定实例维度，`fill` 为 `null`，`funcList` 为空。
- [ ] `fieldFunc` 为 `last`，无 rollup，`queryFuncs` 与外层函数一致。
- [ ] 概览卡片使用多彩色盘。

### sequence 验证

- [ ] 原始计数器、仪表值和预聚合字段使用正确查询方式。
- [ ] 普通趋势没有无必要的 `_max/_min` 或节点/分片维度。
- [ ] 一个 query 只查询一个指标字段。
- [ ] `fill/currentChartType/chartType/funcList/queryFuncs/groupByTime` 正确。
- [ ] grouped query 没有固定颜色导致图表内部所有实例同色。

### 官方资料与映射验证

- [ ] 非显然单位和枚举使用当前产品的第一方资料。
- [ ] 证据记录包含来源 URL、接口/文档版本和确认日期。
- [ ] 只有已确认或证据完整的交叉确认值进入 `valMappings`。
- [ ] 通用 skill 未写入任何云厂商或产品数据字典。

### DQL 验证（强制）

- [ ] 提取 `main.charts[].queries[].query.q` 全部 DQL。
- [ ] 每条 DQL 单独通过 `dqlcheck -q`。
- [ ] 失败项已修复并重新校验，最终交付不存在失败 DQL。
- [ ] 交付说明包含 DQL 校验总数和结果。

## 相关文件

- 输入指标：`csv/{{type}}*.csv`。
- 输入对象：资源目录/自定义对象 JSON 或 CSV。
- 可选输入：人工修改 Dashboard JSON。
- 输出：`output/dashboard/{{type}}/{{type}}.json`。
- 参考：[Dashboard JSON 契约](references/dashboard-json-contract.md)。
- 参考：[查询语义与可读性](references/query-semantics.md)。
- 参考：[资源对象实例表](references/resource-object-tables.md)。
- 参考：[官方字段研究流程](references/official-field-research.md)。
