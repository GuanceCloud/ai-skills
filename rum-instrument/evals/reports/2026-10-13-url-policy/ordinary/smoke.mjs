import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
const require=createRequire('/var/folders/8x/2_sfyjt11tb3y7_n0m9l53lc0000gn/T/rum-full-eval-fsgyxvww/web/test-tools/package.json');
const {chromium}=require('playwright');
const root=process.cwd(); const requests=[];const captures=[];const results={};
const server=http.createServer(async(req,res)=>{
 requests.push({url:req.url,method:req.method,headers:Object.fromEntries(Object.entries(req.headers).filter(([name])=>name!=='cookie'&&name!=='authorization'))});
 if(req.url.startsWith('/api/catalog')) {res.setHeader('Content-Type','application/json');res.end('{"items":["catalog-item"]}');return;}
 let pathname=new URL(req.url,'http://localhost').pathname;
 const file=path.join(root,'dist',pathname==='/'?'index.html':pathname);
 try{const content=await fs.readFile(file);res.setHeader('Content-Type',file.endsWith('.html')?'text/html':'text/javascript');res.end(content);}catch{res.statusCode=404;res.end('Not Found');}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const origin=`http://127.0.0.1:${server.address().port}`;
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true,args:['--no-sandbox']});
try{
 const context=await browser.newContext();
 await context.route('http://127.0.0.1:19529/**',async route=>{const r=route.request();captures.push({url:r.url(),method:r.method(),body:r.postData()||''});await route.fulfill({status:200,headers:{'access-control-allow-origin':'*'},body:'{}'});});
 const page=await context.newPage();const consoleMessages=[];page.on('console',m=>consoleMessages.push({type:m.type(),text:m.text()}));
 await page.addInitScript(()=>{window.previousErrorCalls=0;window.onerror=()=>{window.previousErrorCalls++;return false;};});
 const cdp=await context.newCDPSession(page);await cdp.send('Profiler.enable');await cdp.send('Profiler.startPreciseCoverage',{callCount:true,detailed:true});
 await page.goto(origin+'/?page=1&sort=price');
 await page.waitForSelector('#next');await page.waitForTimeout(1000);
 const before=await page.locator('#page').innerText();
 await Promise.all([page.waitForResponse(r=>r.url().includes('/api/catalog?page=2&sort=price')),page.click('#next')]);
 results.navigation={before,after:await page.locator('#page').innerText(),url:page.url()};
 await page.evaluate(()=>{setTimeout(()=>{throw new Error('ordinary-unhandled-smoke');},0);console.error('ordinary-console-error-smoke');});
 await page.waitForTimeout(1500);
 results.previousErrorCalls=await page.evaluate(()=>window.previousErrorCalls);
 await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pagehide')));
 await page.waitForTimeout(1500);
 const coverage=await cdp.send('Profiler.takePreciseCoverage');
 const sdkScript=coverage.result.find(s=>/\/src\/rum-[^/]+\.js/.test(s.url));
 await fs.writeFile('evidence/coverage.json',JSON.stringify(coverage,null,2));
 const sdkSource=sdkScript?await(await fetch(sdkScript.url)).text():'';
 results.initCoverage=sdkScript?.functions.filter(f=>sdkSource.slice(f.ranges[0].startOffset,f.ranges[0].endOffset).startsWith('function(initConfiguration) {\n      strategy.init')).map(f=>({name:f.functionName,count:f.ranges[0].count}));
 results.runtimeConfig=await page.evaluate(()=>window.CATALOG_RUM);
 results.consoleMessages=consoleMessages;
 const failed=await context.newPage();await failed.route('**/rum-*.js',r=>r.abort());
 await failed.goto(origin+'/?page=1&sort=price');await failed.click('#next');await failed.waitForTimeout(500);
 results.sdkLoadFailure={page:await failed.locator('#page').innerText(),url:failed.url()};
 await failed.close();await page.close();
 await fs.writeFile('evidence/payloads.json',JSON.stringify(captures,null,2));
 const text=captures.map(c=>c.body).join('\n');
 results.requests=requests.filter(r=>r.url.startsWith('/api/'));
 results.payload={requests:captures.length,bytes:Buffer.byteLength(text),view:/view_url/.test(text),resource:/resource_url/.test(text),error:/ordinary-unhandled-smoke/.test(text),handledConsoleError:/ordinary-console-error-smoke/.test(text),ordinaryQuery:/page/.test(text)&&/sort/.test(text)};
 results.checks={nonempty:results.payload.bytes>0,view:results.payload.view,resource:results.payload.resource,error:results.payload.error,handled:results.payload.handledConsoleError,oneInit:results.initCoverage?.length===1&&results.initCoverage[0].count===1,navigation:results.navigation.after==='2'&&results.navigation.url.endsWith('/?page=2&sort=price'),resourceRequest:results.requests.some(r=>r.url==='/api/catalog?page=2&sort=price'),previousErrorHandler:results.previousErrorCalls===1,loadFailureDoesNotBlock:results.sdkLoadFailure.page==='2',correctReceiver:captures.length>0&&captures.every(c=>c.url.startsWith('http://127.0.0.1:19529/')),correctApplication:text.includes('eval_catalog'),correctService:text.includes('rum-catalog-fixture'),noTraceHeaders:results.requests.every(r=>!Object.keys(r.headers).some(h=>/traceparent|x-datadog|x-b3/.test(h))),noReplay:captures.every(c=>!c.url.includes('replay'))};
 results.exit=Object.values(results.checks).every(Boolean)?0:1;
 await fs.writeFile('evidence/smoke-results.json',JSON.stringify(results,null,2));console.log(JSON.stringify(results,null,2));process.exitCode=results.exit;
}finally{await browser.close();await new Promise(r=>server.close(r));}
