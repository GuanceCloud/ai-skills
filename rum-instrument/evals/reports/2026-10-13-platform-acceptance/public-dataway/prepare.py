from pathlib import Path
import json,subprocess,os,difflib
r=Path('/private/tmp/rum-platform-acceptance/web-public-dataway')
p=json.loads(Path('/private/tmp/rum-platform-acceptance/web/evidence/validated-plan.json').read_text())
p['repository']={'root':str(r),'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip(),'initial_status':[]}
p['request']['application_id_input']['reference']['value']='new_skill_001'
p['request']['receiver']={'mode':'public_dataway','endpoint':{'value':'http://testing-openway.dataflux.cn'},'client_tokens':{'web':{'source':'runtime:VITE_RUM_CLIENT_TOKEN','availability':'planned','sink':{'path':'.env.production.local','format':'dotenv','scope':'repository','key':'VITE_RUM_CLIENT_TOKEN'}}},'control_plane':{'status':'catalog_resolved','catalog':'builtin_testing','site_code':'testing','ai_api_endpoint':{'value':'https://testing-ft2x-ai-api.dataflux.cn'},'exchange_path':'/api/v1/account/accesskey/exchange','application_lookup_path':'/api/v1/rum/app/get','api_key_persistence':'memory_only','tls_verification':'verified','test_only':True,'temporary_authorization_code':{'source':'prompt:provided'}}}
t=p['targets'][0];t['application_ids']['web']['value']='new_skill_001';t['application_types']['web']['verification']='pending';t['existing_instrumentation']={'status':'existing','files':['src/rum.ts','src/main.ts','.env.production'],'sdk':'@cloudcare/browser-rum','version':'3.3.21','signals':['rum']};t['receiver_mapping']={'applicationId':'VITE_RUM_APP_ID','site':'VITE_RUM_SITE','clientToken':'VITE_RUM_CLIENT_TOKEN'}
blockers=['Trusted CA PEM path not yet supplied; certificate verification remains enabled. Credential resolution and implementation await successful verified preflight.']
t['blockers']=blockers;t['disposition']='planned'
p['authorizations']={'testing_site':{'evidence':'User explicitly selected http://testing-openway.dataflux.cn for real test, corrected application ID to new_skill_001, supplied fresh temporary code to parent agent, and requested trusted CA with verification retained.','conditions':{'test_only':'Isolated test project only; not production deployment'}}}
changes=[('.env.production','Prepare non-secret testing site and application ID; remove old DataKit variable'),('.env.example','Document blank client Token key with ignored local sink'),('src/rum-config.ts','Prepare typed framework-native Vite config reader; consume Token only through import.meta.env'),('src/rum.ts','AFTER state validation replace DataKit init branch with typed Public DataWay config, preserving single initialization and failure handling'),('README.md','Explain test-only config, ignored sink and verified-TLS staged workflow')]
p['planned_changes']=[]
for i,(file,purpose) in enumerate(changes,1):p['planned_changes'].append({'target_id':'web:.','file':file,'order':i,'purpose':purpose,'edits':[purpose],'dependency_decision':{'action':'none'},'validation':['Full vue-tsc strict declaration check and Vite production build','After verified token persistence: implementation state validation, actual config consumption without printing credential values'],'risk':'No remote browser execution before configuration resolution; token-bearing build remains ignored','rollback':'Restore copied baseline only in this isolated worktree'})
p['approval']={'status':'pending','basis':'explicit_implementation_request','blockers':blockers,'revision':1};p['batches']=[{'id':'web','target_ids':['web:.'],'depends_on':[],'approval':dict(p['approval'])}]
p['validation']=['Plan validation before credential resolution','Verify .env.production.local and .rum/control-plane-state.json are distinct ignored regular paths; helper uses 0600','No old code consumed; parent feeds fresh code only through stdin after trusted TLS preflight','Full strict Vue TypeScript and production build after local preparation','After credential resolution validate state before applying held initializer patch','Actual remote runtime test only when parent executes authorized continuation']
p['risks']=['Public testing DataWay uses user-selected HTTP and is test-only','Current AI API self-signed chain rejected by default trust; user selected trusted CA rather than disabled verification','No token resolution or external telemetry performed during preparation']
p['handoff']=['Parent obtain trusted CA PEM path; pass verified trust via process SSL_CERT_FILE as appropriate','After CA verification clear execution blockers; retain verified TLS, add no disabled_tls receipt','Use plan helper without legacy --insecure-test-tls; state defaults .rum/control-plane-state.json']
data=json.dumps(p,ensure_ascii=False,indent=2,sort_keys=True)+'\n';(r/'.rum/plan.json').write_text(data);(r/'evidence/first-plan.json').write_text(data)
(r/'.env.production').write_text('VITE_RUM_APP_ID=new_skill_001\nVITE_RUM_SITE=http://testing-openway.dataflux.cn\n')
(r/'.env.example').write_text('# Test-only non-secret values. Actual token is written only by the helper to ignored .env.production.local.\nVITE_RUM_APP_ID=new_skill_001\nVITE_RUM_SITE=http://testing-openway.dataflux.cn\nVITE_RUM_CLIENT_TOKEN=\n')
fd=os.open(r/'.env.production.local',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
(r/'src/rum-config.ts').write_text('''import type { RumInitConfiguration } from '@cloudcare/browser-rum'

// Vite loads the ignored .env.production.local at build time. Never log these values.
export function readRumConfiguration(): RumInitConfiguration | undefined {
  const applicationId = import.meta.env.VITE_RUM_APP_ID
  const site = import.meta.env.VITE_RUM_SITE
  const clientToken = import.meta.env.VITE_RUM_CLIENT_TOKEN
  if (!applicationId || !site || !clientToken) return undefined
  return {
    applicationId,
    site,
    clientToken,
    service: __APP_SERVICE__,
    version: __APP_VERSION__,
    env: import.meta.env.MODE,
    sessionReplaySampleRate: 0,
  }
}
''')
old=(r/'src/rum.ts').read_text();new='''import { readRumConfiguration } from './rum-config'

let startup: Promise<void> | undefined

export function initializeRum(): Promise<void> {
  startup ??= (async () => {
    try {
      const configuration = readRumConfiguration()
      if (!configuration) return
      const { datafluxRum } = await import('@cloudcare/browser-rum')
      datafluxRum.init(configuration)
    } catch {
      console.warn('RUM initialization unavailable; application continues')
    }
  })()
  return startup
}
'''
patch=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/src/rum.ts',tofile='b/src/rum.ts'))
(r/'evidence/after-state-initializer.patch').write_text(patch)
(r/'README.md').write_text('''# 隔离 Vue Public DataWay 测试准备

由已通过完整验收的 Vue 工程复制，保留真实 Browser SDK 3.3.21 和公开 lockfile。原工程不变。

非秘密配置 `.env.production` 使用 `new_skill_001` 和用户选定测试 Public DataWay。Client Token 由 plan helper 写入 Git ignored、0600 的 `.env.production.local`，键 `VITE_RUM_CLIENT_TOKEN`；不可打印、提交或手动检查内容。Vite 会加载该框架原生文件，类型化读取器是 `src/rum-config.ts`。

当前只是准备阶段。原 `src/rum.ts` 的 DataKit 初始化器未改动；旧 DataKit 环境键已移除，因此当前启动会跳过 RUM，不向外发送数据。Public DataWay 初始化改动保存在 `evidence/after-state-initializer.patch`，必须在可信 CA、凭据解析和 saved-state 校验通过后再应用。

用户选择保留 TLS 校验，需要可信 CA PEM；不得增加 TLS 例外。此工程不用于生产部署。

`npm ci --registry=https://registry.npmjs.org` 后 `npm run build` 会运行 strict Vue SFC/SDK 声明检查和 Vite production build。生成的 dist 被 Git 忽略；换码后构建产物包含客户端配置，不应打印或归档其中内容。

复制的 `scripts/acceptance.mjs` 是原 DataKit localhost 验收脚本，当前阶段不运行；父代理继续 Public DataWay 验收时需调整为不输出 Token 的专用配置检查。
''')
