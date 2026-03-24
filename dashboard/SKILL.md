---
name: dashboard
description: 生成观测云 Dashboard 仪表板。根据 CSV 指标文件生成 Dashboard JSON 配置。
---

# 观测云 Dashboard 生成技能

## 技能描述

根据 CSV 指标文件生成观测云 Dashboard JSON 配置文件。

## 工作流程

```
输入：csv/{{type}}*.csv
        ↓
   [检查 CSV 文件] ← 没有文件则拒绝生成
        ↓
     [解析指标]
        ↓
   [专业运维基线设计]
        ↓
     [生成 JSON]
        ↓
   [样式自动修正] ← 强制补齐分组与配色
        ↓
   [DQL 验证] ← 使用 dqlcheck 逐条验证
        ↓
输出：output/dashboard/{{type}}/{{type}}.json
```

### 第四步：样式自动修正（强制）

**严格规则**：生成 Dashboard JSON 后，必须先执行样式自动修正，再进入 DQL 验证。

**自动修正项**（必须全部执行）：

1. **分组展开修正**：`dashboardExtend.groupUnfoldStatus` 中所有分组强制设为 `true`
2. **分组顺序修正**：`概览` 固定第一；若存在列表分组（`*列表`），固定第二；其他分组按业务顺序排后
3. **分组配色修正（科技蓝）**：
   - 移除 `dashboardExtend.groupColor`
   - `main.groups[].extend.bgColor` 强制使用科技蓝色盘按顺序生成的 `rgba(...)`
   - 移除 `main.groups[].extend.colorKey`
4. **概览配色修正（多彩数据）**：
   - 每个 singlestat 强制补齐 `extend.settings.bgColor`（使用多彩调色盘对应的 14% 透明背景）
   - 每个 singlestat 强制补齐 `extend.settings.valueColor`，并按多彩调色盘轮换
5. **回写修正结果**：自动修正后的 JSON 才能作为最终输出与后续校验输入

**自动修正伪代码**：

```python
def to_alpha_bg(hex_color, alpha=0.12):
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"

def autofix_dashboard_style(dashboard):
    groups = [g['name'] for g in dashboard['main']['groups']]

    # 1) 不折叠
    dashboard['dashboardExtend']['groupUnfoldStatus'] = {name: True for name in groups}

    # 2) 分组顺序：概览 -> 列表 -> 其他
    list_groups = [g for g in groups if '列表' in g and g != '概览']
    other_groups = [g for g in groups if g not in (['概览'] + list_groups)]
    ordered = (['概览'] if '概览' in groups else []) + list_groups + other_groups

    # 3) 分组科技蓝（严格顺序）
    tech = ['#3B82F6', '#60A5FA', '#22C55E', '#F59E0B', '#EF4444', '#06B6D4']
    dashboard['dashboardExtend'].pop('groupColor', None)

    # 4) 概览多彩（严格顺序）
    multi = ['#06B6D4', '#10B981', '#EAB308', '#F97316', '#EF4444', '#8B5CF6', '#EC4899']
    i = 0
    for chart in dashboard['main']['charts']:
        gname = chart.get('group', {}).get('name')
        st = chart.setdefault('extend', {}).setdefault('settings', {})
        if chart.get('type') == 'singlestat' and gname == '概览':
            st['valueColor'] = multi[i % len(multi)]
            st['bgColor'] = to_alpha_bg(st['valueColor'], 0.66)
            st['borderColor'] = '#E5E7EB'
            i += 1
        else:
            # 分组图背景
            if gname == '概览':
                st.setdefault('bgColor', to_alpha_bg('#3B82F6', 0.08))
            else:
                st.setdefault('bgColor', to_alpha_bg('#3B82F6', 0.08))

    # 5) 分组 UI 兼容修正：仅保留 bgColor（移除 colorKey）
    for idx, g in enumerate(dashboard['main']['groups']):
        g_ext = g.setdefault('extend', {})
        g_ext['bgColor'] = to_alpha_bg(tech[idx % len(tech)], 0.10)
        g_ext.pop('colorKey', None)

    return dashboard
```

### 第五步：DQL 验证（强制）

