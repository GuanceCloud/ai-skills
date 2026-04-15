---
name: alert_manager
description: 将用户提供的 alertmanager rule 语句或 rule 文件转换为观测云监控器配置。实际处理对象是告警规则定义,不处理 Alertmanager 路由配置;复用 monitor skill 的监控器结构,并在输出前强制校验全部 DQL。
---

# alertmanager rule 转观测云监控器技能

## 技能描述

当用户希望把 alertmanager rule 转换成观测云监控器配置时，使用本技能。

这里的 “alertmanager rule” 统一按告警规则定义理解。输入可以是单条 rule 语句，也可以是 rule 文件；不是 `alertmanager.yml` 的路由配置。

按官方定义：

- Prometheus alerting rules 负责定义 `alert / expr / for / labels / annotations`
- Alertmanager 负责接收 Prometheus 发出的告警，并执行去重、分组、路由、静默、抑制与通知发送

因此本技能的输入应是告警规则，而不是 Alertmanager 的 `route / receiver / inhibit_rules / mute_time_intervals` 配置。

本技能不是重新设计监控器结构，而是：

1. 复用 `monitor` skill 中的监控器 JSON 骨架
2. 将 alertmanager rule 中的告警规则字段映射到观测云 `checkers` 结构
3. 对生成后的全部 DQL 执行强制校验

## 快速规则

- 输入必须是告警规则定义，不能是 `alertmanager.yml`
- 没有指标映射时，先整理映射，不能硬写 DQL
- 每条规则都要同时生成 `targets[].dql` 和 `extend.querylist[].query.q`
- `checkerOpt.rules` 与 `extend.rules` 必须同步
- 最终 JSON 中不能残留 PromQL
- 所有 DQL 必须通过 `dqlcheck`

## 输入与输出

**输入：**

- 单条 rule 语句
- rule 文件（YAML/JSON，如 Prometheus alerting rules / PrometheusRule）
- 指标与数据源映射信息
  - 至少要能确定 `measurement`、`field`、聚合函数、分组 tag
- 可选：现有观测云 monitor 模板或 `csv/{{component}}*.csv`

**输出：**

- `output/monitor/{{component}}/{{component}}.json`

### 最小映射信息

如果规则表达式里的指标名无法直接映射到观测云字段，至少要补齐下表中的信息：

| 必填项 | 说明 | 示例 |
|---|---|---|
| `component` | 组件名，用于输出目录和 `signId` | `mysql` |
| `source_metric` | 源规则中的指标名 | `mysql_global_status_threads_connected` |
| `dataSource` | 观测云数据源 | `mysql` |
| `field` | 观测云字段名 | `status_threads_connected` |
| `groupBy` | 监控分组标签 | `host` |
| `fieldType` | 字段类型 | `int` |
| `fieldFunc` | 建议聚合函数 | `max` |

缺少以上任一关键项，尤其是 `dataSource / field / groupBy` 时，必须先停下来补映射。

## 工作流程

```
输入：rule 语句或 rule 文件 + 可选指标映射
         ↓
    [第一步：抽取 monitor 结构骨架]
         ↓
    [第二步：解析 alertmanager rule]
         ↓
    [第三步：字段映射到 checkers]
         ↓
    [第四步：补全双份查询结构]
         ↓
    [第五步：验证并修复 DQL]
         ↓
输出：output/monitor/{{component}}/{{component}}.json
```

## 输入判定

### 可以直接处理的输入

- 单条 rule 语句，只要能明确 `alert / expr / for / labels / annotations`
- rule 文件中的单条或多条规则
- PrometheusRule `groups[].rules[]`
- 单条 alerting rule JSON/YAML

### 必须拒绝直接转换的输入

如果输入主体包含以下 Alertmanager 配置字段，则说明它是通知路由配置，不是告警规则：

- `route`
- `receivers`
- `inhibit_rules`
- `mute_time_intervals`
- `templates`

此时必须明确说明：当前文件不是 rule 定义，不能直接转换为观测云 monitor。

## 第一步：抽取 monitor 结构骨架

必须以 `monitor` skill 的监控器结构为准，至少保留以下层级：

