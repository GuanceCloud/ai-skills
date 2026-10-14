const fs=require('fs'),auto=require('./tooling/node_modules/miniprogram-automator');
const out=__dirname+'/logs/authorized-appid/'; const results={};let app;
const timer=setTimeout(()=>{results.timeout=true;fs.writeFileSync(out+'baseline-runtime-config.json',JSON.stringify(results,null,2));process.exit(124)},45000);
(async()=>{app=await auto.connect({wsEndpoint:'ws://127.0.0.1:19534'});
app.on('exception',e=>fs.appendFileSync(out+'diagnostic-exceptions.jsonl',JSON.stringify(e)+'\n'));
for(const [name,fn] of [
 ['system',()=>app.systemInfo()],
 ['runtime',()=>app.evaluate(()=>({app:typeof getApp==='function',launchCount:typeof getApp==='function'&&getApp()&&getApp().globalData.launchCount,pages:typeof getCurrentPages==='function'?getCurrentPages().map(p=>p.route):[]}))],
 ['config',()=>app.evaluate(()=>({pages:typeof __wxConfig==='object'?__wxConfig.pages:null,entry:typeof __wxConfig==='object'?__wxConfig.entryPagePath:null,code:typeof __wxAppCode__==='object'?Object.keys(__wxAppCode__):[],pageFunction:typeof Page}))],
 ['relaunch',async()=>{const p=await app.reLaunch('/pages/index/index');return {path:p&&p.path,data:p&&await p.data()}}]
]){try{results[name]={ok:true,value:await fn()}}catch(e){results[name]={ok:false,error:e.message}}fs.writeFileSync(out+'baseline-runtime-config.json',JSON.stringify(results,null,2));console.log(name,JSON.stringify(results[name]));}
})().catch(e=>console.error(e)).finally(()=>{clearTimeout(timer);if(app)app.disconnect()});
