const assert = require('assert/strict')
const requests = [], events = [], store = new Map()
global.wx = {
  getAccountInfoSync: () => ({miniProgram:{envVersion:'trial',version:'1.2.3'}}),
  getSystemInfoSync: () => ({system:'iOS 17',version:'8.0',SDKVersion:'3.0',platform:'ios',model:'simulated',brand:'simulated'}),
  getNetworkType: ({success}) => success({networkType:'wifi'}),
  onNetworkStatusChange() {},
  getLaunchOptionsSync: () => ({path:'pages/index/index',query:{secret:'CANARY_QUERY'}}),
  getStorageSync: key => store.get(key),
  setStorageSync: (key,value) => store.set(key,value),
  removeStorageSync: key => store.delete(key),
  request(options) { requests.push(options); if (options.success) options.success({statusCode:200,data:{},profile:{}}); if(options.complete) options.complete({statusCode:200}); return {abort(){},onHeadersReceived(){}} },
  onError() {}, onUnhandledRejection() {}, onAppHide() {}, onAppShow() {},
}
let app, page
global.App = value => {app=value; events.push('App')}
global.Page = value => {page=value}
global.Component = () => {}
global.getCurrentPages = () => page ? [page] : []
const {datafluxRum} = require('./project/node_modules/@cloudcare/rum-miniapp')
const original = datafluxRum.init
let initCount = 0
datafluxRum.init = function(config) {initCount++;events.push('init');return original.call(this,config)}
const warnings=[]
console.warn = (...args) => warnings.push(args.join(' '))
require('./project/app')
require('./project/rum').initializeRum()
assert.equal(initCount,1)
assert.deepEqual(events,['init','App'])
assert.equal(warnings.length,0, warnings.join('\n'))
assert.equal(typeof app.onLaunch,'function')
app.onLaunch.call(app,{path:'pages/index/index',query:{secret:'CANARY_QUERY'}})
app.onShow.call(app,{path:'pages/index/index',query:{secret:'CANARY_QUERY'}})
Page({route:'pages/index/index'})
page.onLoad.call(page,{secret:'CANARY_QUERY'})
page.onShow.call(page)
page.onReady.call(page)
wx.request({url:'https://unlisted.example/api?secret=CANARY_QUERY',method:'POST',header:{authorization:'CANARY_AUTH'},data:{value:'CANARY_BODY'}})
datafluxRum.addError(new Error('synthetic smoke error'))
datafluxRum.addAction('smoke_action')
setTimeout(() => {
  try {
    page.onHide.call(page)
    app.onHide.call(app)
    const telemetry = requests.filter(r=>r.url.startsWith('http://127.0.0.1:19529'))
    assert.ok(telemetry.length>0,'SDK did not produce local mock telemetry')
    const payload = telemetry.map(r=>typeof r.data==='string'?r.data:JSON.stringify(r.data)).join('\n')
    for (const canary of ['CANARY_QUERY','CANARY_AUTH','CANARY_BODY']) assert.equal(payload.includes(canary),false,canary)
    const business = requests.find(r=>r.url.startsWith('https://unlisted.example'))
    assert.deepEqual(business.header,{authorization:'CANARY_AUTH'})
    assert.equal(business.data.value,'CANARY_BODY')
    assert.ok(business.url.includes('CANARY_QUERY'))
    require('fs').writeFileSync('logs/real-sdk-payload.txt',payload)
    console.log(JSON.stringify({result:'PASS',realSdkVersion:'2.2.20',runtime:'mock wx/App/Page in Node',initCount,telemetryRequests:telemetry.length,privacyCanariesAbsent:true,businessRequestUnchanged:true,remoteNetwork:false}))
    process.exit(0)
  } catch(error) { console.error(error);process.exit(1) }
}, 1500)