- `checkers[]`
- `checkers[].jsonScript`
- `checkers[].jsonScript.targets[]`
- `checkers[].jsonScript.checkerOpt.rules[]`
- `checkers[].extend.rules[]`
- `checkers[].extend.querylist[]`

不要只生成 `jsonScript.targets`，必须同时维护 `extend.querylist`，两处查询语义保持一致。

## 第二步：解析 alertmanager rule

优先解析以下字段：

- `alert`
- `expr`
- `for`
- `labels`
- `annotations`

常见来源格式：

- PrometheusRule `groups[].rules[]`
- 单条 Prometheus alerting rule JSON

如果输入规则缺少 `expr`，或无法确定指标与数据源映射，必须停止并明确告知用户缺失项，不能臆造 DQL。

如果输入是单条 rule 语句，先标准化成以下结构再继续：

```yaml
alert: xxx
expr: xxx
for: 5m
labels:
  severity: critical
annotations:
  summary: xxx
  description: xxx
```

## 第三步：字段映射规则

| alertmanager rule 字段 | 观测云字段 | 映射规则 |
|---|---|---|
| `alert` | `jsonScript.title` | 直接作为监控器标题 |
| `alert` | `signId` | 基于标题和组件生成稳定唯一值；若已有模板则沿用模板风格 |
| `expr` | `jsonScript.targets[].dql` | 先将源规则表达式转换为 DQL，再写入 |
| `expr` | `extend.querylist[].query.q` | 与 `targets[].dql` 保持语义一致 |
| `for` | `jsonScript.every` / `interval` / `matchTimes` | 默认按 `1m` 轮询；`matchTimes = ceil(for / every)`；`interval` 为秒数 |
| `labels.severity` | `rules[].status` | 优先映射到 `critical` / `warning` / `error` / `info` |
| `annotations.summary` | `jsonScript.message` | 优先作为告警文案主体 |
| `annotations.description` | `jsonScript.message` | 若存在，拼接到告警内容中 |
| `expr` 中的分组维度 | `groupBy` / `query.groupBy` | 优先从表达式中的维度、已有模板或指标映射里提取 |
| 组件/云厂商标签 | `tagInfo[]` | 用于补充组件分类和组件名称 |

### 严重级别映射

| 源级别 | 观测云状态 |
|---|---|
| `critical` / `fatal` / `page` | `critical` |
| `warning` / `warn` | `warning` |
| `error` | `error` |
| `info` / `notice` | `info` |

若源规则没有 `labels.severity`，默认使用 `critical`，并在结果中注明是默认值。

### 比较运算映射

| 源表达式 | `conditions[].operator` |
|---|---|
| `>` | `>` |
| `>=` | `>=` |
| `<` | `<` |
| `<=` | `<=` |
| `==` | `==` |
| `!=` | `!=` |

阈值写入 `conditions[].operands`，不要把阈值硬编码进 message。

### `for` 映射规则

- 默认 `every = 1m`
- `interval = 60`
- `matchTimes = ceil(for / 1m)`
- 若没有 `for`，默认 `matchTimes = 1`
- 若 `for` 小于 `1m`，仍按 `matchTimes = 1` 处理

## 第三步半：推荐转换顺序

按以下顺序转换，避免来回回填：

1. 先从 `expr` 提取指标名、比较符、阈值、聚合函数、分组维度
2. 再把指标名映射成 `dataSource + field`
3. 先生成一份标准 DQL
4. 用这份 DQL 回填 `targets[].dql`
5. 再把同一份 DQL 回填 `extend.querylist[].query.q`
6. 最后回填 `rules / groupBy / field / fieldFunc / fieldType`

## 映射示例

### 输入示例：rule YAML

```
groups:
  - name: mysql
    rules:
      - alert: MySQLHighThreadsConnected
        expr: mysql_global_status_threads_connected > 80
        for: 5m
        labels:
          severity: critical
          service: mysql
        annotations:
          summary: MySQL 连接数过高
          description: 当前连接数持续超过 80，请检查连接池或慢查询情况
```

### 已知映射前提

- `mysql_global_status_threads_connected` 对应观测云数据源 `mysql`
- 字段映射为 `status_threads_connected`
- 按 `host` 分组
- 聚合函数使用 `max`

### 输出示例：观测云 monitor JSON 片段

