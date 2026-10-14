# RUM Skill 五场景独立评估

隔离位置：/private/tmp/rum-slim-forward-eval-20261014
全部应用与 Git 仓库仅存在于 /private/tmp；未修改仓库实现或已安装 Skill，未使用账号、凭据、远端接收端或发布。

## 范围
实际运行 detect、--complete-draft、plan/implement 校验和 Node VM 启动/本地 HTTP 接收探针。SDK 为明确标记的受控替身，事件也是人工构造；不证明真实 SDK 自动采集、浏览器兼容性或后端入库。官方 Web 指南读取超时，因此未添加真实依赖或编造兼容性证据。

| 场景 | 补问 | 常规审批 | 首次计划失败 | 计划修复 | 结果 |
|---|---:|---:|---:|---:|---|
| 01_complete_datakit | 0 | 0 | 0 | 0 | Local source integration and controlled SDK/HTTP runtime smoke completed; real browser/SDK/backend unverified. |
| 02_missing_essentials | 1 | 0 | 0 | 0 | Stopped at missing answers after useful discovery. No endpoint/ID guessed, no source changes or plan completion attempted. |
| 03_existing_configuration | 0 | 0 | 0 | 0 | Existing effective configuration reused, including sessionSampleRate=35; no repeated question, no source edit. |
| 04_repeat_completed | 0 | 0 | 0 | 0 | Repeat rediscovery kept source unchanged, preserved original plan baseline and runtime initializer count=1. Only plan completion disposition was updated. |
| 05_independent_partial | 1 | 0 | 0 | 0 | Full-plan implementation correctly blocked on admin missing ID; selected storefront batch completed local source and controlled runtime smoke. Admin remains explicitly blocked. |

补问计数为记录的拟询问轮次，没有向真实用户提问。缺信息场景未尝试生成无效计划，因此首次计划失败数为 0/未进入。多应用的全量 implement 非零属于预期拦截，不计为计划失败或修复。

所有命令、返回码、stdout/stderr 和逐场景读取文件清单保存在 results.json 及各场景 commands.json。

运行探针实际遇到 4 次沙箱本地监听 EPERM；工具级授权后发现系统 Node 15.6.0 无 global fetch，产生 1 次探针失败。仅将外部测试探针改为 node:http 后重跑，未修改被评估 Skill 或应用源码。各运行场景记探针修复 1 次，计划修复仍为 0。最终运行结果详见 results.json 的 runtime_verified_with_controlled_double 与 runtime_result。

无 RUM 基线也以相同的 fetch is not defined 失败，确认属于 Node 测试环境。修复的是外部评估探针，未将其算作 Skill 计划修复。沙箱工具级授权请求 2 次，常规实施二次审批/真实用户补问均为 0 次。

复用和重复执行场景的所有应用文件哈希保持不变；多应用场景 admin 全部应用文件哈希保持不变。首次新计划 3/3 通过；重复执行使用原计划且保留原 Git 基线；完全缺参数场景在发现后记录一轮必要问题并停止。4 个可运行场景的受控 SDK、本地 HTTP 探针最终全部通过。
