---
name: monitor
description: 生成观测云监控器配置。根据 CSV 指标文件生成监控器 JSON 配置，适用于任何组件。
---

# 观测云监控器生成技能

## 技能描述

通用的监控器生成技能，根据提供的 CSV 指标文件，为任意组件生成观测云监控器配置文件。

## 工作流程

```
输入：csv/{{component}}*.csv + 监控需求
         ↓
    [第一步：检查 CSV 文件] ← 没有则停止
         ↓
    [第二步：解析 CSV 指标]
         ↓
    [第三步：选择关键指标] ← 5-10 个告警项
         ↓
    [第四步：配置告警规则]
         ↓
    [第五步：生成 JSON 配置]
         ↓
    [第六步：DQL 验证] ← 使用 dqlcheck 逐条验证
         ↓
输出：output/monitor/{{component}}/{{component}}.json
```

## 第六步：DQL 验证（强制）

**严格规则**：生成监控器 JSON 后，**必须**使用 `dqlcheck` 工具验证所有 DQL 查询，流程与 Dashboard 一致。

1. **提取 DQL**：
   - 从 `checkers[].jsonScript.targets[].dql` 提取
   - 从 `checkers[].extend.querylist[].query.q` 提取
2. **逐条验证**：对每条 DQL 运行 `dqlcheck -q '<DQL>'`
3. **修复失败项**：若验证失败，根据报错修复 DQL 后重新验证
4. **一致性检查**：`targets[].dql` 与 `extend.querylist[].query.q` 对应项必须语义一致
5. **过滤条件同步**：若指标需要固定标签/维度过滤（来自标签 CSV、指标元数据、对象模型或用户要求），DQL 与 `extend.querylist[].query.filters` 必须同时包含同一批过滤条件
6. **聚合函数核对**：按指标含义选择 `last`、`max`、`min`、`sum`、`avg` 等函数；已由采集侧聚合的水位值、状态值、计数快照等优先使用 `last`，不要默认套 `avg`
7. **记录结果**：仅保留通过验证的 DQL 到最终监控器配置

**dqlcheck 命令示例**：

```bash
# 验证监控器中的普通指标 DQL
./bin/dqlcheck -q 'M::`mysql`:(max(`Threads_connected`) AS `Result`) BY `host`'

# 验证包含过滤条件与分组的 DQL
./bin/dqlcheck -q 'M::`redis`:(avg(`used_memory_percent`) AS `Result`) { `host` = '#{host}' } BY `host`'
```

**验证通过标准**：

- ✅ `targets[].dql` 全部通过 `dqlcheck`
- ✅ `extend.querylist[].query.q` 全部通过 `dqlcheck`
- ✅ 同一告警器内 targets/querylist 的 DQL 一致
- ❌ 若存在无法修复的 DQL，必须在输出中明确标注失败项并提示用户

## 执行规则

### 第一步：检查 CSV 文件（必需）

**在开始生成监控器之前，必须检查 CSV 文件是否存在：**

1. 搜索 `csv/` 目录下是否有匹配的 CSV 文件
2. 搜索模式：`csv/{{component}}*.csv` 或 `csv/{{component}}.csv`
3. **如果没有找到 CSV 文件，必须停止并提示用户：**

```
❌ 未找到 CSV 指标文件

请提供指标文件，存放位置：`csv/{{component}}.csv`

CSV 文件格式示例：
```csv
指标名，字段类型，单位，操作
cpu_util,float，%,
memory_util,float，%,
disk_util,float，%,
```

指标来源说明：
- 原生指标：从观测云数据探索中导出
- 云服务指标：从云厂商 API 文档整理
```

**只有 CSV 文件存在时，才继续执行后续步骤。**

### 第二步：解析 CSV 文件

读取 CSV 文件，提取指标信息：
- **指标名**：用于 DQL 查询的字段名
- **字段类型**：float/int 等
- **单位**：用于判断阈值类型（%/ms/bytes 等）
- **操作**：额外的处理说明

### 第三步：选择关键指标

根据组件类型和指标特性，选择 **5-10 个关键指标** 作为告警：

**选择原则：**

| 指标类型 | 选择优先级 | 说明 |
|---------|-----------|------|
| 可用性指标 | P0 | 如 broker_online_rate、节点在线率 |
| 资源使用率 | P0 | CPU、内存、磁盘使用率 |
| 性能指标 | P1 | P99 延迟、响应时间 |
| 业务指标 | P1 | QPS、TPS、消息堆积量 |
| 异常指标 | P1 | 错误率、重平衡次数 |

**指标口径自检：**

