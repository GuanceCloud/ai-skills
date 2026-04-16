# AI Skills 使用说明

本仓库提供面向观测云场景的技能（Skills），用于标准化生成 Dashboard、Monitor、DQL 以及 Grafana Dashboard 转观测云 Dashboard 等交付内容。

## 目录结构

```text
ai-skills/
├── alert_manager/
│   └── SKILL.md
├── dashboard/
│   └── SKILL.md
├── dql/
│   ├── SKILL.md
│   ├── bin/
│   │   ├── dqlcheck
│   │   └── dqldocs
├── grafana-to-guance-dashboard/
│   ├── SKILL.md
│   ├── agents/
│   ├── fixtures/
│   ├── references/
│   ├── schemas/
│   ├── scripts/
│   ├── test/
│   └── package.json
└── monitor/
    └── SKILL.md
```

## 已提供 Skills

| Skill | 作用 | 关键输入 | 关键输出 |
|---|---|---|---|
| `alert_manager` | 将 alertmanager rule 转换为观测云监控器 JSON | alertmanager rule 语句或 rule 文件 + 指标映射 | `output/monitor/{{component}}/{{component}}.json` |
| `dashboard` | 根据 CSV 指标生成观测云 Dashboard JSON | `csv/{{type}}*.csv` | `output/dashboard/{{type}}/{{type}}.json` |
| `monitor` | 根据 CSV 指标生成观测云监控器 JSON | `csv/{{component}}*.csv` | `output/monitor/{{component}}/{{component}}.json` |
| `dql` | 解释、评审、生成、修复 DQL | 用户查询需求 / DQL 语句 | 通过校验的最终 DQL |
| `grafana-to-guance-dashboard` | 分析、转换、审计、修复 Grafana Dashboard 到观测云 Dashboard 的映射 | Grafana dashboard JSON | 观测云 dashboard JSON、转换审计报告 |

## 快速开始

### 1. 准备指标 CSV

请先在项目中准备指标文件（示例）：

```text
csv/mysql.csv
csv/redis.csv
csv/volcengine_kafka.csv
```

CSV 建议包含以下列（中英文均可）：

- `指标名` / `metric_name`
- `字段类型` / `data_type`
- `单位` / `unit`
- `操作` / `tag_key` / `Tag`

示例：

```csv
指标名,字段类型,单位,操作
cpu_util,float,%,host
memory_util,float,%,host
```

### 2. 调用 Skill（示意）

在支持 Skills 的对话环境中：

```text
/skill dashboard
生成 mysql 的 dashboard
```

```text
/skill monitor
生成 redis 的监控器
```

```text
/skill dql
修复这条 DQL 并返回可执行版本
```

```text
/skill grafana-to-guance-dashboard
分析并转换这个 Grafana dashboard JSON，输出观测云 dashboard，并说明缺失映射
```

## 强制规则（务必遵守）

### 通用规则

- 无 CSV 文件时，`dashboard` 和 `monitor` 必须拒绝生成。
- 不能凭空假设指标，也不能用网上示例代替用户 CSV。
- 交付内容必须可执行、可落地，不输出“看起来正确但未验证”的结果。

### DQL 校验规则（核心）

- 凡是要交付“最终可执行 DQL”，必须先逐条通过 `dqlcheck`。
- 每条 DQL 单独校验，不用“批量整体通过”替代。
- 校验失败时按报错位置做最小修复并重试。
- 连续 3 次失败的条目不得作为最终交付。

常用命令：

```bash
./dql/bin/dqlcheck -q '<DQL>'
./dql/bin/dqlcheck --file /tmp/query.dql
```

## 各 Skill 重点说明

### `dashboard`

- 从 CSV 自动解析变量维度（如 `instanceId` / `instance_id` / `host`）。
- 所有图表查询中的 `BY`、`filters`、`groupBy` 必须与变量 `code` 一致。
- 必须覆盖基础运维面板能力：
  - 至少 1 个实例级 `table`
  - 至少 1 行 `singlestat` 概览（4~8 KPI）
  - 至少 6 个 `sequence` 趋势图
