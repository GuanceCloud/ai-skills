# SDK 3.3.21 transport / ERR_ABORTED 独立调查

结论：源码和本机对照均不支持“SDK 收到 HTTP 200 后主动调用 abort/cancel”。SDK 只读取响应 status/type、不消费 body。在本次 Google Chrome / Playwright 组合，未消费的空 HTTP 200 响应可产生 `response(200) → requestfailed(net::ERR_ABORTED)` 且 Playwright response.text 不可读；完全原生 fetch 也精确复现。页面 JS 主动读取同一空响应体后，返回空串且 Playwright 变为 finished。

因此不能只凭 requestfailed 把父代理记录的全部 200 判成上报失败。应分别记录 HTTP 响应状态、响应体完成情况、SDK 状态和远端入库；HTTP 200 也不等于入库成功。

## 源码证据（未经修改的公开 npm SDK）

根目录 `/private/tmp/rum-platform-acceptance/web/node_modules/@cloudcare/`：

- `browser-core/src/transport/httpRequest.js:240–279`：创建 AbortController，fetch.then 将 `response.status`/`response.type` 交给 callback。未调用 response.body.cancel 或 controller.abort，也不读取 body。对应实际 ESM `esm/transport/httpRequest.js:179–220` 行为一致。
- `browser-core/src/transport/sendWithRetryStrategy.js:192–220`：响应处理防重入，清除 watchdog，移除 ongoing；无需重试则状态设 UP 并调用成功路径。
- 同文件 `325–365`：200 不匹配 0、408、429、>=500 重试条件，2xx 不属于 permanent-drop。
- 同文件 `247–263`：显式 abort 用于未完成有序请求的超时；`440–453` 用于无效 payload 淘汰。200 成功时已清 watchdog 并移除 ongoing，因此这些不是成功响应后的固定取消动作。
- `browser-core/src/browser/fetchObservable.js:120–148`：fetch resolve 后报告 status 与 isAborted:false；拒绝分支才报告 status:0 与取消信息。
- `browser-rum/src/domain/requestCollection.js:135–150` 会克隆业务响应并读取；`browser-core/src/helper/readBytesFromStream.js:41` 的 reader.cancel 是该克隆流读完后的清理。资源采集先由 resourceUtils 的 isAllowedRequestUrl 过滤 intake。不能仅搜到 cancel 就认定它取消 RUM 上报。

## 本机实测

对实际安装 SDK 的 `fetchStrategyWithFallback` + `sendWithRetryStrategy` 直接打包成独立本地测试入口；未修改 SDK 源码。完全原生 fetch 为对照。仅监听 127.0.0.1:19641/19642，仅合成非秘密请求体，无真实 Token。

| 场景 | SDK | 原生 fetch（不读 body） |
|---|---|---|
| 200 空 body | JS 回调200/cors，Playwright ERR_ABORTED | 相同 |
| 200 Content-Length:0 | JS 回调200/cors，Playwright ERR_ABORTED | 相同 |
| 200 JSON + Content-Type | finished，body可读 | 相同 |
| 200 JSON 无 Content-Type | finished，body可读 | 相同 |
| 200 headers 后延迟200ms给 body | finished，body可读 | 相同 |
| 200 headers 后断开连接 | ERR_INCOMPLETE_CHUNKED_ENCODING | 相同 |

12个场景中，AbortController.abort 和 ReadableStreamDefaultReader.cancel 包装观测计数均为0。SDK各场景在响应头200到达时均进入UP，pending=0、ongoing=0；这也说明 SDK 成功状态并不检查后续 body 完整性。

额外2个原生 fetch 对照主动在页面JS执行 response.text()：空200得到空串length0、JSON得到length11，两者都 finished，Playwright body可读、无取消调用。

原始证据 `results.json` 与 `native-read-results.json`。脚本 `entry.js`、`test.mjs`、`test-read.mjs`；本地生成 `transport.js` 仅为独立测试bundle，不是父代理真实工程dist。全部执行命令 exit 0。

## 对父代理真实结果的解释范围

已只读取安全摘要 `web-public-dataway/evidence/remote-browser-results.json`。其中4个真实请求均返回200，CORS匹配、无console/CORS错误，随后ERR_ABORTED。现象与上述空200未消费body对照一致，是有力解释；未读取真实响应原文，也没有远端body长度证据，因此不把“远端一定空body”或“具体Chrome内部GC/流回收机制”写成已证实事实。

建议修正验收口径：`receiver_http_2xx=true`（4/4）、`response_body_completion=unverified/aborted`、`requestfailed_after_2xx=4`、`local_empty_body_reproduction=true`，并保留 `remote_ingestion_verified=false`。保留原始失败报告，另写解释后的复核结果，不删除异常事实，不需要为了让测试变绿改SDK或追加真实流量。

没有读取真实 sink/Token、没有浏览真实dist、没有修改原Web或Public DataWay工程、没有新增真实遥测。本次 Chrome 和两个本地服务均已退出。