**严格规则**：生成 Dashboard JSON 后，**必须**使用 `dqlcheck` 工具验证所有 DQL 查询。

1. **提取 DQL**：从 `main.charts[].queries[].query.q` 中提取所有 DQL 语句
2. **逐条验证**：对每条 DQL 运行 `dqlcheck -q '<DQL>'`
3. **修复失败项**：若验证失败，根据错误信息修复 DQL 后重新验证
4. **记录结果**：只有通过验证的 DQL 才能保留在最终 Dashboard 中

**dqlcheck 命令示例**：
```bash
# 验证单条 DQL
./bin/dqlcheck -q 'M::`mysql`:(AVG(`Threads_connected`) AS `连接数`) { `host` = '#{host}' } BY `host`'

# 验证 singlestat 的 series_sum 包装 DQL
./bin/dqlcheck -q 'series_sum("M::`mysql`:(AVG(`Threads_connected`) AS `连接数`) { `host` = '#{host}' } BY `host`")'
```

**验证通过标准**：
- ✅ 所有 sequence 图表的 DQL 通过 `dqlcheck`
- ✅ 所有 singlestat 图表的 DQL 通过 `dqlcheck`
- ✅ 所有 table 图表的 DQL 通过 `dqlcheck`
- ❌ 若有 DQL 验证失败且无法修复，需在输出中标注并提示用户

### 第五步：变量命名验证（强制）

**严格规则**：生成 Dashboard 后，**必须**验证变量命名一致性。

```python
def validate_variable_consistency(dashboard):
    """验证变量命名一致性"""
    var_code = dashboard['main']['vars'][0]['code']
    errors = []
    
    for chart in dashboard['main']['charts']:
        for q in chart['queries']:
            query = q['query']
            
            # 检查 DQL 中的 BY
            if f'BY `{var_code}`' not in query['q']:
                errors.append(f"图表 {chart['name']}: DQL 中 BY 未使用 `{var_code}`")
            
            # 检查 filters
            for f in query.get('filters', []):
                if f['name'] != var_code:
                    errors.append(f"图表 {chart['name']}: filter name 未使用 `{var_code}`")
                if f['value'] != f"#{{{var_code}}}":
                    errors.append(f"图表 {chart['name']}: filter value 未使用 `#{{{var_code}}}`")
            
            # 检查 groupBy
            if var_code not in query.get('groupBy', []):
                errors.append(f"图表 {chart['name']}: groupBy 未包含 `{var_code}`")
    
    return errors
```

**验证检查项**：
- ✅ 变量 `code` 来自 CSV 的实际 tag key（不做名称强制转换）
- ✅ 所有 DQL 的 `BY` 子句使用变量 `code`
- ✅ 所有 filters 的 `name` 使用变量 `code`
- ✅ 所有 filters 的 `value` 使用 `#{code}` 格式
- ✅ 所有 groupBy 数组包含变量 `code`

**错误示例**（必须拒绝）：
```json
// ❌ 错误：变量与 DQL 不一致
{
  "vars": [{"code": "instanceId"}],
  "charts": [{
    "query": {"q": "... BY `instance_id`"}
  }]
}
```

**正确示例**：
```json
// ✅ 正确：使用 CSV 的实际 tag key
{
  "vars": [{"code": "instanceId"}],
  "charts": [{
    "query": {
      "q": "... BY `instanceId`",
      "filters": [{"name": "instanceId", "value": "#{instanceId}"}],
      "groupBy": ["instanceId"]
    }
  }]
}
```

## 执行规则（重要）

### 第一步：强制检查 CSV 文件

**严格规则**：在开始生成 Dashboard 之前，**必须**检查 CSV 文件是否存在。

1. 搜索 `csv/` 目录下是否有匹配的 CSV 文件
2. 搜索模式：`csv/{{type}}*.csv` 或 `csv/{{type}}.csv` 或 `csv/{{type}}/*.csv`
3. **如果没有找到 CSV 文件，必须拒绝生成并提示用户**：