- 生成后必须先执行样式自动修正：
  - `groupUnfoldStatus` 中所有分组强制为 `true`
  - `概览` 固定第一，列表类分组紧随其后
  - 移除 `dashboardExtend.groupColor` 和 `main.groups[].extend.colorKey`
  - 分组使用科技蓝色盘，概览 `singlestat` 使用多彩数据色盘
- 生成后必须对图表 DQL 逐条执行校验。

### `monitor`

- 从 CSV 中选择 5~10 个关键指标设置告警。
- 告警应覆盖可用性、资源、性能、异常等核心维度。
- 监控器 JSON 必须包含清晰 `groupBy`、规则阈值和告警消息模板。
- 生成后必须同时校验 `checkers[].jsonScript.targets[].dql` 和 `checkers[].extend.querylist[].query.q`。
- 若 DQL 修复过，必须同步回两个位置，不能出现结构内语句不一致。

### `alert_manager`

- 输入必须是告警规则定义（`alert / expr / for / labels / annotations`），不能是 `alertmanager.yml` 的路由配置。
- 没有指标映射时，必须先补映射（`dataSource / field / groupBy / fieldType / fieldFunc`），不能硬写 DQL。
- 每条规则都要同时生成 `targets[].dql` 和 `extend.querylist[].query.q`，两处查询语义必须一致。
- `checkerOpt.rules` 与 `extend.rules` 必须同步。
- 最终 JSON 中不能残留 PromQL。
- 所有 DQL 必须通过 `dqlcheck`。

### `dql`

- 分两种模式：
  - 解释/评审模式：只给语义、风险、建议，不输出新最终 DQL。
  - 生成/修复模式：仅输出逐条校验通过的最终 DQL。
- 最终交付前必须逐条通过 `dqlcheck`，不要用批量校验替代单条校验。

### `grafana-to-guance-dashboard`

- 用于 Grafana dashboard JSON 到观测云 dashboard JSON 的分析、转换、审计和修复。
- Skill 自带独立脚本、Schema、测试、fixtures 和 `package.json`，可在目录内独立运行。
- 默认流程应覆盖：
  - 转换前预检：面板类型、变量、数据源、PromQL 风险、隐式单位
  - 转换执行：按需选择 `--guance-promql-compatible`、`--keep-grafana-meta`
  - 转换后校验：输出 JSON 必须通过 skill 内置 schema 校验
  - 审计报告：说明成功转换、丢失面板、部分映射、单位推断置信度、兼容性风险
- 常用命令：

```bash
cd grafana-to-guance-dashboard
npm install
npm run convert -- --input ./fixtures/grafana-dashboard.json --output ./output/guance-dashboard.json --validate
npm run validate:file -- ./output/guance-dashboard.json
npm test
```

- 环境要求：`Node.js >= 18`

## 团队协作建议

- 新增或调整 Skill 时，先更新对应 `SKILL.md`，再更新本 README。
- 在 PR 描述中附上：
  - 输入样例（CSV 或 DQL）
  - 校验命令与结果（尤其是 `dqlcheck`）
  - 产出文件路径
- 评审重点放在“可执行性”和“规则一致性”，不是文字描述完整度。

## 常见问题

### 1) 没有 CSV 能否先生成模板？
不能。`dashboard` 和 `monitor` 都要求先存在 CSV，再继续生成。

### 2) DQL 语法看起来对，但没跑校验可以交付吗？
不能。必须以 `dqlcheck` 通过为准。

### 3) 校验器不可用怎么办？
需明确标注 `UNVERIFIED`、说明阻断原因，并给出修复所需动作。

## 参考

- [alert_manager/SKILL.md](alert_manager/SKILL.md)
- [dashboard/SKILL.md](dashboard/SKILL.md)
- [monitor/SKILL.md](monitor/SKILL.md)
- [dql/SKILL.md](dql/SKILL.md)
- [grafana-to-guance-dashboard/SKILL.md](grafana-to-guance-dashboard/SKILL.md)
