from pathlib import Path
import subprocess,json,hashlib,copy,datetime

BASE=Path('/private/tmp/rum-slim-forward-eval-20261014')
SKILL=Path('/Users/oneandonly/Workspace/ai-skills/rum-instrument')
RESULTS=[]
COMMON_READS=['SKILL.md','references/web.md','references/contracts.md','references/execution.md','references/official-sources.json','assets/plan-draft.example.json']
APP='''window.appStarted = (window.appStarted || 0) + 1;
document.getElementById('app').textContent = 'Fixture application ready';
window.appRequest = fetch('/api/health').then(response => response.json());
'''
INIT='''// RUM evaluation fixture: window.DATAFLUX_RUM is a controlled test double.
if (!window.__rumInitialized && window.RUM_CONFIG?.applicationId && window.RUM_CONFIG?.datakitOrigin) {
  try {
    window.DATAFLUX_RUM.init(window.RUM_CONFIG);
    window.__rumInitialized = true;
  } catch (error) {
    console.warn('RUM initialization unavailable');
  }
}
'''
SMOKE=r'''const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const http = require('http');
(async () => {
 const events=[];
 const server=http.createServer((req,res)=>{
  let body=''; req.on('data',c=>body+=c); req.on('end',()=>{
   if(req.url==='/api/health'){res.setHeader('Content-Type','application/json');res.end('{"ok":true}');return;}
   events.push(JSON.parse(body)); res.end('accepted by local synthetic receiver');
  });
 });
 await new Promise((resolve,reject)=>server.once('error',reject).listen(19529,'127.0.0.1',resolve));
 try {
  const main=fs.readFileSync('src/main.js','utf8');
  const config=JSON.parse(fs.readFileSync('rum.config.json','utf8'));
  const startup=(sdkFails=false)=>{
   const state={inits:[],warns:[],element:{},pending:[]};
   const context={console:{warn:msg=>state.warns.push(msg)},document:{getElementById:()=>state.element},fetch:url=>fetch(new URL(url,'http://127.0.0.1:19529'))};
   context.window=context;context.RUM_CONFIG=config;
   context.DATAFLUX_RUM={init:options=>{
    if(sdkFails)throw Error('Synthetic SDK load/init failure');
    state.inits.push(options);
    // Deliberately synthetic view/resource/error events: no real SDK behavior claimed.
    for (const type of ['view','resource','error']) state.pending.push(fetch(options.datakitOrigin+'/synthetic-rum',{method:'POST',body:JSON.stringify({type,applicationId:options.applicationId,service:options.service,version:options.version,env:options.env})}));
   }};
   vm.createContext(context); vm.runInContext(main,context);return {context,state};
  };
  const success=startup();
  assert.equal(success.context.appStarted,1);assert.equal(success.state.inits.length,1);
  assert.equal(success.state.element.textContent,'Fixture application ready');
  assert.deepEqual(await success.context.appRequest,{ok:true});
  vm.runInContext(main,success.context);assert.equal(success.state.inits.length,1);
  await success.context.appRequest;await Promise.all(success.state.pending);
  assert.equal(success.state.inits[0].applicationId,config.applicationId);
  assert.equal(success.state.inits[0].datakitOrigin,'http://127.0.0.1:19529');
  assert.equal('site' in success.state.inits[0],false);assert.equal('clientToken' in success.state.inits[0],false);
  const failed=startup(true);assert.equal(failed.context.appStarted,1);await failed.context.appRequest;
  assert.equal(failed.state.warns.length,1);
  assert.deepEqual(events.map(e=>e.type).sort(),['error','resource','view']);
  console.log(JSON.stringify({mode:'controlled-SDK-and-local-HTTP-receiver',initializers:success.state.inits.length,startup_preserved:true,request_preserved:true,sdk_failure_startup_preserved:true,configuration:config,events,real_sdk_verified:false,backend_ingestion_verified:false}));
 } finally { await new Promise(resolve=>server.close(resolve)); }
})().catch(error=>{console.error(error);process.exitCode=1});
'''