```
❌ 无法生成 Dashboard

原因：未找到 CSV 指标文件

请提供指标文件，存放位置：
- `csv/{{type}}.csv`
- `csv/{{type}} 指标.csv`
- `csv/{{type}}/{{type}} 指标.csv`

CSV 文件格式示例：
```csv
指标名，字段类型，单位，操作
Threads_connected,int,-,host
Questions,int,-,host
Com_commit,int,-,host
```

**重要**：没有 CSV 文件无法生成 Dashboard，请先从观测云数据探索导出指标或整理云厂商 API 指标。
```

**禁止行为**（违反将导致 Dashboard 无法使用）：
- ❌ **严禁**从网上搜索指标来生成 Dashboard
- ❌ **严禁**使用示例指标或假设指标存在
- ❌ **严禁**在缺少 CSV 文件时尝试生成 Dashboard
- ❌ **严禁**生成没有 units 配置的图表
- ✅ **必须**基于用户提供的 CSV 文件生成
- ✅ **必须**为每个图表配置 units 字段

### 第二步：解析 CSV 文件

读取 CSV 文件，提取：
- `指标名`/`metric_name`: 指标名称（用于 DQL 查询）
- `字段类型`/`data_type`: 数据类型（int/float）
- `单位`/`unit`: 单位（用于图表单位配置）
- `操作`/`tag_key`/`Tag`: 标签键（**用于变量定义**，以 CSV 实际 tag 为准）

### 第三步：从 CSV 提取变量名（强制规则）

**根据 CSV 实际 tag 自动确定变量 code**：

```python
def get_variable_code(csv_row):
    # 支持中英文列名
    tag_text = csv_row.get('操作') or csv_row.get('tag_key') or csv_row.get('Tag') or ''
    tags = [t.strip() for t in tag_text.split(',') if t.strip()]

    # 常用优先级：instanceId > instance_id > host
    for key in ['instanceId', 'instance_id', 'host']:
        if key in tags:
            return key

    # 否则使用第一个实际 tag，若为空再回退 host
    return tags[0] if tags else 'host'
```

**强制检查**：
- ✅ 变量 `code` 必须来自 CSV 实际 tag
- ✅ 所有 DQL、filters、groupBy 必须与该变量 `code` 一致
- ✅ 允许 `instanceId`、`instance_id`、`host` 或其他业务 tag

### 第三步补充：专业运维覆盖基线（强制）

**目标**：避免仅有少量概览图，必须具备运维排障可用性。

**通用最低要求**：
- ✅ 至少 1 个实例级 `table` 面板（按核心指标排序）
- ✅ 至少 1 个 `singlestat` 概览行（4~8 个关键 KPI）
- ✅ 至少 6 个 `sequence` 趋势图（按主题分组）

**MySQL 场景最低要求**（若存在对应 CSV）：
- ✅ `mysql`：连接、查询、事务、网络至少各 1 张趋势图
- ✅ `mysql_user_status`：至少 1 张用户维度 `table`（`BY host, user`）
- ✅ `mysql_schema`：至少 1 张 schema 维度 `table`（`BY host, schema_name`）
- ✅ `mysql_table_schema`：至少 1 张表维度 `table`（`BY host, table_schema, table_name`）
- ✅ `mysql_replication`：至少 1 张复制相关图（如 `Replicas_connected`）

**禁止**：
- ❌ 只做概览图，不提供实例/用户/库表维度表格
- ❌ 有 CSV 指标却不落图（除非指标明确无运维价值并在说明中标注）

### 第四步：生成 Dashboard JSON

严格按照以下规范生成，**必须配置单位**。

## 核心规范

### 1. 基础结构

```json
{
  "title": "MySQL 监控",
  "dashboardType": "CUSTOM",
  "dashboardExtend": {
    "groupUnfoldStatus": {"概览": true, "性能": true, "实例列表": true}
  },
  "dashboardMapping": [],
  "dashboardOwnerType": "node",
  "iconSet": {"url": "...", "icon": "..."},
  "dashboardBindSet": [],
  "thumbnail": "",
  "tagInfo": [{"name": "数据库"}, {"name": "MySQL"}],
  "summary": "描述",
  "main": {
    "vars": [...],
    "charts": [...],
    "groups": [...]
  }
}
```

