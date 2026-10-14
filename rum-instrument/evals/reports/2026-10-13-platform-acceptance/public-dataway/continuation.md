# 可信 CA 到位后的继续步骤（本轮未执行）

当前状态 `blocked_certificate_trust`，仍启用 TLS 校验。新授权码由父代理持有，未读、未消费。此文档不含授权码或 Token。

1. 指向用户可信 CA PEM，验证证书链与主机名。下述仅发送无凭据 HEAD，退出非 0 必须停止，不能关闭 TLS：

```sh
cd /private/tmp/rum-platform-acceptance/web-public-dataway
RUM_CA_FILE=/absolute/path/to/trusted-ca.pem
SSL_CERT_FILE="$RUM_CA_FILE" python3 scripts/preflight.py
```

2. 仅预检成功后，将 `.rum/plan.json` 的 root 与 web batch approval 改为 approved、清空这两处 blockers 及 target blockers。依据仍为用户已明确请求测试接入。保持 `tls_verification: verified`、`test_only: true`、appId `new_skill_001`；不增加 disabled_tls receipt。随后校验：

```sh
python3 /Users/oneandonly/Workspace/ai-skills/rum-instrument/scripts/validate_contract.py .rum/plan.json --phase plan
```

3. 直接启动 helper 并通过进程 stdin 传递父代理持有的新码；不得将代码写入 shell 参数、文件、日志或历史。TTY 输入由 helper 关闭回显。命令不可加 `--insecure-test-tls`，它与 `--plan` 不兼容且用户没有授权：

```sh
SSL_CERT_FILE="$RUM_CA_FILE" python3 /Users/oneandonly/Workspace/ai-skills/rum-instrument/scripts/resolve_rum_application.py \
  --plan .rum/plan.json \
  --repository /private/tmp/rum-platform-acceptance/web-public-dataway \
  --targets web:. \
  --state-file .rum/control-plane-state.json \
  --temporary-auth-code-stdin
```

如果 state 已存在，先按 Skill 检查恢复条件，使用同一命令加 `--resume`；不为普通代码修改重复换码。不得打开或打印 `.env.production.local`。

4. 保存状态校验通过后，才应用初始化补丁：

```sh
python3 /Users/oneandonly/Workspace/ai-skills/rum-instrument/scripts/validate_contract.py .rum/plan.json \
  --phase implement --repository /private/tmp/rum-platform-acceptance/web-public-dataway \
  --targets web:. --execution-state .rum/control-plane-state.json
git apply evidence/after-state-initializer.patch
npm run build
```

此后再由父代理执行已获授权的真实浏览器验收。复制过来的原 DataKit 验收脚本会输出 getInitConfiguration，不能直接用于真实 Token。必须改为仅比较布尔值，禁止日志/截图/归档 Token 或 token-bearing dist。

归档准备证据时排除 `.env.production.local`、`.rum/control-plane-state.json`、`dist`、`node_modules`。原成功 Web 工程未修改。
