import { createServer } from 'node:http'
import { readFile, readdir, writeFile } from 'node:fs/promises'
import { resolve, extname } from 'node:path'
import { pathToFileURL } from 'node:url'
const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE || '/var/folders/8x/2_sfyjt11tb3y7_n0m9l53lc0000gn/T/rum-full-eval-fsgyxvww/web/test-tools/node_modules/playwright/index.mjs'))
const root=resolve(import.meta.dirname,'..'), payloads=[], checks=[], requests=[]
const check=(name,passed,detail)=>{checks.push({name,passed,detail});console.log(`${passed?'PASS':'FAIL'} ${name}`)}
const appServer=createServer(async(req,res)=>{
  const pathname=new URL(req.url,'http://127.0.0.1').pathname
  const path=pathname.startsWith('/assets/')||['/sample.json','/mark.svg'].includes(pathname)?pathname:'/index.html'
  try { const data=await readFile(root+'/dist'+path);res.writeHead(200,{'Content-Type':({'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml'})[extname(path)]||'text/plain'});res.end(data) }
  catch {res.writeHead(404);res.end()}
})
const receiver=createServer(async(req,res)=>{
  const chunks=[];for await(const c of req)chunks.push(c)
  const body=Buffer.concat(chunks).toString()
  if(body)payloads.push({url:req.url,method:req.method,body})
  res.writeHead(200,{'Access-Control-Allow-Origin':'http://127.0.0.1:19538','Access-Control-Allow-Credentials':'true','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'GET,POST,OPTIONS','Content-Type':'application/json'});res.end('{}')
})
await Promise.all([new Promise(r=>appServer.listen(19538,'127.0.0.1',r)),new Promise(r=>receiver.listen(19539,'127.0.0.1',r))])
let browser
try {
 browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true})
 const assets=await readdir(root+'/dist/assets');const rumAsset=assets.find(x=>/^rum-.*\.js$/.test(x))
 const page=await browser.newPage();const messages=[],errors=[]
 page.on('console',m=>messages.push({type:m.type(),text:m.text()}));page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push({url:r.url(),method:r.method(),headers:r.headers()}))
 const cdp=await page.context().newCDPSession(page);await cdp.send('Profiler.enable');await cdp.send('Profiler.startPreciseCoverage',{callCount:true,detailed:true})
 await page.goto('http://127.0.0.1:19538/')
 await page.getByRole('heading',{name:'首页',exact:true}).waitFor()
 check('production_vue_mount',true)
 // Import the same emitted module to inspect official SDK state, without altering bundle/source.
 const rumText=await readFile(root+'/dist/assets/'+rumAsset,'utf8')
 const sdkFile=(rumText.match(/import\("\.\/([^\"]+\.js)"\)/)||[])[1]
 if(!sdkFile)throw Error('Cannot locate emitted dynamic SDK import')
 const initial=await page.evaluate(async({sdkFile,rumAsset})=>{
   const exports=await import('/assets/'+sdkFile);const sdk=Object.values(exports).find(v=>v&&typeof v.getInitConfiguration==='function')
   window.__acceptanceSDK=sdk
   const cfg=sdk.getInitConfiguration();let additionalCalls=0;const original=sdk.init;sdk.init=(...args)=>{additionalCalls++;return original(...args)}
   const rumExports=await import('/assets/'+rumAsset);const start=Object.values(rumExports).find(v=>typeof v==='function');await Promise.all([start(),start(),start()]);
   return {config:cfg,additionalCalls,recording:sdk.isRecording()}
 },{sdkFile,rumAsset})
 check('runtime_configuration_consumed',initial.config.applicationId==='eval_vue_acceptance'&&initial.config.datakitOrigin==='http://127.0.0.1:19539'&&initial.config.service==='vue-rum-acceptance'&&initial.config.version==='1.2.3'&&initial.config.env==='production',initial)
 check('single_init_and_repeated_initialization_guard',initial.additionalCalls===0&&!messages.some(m=>/already.*initializ/i.test(m.text)),initial.additionalCalls)
 check('no_replay_or_trace_configuration',initial.recording===false&&initial.config.sessionReplaySampleRate===0&&!initial.config.allowedTracingOrigins&&!initial.config.site&&!initial.config.clientToken)
 const coverage=await cdp.send('Profiler.takePreciseCoverage');const rumCoverage=coverage.result.find(s=>s.url.endsWith('/'+rumAsset));await writeFile(root+'/evidence/rum-coverage.json',JSON.stringify(rumCoverage,null,2))
 const initOffset=rumText.indexOf('n.init(');const initRanges=rumCoverage.functions.flatMap(f=>f.ranges).filter(r=>r.startOffset<=initOffset&&r.endOffset>initOffset).sort((a,b)=>(a.endOffset-a.startOffset)-(b.endOffset-b.startOffset));check('actual_initializer_block_executes_once',initRanges[0]?.count===1,initRanges)
 await page.getByLabel('本地草稿').fill('CANARY_LOCAL_DRAFT_MUST_NOT_BE_COLLECTED')
 await page.getByRole('button',{name:'请求资源'}).click();await page.getByText('资源请求成功').waitFor()
 await page.getByRole('button',{name:'触发错误'}).click();await page.waitForFunction(()=>document.documentElement.dataset.appErrors==='1')
 check('original_application_error_handler_preserved',true)
 await page.getByRole('link',{name:'详情',exact:true}).click();await page.getByRole('heading',{name:'详情页',exact:true}).waitFor()
 check('spa_navigation_preserved',page.url().endsWith('/details?page=2'))
 await page.waitForTimeout(4000)
 await page.getByRole('link',{name:'首页',exact:true}).click();await page.waitForTimeout(1000)
 // Page lifecycle change flushes the real SDK's buffered payload.
 await page.goto('about:blank');await page.waitForTimeout(700)
 const body=payloads.map(x=>x.body).join('\n')
 check('nonempty_sdk_payload',payloads.length>0&&body.length>0,{count:payloads.length,bytes:body.length})
 check('view_event_and_route_exported',/^view,[^\n]*details/m.test(body))
 check('resource_event_exported',/^resource,[^\n]*sample\.json/m.test(body))
 check('error_event_exported',/^error,[^\n]*acceptance-unhandled-error/m.test(body))
 check('harmless_query_allowed',/page(?:=|%3D|\\=)2/.test(body))
 check('local_draft_not_custom_collected',!body.includes('CANARY_LOCAL_DRAFT_MUST_NOT_BE_COLLECTED'))
 check('application_requests_no_trace_headers',requests.filter(r=>/sample\.json/.test(r.url)).every(r=>!Object.keys(r.headers).some(h=>/^(traceparent|tracestate|x-datadog|x-b3)/.test(h))))
 await page.close()
 for(const mode of ['abort','stall']){
  const p=await browser.newPage(),failureMessages=[];p.on('console',m=>failureMessages.push(m.text()));let release
  const blocked=new Promise(r=>release=r)
  await p.route('**/assets/'+sdkFile,async route=>{if(mode==='stall')await blocked;await route.abort()})
  const start=Date.now();await p.goto('http://127.0.0.1:19538/');await p.getByRole('heading',{name:'首页',exact:true}).waitFor({timeout:5000});const elapsed=Date.now()-start
  await p.getByRole('button',{name:'请求资源'}).click();await p.getByText('资源请求成功').waitFor();await p.getByRole('button',{name:'触发错误'}).click();await p.waitForFunction(()=>document.documentElement.dataset.appErrors==='1')
  check('sdk_'+mode+'_application_survives',elapsed<5000,{elapsed,messages:failureMessages})
  release();await p.close()
 }
 await writeFile(root+'/evidence/browser-console.json',JSON.stringify({messages,errors},null,2))
 await writeFile(root+'/evidence/runtime-config.json',JSON.stringify(initial,null,2))
} catch(error){check('harness_completed',false,String(error.stack||error))}
finally{
 await writeFile(root+'/evidence/payloads.json',JSON.stringify(payloads,null,2));await writeFile(root+'/evidence/requests.json',JSON.stringify(requests,null,2));await writeFile(root+'/evidence/browser-results.json',JSON.stringify({checks,remoteVerification:false},null,2));if(browser)await browser.close();appServer.close();receiver.close()
}
if(checks.some(x=>!x.passed))process.exitCode=1
