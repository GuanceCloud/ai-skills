# Android RUM 实机链路验收（本机模拟器）

已完成真实 Android APK 构建、安装、启动，以及官方 ft-sdk 1.7.5 在 Android 34 arm64-v8a 模拟器上的本机上报。此处接收器是 Python 实现的 DataKit 协议模拟服务，**不是实际 DataKit，也没有证明远端入库**。

## 固定版本与结果

- 工程：`project/`，Gradle wrapper 8.7、AGP 8.5.2、compile/target SDK 34、min SDK 23、Java source/target 8。
- 构建 JDK：Eclipse Temurin 17.0.20.1+1，macOS aarch64，下载到本目录 `toolchain/`；原本 WebStorm JBR 实际为 Java 11，未修改系统 Java。
- SDK：`com.cloudcare.ft.mobile.sdk.tracker.agent:ft-sdk:1.7.5`，实际 Maven 解析版本记录在 `evidence/build-03-rerun.log`。
- 配套：OkHttp 4.12.0、Gson 2.10.1、AndroidX annotation 1.7.1。完整传递依赖见同一日志。
- 合成 AppId：`eval_android_acceptance`，service `com.example.rumacceptance`，env `acceptance`，version `1.0-acceptance`。
- 仅使用 `http://127.0.0.1:19529` 接收 SDK 上报，`http://127.0.0.1:19530/resource` 测试资源请求；没有授权码、Client Token、API Key 或生产接收端。
- 模拟器 `emulator-5580`：API34、ABI `arm64-v8a`。启动时使用 `-read-only -no-snapshot -datadir <独立目录>`；未擦除原 AVD 数据。
- 两次冷启动，应用 PID 分别为 4344、4495，每进程 SDK 初始化记录均为 1。第二次实际接收 View、Resource、Error 各 1 条。
- 首次实际 plan/implement 契约校验通过，随后才编辑接入初始化代码。
- `assembleDebug lintDebug testDebugUnitTest wrapper` 最终退出 0；`testDebugUnitTest` 为 NO-SOURCE，不能算单元测试通过。
- wrapper 离线重跑 `assembleDebug lintDebug :app:dependencies --configuration debugRuntimeClasspath` 退出 0。
- `verify_payload.py` 16 个断言全部通过，进程退出 0；`git diff --check` 退出 0。

## 本地证据

`evidence/payload-verification.json` 是机器可读结果。`payloads.jsonl` 保留真实 SDK 压缩传输解码后的合成载荷；`resource-requests.jsonl` 证明原请求的 Authorization 和 body 合成 canary 确实到达本机测试 API。SDK 上报中三种 canary（输入内容、授权头、请求体）均未出现，Authorization 被默认掩码为 `██`；未添加 Trace 头。标准 Resource URL、HTTP200、耗时及 Error stack 均保留。

View 使用手动 `startView/stopView`，Error 使用手动 `addError` 加入固定合成异常；Resource 使用真实 OkHttp 官方 interceptor + event listener。没有使用 ft-plugin，因此不宣称验证了插件自动 Activity/Fragment/click 插桩。没有启用 crash capture、Logs、Trace、Replay、WebView 或符号上传；没有验证发布签名、真实设备、其他 Android API 或真实 DataKit。

第一轮构建中 assemble 已完成，但 lint 因 debug 网络配置缺少 `includeSubdomains` 失败（exit 1）；修正后独立重跑通过，原日志保留为 `build-01.log`。第一次冷启动中本机接收器未处理 chunked/deflate，导致捕获为空；该失败保存在 `payloads-first-collector-bug.jsonl`。修正接收器后第二次冷启动捕获成功，未将首次空捕获算作通过。

初始化工程脚本最初使用当前旧 Git 不支持的 `git init -b`，执行失败且计划尚未创建；改用兼容的 `git init` 后才完成基线及首次真实契约验证。此为夹具工具兼容问题，不是 Skill 契约失败。

## 重跑

要求已有 Android SDK API34/build-tools34 和 AVD `rum_mock_api34`。若本机端口已占用，请更换专用模拟器端口并相应更改 serial，不能关闭他人的设备。以下环境变量只作用于当前 shell。

```sh
cd /private/tmp/rum-platform-acceptance/android
export JAVA_HOME="$PWD/toolchain/jdk-17.0.20.1+1/Contents/Home"
export ANDROID_HOME=/Users/oneandonly/Library/Android/sdk
cd project
cp rum.properties.example rum.properties
./gradlew --no-daemon --console=plain assembleDebug lintDebug
```

单独终端启动本机接收器（历史 JSONL 为追加写入，重新统计前请使用独立证据目录/副本）：

```sh
python3 /private/tmp/rum-platform-acceptance/android/collector.py
```

单独终端启动专用模拟器：

```sh
/Users/oneandonly/Library/Android/sdk/emulator/emulator -avd rum_mock_api34 -port 5580 -read-only -no-snapshot -no-window -no-audio -no-boot-anim -gpu swiftshader_indirect -datadir /private/tmp/rum-platform-acceptance/android/emulator-data
```

启动完成后安装并运行：

```sh
adb -s emulator-5580 reverse tcp:19529 tcp:19529
adb -s emulator-5580 reverse tcp:19530 tcp:19530
adb -s emulator-5580 install -r app/build/outputs/apk/debug/app-debug.apk
adb -s emulator-5580 shell am start -W -n com.example.rumacceptance/.MainActivity
adb -s emulator-5580 logcat -d -s RUMAcceptance
```

等待约 10 秒检查非空 `/v1/write/rum`。`verify_payload.py` 校验已保存的本次两次冷启动证据；新的实验请同步更新对应启动日志、设备信息和预期次数。结束时仅关闭自己刚启动的专用模拟器及接收器。

官方依据：[Android 接入文档](https://docs.guance.com/real-user-monitoring/android/app-access/)、[SDK 源码](https://github.com/GuanceCloud/datakit-android)、官方 Maven `https://mvnrepo.guance.com/repository/maven-releases/`。验证日期 2026-10-13。
