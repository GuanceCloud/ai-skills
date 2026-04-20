# SLSConvert 快速开始

## 1. 先检查二进制版本

```bash
./sls2dql version
```

## 2. 转换一条普通 SQL 查询

```bash
./sls2dql convert \
  --namespace L \
  --index production \
  --query "SELECT count(*) AS pv FROM access_log GROUP BY host ORDER BY pv DESC LIMIT 10"
```

如果你不希望输出里带 DQL index，只要不传 `--index` 即可。

## 3. 转换 search-only 查询

这类查询还需要补一个 fallback source：

```bash
./sls2dql convert \
  --namespace L \
  --source access_log \
  --query "status:500 AND service:api"
```

## 4. 需要时允许近似转换

```bash
./sls2dql convert \
  --namespace L \
  --mode allow-approximate \
  --query "SELECT * FROM access_log WHERE message LIKE 'error%'"
```

## 5. 查看转换解释

```bash
./sls2dql explain \
  --namespace L \
  --query "* | SELECT count(*) AS pv, date_trunc('minute', __time__) AS time FROM access_log GROUP BY time ORDER BY time"
```

## 6. 批量评估真实查询

```bash
./sls2dql report \
  --namespace L \
  --file testdata/real_sample_template.json
```

## 7. 记住两个最常见错误

- `NAMESPACE_REQUIRED`：补 `--namespace`
- `SOURCE_REQUIRED`：search-only 查询补 `--source`

## 更多说明

- 完整英文手册：[USER_GUIDE.md](USER_GUIDE.md)
- 完整中文手册：[USER_GUIDE_zh.md](USER_GUIDE_zh.md)
- 发布说明：[RELEASE.md](RELEASE.md)
