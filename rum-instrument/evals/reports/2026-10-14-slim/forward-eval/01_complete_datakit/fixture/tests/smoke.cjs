const fs = require('fs');
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