- 使用率/比率字段先核对真实取值范围。样本为 `0~1` 时阈值也使用小数（如 `0.7/0.85`）；只有样本为 `0~100` 时才使用 `70/85`。官方单位写 `%` 不能替代真实数据量纲检查。
- 原始值为 `0~1` 且 DQL 未乘 100 时，消息模板不要直接拼接 `%`；应显示原始比例，或将查询结果、阈值和消息单位一起换算到 `0~100`。
- “出现”“新增”类告警优先选择 `_incr`、`increase`、`delta` 等增量指标；不要用累计长度、历史总数或当前日志长度冒充新增事件。
- 延迟分桶、慢请求计数等高频事件指标没有业务基线时不默认配置“出现即告警”；优先使用平均/最大延迟水位，或要求用户提供可接受频率。

**阈值设置参考：**

| 指标类型 | 告警条件 | 阈值 | 级别 | 持续时间 |
|---------|---------|------|------|---------|
| 使用率 (百分比) | 严重告警 | >= 80% | critical | 5m |
| 使用率 (百分比) | 警告 | >= 60% | warning | 5m |
| 磁盘使用率 | 严重告警 | >= 85% | critical | 5m |
| 磁盘使用率 | 警告 | >= 75% | warning | 5m |
| 可用性 | 严重告警 | < 100% | critical | 5m |
| 延迟 (ms) | 警告 | >= 1000ms | warning | 5m |
| 堆积量 | 警告 | >= 10000 | warning | 5m |
| 错误率 | 严重告警 | >= 1% | critical | 5m |
| 错误率 | 警告 | >= 0.1% | warning | 5m |

**等级与区间规则：**

- 观测云告警等级从高到低为 `fatal`、`critical`、`error`、`warning`
- 单个指标不需要覆盖四个等级，通常选择 1-2 个符合风险程度的等级
- 配置两个及以上等级时必须连续，不跳档；例如使用 `warning` + `error` 或 `error` + `critical`，不要直接使用 `warning` + `critical`
- 多等级阈值只配置各等级的触发下界，例如 `warning >= 75`、`error >= 85`；低等级不额外添加 `< 85`，开放区间由系统按等级优先级处理
- `<` 仅用于指标本身的低值异常，例如可用性或健康度 `< 1`，不用于切分高水位等级区间
- 上方阈值表是选型参考，不表示必须同时配置表中所有等级

### 第四步：配置告警规则

每个告警规则包含：
- **title**: 告警名称（清晰描述问题）
- **groupBy**: 分组标签（从 CSV 指标中推断，如 instance_id、host 等）
- **message**: 告警消息模板（包含变量恢复信息）
- **targets**: DQL 查询目标
- **rules**: 告警规则（级别、条件、阈值）

**查询配置要求：**

- `targets[].dql` 是执行查询，`extend.querylist[].query.q` 是编辑器查询，两处 DQL 必须保持一致
- `extend.querylist[].query.fieldFunc` 必须与 DQL 中的函数一致；预聚合指标、状态指标、资源水位快照优先使用 `last`
- 固定标签/维度过滤必须同时写入 DQL 过滤段和 `extend.querylist[].query.filters`，例如 `dimensions = '<dimension_value>'` 不能只出现在其中一处
- `extend.querylist[].query.groupBy` 必须与 DQL 的 `BY` 字段一致，避免界面展示的查询行和实际告警口径不同

### 第五步：生成 JSON 配置

按照观测云监控器格式生成配置文件。

### 第六步：执行 DQL 校验并回写

生成 JSON 后，必须执行以下动作：

1. 提取所有 DQL（`targets[].dql` + `querylist[].query.q`）
2. 逐条运行 `dqlcheck`
3. 修复失败项并重新验证
4. 将修复后的 DQL 同步回两个位置，避免结构内语句不一致
5. 确认全部通过后，才输出最终文件

## 监控器结构

