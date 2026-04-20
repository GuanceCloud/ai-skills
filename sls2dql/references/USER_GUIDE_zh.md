# SLSConvert 用户使用指南

## 工具作用

`sls2dql` 用于把一部分可安全转换的阿里云 SLS 查询转换为 GuanceDB DQL。

这个工具是保守设计的：

- 只有在确认语义足够安全时才输出 DQL
- 只能近似转换时会明确标记
- 无法保证正确时会直接拒绝，而不是硬转

## 一个关键前提

SLS 查询本身没有 DQL 的命名空间概念，但 DQL 执行必须带 namespace。

因此每次转换都必须显式传入：

```bash
--namespace L
```

如果没有传，工具会返回 `NAMESPACE_REQUIRED`。

如果你希望生成的 DQL 带上 index，也可以显式传入：

```bash
--index production
```

只有显式指定时，转换器才会注入 DQL index，不会自动猜测。

## 安装方式

建议直接使用发布产物中的二进制包。

当前支持的平台有：

- macOS amd64
- macOS arm64
- Linux amd64
- Linux arm64

解压后可以先检查版本：

```bash
./sls2dql version
```

## 基本命令

### 查看版本

```bash
./sls2dql version
```

### 转换单条查询

```bash
./sls2dql convert \
  --namespace L \
  --index production \
  --query "* | SELECT count(*) AS pv FROM access_log GROUP BY host ORDER BY pv DESC LIMIT 10"
```

### 验证单条查询

```bash
./sls2dql validate \
  --namespace L \
  --query "status:500 | SELECT count(*) AS pv FROM access_log"
```

### 查看转换解释

```bash
./sls2dql explain \
  --namespace L \
  --query "* | SELECT count(*) AS pv, date_trunc('minute', __time__) AS time FROM access_log GROUP BY time ORDER BY time"
```

### 批量转换

```bash
./sls2dql batch \
  --namespace L \
  --file queries.json \
  --format json
```

### 生成 Markdown 验证报告

```bash
./sls2dql report \
  --namespace L \
  --file queries.json
```

## 常用参数

- `--namespace`：目标 DQL namespace，必填
- `--query`：直接传入单条 SLS 查询
- `--file`：从文件读取单条查询或批量输入
- `--source`：给 search-only 查询补 fallback source
- `--index`：可选，注入到输出 DQL 中的 index
- `--mode strict|allow-approximate`
- `--format text|json`
- `--skip-validation`：跳过 GuanceDB DQL parser 回环校验
- `--with-explain`：批量模式里带上 explanation

## 输入形式

### 单条查询

可以通过以下任一方式输入：

- `--query`
- `--file`
- 标准输入

### 批量输入

批量模式支持：

- JSON array
- JSONL，每行一个对象

示例：

```json
{
  "name": "pv_by_host",
  "query": "* | SELECT count(*) AS pv FROM access_log GROUP BY host ORDER BY pv DESC LIMIT 10",
  "namespace": "L",
  "index": "production",
  "source": "access_log",
  "mode": "strict"
}
```

批量项还可以带这些辅助字段：

- `category`
- `source_url`
- `notes`
- `tags`

## 常见转换示例

### 1. search-only 查询

SLS：

```text
status:500 AND service:api
```

命令：

```bash
./sls2dql convert \
  --namespace L \
  --source access_log \
  --query "status:500 AND service:api"
```

### 2. SQL 查询

SLS：

```sql
SELECT count(*) AS pv FROM access_log GROUP BY host ORDER BY pv DESC LIMIT 10
```

命令：

```bash
./sls2dql convert \
  --namespace L \
  --index production \
  --query "SELECT count(*) AS pv FROM access_log GROUP BY host ORDER BY pv DESC LIMIT 10"
```

### 3. 近似转换

SLS：

```sql
SELECT * FROM access_log WHERE message LIKE 'error%'
```

命令：

```bash
./sls2dql convert \
  --namespace L \
  --mode allow-approximate \
  --query "SELECT * FROM access_log WHERE message LIKE 'error%'"
```

这类结果会是 `approximate`，同时带 `LIKE_APPROXIMATION` 诊断。

## 如何理解输出结果

### 状态字段

- `exact`：安全精确转换
- `approximate`：可以执行，但不是完全等价
- `unsupported`：明确拒绝转换

### unsupported_class

当结果是 `unsupported` 时，还可能看到：

- `converter-fixable`：输入不完整，或者当前转换器还没覆盖
- `dql-blocked`：受限于 DQL 当前缺少或未验证的能力

## 退出码

- `0`：成功
- `1`：命令或输入错误
- `2`：转换失败、结果不支持、或者校验失败

## 常见错误

### `NAMESPACE_REQUIRED`

原因：

- 没有传 `--namespace`

解决：

```bash
./sls2dql convert --namespace L ...
```

### `SOURCE_REQUIRED`

原因：

- 查询是 search-only
- 没有 SQL `FROM`
- 也没有传 `--source`

解决：

```bash
./sls2dql convert --namespace L --source access_log ...
```

### `CASE_EXPR_UNSUPPORTED`

原因：

- 当前 `CASE WHEN` 还不能安全转换

解决：

- 尝试改写查询
- 或把它视为 DQL 能力缺口

## 使用建议

- 永远显式传 `--namespace`
- search-only 查询记得补 `--source`
- 默认使用 `strict`
- 只有在接受近似语义时才使用 `allow-approximate`
- 遇到复杂问题先跑 `explain`
- 评估一批真实查询时优先用 `report`

## 相关文档

- [README.md](README.md)
- [RELEASE.md](RELEASE.md)
- [REAL_SAMPLE_WORKFLOW.md](REAL_SAMPLE_WORKFLOW.md)
