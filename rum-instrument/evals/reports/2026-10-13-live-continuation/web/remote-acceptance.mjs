import { createServer } from 'node:http'
import { readFile, readdir, writeFile } from 'node:fs/promises'
import { resolve, extname } from 'node:path'
import { pathToFileURL } from 'node:url'
const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE || '/var/folders/8x/2_sfyjt11tb3y7_n0m9l53lc0000gn/T/rum-full-eval-fsgyxvww/web/test-tools/node_modules/playwright/index.mjs'))
const root=resolve(import.meta.dirname,'..'), checks=[], requests=[], responses=[], failures=[], responseReads=[], consoleCounts={errors:0,cors:0}, pageErrors={count:0}
const origin='http://testing-openway.dataflux.cn', canary='CANARY_LOCAL_DRAFT_MUST_NOT_BE_COLLECTED'
const check=(name,passed,detail)=>checks.push({name,passed,detail})
const isReceiver=r=>{try{return new URL(r.url()).origin===origin}catch{return false}}
const server=createServer(async(req,res)=>{
 const path=new URL(req.url,'http://127.0.0.1').pathname
 const file=path.startsWith('/assets/')||['/sample.json','/mark.svg'].includes(path)?path:'/index.html'
 if(file.includes('..')){res.writeHead(400);return res.end()}
 try{const data=await readFile(root+'/dist'+file);res.writeHead(200,{'Content-Type':({'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml'})[extname(file)]||'text/plain'});res.end(data)}catch{res.writeHead(404);res.end()}
})
await new Promise(r=>server.listen(19538,'127.0.0.1',r))
let browser
try{
 browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true})
 const page=await browser.newPage()
 page.on('request',r=>{if(!isReceiver(r))return;const body=r.postData()||'';requests.push({method:r.method(),transport:r.resourceType(),path:new URL(r.url()).pathname,bytes:Buffer.byteLength(body),measurements:Object.fromEntries(['view','resource','error'].map(k=>[k,(body.match(new RegExp('^'+k+',','gm'))||[]).length])),canary_absent:!body.includes(canary),expected_app:body.includes('app_id=new_skill_001')})})
 page.on('response',r=>{if(!isReceiver(r))return;const headers=r.headers();const record={path:new URL(r.url()).pathname,status:r.status(),transport:r.request().resourceType(),cors_origin:headers['access-control-allow-origin']||null,cors_credentials:headers['access-control-allow-credentials']||null,content_type:headers['content-type']||null};responses.push(record);responseReads.push((async()=>{try{const body=await r.text();record.response_body_empty=body.length===0;try{const json=JSON.parse(body);record.response_success=json.success===true;record.response_has_error=Boolean(json.error||json.errorCode)}catch{record.response_is_json=false}}catch{record.response_body_readable=false}})())})
 page.on('console',m=>{if(m.type()==='error')consoleCounts.errors++;if(/cors|access-control/i.test(m.text()))consoleCounts.cors++})
 page.on('pageerror',()=>pageErrors.count++)
 page.on('requestfailed',r=>{if(isReceiver(r))failures.push({path:new URL(r.url()).pathname,transport:r.resourceType(),error:r.failure()?.errorText?.match(/net::[A-Z_]+/)?.[0]||'request_failed'})})
 await page.goto('http://127.0.0.1:19538/')
 await page.getByRole('heading',{name:'首页',exact:true}).waitFor()
 check('production_vue_mount',true)
 const assets=await readdir(root+'/dist/assets'),rumAsset=assets.find(x=>/^rum-.*\.js$/.test(x))
 const text=await readFile(root+'/dist/assets/'+rumAsset,'utf8'),sdkFile=text.match(/import\("\.\/([^\"]+\.js)"\)/)?.[1]
 if(!sdkFile)throw Error('SdkModuleNotFound')
 const configCheck=await page.evaluate(async({sdkFile,rumAsset})=>{
  const exports=await import('/assets/'+sdkFile),sdk=Object.values(exports).find(v=>v&&typeof v.getInitConfiguration==='function')
  const before=sdk.getInitConfiguration(),rum=await import('/assets/'+rumAsset)
  for(const fn of Object.values(rum))if(typeof fn==='function')await fn()
  const after=sdk.getInitConfiguration()
  return {app:after.applicationId==='new_skill_001',site:after.site==='http://testing-openway.dataflux.cn',token_present:typeof after.clientToken==='string'&&after.clientToken.length>0,no_datakit:!after.datakitOrigin,replay_off:after.sessionReplaySampleRate===0&&!sdk.isRecording(),trace_off:!after.allowedTracingOrigins,config_unchanged:['applicationId','site','clientToken','service','version','env','sessionReplaySampleRate'].every(key=>before[key]===after[key])}
 },{sdkFile,rumAsset})
 check('public_dataway_configuration',Object.values(configCheck).every(Boolean),configCheck)
 await page.getByLabel('本地草稿').fill(canary)
 await page.getByRole('button',{name:'请求资源'}).click();await page.getByText('资源请求成功').waitFor()
 await page.getByRole('button',{name:'触发错误'}).click();await page.waitForFunction(()=>document.documentElement.dataset.appErrors==='1')
 check('application_resource_and_error_handler',true)
 await page.waitForTimeout(2500)
 await page.getByRole('link',{name:'详情',exact:true}).click();await page.getByRole('heading',{name:'详情页',exact:true}).waitFor()
 check('spa_navigation',page.url().endsWith('/details?page=2'))
 await page.waitForTimeout(5000)
 await page.getByRole('link',{name:'首页',exact:true}).click();await page.waitForTimeout(6000)
 await page.waitForTimeout(1200)
 const writes=requests.filter(r=>r.method==='POST'&&r.bytes>0)
 check('nonempty_real_sdk_upload',writes.length>0)
 for(const kind of ['view','resource','error'])check(kind+'_sent',writes.some(r=>r.measurements[kind]>0))
 check('correct_app_in_upload',writes.length>0&&writes.every(r=>r.expected_app))
 check('local_draft_not_collected',writes.length>0&&writes.every(r=>r.canary_absent))
 check('receiver_http_success',writes.length>0&&responses.length>0&&responses.every(r=>r.status>=200&&r.status<300)&&failures.length===0)
}catch(error){check('harness_completed',false,{error_type:error.name})}
finally{
 if(browser)await browser.close()
 await Promise.allSettled(responseReads)
 await new Promise(r=>server.close(r))
 const result={checks,requests,responses,failures,consoleCounts,pageErrors,remote_ingestion_verified:false,proof_level:'Real Browser SDK sent requests to user-authorized test DataWay; no server-side query performed',sensitive_output:'No credential values, request query strings, headers, raw payloads, console text or bundle source stored'}
 await writeFile(root+'/evidence/remote-browser-results.json',JSON.stringify(result,null,2)+'\n')
 console.log(JSON.stringify(result,null,2))
}
if(checks.some(c=>!c.passed))process.exitCode=1
