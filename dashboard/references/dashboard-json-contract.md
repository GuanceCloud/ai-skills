# Dashboard JSON 契约

## 目录

- [顶层结构](#1-顶层结构)
- [分组](#2-分组)
- [变量](#3-变量)
- [查询公共字段](#4-查询公共字段)
- [单位](#5-单位)
- [Singlestat](#6-singlestat)
- [Sequence](#7-sequence)
- [布局](#8-布局)
- [最终检查](#9-最终检查)

## 1. 顶层结构

```json
{
  "title": "服务监控",
  "dashboardType": "CUSTOM",
  "dashboardExtend": {"groupUnfoldStatus": {"概览": true}},
  "dashboardMapping": [],
  "dashboardOwnerType": "node",
  "iconSet": {"url": "", "icon": ""},
  "dashboardBindSet": [],
  "thumbnail": "",
  "tagInfo": [],
  "summary": "",
  "main": {"vars": [], "charts": [], "groups": []}
}
```

- `main.groups` 必须存在。
- `main` 不得包含 `chartGroupPos`。
- 所有 chart 必须有 `uuid`、`chartGroupUUID`、`group`、`prevGroupName` 和 `pos`。

## 2. 分组

- `概览` 排第一。
- `实例列表`、`主机列表`等列表分组排第二。
- 其他分组按运维排障顺序排列。
- `dashboardExtend.groupUnfoldStatus` 为每个分组设置 `true`。
- 移除 `dashboardExtend.groupColor`。
- `main.groups[].extend.bgColor` 使用 `rgba(...)`。
- 移除 `main.groups[].extend.colorKey`。

## 3. 变量

变量使用真实 tag key：

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

多变量校验必须遍历整个 `main.vars`。DQL 可以使用多个变量过滤，但 `BY/groupBy` 只放图表展示维度。

## 4. 查询公共字段

每个 `queries[]` 外层包含：

```json
{
  "name": "",
  "type": "sequence",
  "unit": "",
  "color": "",
  "qtype": "dql",
  "query": {},
  "datasource": "dataflux"
}
```

每个 `query.filters[]` 包含 `id/op/name/type/logic/value`。默认 `op` 使用 `=`，除非产品语义明确需要其他操作符。

## 5. 单位

每张图必须有 `extend.settings.units`，每个查询字段都有对应项。

| 输入单位 | 配置 |
| --- | --- |
| 无单位 / `-` | `["custom", ""]` |
| `%` / percent | `["percent", "percent"]` |
| `B`、`KB`、`MB`、`GB` | `["digital", "B/KB/MB/GB"]` |
| `B/S`、`KB/S`、`MB/S` | `["traffic", "B/S/KB/S/MB/S"]` |
| `ms`、`s` | `["time", "ms/s"]` |
| `iops` | `["throughput", "iops"]` |
| `ops` | `["throughput", "ops"]` |
| `reqps` | `["throughput", "reqps"]` |

只有确实无法识别时才使用 custom。单位符号、量纲与大小写必须一致。

## 6. Singlestat

- `fill: null`。
- `funcList: []`。
- `fieldFunc: "last"`。
- 不使用 rollup。
- 外层聚合按指标语义选择 `series_sum`、`avg` 或明确的其他函数。
- 配置 `valueColor`、对应透明 `bgColor` 和 `borderColor: "#E5E7EB"`。
- 概览卡片按多彩色盘轮换，不全部同色。

建议色盘：`#06B6D4`、`#10B981`、`#EAB308`、`#F97316`、`#EF4444`、`#8B5CF6`、`#EC4899`。

## 7. Sequence

- `fill: "linear"`。
- `currentChartType: "area"`。
- `chartType: "areaLine"`。
- `funcList: []`、`queryFuncs: []`、`groupByTime: ""`。
- 不添加无依据的 `showLine/openStack/stackType/xAxisShowType/timeInterval/legendPostion`。
- 一条分组 query 返回多实例系列时，query 色和 settings colors 保持空，让 UI 按系列配色。

## 8. 布局

概览高度默认 `h=6`：

| 每行 | `w` | `x` |
| --- | --- | --- |
| 8 | 3 | 0,3,6,9,12,15,18,21 |
| 6 | 4 | 0,4,8,12,16,20 |
| 4 | 6 | 0,6,12,18 |
| 3 | 8 | 0,8,16 |

趋势图高度默认 `h=10`：

| 每行 | `w` | `x` |
| --- | --- | --- |
| 4 | 6 | 0,6,12,18 |
| 3 | 8 | 0,8,16 |
| 2 | 12 | 0,12 |
| 1 | 24 | 0 |

表格默认 `w=24`、`h=10`。确保同组图表位置不重叠。

## 9. 最终检查

- JSON 可解析且没有未知临时字段。
- 分组顺序和展开状态一致。
- 所有图表 units 完整。
- 所有 query 公共字段完整。
- 所有变量引用存在，filters 和 groupBy 与 DQL 一致。
- 表格列别名、字段映射和值映射引用正确查询字段。
- 概览聚合符合语义。
- 高基数图没有重复统计线、节点级噪声或内部同色问题。
- 所有 DQL 逐条通过 `dqlcheck`。