```
{
  "checkers": [
    {
      "jsonScript": {
        "type": "simpleCheck",
        "every": "1m",
        "title": "MySQLHighThreadsConnected",
        "groupBy": ["host"],
        "message": ">等级：{{df_status}}  \n>主机：{{host}}\n{% if df_status != 'ok' %}\n>内容：MySQL 连接数过高。当前连接数持续超过 80，请检查连接池或慢查询情况\n{% else %}\n>恢复时间：{{ date | to_datetime }}\n>内容：告警已恢复\n{% endif %}",
        "targets": [
          {
            "dql": "M::`mysql`:(max(`status_threads_connected`) AS `Result`) BY `host`",
            "alias": "Result",
            "qtype": "dql"
          }
        ],
        "checkerOpt": {
          "rules": [
            {
              "status": "critical",
              "conditions": [
                {
                  "alias": "Result",
                  "operands": ["80"],
                  "operator": ">"
                }
              ],
              "matchTimes": 5,
              "conditionLogic": "and"
            }
          ]
        }
      },
      "extend": {
        "rules": [
          {
            "status": "critical",
            "conditions": [
              {
                "alias": "Result",
                "operands": ["80"],
                "operator": ">"
              }
            ],
            "matchTimes": 5,
            "conditionLogic": "and"
          }
        ],
        "querylist": [
          {
            "qtype": "dql",
            "query": {
              "q": "M::`mysql`:(max(`status_threads_connected`) AS `Result`) BY `host`",
              "code": "A",
              "type": "simple",
              "field": "status_threads_connected",
              "groupBy": ["host"],
              "fieldFunc": "max",
              "fieldType": "int",
              "namespace": "metric",
              "dataSource": "mysql"
            }
          }
        ]
      }
    }
  ]
}
```

### 示例说明

- `alert` 映射到 `title`
- `expr` 中的阈值 `> 80` 映射到 `conditions[].operator` 与 `operands`
- `for: 5m` 映射为 `every: 1m` + `matchTimes: 5`
- `labels.severity=critical` 映射到 `rules[].status`
- `annotations.summary/description` 合并到 `message`
- `targets[].dql` 与 `extend.querylist[].query.q` 必须一致

### 示例校验

```
./bin/dqlcheck -q 'M::`mysql`:(max(`status_threads_connected`) AS `Result`) BY `host`'
```

只有校验通过，才能输出最终监控器文件。

## 第四步：补全观测云双份查询结构

观测云监控器中，查询至少要同时出现在两个位置：

1. `checkers[].jsonScript.targets[].dql`
2. `checkers[].extend.querylist[].query.q`

并保持以下字段同步：

- `rules`
- `groupBy`
- `dataSource`
- `field`
- `fieldFunc`
- `fieldType`

最小结构示例：

```
{
  "checkers": [
    {
      "jsonScript": {
        "title": "CPU 使用率过高",
        "every": "1m",
        "groupBy": ["host"],
        "targets": [
          {
            "dql": "M::`cpu`:(max(`usage_total`) AS `Result`) BY `host`",
            "alias": "Result",
            "qtype": "dql"
          }
        ],
        "checkerOpt": {
          "rules": [
            {
              "status": "critical",
              "conditions": [
                {
                  "alias": "Result",
                  "operands": ["80"],
                  "operator": ">"
                }
              ],
              "matchTimes": 5,
              "conditionLogic": "and"
            }
          ]
        }
      },
      "extend": {
        "rules": [
          {
            "status": "critical",
            "conditions": [
              {
                "alias": "Result",
                "operands": ["80"],
                "operator": ">"
              }
            ],
            "matchTimes": 5,
            "conditionLogic": "and"
          }
        ],
        "querylist": [
          {
            "qtype": "dql",
            "query": {
              "q": "M::`cpu`:(max(`usage_total`) AS `Result`) BY `host`",
              "code": "A",
              "type": "simple",
              "field": "usage_total",
              "groupBy": ["host"],
              "fieldFunc": "max",
              "fieldType": "float",
              "namespace": "metric",
              "dataSource": "cpu"
            }
          }
        ]
      }
    }
  ]
}
```

## 第五步：表达式转换规则

