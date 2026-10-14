# RUM 接入入口

供执行当前用户接入请求的 Agent 阅读。默认完成基础 RUM 的安装、代码接入和必要验证；只要求规划或审查时保持相应范围。

## 安装或复用

1. 从当前会话实际可用的 Skill 中找到 `rum-instrument`，读取它的 `SKILL.md`。可用即复用，不例行联网检查更新；不要只凭磁盘上存在同名目录判定已加载。
2. 未安装时，根据自身运行环境确定 agent：Codex=`codex`、Claude Code=`claude`、OpenCode=`opencode`、Pi=`pi`、Gemini CLI=`gemini`、GitHub Copilot=`copilot`、Cursor=`cursor`、Amp=`amp`，其他明确使用通用 Agents 目录的宿主=`agents`。不要根据项目依赖猜 Agent。确实无法识别时才询问安装位置。
3. 以本入口 URL 所在目录为分发根目录，不切换到另一品牌或镜像。稳定入口使用该目录的安装器；若入口位于 `versions/<40 位提交 SHA>/rum.md`，使用同目录安装器、上溯到分发根目录作为 base URL，并传入该 SHA 的版本参数。
4. macOS/Linux 下载该目录的 `install.sh`，使用 `sh` 执行，参数为 `--base-url <分发根目录> --skill rum-instrument --agent <自身类型> --scope user --yes`。Windows 使用同目录 `install.ps1`，对应参数为 `-BaseUrl <分发根目录> -Skill rum-instrument -Agent <自身类型> -Scope user -Yes`。版本固定时追加 `--version <SHA>` / `-Version <SHA>`。参数由 Agent 填写，不要求用户拼装命令。
5. 仅在用户要求更新或现有版本缺少本次任务必需能力时使用 `--upgrade` / `-Upgrade`。禁止自动 `--force` 覆盖本地修改。沿用安装器的校验和目录保护，不绕过宿主权限。
6. 安装成功后读取返回的实际安装目录中的 Skill，并在当前会话继续执行。若宿主确实不允许当前会话读取新 Skill，只说明必要的重新加载步骤，不声称已经完成接入。

## 连续接入

Public DataWay 的凭据落盘目前需要 macOS/Linux 的 POSIX 权限；原生 Windows 请使用 WSL 的 Linux 文件系统或受支持宿主。先确认这一条件再索取授权码。Windows 安装、站点发现和 DataKit 本地接入仍可使用。

用户可以只说“帮我接入 RUM”。先分析项目并复用配置，再集中补齐当前已知的必需信息。接受自然语言、接入片段或以下字段，不要求重新排版：

- Public DataWay：`datawayUrl`、`appId`；首次解析配置需要 `temporaryAuthCode`。
- DataKit：`datakitUrl`、`appId`，不需要授权码。
- 已有有效配置的字段可以省略；空值视为缺失。`applicationType` 是高级覆盖项，不主动询问。

不要重复展示安装规则或参数问卷。遵循安装后 Skill 的发现、补齐、准备、解析、实施、验证流程；授权范围内连续执行，不要求常规二次确认。最终按 Skill 的交付口径说明实际应用 ID、接收地址、是否测试配置，分别报告源码接入、运行验证和后台入库状态，以及必要下一步。