**注意**：
- `main` 中**不要**包含 `chartGroupPos` 字段
- `groups` 必须在 `main` 中定义

### 2. 变量配置

```json
{
  "name": "主机",
  "seq": 0,
  "datasource": "dataflux",
  "code": "host",
  "type": "QUERY",
  "definition": {
    "tag": "",
    "field": "",
    "value": "SHOW_TAG_VALUE(from=['mysql'],keyin=['host'])[10m]",
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

**变量命名规范**：

| 来源 | 变量 code | DQL 引用 |
|------|----------|---------|
| CSV `Tag` 包含 `instanceId` | `instanceId` | `#{instanceId}` |
| CSV `Tag` 包含 `instance_id` | `instance_id` | `#{instance_id}` |
| CSV `Tag` 包含 `host` | `host` | `#{host}` |

**重要规则**：
- ✅ 变量 `code` 必须与 CSV 中的 `操作`/`tag_key` 列一致
- ✅ DQL 中的 `BY`、`filters.name`、`value` 必须与变量 `code` 一致
- ✅ 不做 tag 名称强制转换，严格按 CSV 实际值生成

**示例（按 CSV 实际 tag）**：
```json
{
  "vars": [{
    "code": "instanceId",  // 变量代码
    "definition": {
      "value": "SHOW_TAG_VALUE(from=['aliyun_acs_ecs_dashboard'],keyin=['instanceId'])[10m]"
    }
  }],
  "charts": [{
    "queries": [{
      "query": {
        "q": "M::`aliyun_acs_ecs_dashboard`:(AVG(`CPUUtilization_Average`) AS `CPU 使用率`) { `instanceId` = '#{instanceId}' } BY `instanceId`",
        "filters": [{"name": "instanceId", "value": "#{instanceId}"}],
        "groupBy": ["instanceId"]
      }
    }]
  }]
}
```

### 3. 分组配置（必需）

```json
{
  "main": {
    "groups": [
      {
        "name": "概览",
        "extend": {
          "bgColor": "rgba(59, 130, 246, 0.10)"
        }
      },
      {
        "name": "实例列表",
        "extend": {
          "bgColor": "rgba(96, 165, 250, 0.10)"
        }
      },
      {
        "name": "性能",
        "extend": {
          "bgColor": "rgba(34, 197, 94, 0.10)"
        }
      }
    ]
  }
}
```

**分组展开规则（强制）**：
- ✅ 不折叠分组：`dashboardExtend.groupUnfoldStatus` 中所有分组均为 `true`
- ✅ 概览组默认展开，其他组也保持展开，不再使用默认折叠

**分组顺序规则（强制）**：
- ✅ `概览` 组必须排在第一位
- ✅ 若存在列表类分组（如 `实例列表`、`主机列表`、`库表列表`），必须紧跟在 `概览` 后面
- ✅ 其他趋势/明细分组排在列表组之后

**配色体系（强制）**：

1) **分组图使用「科技蓝」**（严格按下列顺序轮换）
- 次主色 `#3B82F6`
- 高亮 `#60A5FA`
- 成功 `#22C55E`
- 警告 `#F59E0B`
- 错误 `#EF4444`
- 信息 `#06B6D4`
- 背景 `#F1F5F9`
- 边框 `#CBD5E1`

2) **概览图使用「多彩数据」**（严格按下列顺序）
- 调色盘：`#06B6D4`、`#10B981`、`#EAB308`、`#F97316`、`#EF4444`、`#8B5CF6`、`#EC4899`
- 背景：`#F9FAFB`
- 边框：`#E5E7EB`
- 概览多卡片应按调色盘轮换，避免全部同色

**配色落地规则（强制）**：
- ✅ `dashboardExtend.groupColor` 必须移除
- ✅ `main.groups[].extend.bgColor` 必须使用 `rgba(...)`（按科技蓝色盘顺序生成）
- ✅ `main.groups[].extend.colorKey` 必须移除
- ✅ 每个 singlestat 的 `extend.settings.bgColor` 必须使用 `rgba(...)`（由 valueColor 按 14% 透明度生成）
- ✅ 每个 singlestat 的 `extend.settings.borderColor` 必须固定为 `#E5E7EB`
- ✅ 每个 singlestat 的 `extend.settings.valueColor` 必须来自多彩调色盘，并按面板顺序轮换

