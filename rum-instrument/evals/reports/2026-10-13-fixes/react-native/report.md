# React Native 修复后独立 forward-test

结论：最新安装的 RUM Skill 能指导修复前次 React Native SDK 0.4.2 错误处理链缺陷。修复后 24 个严格断言场景均通过，聚合命令 exit 0。此结论只覆盖真实 SDK JavaScript 与模拟 native bridge；不代表完成原生设备构建或远程入库。

## 安装和隔离

- 从 `http://127.0.0.1:18764` 经主仓库 `install.sh` 安装到本隔离目录，命令 exit 0。精确命令在 `logs/install.log`。
- 安装回执：`install-receipt.json`；版本 `97bff6dd3ab0fb1601b41aadbc1a47847811b99b`；归档 SHA-256 `41ab6cd9b73dc2ffab0faf2c0341f0d21101661e38927de027aacf41c07d0175`。
- 运行态 Skill/引用/脚本/资产 13 个文件的哈希在 `runtime-sha256.json`。实际采用的应用错误钩子与安装资产逐字节一致。
- 原夹具整体复制到 `project/`。原夹具 Git 有上次实施留下的修改及 untracked `rum.js`，原 status/diff 已保存在 `logs/original-git-*`。仅在隔离副本提交夹具快照建立本次修复基线，未修改原夹具、主仓库、用户安装 Skill。
- 真实 SDK 109 个文件修复前后 SHA-256 全部相同，见 `sdk-integrity.json`；无 SDK 内部修改。

## 计划与实施

首次生成的 v3 计划通过 plan 与 implement 两阶段校验，均 exit 0；计划未因 schema 错误重写。完整计划在 `plan.json`，验证命令及输出在 `logs/plan-validation.log` 和 `logs/implement-validation.log`。

业务补问 0 次，重复问题 0 次，常规阶段审批 0 次。两次 sandbox escalation 分别用于授权的本机镜像安装和官方公开 npm 元数据核验，均成功。

维护源码的改动仅三处：

1. `rum.js` 禁用缺陷 `enableAutoTrackError`，在配置成功后安装应用侧错误钩子，保留 DataKit、两个 appId、已有信号配置和初始化恢复机制。
2. `rum-error-handler.cjs` 从安装 Skill 的公开资产复制：原处理器同步执行，完整保留 this、全部参数、返回对象和异常对象；上报走独立微任务，失败被隔离。
3. `rum-error-payload.js` 使用固定错误类别与白名单文件/行列信息，避免原始消息、任意字段、查询参数及完整路径进入 payload；SDK 实际桥接 payload 包含有效 `index.js:12:9` 帧和 SDK 自带版本字段，敏感 canary 不出现。

精确补丁在 `source.patch`，源码哈希在 `source-sha256.json`。

## 严格验证结果

使用 `/Users/oneandonly/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node`。

| 命令/阶段 | 实际退出码 | 结论 |
| --- | --- | --- |
| 安装命令（见 install.log） | 0 | 镜像安装成功 |
| detect_rum_targets.py project --pretty | 0 | 一个 React Native target，Android/iOS 两个独立 slot |
| validate_contract.py plan --phase plan | 0 | 首次计划通过 |
| validate_contract.py plan --phase implement --repository project | 0 | 首次实施校验通过 |
| node verify.cjs android success，修复前严格基线 | 1 | 原处理器返回值变为 undefined |
| node --check，4 个维护 JS/CJS 文件 | 全部 0 | 语法通过 |
| python3 run-tests.py，修复后最终矩阵 | 0 | 24/24 通过 |
| 官方 npm latest 元数据读取 | 0 | 当前版本 0.4.2，RN peer 范围覆盖夹具 0.80.0 |

矩阵为 Android/iOS × 上报成功、拒绝、同步抛错、永不 resolve、配置失败后重试、缺桥失败与恢复 × 原处理器返回/抛错。每个成功配置场景检查：

- 同步原处理器调用恰好一次，this、3 个参数、返回对象或抛出的同一异常对象保留。
- 上报发生在原处理器之后，真实公开 `FTReactNativeRUM.addError` 进入 native double 一次；上报 reject/throw/never 不改变应用行为。
- 重复启动与应用模块 reload 不重复配置/安装错误钩子，console.error 的函数身份保持。
- 配置第一次失败后不安装钩子，后续重试成功；base sdkConfig 仍只调用一次。
- 清理仅撤销自己拥有的钩子，不覆盖后来注册的其他处理器；重复清理无副作用。
- 错误 payload 非空，有可用位置，敏感 canary 未进入最终桥接数据。

每次子进程的精确 command、exit、stdout、stderr 都在 `test-results.json`；每场景桥接内容在 `logs/<platform>-<mode>-<returns|throws>.json`。

## 保留的失败与限制

首次 harness 自身出现过一次假绿：断言 catch 调用了被缺陷 SDK 替换的 `console.error`，该调用在设置 exitCode 前抛错，而临时 unhandledRejection 监听吞掉该失败，得到 exit 0。原输出保存在 `logs/baseline-strict.log`，不计为通过证据。立即将 harness 改为启动时默认 exitCode=1、使用 `fs.writeSync` 输出失败、只有全部断言完成才置 0。重新运行基线得到明确 exit 1，失败栈在 `logs/baseline-strict-corrected.log`。最终 24 个用例全部采用修正后的严格 harness。

缺 bridge 时 startRum 多次返回 false、原错误处理器不变。真实 SDK 在模块实例中缓存 null bridge，单纯恢复模拟桥后同进程重试仍为 false；恢复验证明确重载 SDK JS 模块，再重试成功。此处代表模块/进程重启，不声称动态 native bridge 自动恢复。

未运行 Android/iOS 原生构建：夹具缺完整 Gradle/Podfile/AppRegistry/应用骨架。未执行 native 平台 appId 选择代码、未验证设备网络或远程数据入库。只验证 JS 向 native 传入正确的独立 appId 配置。未发现本次修复 Skill 的新增阻断问题；应用侧 payload 脱敏需按各真实项目源文件/发布格式适配，此夹具采用最小白名单。

官方来源核验：`logs/official-npm-source.json` 记录 npm 注册表元数据；并读取了官方快速开始文档 https://docs.guance.com/real-user-monitoring/react-native/quick-start/ 。