`expr` 到 DQL 不是简单拷贝，必须做语义转换：

1. 识别源表达式中的指标名、聚合函数、过滤条件、分组维度、阈值比较
2. 将指标名映射到观测云 `measurement + field`
3. 将聚合函数映射到 DQL 函数，如 `max / avg / min / sum`
4. 将过滤条件写入 `{ ... }`
5. 将分组维度写入 `BY ...`

### 优先支持的表达式形态

优先处理以下常见模式：

1. `metric > 80`
2. `metric >= 80`
3. `max(metric) by (host) > 80`
4. `avg(metric{label="x"}) by (host) > 80`
5. `sum(rate(metric[5m])) by (host) > 100`

### 推荐落地方式

对常见表达式，按语义转换而不是字面转换：

- `metric > 80` -> `M::\`ds\`:(max(\`field\`) AS \`Result\`) BY ...`
- `avg(metric{label="x"}) by (host) > 80` -> `M::\`ds\`:(avg(\`field\`) AS \`Result\`) { \`label\` = 'x' } BY \`host\``
- `sum(rate(metric[5m])) by (host) > 100` -> 优先转为 rollup/速率语义等价的 DQL；若无法确认，停止并说明

### 必须停止的复杂场景

遇到以下场景时，不要猜测转换：

- 多指标二元运算，如 `a / b > 0.8`
- `and / or / unless` 组合表达式
- `label_replace`、`histogram_quantile`、复杂子查询
- 无法确认 `rate/increase/irate` 对应哪种 DQL 语义
- 依赖 recording rule，但未提供 recording rule 到原始指标的映射

**禁止**把 PromQL 直接写进 `dql` 字段。

如果遇到以下情况，必须停止并向用户说明：

- 无法判断 PromQL 指标对应哪个观测云数据源
- 无法确定分组 tag 是否存在
- 无法确定聚合函数或字段类型

## 第六步：DQL 验证（强制）

映射完成后，必须校验全部 DQL。

1. 提取 `checkers[].jsonScript.targets[].dql`
2. 提取 `checkers[].extend.querylist[].query.q`
3. 对每条语句执行 `dqlcheck -q '<DQL>'`
4. 如果失败，按报错修复后重新验证
5. 确认双份查询语义一致后再输出最终文件

命令示例：

```
./bin/dqlcheck -q 'M::`cpu`:(max(`usage_total`) AS `Result`) BY `host`'
```

通过标准：

- `targets[].dql` 全部通过
- `extend.querylist[].query.q` 全部通过
- 同一条规则的两份查询语义一致
- 没有 PromQL 残留在最终 JSON 中

## 执行约束

### 1. 没有映射信息时不要硬转

alertmanager rule 对应的告警规则通常只有源表达式，没有观测云数据源信息。若缺少映射表或现有模板，只能先整理缺失信息，不能直接输出最终监控器。

### 2. 严格复用 monitor 结构

不要发明新的 monitor JSON 结构；以 `monitor` skill 中的 `checkers -> jsonScript/extend` 结构为准。

### 3. 文案优先使用 annotations

`annotations.summary` 和 `annotations.description` 优先进入 `message`，并补齐观测云恢复模板：

```
>等级：{{df_status}}
{% if df_status != 'ok' %}
>内容：这里放 annotations 里的告警描述
{% else %}
>恢复时间：{{ date | to_datetime }}
>内容：告警已恢复
{% endif %}
```

### 4. 规则两处同步

以下内容必须同步更新，不能只改一处：

- `jsonScript.checkerOpt.rules`
- `extend.rules`
- `jsonScript.targets[].dql`
- `extend.querylist[].query.q`

## 输出检查清单

- [ ] 已从 `monitor` skill 复用监控器结构骨架
- [ ] 已完成 `alert/expr/for/labels/annotations` 字段映射
- [ ] 已确认输入不是 `alertmanager.yml` 的路由/接收器配置
- [ ] `targets[].dql` 与 `querylist[].query.q` 已同步
- [ ] 没有直接残留 PromQL 到最终 JSON
- [ ] 所有 DQL 均已通过 `dqlcheck -q '<DQL>'`
- [ ] 输出文件已写入 `output/monitor/{{component}}/{{component}}.json`