### 4. 图表结构（必须配置单位）

```json
{
  "extend": {
    "settings": {
      "alias": [],
      "units": [
        {
          "key": "字段名",
          "name": "字段名",
          "unit": "单位符号",
          "units": ["单位类型", "单位子类型"]
        }
      ],
      "colors": [{"key": "字段名", "name": "字段名", "color": "#xxx"}],
      "levels": [],
      "density": "medium",
      "showTitle": true,
      "titleDesc": "描述",
      "showLegend": true,
      "currentChartType": "sequence",
      "showFieldMapping": false,
      "decimalPlaces": 0
    },
    "fixedTime": "",
    "isRefresh": true
  },
  "group": {"name": "分组名"},
  "chartGroupUUID": "chtg_xxx",
  "name": "图表名",
  "pos": {"h": 8, "w": 12, "x": 0, "y": 0},
  "type": "sequence",
  "queries": [...],
  "prevGroupName": "上一个分组名或 null",
  "uuid": "chrt_xxx"
}
```

### 5. 单位配置（强制要求）

**每个图表必须配置 units 字段**，否则数据无法正常展示。

**生成图表时的单位处理流程**：
1. 从 CSV 文件中读取每个指标的 `单位` 列
2. 根据单位映射表转换为标准的 `units` 配置
3. **如果 CSV 中没有单位信息，使用 `["custom", ""]` 作为默认值**
4. 每个查询字段都需要配置对应的 units 条目

#### 单位映射表

| CSV 单位 | units 配置 | 说明 |
|---------|-----------|------|
| `-` | `["custom", ""]` | 无单位（计数） |
| `percent（百分比）` | `["percent", "percent"]` | 百分比 |
| `B（数据大小）` | `["digital", "B"]` | 字节 |
| `KB（数据大小）` | `["digital", "KB"]` | 千字节 |
| `MB（数据大小）` | `["digital", "MB"]` | 兆字节 |
| `GB（数据大小）` | `["digital", "GB"]` | 吉字节 |
| `B/S（流量）` | `["traffic", "B/S"]` | 流量 |
| `KB/S（流量）` | `["traffic", "KB/S"]` | 流量 |
| `MB/S（流量）` | `["traffic", "MB/S"]` | 流量 |
| `ms（时间间隔）` | `["time", "ms"]` | 毫秒 |
| `s（时间间隔）` | `["time", "s"]` | 秒 |
| `iops（吞吐）` | `["throughput", "iops"]` | IOPS |
| `ops（吞吐）` | `["throughput", "ops"]` | 操作/秒 |
| `reqps（吞吐）` | `["throughput", "reqps"]` | 请求/秒 |

#### 配置示例

```json
{
  "units": [
    {"key": "QPS", "name": "QPS", "unit": "req/s", "units": ["throughput", "reqps"]},
    {"key": "连接数", "name": "连接数", "unit": "", "units": ["custom", ""]},
    {"key": "锁等待时间", "name": "锁等待时间", "unit": "ms", "units": ["time", "ms"]},
    {"key": "CPU 使用率", "name": "CPU 使用率", "unit": "%", "units": ["percent", "percent"]}
  ]
}
```

### 6. 概览图（singlestat）- 关键规则

**正确示例**（UI 正常展示）：
```json
{
  "type": "singlestat",
  "extend": {
    "settings": {
      "units": [{"key": "连接数", "name": "连接数", "unit": "", "units": ["custom", ""]}],
      "colors": [],
      "decimalPlaces": 0,
      "valueColor": "#3B82F6",
      "bgColor": "rgba(59, 130, 246, 0.12)"
    }
  },
  "queries": [{
    "query": {
      "q": "series_sum(\"M::`mysql`:(`Threads_connected` AS `连接数`) { `host` = '#{host}' } BY `host`\")",
      "code": "A",
      "fill": null,
      "type": "simple",
      "alias": "连接数",
      "field": "Threads_connected",
      "groupBy": ["host"],
      "funcList": [],
      "fieldFunc": "last",
      "fieldType": "float",
      "namespace": "metric",
      "dataSource": "mysql",
      "queryFuncs": [{"args": [], "name": "series_sum"}],
      "groupByTime": ""
    },
    "datasource": "dataflux"
  }]
}
```

