const fs = require('fs'), http = require('http'), assert = require('assert');
const { chromium } = require('./test-tools/node_modules/playwright');
const path = require('path');
const sdkFile = fs.readdirSync('build').find(x => x.startsWith('esm-'));
const captures=[], browserErrors=[], appRequests=[];
const server=http.createServer((req,res)=>{
 if(req.url.startsWith('/ping')){let body='';req.on('data',d=>body+=d);req.on('end',()=>{appRequests.push({url:req.url,body,headers:req.headers});res.setHeader('Content-Type','application/json');res.end('{}')});return;}
 let file=req.url.split('?')[0].slice(1);
 if(!file || !file.includes('.')){res.setHeader('Content-Type','text/html');res.end(fs.readFileSync('project/index.html','utf8').replace('/src/main.ts','/main.js'));return;}
 if(file==='rum-config.js'){res.setHeader('Content-Type','text/javascript');res.end(fs.readFileSync('project/rum-config.js','utf8')+'\nwindow.__RUM_CONFIG__.env="eval-local"; window.__RUM_CONFIG__.version="eval-release";');return;}
 try {res.setHeader('Content-Type','text/javascript');res.end(fs.readFileSync(path.join('build',file)));}catch{res.statusCode=404;res.end();}
});
(async()=>{
 await new Promise(r=>server.listen(19631,'127.0.0.1',r));
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--no-first-run','--disable-background-networking']});
 try{
 const page=await browser.newPage();
 page.on('pageerror',e=>browserErrors.push(e.message));
 await page.route('**/*',async route=>{
  const u=new URL(route.request().url());
  if(u.origin==='http://127.0.0.1:19529'){captures.push({url:u.pathname,body:route.request().postData()||''});await route.fulfill({status:200,contentType:'application/json',body:'{}',headers:{'Access-Control-Allow-Origin':'*'}});}
  else if(u.origin==='http://127.0.0.1:19631')await route.continue(); else await route.abort();
 });
 await page.route('**/main.js', route=>route.fulfill({contentType:'text/javascript',body:`import { datafluxRum } from '/${sdkFile}'; window.__sdk=datafluxRum; window.__initCalls=0; const original=datafluxRum.init; datafluxRum.init=(config)=>{window.__initCalls++;return original(config)}; const {startRum}=await import('/rum.js'); await Promise.all([startRum(),startRum(),startRum()]); window.__ready=true;`}));
 await page.goto('http://127.0.0.1:19631/');
 await page.waitForFunction(()=>window.__ready===true);
 const initial=await page.evaluate(()=>({calls:window.__initCalls,config:window.__sdk.getInitConfiguration(),recording:window.__sdk.isRecording()}));
 assert.equal(initial.calls,1); assert.equal(initial.config.applicationId,'eval_web'); assert.equal(initial.config.datakitOrigin,'http://127.0.0.1:19529'); assert.equal(initial.config.env,'eval-local');assert.equal(initial.config.version,'eval-release');assert.equal(initial.recording,false);assert(!('site' in initial.config));assert(!('clientToken' in initial.config));
 await page.evaluate(async()=>{
  document.body.insertAdjacentHTML('beforeend','<input id="canary" value="CANARY_INPUT">');
  document.cookie='eval_cookie=CANARY_COOKIE';
  history.pushState({},'', '/route?value=CANARY_QUERY#CANARY_HASH');
  await fetch('/ping?value=CANARY_RESOURCE_QUERY',{method:'POST',headers:{Authorization:'CANARY_AUTH','Content-Type':'application/json'},body:JSON.stringify({private:'CANARY_BODY'})});
  window.__sdk.addError(new Error('synthetic handled error'));
  setTimeout(()=>{throw new Error('synthetic unhandled error')},0);
 });
 await page.waitForTimeout(3200);
 await page.evaluate(()=>{window.dispatchEvent(new PageTransitionEvent('pagehide',{persisted:false}));});
 await page.waitForTimeout(1000);
 const raw=JSON.stringify(captures); const privacy=Object.fromEntries(['CANARY_INPUT','CANARY_COOKIE','CANARY_AUTH','CANARY_BODY','CANARY_QUERY','CANARY_HASH','CANARY_RESOURCE_QUERY'].map(x=>[x,!raw.includes(x)]));
 assert(captures.length>0,'Real SDK should attempt local telemetry');
 assert(appRequests[0].body.includes('CANARY_BODY'));assert.equal(appRequests[0].headers.authorization,'CANARY_AUTH');
 const failure=await browser.newPage(); const warnings=[];failure.on('console',m=>warnings.push(m.text()));
 await failure.route('**/*',async route=>{const u=new URL(route.request().url());if(u.origin!=='http://127.0.0.1:19631')return route.abort();if(u.pathname.includes(sdkFile))return route.abort();return route.continue();});
 await failure.goto('http://127.0.0.1:19631/');
 await failure.waitForFunction(()=>!window.__RUM_START__);
 const fail=await failure.evaluate(async()=>({result:await (await import('/rum.js')).startRum(),dom:!!document.querySelector('#app')}));assert.equal(fail.result,false);assert.equal(fail.dom,true);
 const out={sdk:'3.3.5',real_sdk:true,mock_receiver:true,initial,browserErrors,privacy,request_behavior_preserved:true,capture_count:captures.length,capture_endpoints:[...new Set(captures.map(x=>x.url))],failure:fail,warnings};
 fs.writeFileSync('logs/browser-smoke.json',JSON.stringify(out,null,2));fs.writeFileSync('logs/local-payloads.json',JSON.stringify(captures,null,2));console.log(JSON.stringify(out,null,2));
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1});