```json
{
  "checkers": [
    {
      "jsonScript": {
        "type": "simpleCheck",
        "every": "5m",
        "title": "告警名称",
        "groupBy": ["instance_id"],
        "message": ">等级：{{df_status}}  \n>实例：{{instance_id}}\n{% if  df_status != 'ok' %}\n>内容：告警内容，请排查！\n{% else %}\n>恢复时间： {{ date | to_datetime }}\n>内容：告警已恢复\n{% endif %}",
        "targets": [
          {
            "dql": "M::`data_source`:(max(`metric`)) BY `instance_id`",
            "alias": "Result",
            "qtype": "dql"
          }
        ],
        "channels": [],
        "interval": 300,
        "atAccounts": [],
        "checkerOpt": {
          "rules": [
            {
              "status": "critical",
              "conditions": [
                {
                  "alias": "Result",
                  "operands": ["80"],
                  "operator": ">="
                }
              ],
              "matchTimes": 1,
              "conditionLogic": "and"
            }
          ],
          "infoEvent": false,
          "openMatchTimes": false,
          "openOkConditions": false,
          "disableLargeScaleEventProtect": false
        },
        "eventCharts": [],
        "atNoDataAccounts": [],
        "eventChartEnable": false,
        "disableCheckEndTime": false,
        "recoverNeedPeriodCount": 1
      },
      "extend": {
        "rules": [
          {
            "status": "critical",
            "conditions": [
              {
                "alias": "Result",
                "operands": ["80"],
                "operator": ">="
              }
            ],
            "matchTimes": 1,
            "conditionLogic": "and"
          }
        ],
        "manager": [],
        "funcName": "",
        "querylist": [
          {
            "uuid": "metric_001",
            "qtype": "dql",
            "query": {
              "q": "M::`data_source`:(max(`metric`)) BY `instance_id`",
              "code": "A",
              "type": "simple",
              "alias": "",
              "field": "metric",
              "filters": [],
              "groupBy": ["instance_id"],
              "funcList": [],
              "fieldFunc": "max",
              "fieldType": "float",
              "namespace": "metric",
              "dataSource": "data_source",
              "groupByTime": "",
              "additionalFields": null
            },
            "disabled": false,
            "datasource": "dataflux"
          }
        ],
        "issueLevelUUID": "",
        "needRecoverIssue": false,
        "isNeedCreateIssue": false,
        "issueDfStatus": [],
        "bindIncidentsInfo": [],
        "incidentsTags": []
      },
      "is_disable": false,
      "tagInfo": [
        {"name": "组件分类"},
        {"name": "组件名称"}
      ],
      "secret": "",
      "type": "trigger",
      "signId": "unique_sign_id",
      "monitorName": "default",
      "alertPolicyNames": []
    }
  ]
}
```

## 告警消息模板

### 通用模板
```
>等级：{{df_status}}  
>{{group_by_key}}：{{group_by_value}}
{% if  df_status != 'ok' %}
>内容：{{metric_name}}为 {{Result}}{{unit}}，请排查！
{% else %}
>恢复时间： {{ date | to_datetime }}
>内容：告警已恢复
{% endif %}
```

非恢复分支只描述触发事实和“请排查！”，不要写可能原因、建议处置步骤或未经确认的根因推测。

## 验证清单

- [ ] CSV 文件存在（必需条件）
- [ ] 选择 5-10 个关键监控指标
- [ ] 阈值设置合理
- [ ] 使用率/比率阈值与真实 `0~1` 或 `0~100` 取值范围一致
- [ ] 告警消息单位与 DQL 结果量纲一致，原始 `0~1` 比率未被误显示为百分数
- [ ] “出现/新增”告警使用增量指标，没有误用累计长度或历史总数
- [ ] 高频延迟桶或事件计数具有业务基线，否则未配置固定阈值告警
- [ ] 多等级规则不跳档，使用的等级连续且各等级只配置触发下界，无需强行覆盖四级
- [ ] groupBy 标签正确
- [ ] 告警消息模板清晰
- [ ] tagInfo 包含组件分类和名称
- [ ] JSON 格式正确
- [ ] 已提取 `targets[].dql` 和 `querylist[].query.q` 的全部 DQL
- [ ] 所有 DQL 均通过 `dqlcheck -q '<DQL>'` 验证
- [ ] DQL 失败项已修复并完成二次验证
- [ ] `targets[].dql` 与 `querylist[].query.q` 保持一致
- [ ] 固定标签/维度过滤同时存在于 DQL 和 `query.filters`
- [ ] DQL 聚合函数与 `fieldFunc` 一致，已聚合指标未默认使用 `avg`

## 使用示例

### 示例 1：生成 MySQL 监控器
```
/skill monitor
输入：生成 mysql 监控器
检查：csv/mysql*.csv 是否存在
输出：output/monitor/mysql/mysql.json
```

### 示例 2：生成火山引擎 Kafka 监控器
```
/skill monitor
输入：生成 volcengine_kafka 监控器
检查：csv/volcengine_kafka*.csv 是否存在
输出：output/monitor/volcengine_vcm_kafka/volcengine_vcm_kafka.json
```

### 示例 3：生成 Redis 监控器
```
/skill monitor
输入：生成 redis 监控器
检查：csv/redis*.csv 是否存在
输出：output/monitor/redis/redis.json
```

## 相关文件

- 输入：`csv/{{component}}*.csv`
- 输出：`output/monitor/{{component}}/{{component}}.json`
- 参考模板：`template/monitor/`
