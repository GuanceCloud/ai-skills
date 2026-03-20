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
输出：output/monitor/{{component}}/{{component}}.json
```

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

### 第四步：配置告警规则

每个告警规则包含：
- **title**: 告警名称（清晰描述问题）
- **groupBy**: 分组标签（从 CSV 指标中推断，如 instance_id、host 等）
- **message**: 告警消息模板（包含变量恢复信息）
- **targets**: DQL 查询目标
- **rules**: 告警规则（级别、条件、阈值）

### 第五步：生成 JSON 配置

按照观测云监控器格式生成配置文件。

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

## 验证清单

- [ ] CSV 文件存在（必需条件）
- [ ] 选择 5-10 个关键监控指标
- [ ] 阈值设置合理
- [ ] groupBy 标签正确
- [ ] 告警消息模板清晰
- [ ] tagInfo 包含组件分类和名称
- [ ] JSON 格式正确

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