def write(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n' if not isinstance(data,str) else data)

def cmd(s,args,cwd=None,expected=0):
 cwd=cwd or Path(s['fixture'])
 p=subprocess.run([str(x) for x in args],cwd=cwd,capture_output=True,text=True)
 entry={'command':[str(x) for x in args],'cwd':str(cwd),'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'expected_exit':expected}
 s['commands'].append(entry)
 write(BASE/s['id']/'commands.json',s['commands'])
 if expected is not None and p.returncode!=expected:print('UNEXPECTED',s['id'],entry,flush=True)
 return p

def config(appid):return {'applicationId':appid,'datakitOrigin':'http://127.0.0.1:19529','service':'synthetic-web-fixture','version':'1.0.0','env':'test','sessionSampleRate':35}

def app(root,existing=False,appid='synthetic-web-01'):
 write(root/'package.json',{'name':'rum-behavior-fixture','version':'1.0.0','private':True,'scripts':{'check':'node --check src/main.js','test':'node tests/smoke.cjs'}})
 write(root/'index.html','<!doctype html><html><body><main id="app"></main><script src="test-support/rum-sdk-double.js"></script><script src="src/bootstrap.js"></script></body></html>\n')
 write(root/'test-support/rum-sdk-double.js','// Controlled evaluation double, not the official Guance SDK.\nwindow.DATAFLUX_RUM = {init(options) { window.lastSyntheticRumOptions = options; }};\n')
 write(root/'src/bootstrap.js',"fetch('./rum.config.json').then(r => r.ok ? r.json() : {}).catch(() => ({})).then(config => { window.RUM_CONFIG = config; const script = document.createElement('script'); script.src = 'src/main.js'; document.body.appendChild(script); });\n")
 write(root/'src/main.js',(INIT if existing else '')+APP)
 write(root/'rum.config.json',config(appid) if existing else {})
 write(root/'tests/smoke.cjs',SMOKE)
 write(root/'README.md','# Synthetic RUM evaluation app\nRun npm run check and npm test after integration. The SDK is a controlled test double. No real SDK dependency, remote receiver or credentials are used.\n')

def scenario(sid,apps=None,existing=False):
 root=BASE/sid/'fixture';root.mkdir(parents=True,exist_ok=True)
 s={'id':sid,'fixture':str(root),'commands':[],'read_files':COMMON_READS.copy(),'followup_questions':[],'followup_count':0,'routine_approval_count':0,'first_plan_failed':False,'plan_repair_count':0,'runtime_repairs':0,'simulation':'Controlled SDK double; real local HTTP on 127.0.0.1:19529; no remote/control-plane operations','remote_verification':False}
 write(root/'AGENTS.md','# Fixture instructions\nOnly modify maintained application files. This is a synthetic offline fixture.\n')
 write(root/'.gitignore','.rum/\nnode_modules/\n')
 for p in apps or ['.']:app(root/p,existing)
 for args in [['git','init','-q'],['git','add','.'],['git','-c','user.name=RUM Evaluation','-c','user.email=rum-eval@example.invalid','commit','-qm','synthetic baseline']]:cmd(s,args)
 for args in [['git','status','--short'],['git','diff'],['git','rev-parse','HEAD'],['python3',SKILL/'scripts/detect_rum_targets.py',root,'--pretty']]:cmd(s,args)
 for p in ['AGENTS.md','.gitignore']+[(str(Path(prefix)/f)) for prefix in apps or ['.'] for f in ['package.json','index.html','src/main.js','src/bootstrap.js','rum.config.json','README.md','test-support/rum-sdk-double.js','tests/smoke.cjs']]:
  (root/p).read_text();s['read_files'].append(p)
 RESULTS.append(s);return s,root

def target(prefix='.',slot='web',appid='synthetic-web-01',existing=False,blocked=False):
 t={'id':f'web:{prefix}','path':prefix,'platform':'web','variants':['browser'],'evidence':[str(Path(prefix)/p) for p in ['index.html','package.json','src/main.js','rum.config.json']],'application_id_slots':[slot],'application_ids':{} if blocked else {slot:{'value':appid}},'application_types':{slot:{'value':'web','source':'repository','confidence':'high','verification':'not_applicable','api_value':None}},'existing_instrumentation':{'status':'present' if existing else 'none','files':[str(Path(prefix)/'src/main.js')] if existing else [],'sdk':'controlled-test-double' if existing else None,'version':'fixture-1' if existing else None,'signals':['rum'] if existing else []},'official_sources':['https://docs.guance.com/real-user-monitoring/web/app-access/']}
 if existing:t['disposition']='existing'
 if blocked:t.update(disposition='blocked',blockers=[f'missing {slot} Application ID'])
 return t

def draft(targets,existing=False):
 ids={key:v for t in targets for key,v in t['application_ids'].items()}
 d={'request':{'intent':'implement','application_id_input':{'kind':'scalar','reference':next(iter(ids.values()))} if len(targets)==1 else {'kind':'map','references':ids},'receiver':{'mode':'datakit','endpoint':{'value':'http://127.0.0.1:19529'}},'authorization_evidence':'Evaluation task explicitly authorizes core RUM integration in isolated synthetic fixtures; no remote operations.'},'targets':targets,'planned_changes':[]}
 if len(targets)>1:d['batches']=[{'id':t['application_id_slots'][0],'target_ids':[t['id']],'depends_on':[]} for t in targets]
 for t in targets:
  if t.get('disposition') in ['blocked','existing']:continue
  for f,purpose in [('src/main.js','Initialize controlled RUM double once while preserving app startup'),('rum.config.json','Use synthetic application ID and localhost DataKit receiver')]:
   d['planned_changes'].append({'target_id':t['id'],'file':str(Path(t['path'])/f),'order':len(d['planned_changes'])+1,'purpose':purpose,'edits':[purpose],'dependency_decision':{'action':'none'},'validation':['npm run check','npm test using controlled SDK and local synthetic HTTP receiver'],'risk':'Only controlled SDK behavior is tested; real SDK and backend not verified','rollback':'Revert only this RUM fixture edit'})
 return d

def complete(s,root,d):
 write(root/'.rum/draft.json',d)
 p=cmd(s,['python3',SKILL/'scripts/validate_contract.py','.rum/draft.json','--complete-draft','.rum/plan.json','--repository',root])
 s['first_plan_failed']=p.returncode!=0
 if p.returncode:return False
 cmd(s,['python3',SKILL/'scripts/validate_contract.py','.rum/plan.json','--phase','plan'])
 return True

def impl(s,root,selection=None,expected=0):
 args=['python3',SKILL/'scripts/validate_contract.py','.rum/plan.json','--phase','implement','--repository',root]
 if selection:args.extend(['--targets',*selection])
 return cmd(s,args,expected=expected)

def integrate(s,root,prefix='.',appid='synthetic-web-01'):
 path=root/prefix
 write(path/'src/main.js',INIT+APP);write(path/'rum.config.json',config(appid))
 cmd(s,['npm','run','check'],path);cmd(s,['npm','test'],path)
 cmd(s,['git','diff','--check']);cmd(s,['git','diff','--stat'])

def hashes(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and not any(x in p.relative_to(root).parts for x in ['.git','.rum'])}

s,r=scenario('01_complete_datakit')
if complete(s,r,draft([target()])):
 if impl(s,r).returncode==0:integrate(s,r)
s['outcome']='Local source integration and controlled SDK/HTTP runtime smoke completed; real browser/SDK/backend unverified.'

s,r=scenario('02_missing_essentials')
before=hashes(r)
s.update(followup_count=1,followup_questions=[{'when':'After Git/manifests/maintained entry/config discovery and target confirmation; before draft completion and implementation','fields':['RUM application ID','receiver mode and receiver URL'],'proposed_question':'请提供此 Web 应用的 RUM Application ID，以及接收方式和地址（DataKit 或 Public DataWay）。若使用 Public DataWay 且无法复用有效配置，还需一次性授权码。','conditional_fields':['temporaryAuthCode only for Public DataWay when no reusable credentials exist']}],outcome='Stopped at missing answers after useful discovery. No endpoint/ID guessed, no source changes or plan completion attempted.')
s['source_unchanged']=before==hashes(r)

s,r=scenario('03_existing_configuration',existing=True)
before=hashes(r)
t=target(existing=True);t['application_ids']={'web':{'source':'existing:rum.config.json#applicationId'}}
d=draft([t],existing=True);d['request']['receiver']['endpoint']={'source':'existing:rum.config.json#datakitOrigin'}
if complete(s,r,d):
 impl(s,r);cmd(s,['npm','run','check']);cmd(s,['npm','test'])
s.update(source_unchanged=before==hashes(r),outcome='Existing effective configuration reused, including sessionSampleRate=35; no repeated question, no source edit.')

# Repeat uses exactly the first fixture and retains its original repository baseline.
original=RESULTS[0];r=Path(original['fixture'])
s={'id':'04_repeat_completed','fixture':str(r),'commands':[],'read_files':COMMON_READS+['.rum/plan.json','src/main.js','rum.config.json','package.json','index.html'],'followup_questions':[],'followup_count':0,'routine_approval_count':0,'first_plan_failed':False,'plan_repair_count':0,'runtime_repairs':0,'simulation':original['simulation'],'remote_verification':False}
RESULTS.append(s)
before=hashes(r)
for args in [['git','status','--short'],['git','diff'],['python3',SKILL/'scripts/detect_rum_targets.py',r,'--pretty']]:cmd(s,args)
plan=json.loads((r/'.rum/plan.json').read_text());baseline=copy.deepcopy(plan['repository'])
plan['targets'][0]['disposition']='instrumented';plan['planned_changes']=[]
write(r/'.rum/plan.json',plan)
cmd(s,['python3',SKILL/'scripts/validate_contract.py','.rum/plan.json','--phase','plan']);impl(s,r)
cmd(s,['npm','run','check']);cmd(s,['npm','test'])
s.update(source_unchanged=before==hashes(r),original_baseline_preserved=baseline==json.loads((r/'.rum/plan.json').read_text())['repository'],outcome='Repeat rediscovery kept source unchanged, preserved original plan baseline and runtime initializer count=1. Only plan completion disposition was updated.')

s,r=scenario('05_independent_partial',apps=['storefront','admin'])
before=hashes(r/'admin')
t1=target('storefront','storefront','synthetic-storefront-01');t2=target('admin','admin',blocked=True)
s.update(followup_count=1,followup_questions=[{'when':'After both independent deployable apps discovered; does not prevent storefront implementation','fields':['admin Application ID'],'proposed_question':'请提供 admin 应用的 RUM Application ID；storefront 的参数齐全，我会先完成它的本地接入。'}])
if complete(s,r,draft([t1,t2])):
 impl(s,r,expected=1)
 if impl(s,r,['web:storefront']).returncode==0:integrate(s,r,'storefront','synthetic-storefront-01')
s.update(blocked_app_unchanged=before==hashes(r/'admin'),outcome='Full-plan implementation correctly blocked on admin missing ID; selected storefront batch completed local source and controlled runtime smoke. Admin remains explicitly blocked.')

summary={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'skill_path':str(SKILL),'skill_sha256':hashlib.sha256((SKILL/'SKILL.md').read_bytes()).hexdigest(),'scope':'Behavior evaluation via actual helper CLI calls and controlled fixture execution. Not a benchmark of fresh independent model sessions.','official_guide_check':'Attempted official Web access guide with web tool; timeout. No official SDK dependency added or compatibility claim invented.','scenarios':RESULTS}
write(BASE/'results.json',summary)
lines=['# RUM Skill 五场景独立评估','',f'隔离位置：{BASE}','全部应用与 Git 仓库仅存在于 /private/tmp；未修改仓库实现或已安装 Skill，未使用账号、凭据、远端接收端或发布。','', '## 范围','实际运行 detect、--complete-draft、plan/implement 校验和 Node VM 启动/本地 HTTP 接收探针。SDK 为明确标记的受控替身，事件也是人工构造；不证明真实 SDK 自动采集、浏览器兼容性或后端入库。官方 Web 指南读取超时，因此未添加真实依赖或编造兼容性证据。','', '| 场景 | 补问 | 常规审批 | 首次计划失败 | 计划修复 | 结果 |','|---|---:|---:|---:|---:|---|']
for s in RESULTS:lines.append(f"| {s['id']} | {s['followup_count']} | {s['routine_approval_count']} | {int(s['first_plan_failed'])} | {s['plan_repair_count']} | {s['outcome']} |")
lines.extend(['','补问计数为记录的拟询问轮次，没有向真实用户提问。缺信息场景未尝试生成无效计划，因此首次计划失败数为 0/未进入。多应用的全量 implement 非零属于预期拦截，不计为计划失败或修复。','', '所有命令、返回码、stdout/stderr 和逐场景读取文件清单保存在 results.json 及各场景 commands.json。'])
write(BASE/'report.md','\n'.join(lines)+'\n')
print(str(BASE/'results.json'))
