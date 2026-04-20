---
name: sls2dql
description: 将阿里云 SLS 查询转换、验证、解释为 GuanceDB DQL。适用于单条 SLS 查询转换、search-only 查询补 source、批量评估、近似转换风险说明与 Markdown 报告生成。
---

# SLS 转 DQL Skill

用于把阿里云 SLS 查询转换为 GuanceDB DQL，并在需要时输出解释、批量评估结果或 Markdown 报告。

## 适用场景

- 用户要把一条 SLS 查询转换成 DQL
- 用户要验证一条 SLS 查询是否可安全转换
- 用户要解释为什么某条 SLS 查询无法转换
- 用户要批量评估一组 SLS 查询
- 用户接受“近似转换”，希望明确看到风险和诊断

## 内置资源

- 统一入口：`./sls2dql/bin/sls2dql`
- 示例脚本：`./sls2dql/scripts/run_sls2dql.sh`
- 中文快速开始：`./sls2dql/references/USER_QUICKSTART_zh.md`
- 中文使用指南：`./sls2dql/references/USER_GUIDE_zh.md`

只有在需要更完整参数、批量格式或错误码说明时，再读取 `references/` 下文档。

## 强制规则

- 每次转换都必须显式传 `--namespace`
- 对没有 SQL `FROM` 的 search-only 查询，必须补 `--source`
- 默认使用 `--mode strict`
- 只有用户明确接受近似语义时，才允许使用 `--mode allow-approximate`
- 若结果是 `approximate` 或 `unsupported`，必须把状态和诊断一并说明，不能只贴 DQL
- 需要批量评估真实查询时，优先用 `report` 或 `batch`，不要手工逐条拼输出

## 状态语义

转换结果至少分为三类，交付时必须按状态解释，不能把它们混为“都已经成功转成 DQL”：

- `exact`：认为当前 DQL 与原 SLS 查询语义等价，可以按精确转换处理
- `approximate`：产出了可执行 DQL，但只是近似转换，必须同时说明风险、诊断和可能的语义偏差
- `unsupported`：当前不能安全转换，必须返回阻断原因，而不是臆造 DQL

当用户只说“转换成 DQL”时，也要默认把状态带上；不要只返回一条 DQL 而省略状态。

## 工作流程

### 单条转换

1. 先执行 `./sls2dql/bin/sls2dql version`，确认二进制可用。
2. 判断输入是：
   - 普通 SQL / 混合查询：通常用 `convert`
   - search-only 查询：补 `--source` 后用 `convert`
   - 只想验证是否支持：用 `validate`
   - 先看转换依据：用 `explain`
3. 读取输出中的状态、DQL、诊断。
4. 若为 `approximate`，明确告诉用户这是近似转换及其风险。
5. 若为 `unsupported`，优先返回阻断原因和下一步建议，而不是强行改写。

### 批量评估

1. 让输入整理成 JSON array 或 JSONL。
2. 需要结构化结果时，执行：

```bash
./sls2dql/bin/sls2dql batch \
  --namespace L \
  --file queries.json \
  --format json
```

3. 需要 Markdown 验证报告时，执行：

```bash
./sls2dql/bin/sls2dql report \
  --namespace L \
  --file queries.json
```

4. 若批量项本身已带 `namespace` / `index` / `source` / `mode`，按输入逐项处理。

## 常用命令

```bash
./sls2dql/bin/sls2dql version
./sls2dql/bin/sls2dql convert --namespace L --query "SELECT count(*) AS pv FROM access_log"
./sls2dql/bin/sls2dql convert --namespace L --source access_log --query "status:500 AND service:api"
./sls2dql/bin/sls2dql validate --namespace L --query "status:500 | SELECT count(*) AS pv FROM access_log"
./sls2dql/bin/sls2dql explain --namespace L --query "* | SELECT count(*) AS pv FROM access_log GROUP BY host"
```

## 输出要求

- 返回最终结果时，至少说明：
  - 使用的命令或模式
  - 是否传入 `namespace` / `source` / `index`
  - 转换状态：`exact` / `approximate` / `unsupported`
- 如果用户要“最终 DQL”，只有在转换器明确产出可执行 DQL 时才交付。
- 如果只是解释或评估，不要伪造“看起来像 DQL”的结果。

## 故障排查

- `NAMESPACE_REQUIRED`：补 `--namespace`
- `SOURCE_REQUIRED`：search-only 查询补 `--source`
- `CASE_EXPR_UNSUPPORTED`：说明当前无法安全转换，建议改写查询或当作 DQL 能力缺口处理

需要更多参数细节、批量输入格式、支持范围时，再读取：

- `./sls2dql/references/USER_QUICKSTART_zh.md`
- `./sls2dql/references/USER_GUIDE_zh.md`
