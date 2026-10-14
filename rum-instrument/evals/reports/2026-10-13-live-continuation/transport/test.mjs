import {createServer} from 'node:http'
import {readFile,writeFile} from 'node:fs/promises'
import {chromium} from '/var/folders/8x/2_sfyjt11tb3y7_n0m9l53lc0000gn/T/rum-full-eval-fsgyxvww/web/test-tools/node_modules/playwright/index.mjs'
const root=import.meta.dirname,serverEvents=[],cases=[]
const app=createServer(async(req,res)=>{res.setHeader('Content-Type',req.url==='/transport.js'?'text/javascript':'text/html');res.end(req.url==='/transport.js'?await readFile(root+'/transport.js'):'<!doctype html><script src="/transport.js"></script>')})
const receiver=createServer(async(req,res)=>{
 const path=req.url.split('?')[0];const chunks=[];for await(const c of req)chunks.push(c)
 serverEvents.push({path,method:req.method,receivedBytes:Buffer.concat(chunks).length})
 res.setHeader('Access-Control-Allow-Origin','http://127.0.0.1:19641');res.setHeader('Access-Control-Allow-Headers','x-client-timestamp');res.setHeader('Access-Control-Allow-Methods','POST,OPTIONS')
 if(req.method==='OPTIONS'){res.end();return}
 if(path==='/empty-length'){res.setHeader('Content-Length','0');res.end();return}
 if(path==='/empty'){res.end();return}
 if(path==='/json'){res.setHeader('Content-Type','application/json');res.end('{"ok":true}');return}
 if(path==='/json-no-type'){res.end('{"ok":true}');return}
 if(path==='/delayed-body'){res.flushHeaders();setTimeout(()=>res.end('{"ok":true}'),200);return}
 if(path==='/disconnect-after-headers'){res.flushHeaders();setTimeout(()=>res.destroy(),200);return}
 res.end('ok')
})
await Promise.all([new Promise(r=>app.listen(19641,'127.0.0.1',r)),new Promise(r=>receiver.listen(19642,'127.0.0.1',r))])
let browser
try {
 browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true})
 for(const mode of ['sdk','native'])for(const name of ['empty','empty-length','json','json-no-type','delayed-body','disconnect-after-headers']){
  const page=await browser.newPage(),events=[],bodyReads=[]
  await page.addInitScript(()=>{window.cancelCalls=[];const a=AbortController.prototype.abort;AbortController.prototype.abort=function(...x){window.cancelCalls.push({kind:'abort',stack:new Error().stack});return a.apply(this,x)};const c=ReadableStreamDefaultReader.prototype.cancel;ReadableStreamDefaultReader.prototype.cancel=function(...x){window.cancelCalls.push({kind:'reader.cancel',stack:new Error().stack});return c.apply(this,x)}})
  page.on('response',response=>{if(response.url().includes(':19642/')){events.push({event:'response',status:response.status()});bodyReads.push(response.text().then(text=>({readable:true,length:text.length}),error=>({readable:false,error:error.message})))}})
  page.on('requestfinished',req=>{if(req.url().includes(':19642/'))events.push({event:'finished'})})
  page.on('requestfailed',req=>{if(req.url().includes(':19642/'))events.push({event:'failed',error:req.failure()?.errorText})})
  await page.goto('http://127.0.0.1:19641/')
  const result=await page.evaluate(([mode,name])=>window.runTransport(mode,name),[mode,name]);const cancellations=await page.evaluate(()=>window.cancelCalls)
  cases.push({...result,eventsFromPlaywright:events,bodyReads:await Promise.all(bodyReads),cancellations});await page.close()
 }
 await writeFile(root+'/results.json',JSON.stringify({cases,serverEvents},null,2));console.log(JSON.stringify(cases.map(c=>({mode:c.mode,name:c.name,response:c.events,network:c.eventsFromPlaywright,bodyReadable:c.bodyReads.map(r=>r.readable),cancels:c.cancellations.length,state:c.state})),null,2))
}finally{if(browser)await browser.close();app.close();receiver.close()}