**概览图关键规则**（必须全部满足）：
- ✅ 必须使用 `series_sum` 聚合函数
- ✅ 必须包含 `BY host` 分组
- ✅ `fill` 设置为 `null`
- ✅ `funcList` 设置为 `[]`（**空数组**，不是 `["last"]`）
- ✅ `fieldFunc` 设置为 `last`（**不是** `avg`）
- ✅ **必须配置 units**
- ✅ DQL 中**不要**使用 `AVG()`、`SUM()` 等聚合函数，**直接写字段名**
- ❌ **不能使用 rollup 语法**

**概览图 UI 渲染稳定性规则**（强制）：
- ✅ `queries[]` 外层必须包含：`name`、`type`、`unit`、`color`、`qtype`
- ✅ `queries[].type` 必须为 `singlestat`，`queries[].qtype` 必须为 `dql`
- ✅ `query.filters` 必须存在，且 `name/value` 与变量 code 一致（如 `instanceId` / `#{instanceId}`）
- ✅ `extend.settings` 建议固定包含：`alias`、`levels`、`density`、`showTitle`、`titleDesc`、`showLegend`、`currentChartType`、`showFieldMapping`
- ✅ `extend.settings.bgColor` 必须存在且使用与 valueColor 对应的透明背景
- ✅ `extend.settings.valueColor` 必须命中多彩调色盘

**概览图单位规则（强制）**：
- ✅ 若 CSV 单位可映射（如 `%`、`ms`、`B/S`、`reqps`、`ops`、`iops`），`units[].units` 必须使用标准映射，不可默认 `custom`
- ✅ 仅当 CSV 单位为 `-` 或确实无法识别时，才允许使用 `["custom", ""]`
- ✅ `units[].unit` 必须与 `units[].units` 语义一致（如 `%` ↔ `["percent", "percent"]`）

**对比示例**：

| 配置项 | ❌ 错误（UI 不展示） | ✅ 正确（UI 正常） |
|--------|-------------------|------------------|
| DQL | `AVG(\`field\`) AS \`alias\`` | `\`field\` AS \`alias\`` |
| funcList | `["last"]` | `[]` |
| fieldFunc | `avg` | `last` |

**重要**：`funcList: []` 和 `fieldFunc: last` 是 singlestat 正常显示的关键，错误的配置会导致 UI 不展示数据。

### 7. 时序图（sequence）- 关键配置

```json
{
  "type": "sequence",
  "extend": {
    "settings": {
      "alias": [],
      "units": [{"key": "QPS", "name": "QPS", "unit": "req/s", "units": ["throughput", "reqps"]}],
      "colors": [{"key": "QPS", "name": "QPS", "color": "#3B82F6"}],
      "levels": [],
      "density": "medium",
      "showTitle": true,
      "titleDesc": "QPS 趋势",
      "showLegend": true,
      "currentChartType": "area",
      "chartType": "areaLine",
      "showFieldMapping": false
    },
    "fixedTime": "",
    "isRefresh": true
  },
  "queries": [{
    "name": "",
    "type": "sequence",
    "unit": "",
    "color": "",
    "qtype": "dql",
    "query": {
      "q": "M::`mysql`:(rate(`Questions`) AS `QPS`) { `host` = '#{host}' } BY `host`",
      "code": "A",
      "fill": "linear",
      "type": "simple",
      "alias": "QPS",
      "field": "Questions",
      "filters": [{"id": "qps_filter", "op": "=", "name": "host", "type": "", "logic": "and", "value": "#{host}"}],
      "groupBy": ["host"],
      "funcList": [],
      "fieldFunc": "last",
      "fieldType": "float",
      "namespace": "metric",
      "dataSource": "mysql",
      "queryFuncs": [],
      "groupByTime": ""
    },
    "datasource": "dataflux"
  }]
}
```

