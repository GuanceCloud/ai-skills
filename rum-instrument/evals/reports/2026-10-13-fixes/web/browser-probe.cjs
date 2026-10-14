const fs = require('fs');
const http = require('http');
const { chromium } = require('/var/folders/8x/2_sfyjt11tb3y7_n0m9l53lc0000gn/T/rum-full-eval-fsgyxvww/web/test-tools/node_modules/playwright');
const base = __dirname, origin = 'http://127.0.0.1:19645';
const captures = [], seen = [], requests = [];
const sdk = '/private/tmp/rum-sdk-types-retest/3.3.21/node_modules/@cloudcare/browser-rum/bundle/dataflux-rum.js';
const server = http.createServer((req,res) => {
 const url = new URL(req.url,origin);requests.push(url.pathname+url.search);
 if(url.pathname==='/api/data'){res.setHeader('Content-Type','application/json');return res.end('{"ok":true}');}
 if(url.pathname==='/sdk.js'){res.setHeader('Content-Type','text/javascript');return res.end(fs.readFileSync(sdk));}
 if(url.pathname==='/src/main.js'){res.setHeader('Content-Type','text/javascript');return res.end(fs.readFileSync(base+'/project/src/main.js'));}
 res.setHeader('Content-Type','text/html');res.end(fs.readFileSync(base+'/project/index.html'));
});
(async()=>{
 await new Promise(r=>server.listen(19645,'127.0.0.1',r));
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--disable-background-networking']});
 try{
  const page=await browser.newPage();
  await page.exposeFunction('recordType',type=>seen.push(type));
  await page.route('**/*',route=>{
   const url=new URL(route.request().url());
   if(url.origin==='http://127.0.0.1:19529'){captures.push({path:url.pathname,body:route.request().postData()||''});return route.fulfill({status:200,contentType:'application/json',body:'{}'});}
   if(url.origin===origin)return route.continue();
   return route.abort();
  });
  await page.goto(origin+'/?q=CANARY_INITIAL_QUERY#CANARY_INITIAL_HASH');
  await page.waitForFunction(()=>window.appReady);
  await page.click('#increment');
  const behaviorBefore=await page.textContent('#counter');
  // SDK compatibility probe only: no initialization added to maintained application.
  await page.addScriptTag({url:origin+'/sdk.js'});
  await page.evaluate(()=>{
   window.__probeInitCalls=0;
   window.__probeInitCalls++;
   window.DATAFLUX_RUM.init({applicationId:'eval_web_fixes',datakitOrigin:'http://127.0.0.1:19529',service:'eval-web-fixes',version:'1.0.0',env:'isolated-eval',sessionReplaySampleRate:0,trackUserInteractions:true,beforeSend:event=>{
    window.recordType(event.type);
    for(const key of ['view','resource'])if(event[key]){
     for(const field of ['url','referrer'])if(event[key][field]){try{const u=new URL(event[key][field]);u.search='';u.hash='';u.username='';u.password='';event[key][field]=u.href;}catch{}}
     delete event[key].url_query;
     delete event[key].url_hash;
    }
    return true;
   }});
  });
  await page.evaluate(async()=>{
   await fetch('/api/data?q=CANARY_RESOURCE_QUERY');
   history.pushState({},'', '/next?q=CANARY_HISTORY_QUERY#CANARY_HISTORY_HASH');
   window.DATAFLUX_RUM.addError(new Error('synthetic compatibility check'));
  });
  await page.click('#increment');
  await page.waitForTimeout(3500);
  await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pagehide',{persisted:false})));
  await page.waitForTimeout(800);
  const state=await page.evaluate(()=>({calls:window.__probeInitCalls,configuration:window.DATAFLUX_RUM.getInitConfiguration(),replay:window.DATAFLUX_RUM.isRecording(),counter:document.querySelector('#counter').textContent,url:location.href}));
  const raw=JSON.stringify(captures);
  const privacy=Object.fromEntries(['CANARY_INITIAL_QUERY','CANARY_INITIAL_HASH','CANARY_RESOURCE_QUERY','CANARY_HISTORY_QUERY','CANARY_HISTORY_HASH'].map(c=>[c,!raw.includes(c)]));
  const result={real_sdk:'3.3.21',real_browser:true,receiver:'Playwright mocked local captures, no remote ingestion',application_initialization_enabled:false,probe_initialization_only:true,captured_requests:captures.length,event_types_seen:[...new Set(seen)],serialized_event_types:[...new Set(captures.flatMap(c=>c.body.split('\n').map(x=>x.split(',')[0])))],privacy,privacy_passed:Object.values(privacy).every(Boolean),behavior_preserved:behaviorBefore==='1'&&state.counter==='2'&&state.url.includes('CANARY_HISTORY_QUERY')&&requests.some(x=>x.includes('CANARY_RESOURCE_QUERY')),state};
  fs.writeFileSync(base+'/logs/browser-probe-result.json',JSON.stringify(result,null,2)+'\n');fs.writeFileSync(base+'/logs/local-synthetic-payloads.json',JSON.stringify(captures,null,2)+'\n');
  console.log(JSON.stringify(result,null,2));
  if(!result.privacy_passed||!result.behavior_preserved||captures.length===0)process.exitCode=1;
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
