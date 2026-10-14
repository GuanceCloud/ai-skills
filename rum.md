# RUM 接入入口

供执行当前用户接入请求的 Agent 阅读。默认完成基础 RUM 的安装、代码接入和必要验证；只要求规划或审查时保持相应范围。

## 安装与更新

每次新接入在修改应用或消费授权码前检查最新已发布版本：未安装则安装，有新版则自动升级，同版本校验后复用，无需常规确认。同一任务及续跑固定版本；遵循用户指定的源码、离线或版本要求。

从入口所在目录获取安装器，自动识别 Agent 并填写参数（标识见安装器帮助）：

| 系统 | 安装器 | 参数 |
|---|---|---|
| macOS/Linux | `sh install.sh` | `--base-url <分发根目录> --skill rum-instrument --agent <自身类型> --scope user --yes` |
| Windows | `install.ps1` | `-BaseUrl <分发根目录> -Skill rum-instrument -Agent <自身类型> -Scope user -Yes` |

- **已有安装**：确认实际生效目录及 `.skill-install.json`，追加 `--upgrade --dest <Skill 父目录>`（Windows：`-Upgrade -Dest`）。保留本地修改和未受管理副本，仅为处理此类冲突询问，禁止自动强制覆盖。
- **分发与固定版本**：沿用入口的分发源。若入口为 `versions/<SHA>/rum.md`，使用同目录安装器、上溯的分发根目录及 `--version <SHA>`（Windows：`-Version`）；固定版本也须校验文件完整性。
- **检查失败**：网络或索引不可用时，可复用已知可用版本并注明“未确认是否最新”；无可用副本或校验失败则说明阻塞。
- **继续执行**：重读实际安装目录的 Skill 及所需资源，继续接入并在结果中注明版本。宿主无法加载时只说明必要的重新加载步骤。

## 连续接入

Public DataWay 的凭据落盘目前需要 macOS/Linux 的 POSIX 权限；原生 Windows 请使用 WSL 的 Linux 文件系统或受支持宿主。先确认这一条件再索取授权码。Windows 安装、站点发现和 DataKit 本地接入仍可使用。

用户可以只说“帮我接入 RUM”。先分析项目并复用配置，再集中补齐当前已知的必需信息。接受自然语言、接入片段或以下字段，不要求重新排版：

- Public DataWay：`datawayUrl`、`appId`；首次解析配置需要 `temporaryAuthCode`。
- DataKit：`datakitUrl`、`appId`，不需要授权码。
- 已有有效配置的字段可以省略；空值视为缺失。`applicationType` 是高级覆盖项，不主动询问。

不要重复展示安装规则或参数问卷。遵循安装后 Skill 的发现、补齐、准备、解析、实施、验证流程；授权范围内连续执行，不要求常规二次确认。最终按 Skill 的交付口径说明实际应用 ID、接收地址、是否测试配置，分别报告源码接入、运行验证和后台入库状态，以及必要下一步。
