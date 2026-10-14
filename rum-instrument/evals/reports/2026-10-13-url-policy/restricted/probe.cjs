const fs=require('fs'),path=require('path'),http=require('http');
const {chromium}=require('/var/folders/8x/2_sfyjt11tb3y7_n0m9l53lc0000gn/T/rum-full-eval-fsgyxvww/web/test-tools/node_modules/playwright');
const esbuild=require('/var/folders/8x/2_sfyjt11tb3y7_n0m9l53lc0000gn/T/rum-full-eval-fsgyxvww/web/test-tools/node_modules/esbuild');
const root=__dirname;const out=path.join(root,'evidence');fs.mkdirSync(out,{recursive:true});
const requests=[];let current='';const api=[];
const collector=http.createServer(async(req,res)=>{let chunks=[];for await(const c of req) chunks.push(c);const body=Buffer.concat(chunks);requests.push({run:current,url:req.url,method:req.method,headers:req.headers,body:body.toString('utf8'),base64:body.toString('base64')});res.writeHead(200,{'access-control-allow-origin':'*','access-control-allow-methods':'GET,POST,OPTIONS','access-control-allow-headers':'*','content-type':'application/json'});res.end('{}');});
const app=http.createServer((req,res)=>{if(req.url.startsWith('/api/')){api.push({run:current,url:req.url});res.writeHead(200,{'content-type':'application/json'});return res.end('{"ok":true}');}if(req.url==='/probe.js'){res.writeHead(200,{'content-type':'text/javascript'});return res.end(fs.readFileSync(path.join(out,'bundle.js')));}if(req.url==='/src/main.js'){res.writeHead(200,{'content-type':'text/javascript'});return res.end(fs.readFileSync(path.join(root,'A/src/main.js')));}if(req.url==='/blank'){res.writeHead(200,{'content-type':'text/html'});return res.end('<html><body>done</body></html>');}res.writeHead(200,{'content-type':'text/html'});res.end(fs.readFileSync(path.join(root,'A/index.html'),'utf8').replace('<script type="module" src="/src/main.js">',`<script>window.__probeMode=${JSON.stringify(current.split('-')[1])}</script><script src="/probe.js"></script><script type="module" src="/src/main.js">`));});
(async()=>{
 await esbuild.build({entryPoints:[path.join(root,'probe-browser.js')],bundle:true,outfile:path.join(out,'bundle.js'),platform:'browser',format:'iife'});
 await new Promise((r,j)=>{collector.once('error',j);collector.listen(19529,'127.0.0.1',r)});
 await new Promise(r=>app.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+app.address().port;
 const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true,args:['--no-sandbox']});const summaries=[];
 try{for(const [name,query] of [['A-baseline','?policy_marker=A_PROHIBITED_QUERY_SYNTHETIC'],['A-hook','?policy_marker=A_PROHIBITED_QUERY_SYNTHETIC'],['A-reject','?policy_marker=A_PROHIBITED_QUERY_SYNTHETIC'],['B-hook','?access_token=B_AUTH_TOKEN_SYNTHETIC_NOT_SECRET']]){
 current=name;const context=await browser.newContext();const page=await context.newPage();const consoleMessages=[];page.on('console',m=>consoleMessages.push({type:m.type(),text:m.text()}));
 await page.goto(origin+(name.startsWith('B')?'/auth/callback':'/')+query);await page.waitForTimeout(700);
 await page.evaluate(()=>window.__rum.addError(new Error('Synthetic representative error')));await page.click('#next');await page.waitForTimeout(1800);
 const behavior=await page.evaluate(()=>({url:location.href,page:document.querySelector('#page').textContent,initCount:window.__initCount,hooks:window.__hooks}));
 await page.goto(origin+'/blank');await page.waitForTimeout(700);await context.close();
 const runRequests=requests.filter(r=>r.run===name);fs.writeFileSync(path.join(out,name+'-requests.json'),JSON.stringify(runRequests,null,2));fs.writeFileSync(path.join(out,name+'-browser.json'),JSON.stringify({behavior,consoleMessages,api:api.filter(r=>r.run===name)},null,2));
 const events=runRequests.filter(r=>r.method==='POST').flatMap(r=>{try{return JSON.parse(r.body)}catch{return []}});fs.writeFileSync(path.join(out,name+'-events.json'),JSON.stringify(events,null,2));summaries.push({name,requestCount:runRequests.length,events:events.length,eventTypes:[...new Set(events.map(e=>e.measurement||e.type))],behavior:{...behavior,hooks:undefined},containsProhibitedCanary:JSON.stringify(events).includes(name.startsWith('A')?'A_PROHIBITED_QUERY_SYNTHETIC':'B_AUTH_TOKEN_SYNTHETIC_NOT_SECRET'),api:api.filter(r=>r.run===name)});
 }}finally{await browser.close();collector.close();app.close();}
 fs.writeFileSync(path.join(out,'summary.json'),JSON.stringify(summaries,null,2));console.log(JSON.stringify(summaries,null,2));
})().catch(e=>{console.error(e);collector.close();app.close();process.exitCode=1});
