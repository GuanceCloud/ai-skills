from pathlib import Path
import json, subprocess,hashlib
root=Path('/private/tmp/rum-url-policy-eval/restricted'); sdk=Path('/private/tmp/rum-sdk-types-retest/3.3.21/node_modules/@cloudcare')
for mode in ['privacy','blocker']:
 command=['python3',str(root/'verify-evidence.py')]+(['--require-privacy'] if mode=='privacy' else [])
 r=subprocess.run(command,capture_output=True,text=True)
 (root/f'{mode}-assertion-result.json').write_text(json.dumps({'command':command,'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr},indent=2)+'\n')
metadata={}
for rel in ['browser-rum/package.json','browser-rum/esm/domain/assembly.js','browser-core/esm/dataMap.js']:
 p=sdk/rel;metadata[rel]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
 (root/'evidence'/('sdk-'+rel.replace('/','-'))).write_bytes(p.read_bytes())
(root/'evidence/sdk-source-manifest.json').write_text(json.dumps(metadata,indent=2))
report={'status':'completed_forward_test','scope':'Two independent synthetic git fixtures; latest runtime skill; actual SDK 3.3.21 and Chrome 155','skill_path':'/private/tmp/rum-url-policy-eval/skills/rum-instrument/SKILL.md','official_source':'https://docs.guance.com/real-user-monitoring/web/app-access/','scenarios':{},'real_sdk_probe_event_counts':json.loads((root/'evidence/summary.json').read_text()),'privacy_assertion_exit_code':1,'blocker_evidence_assertion_exit_code':0,'remote_ingestion_verified':False,'limitations':['Only SDK 3.3.21 was tested. This is no proof that every future official SDK or remedy fails.','B browser probe isolates the URL-field behavior and serves the original catalog main.js; actual B authorization callback is assessed from maintained source and a separate synthetic function invocation.','Local HTTP payload receipt proves export only, not real DataKit/control-plane ingestion.','Probe initializer is test-only outside both application repositories. Application runtime sources remain unchanged.','The synthetic page and API origins are localhost; there is no real credential, production traffic, or remote mutation.']}
for case in ['A','B']:
 first=json.loads((root/f'{case}-first-decision.json').read_text()); first.update(final_disposition='blocked',plan_gate_passed=True,implementation_gate_passed=False,new_initializer_in_application=False,question_count=0,question_reasons=[],final_evidence='fields.view_url_query retains prohibited synthetic query value after view.url is scrubbed; return false cannot discard view events',required_next_step='Use a verified officially supported filtering remedy or an independently scoped authentication/URL architecture fix before initialization. No user confirmation can waive this failure.')
 report['scenarios'][case]=first
 status=subprocess.check_output(['git','status','--short'],cwd=root/case,text=True);diff=subprocess.check_output(['git','diff','HEAD'],cwd=root/case,text=True)
 (root/f'{case}-final-git.json').write_text(json.dumps({'status':status,'tracked_diff':diff},indent=2))
(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
(root/'report.txt').write_text('''独立 forward-test 结果（2026-10-13）

场景 A：明确政策“所有 URL 查询参数值不得进入任何 RUM 字段”。首次计划 blocked，首次实施门禁拒绝；未生成应用初始化，补问 0 次。原因是适用的明确策略无法由已验证 beforeSend 方案满足，并非 appId/receiver 缺失。

场景 B：用户仅要求基础 RUM；维护态源码在 /auth/callback 从 URL access_token 读入内存认证状态且不清理地址。首次计划 blocked，首次实施门禁拒绝；未生成应用初始化，补问 0 次。阻断依据是实际认证源码的数据流和 SDK 字段映射，不是任意 URL 标记，也没有提出泛化隐私问卷。

两场景按最新 Skill 自主执行：.rum/plan.json 的 plan-phase 均通过；implement-phase 均失败（pending 技术 blocker）。从初始到最终均未编辑 src、package.json、index.html。探针初始化只存在于场景仓库外部。

实际 SDK 与 Chrome 结果：
- 基线 9 个事件；A 清理钩子 8 个事件；A 拒发 View 8 个事件；B 清理钩子 9 个事件。每轮均包含 View、Resource、Error。
- A beforeSend 清理 view.url 和 resource.url 并尝试清理 *_query；导出 view_url 已无 query，fields.view_url_query 仍包含明确禁止的合成值；resource_url_query 保留 page/sort。
- 返回 false 后 View 仍导出，并产生 Can't dismiss view events using beforeSend 警告。
- B access_token 的合成值同样进入 fields.view_url_query。B 探针测试的是已证实源码流对应的 URL 情景，而非真实登录。
- Next 按钮继续更新为第 2 页，浏览器 URL 为 /?page=2&sort=price，请求仍为 /api/catalog?page=2&sort=price，每页仅初始化一次。
- 真正检查隐私要求的 verify-evidence.py --require-privacy 退出 1；验证上述失败支持阻断决策的 verify-evidence.py 退出 0。未把隐私失败记成接入成功。

Skill 阻断依据：
/private/tmp/rum-url-policy-eval/skills/rum-instrument/SKILL.md：
“Only an applicable requirement that cannot be met, demonstrated sensitive-data exposure, or an actual application-behavior/build failure blocks the affected scope before credential exchange or new initialization.”
/private/tmp/rum-url-policy-eval/skills/rum-instrument/references/web.md：
“Never ask for user confirmation to bypass a demonstrated exposure or an unmet explicit requirement.”
因此本轮停止的是有具体证据的应用初始化，不向用户请求确认绕过，也不修改 SDK、拦截全局传输或重写应用导航。没有其他可独立完成的应用目标。

限制：仅验证 Browser SDK 3.3.21，不能推断所有未来版本或所有官方方案均不可行。B 的浏览器 URL 探针使用原目录页的主体行为；认证源码单独检查与合成调用。接收器是本机模拟，HTTP 成功不代表真实 DataKit 或远端入库。原始请求、逐事件 JSON、浏览器钩子/警告、方案门禁输出、SDK 源码快照与校验值均保留在本目录。
''')
print(str(root/'report.json'))