**时序图规则**：
- ✅ 计数器优先使用 rollup（如 ``field [::1m:irate]``），`fieldFunc` 设置为 `"last"`
- ✅ 若图表出现“仅点不成线”或 UI 渲染异常，可降级为 `fill(last(field), linear)`
- ✅ 非计数器（如连接数、使用率）使用 `AVG(field)`，`fieldFunc` 设置为 `"avg"`
- ✅ `fill` 设置为 `"linear"`
- ✅ `currentChartType` 设置为 `"area"`
- ✅ `chartType` 设置为 `"areaLine"`
- ✅ `funcList` 设置为 `[]`（空数组）
- ✅ `queryFuncs` 设置为 `[]`（空数组）
- ✅ `groupByTime` 设置为 `""`（空字符串）
- ✅ **必须配置 units**
- ✅ filters 的 `op` 使用 `"="`（等号），**不要**使用 `"=~"`（正则）
- ✅ query 结构必须包含：`name`、`type`、`unit`、`color`、`qtype`
- ❌ **不要**添加 `showLine`、`openStack`、`stackType` 等多余字段
- ❌ **不要**添加 `xAxisShowType`、`isTimeInterval`、`timeInterval`、`legendPostion` 等字段

**fieldFunc 配置**：
| DQL 类型 | fieldFunc | 示例 |
|---------|-----------|------|
| `rate(field)` | `last` | QPS、TPS、IOPS |
| `AVG(field)` | `avg` | 连接数、使用率、等待时间 |

**重要经验**：
- 时序图显示为点时，优先检查是否已设置 `currentChartType: "area"` 与 `chartType: "areaLine"`
- 时序图若无法渲染，优先检查 DQL 是否包含不兼容 rollup；必要时改用 `fill(last(), linear)`
- 保持配置简洁，参照 `output/dashboard/mysql/mysql.json` 的格式
- filters 必须包含 `id`、`op`、`name`、`type`、`logic`、`value` 字段

### 8. 图表位置规则

#### 概览层（singlestat）
- 高度 `h`: 6
- 按每行数量自适应铺满 24 栅格：

| 每行数量 | 宽度 `w` | `x` 位置 |
|---------|---------|----------|
| 8 个/行 | 3 | 0, 3, 6, 9, 12, 15, 18, 21 |
| 6 个/行 | 4 | 0, 4, 8, 12, 16, 20 |
| 4 个/行 | 6 | 0, 6, 12, 18 |
| 3 个/行 | 8 | 0, 8, 16 |

- ✅ **关键规则**：概览图一行 6 个时，必须使用 `w=4` 铺满全宽。

#### 时序图（sequence）- 智能布局

**布局规则**（概览除外）：
1. **3 的倍数优先**：如果分组内图表数量是 3 的倍数，按每行 3 个布局（`w=8`）
2. **4 的倍数**：如果分组内图表数量是 4 的倍数，按每行 4 个布局（`w=6`）
3. **默认布局**：其他情况默认按每行 3 个布局（`w=8`）

**布局参数**：

| 每行数量 | 宽度 `w` | 高度 `h` | `x` 位置 |
|---------|---------|---------|----------|
| 3 个/行 | 8 | 10 | 0, 8, 16 |
| 4 个/行 | 6 | 10 | 0, 6, 12, 18 |
| 2 个/行 | 12 | 10 | 0, 12 |
| 1 个/行 | 24 | 10 | 0 |

**示例**：
```python
# 3 个图表的分组（如生产消费）
图表 1: {"x": 0, "y": 16, "w": 8}
图表 2: {"x": 8, "y": 16, "w": 8}
图表 3: {"x": 16, "y": 16, "w": 8}

# 4 个图表的分组
图表 1: {"x": 0, "y": 16, "w": 6}
图表 2: {"x": 6, "y": 16, "w": 6}
图表 3: {"x": 12, "y": 16, "w": 6}
图表 4: {"x": 18, "y": 16, "w": 6}

# 2 个图表的分组
图表 1: {"x": 0, "y": 16, "w": 12}
图表 2: {"x": 12, "y": 16, "w": 12}
```

