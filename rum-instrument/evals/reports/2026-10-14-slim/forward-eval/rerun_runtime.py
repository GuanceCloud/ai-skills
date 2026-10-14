from pathlib import Path
import json,subprocess
base=Path('/private/tmp/rum-slim-forward-eval-20261014')
data=json.loads((base/'results.json').read_text())
original=base/'01_complete_datakit/fixture/tests/smoke.cjs'
polyfill='''const fetch = (url, options = {}) => new Promise((resolve, reject) => {
 const request = http.request(url, { method: options.method || 'GET' }, response => {
  let body=''; response.on('data', chunk => body += chunk);
  response.on('end', () => resolve({ json: async () => JSON.parse(body) }));
 });
 request.on('error', reject); if (options.body) request.write(options.body); request.end();
});
'''
harness=base/'node16-compatible-smoke.cjs'
harness.write_text(original.read_text().replace('(async () => {',polyfill+'(async () => {',1))
for s in data['scenarios']:
 if s['id']=='02_missing_essentials': continue
 root=Path(s['fixture'])/('storefront' if s['id']=='05_independent_partial' else '.')
 p=subprocess.run(['node',str(harness)],cwd=root,capture_output=True,text=True)
 s['commands'].append({'command':['node',str(harness)],'cwd':str(root),'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'sandbox':'tool-authorized localhost listener','expected_exit':0})
 s['runtime_repairs']=1
 s['runtime_repair_details']='Original local HTTP probe blocked by sandbox EPERM; reviewed local-only runtime was authorized. System Node 16 has no global fetch: replaced fetch solely in external evaluation harness with node:http; fixture source unchanged.'
 s['runtime_verified_with_controlled_double']=p.returncode==0
 s['runtime_result']=json.loads(p.stdout) if p.returncode==0 else None
 (base/s['id']/'commands.json').write_text(json.dumps(s['commands'],ensure_ascii=False,indent=2)+'\n')
 print(s['id'],p.returncode,p.stdout,p.stderr,flush=True)
data['environment_failures']=[{'phase':'original sandboxed local HTTP runtime','failure':'listen EPERM 127.0.0.1:19529','count':4,'resolved_by':'tool-authorized local-only listener'},{'phase':'first tool-authorized local HTTP runtime','failure':'ReferenceError: fetch is not defined','count':1,'resolved_by':'external Node 16 compatible harness; no fixture application change'}]
data['runtime_scope']='Node VM with minimal document stub and controlled SDK; synthetic view/resource/error events sent over real loopback HTTP. Not a real browser run or true SDK privacy proof.'
(base/'results.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
with (base/'report.md').open('a') as f:f.write('\n运行探针实际遇到 4 次沙箱本地监听 EPERM；工具级授权后发现系统 Node 16 无 global fetch，产生 1 次探针失败。仅将外部测试探针改为 node:http 后重跑，未修改被评估 Skill 或应用源码。各运行场景记探针修复 1 次，计划修复仍为 0。最终运行结果详见 results.json 的 runtime_verified_with_controlled_double 与 runtime_result。\n')
