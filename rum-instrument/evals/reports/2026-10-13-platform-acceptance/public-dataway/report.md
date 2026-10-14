# Public DataWay 安全准备结果

状态：`blocked_certificate_trust`。用户保留 TLS 校验且暂无可信 CA；本轮停在准备阶段，授权码未消费、Token 未获取、无真实浏览器或外部遥测。

隔离目录 `/private/tmp/rum-platform-acceptance/web-public-dataway`，由已验收完整 Vue 工程复制，原 `/private/tmp/rum-platform-acceptance/web` 和报告保持不变。appId 已采用最新 `new_skill_001`。

已完成：

- Skill `--site-only` 确认固定 testing site / AI API 映射，TLS 策略 verified；没有关闭 TLS。
- v3 计划 plan 校验通过，implementation 因明确 pending/blockers 且没有 state 按预期失败。
- `.env.production.local` 是独立、空、0600、Git ignored 的 Token sink；state 路径独立 ignored 且尚未创建。
- `.env.production` 写入非秘密 site/appId，旧 DataKit 变量移除；原 initializer 保持不变，目前会跳过 RUM。
- `src/rum-config.ts` 准备 Vite 原生 typed config reader。SDK Public DataWay 正确类型为 `RumSiteInitConfiguration`；读取 token 仅通过 `import.meta.env.VITE_RUM_CLIENT_TOKEN`。尚未连接 initializer，刻意遵守凭据状态校验前不修改初始化的要求。
- `after-state-initializer.patch` 准备了单一 Public DataWay 分支，`git apply --check` 成功；凭据状态通过后才应用。
- 公开 npm ci 和 strict Vue SFC/SDK 声明检查 + Vite production build 成功。
- 提供仅无凭据 HEAD 且保留 TLS 验证的 `scripts/preflight.py`；本子任务未运行外部预检，证书失败事实来自父代理 Python 默认信任 / curl 60 检查，单独注明 provenance。

保留失败历史：首次计划 clientToken mapping 使用普通字符串，validator 拒绝，修正为非秘密 runtime source 后通过。首次 config reader 误用 SDK 的 DataKit `RumInitConfiguration` 导致 strict build 拒绝 site 属性，改为官方 `RumSiteInitConfiguration` 后构建通过。均保留原日志，没有绕过声明检查。

继续命令见 `continuation.md`。关键限制：`--plan` 禁止混用 legacy `--insecure-test-tls`；用户没有 TLS 例外授权。真实换码前必须先以可信 CA 完成验证。原 DataKit 浏览器脚本不可用于真实 Token，因为它打印 SDK config；后续必须改为布尔比较并避免输出 Token。

证据包括 `commands.jsonl`、首次/已校验计划、`local-safety.json`、`external-preflight-evidence.json`、`source.patch` 和待实施补丁。归档排除 secret sink、state、dist 和 node_modules。
