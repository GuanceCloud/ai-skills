const fs=require('fs'), assert=require('assert/strict');
const automator=require('./tooling/node_modules/miniprogram-automator');
const out=__dirname+'/logs/authorized-appid/';
const timer=setTimeout(()=>{fs.writeFileSync(out+'baseline-timeout.json',JSON.stringify({status:'timeout',seconds:40}));process.exit(124)},40000);
(async()=>{const app=await automator.connect({wsEndpoint:'ws://127.0.0.1:19534'});try{
app.on('exception',e=>fs.appendFileSync(out+'baseline-exceptions.jsonl',JSON.stringify(e)+'\n'));
const page=await app.currentPage();assert.ok(page,'current page exists');assert.equal(page.path,'pages/index/index');
const before=await page.data();assert.equal(before.status,'已启动');
await (await page.$('#action')).tap();const after=await page.data();assert.equal(after.actions,before.actions+1);
const runtime=await app.evaluate(()=>({launchCount:getApp().globalData.launchCount}));assert.equal(runtime.launchCount,1);
const system=await app.systemInfo();
await app.screenshot({path:out+'baseline.png'});
const result={status:'passed',checks:4,page:page.path,runtime,system:{SDKVersion:system.SDKVersion,platform:system.platform,version:system.version}};
fs.writeFileSync(out+'baseline-result.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{app.disconnect();clearTimeout(timer)}})().catch(e=>{clearTimeout(timer);fs.writeFileSync(out+'baseline-result.json',JSON.stringify({status:'failed',message:e.message},null,2));console.error(e);process.exitCode=1});