**表格图表**：
- 宽度 `w`: 24（满宽）
- 高度 `h`: 10

## 验证清单

### 基础验证
- [ ] **CSV 文件存在**（必需，没有则拒绝生成）
- [ ] JSON 格式有效
- [ ] `main` 中**没有** `chartGroupPos` 字段
- [ ] `main.groups` 存在且配置完整
- [ ] 已执行样式自动修正（autofix）并回写结果
- [ ] 所有分组在 `groupUnfoldStatus` 中为 `true`（不折叠）
- [ ] 若存在列表分组，其顺序紧跟 `概览` 分组

### 变量验证
- [ ] 变量使用 `SHOW_TAG_VALUE` + `keyin`
- [ ] 变量 `code` 从 CSV 实际 tag 提取（不按数据源类型强制转换）
- [ ] 变量 `code` 与 CSV 中的 `操作`/`tag_key` 列一致
- [ ] DQL 中的 `BY`、`filters.name`、`value` 与变量 `code` 完全一致

### singlestat 验证
- [ ] singlestat 使用 `series_sum` + `BY 变量code`
- [ ] singlestat 的 `fill` 为 `null`
- [ ] singlestat **没有** rollup 语法
- [ ] singlestat 的 `queries[]` 外层包含 `name/type/unit/color/qtype`
- [ ] singlestat 的 `query.filters` 存在且与变量 code 一致
- [ ] singlestat 的单位映射正确（可识别单位不允许落为 `custom`）

### sequence 验证
- [ ] 时序图计数器优先使用 rollup（如 `irate`）
- [ ] 若 rollup 导致 UI 异常，已降级为 `fill(last(), linear)`
- [ ] 时序图非计数器使用 `AVG(field)`
- [ ] 时序图 `fill` 为 `"linear"`
- [ ] 时序图 `currentChartType` 为 `"area"`
- [ ] 时序图 `chartType` 为 `"areaLine"`
- [ ] 时序图 `funcList` 为 `[]`
- [ ] 时序图 `queryFuncs` 为 `[]`
- [ ] 时序图 `groupByTime` 为 `""`
- [ ] rate() 指标 `fieldFunc` 为 `"last"`
- [ ] AVG() 指标 `fieldFunc` 为 `"avg"`
- [ ] 时序图**没有** `showLine`、`openStack` 等多余字段

### 通用验证
- [ ] **所有图表配置了 units**（关键）
- [ ] 所有分组配置 `bgColor`（不包含 `colorKey`）
- [ ] 图表配置 `chartGroupUUID`（同组相同）
- [ ] 图表配置 `prevGroupName`
- [ ] filters 的 `op` 使用 `"="`（不是 `"=~"`）
- [ ] query 结构包含 `name`、`type`、`unit`、`color`、`qtype`
- [ ] 至少 1 个实例级 table 面板
- [ ] MySQL 场景包含用户/库表维度 table（有对应 CSV 时）
- [ ] 分组图（sequence/table）采用科技蓝体系
- [ ] 概览图（singlestat）采用多彩数据体系（valueColor 不全同色）
- [ ] `dashboardExtend.groupColor` 已移除
- [ ] `main.groups[].extend.bgColor` 使用 `rgba(...)`，且按科技蓝色盘顺序
- [ ] `main.groups[].extend.colorKey` 已移除
- [ ] 所有 singlestat 都有 `bgColor=rgba(...)` 和 `borderColor=#E5E7EB`

### DQL 验证（强制）
- [ ] 提取所有 charts 中的 DQL 语句
- [ ] 使用 `dqlcheck -q '<DQL>'` 逐条验证
- [ ] 所有 DQL 通过 `dqlcheck` 验证
- [ ] 失败的 DQL 已修复或标注

## 相关文件

- 输入：`csv/{{type}}*.csv`（必需）
- 输出：`output/dashboard/{{type}}/{{type}}.json`
- 参考：
  - `output/dashboard/mysql/mysql.json`（时序图标准格式）
  - `output/dashboard/host/host_monitoring_pro.json`
