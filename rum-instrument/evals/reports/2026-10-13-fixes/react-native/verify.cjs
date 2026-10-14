'use strict';
process.exitCode = 1;
const assert = require('node:assert/strict');
const fs = require('node:fs');
const Module = require('node:module');
const platform = process.argv[2] || 'android';
const mode = process.argv[3] || 'success';
const originalThrows = process.argv[4] === 'original-throws';
const calls = [], originals = [], reports = [], warnings = [], unhandled = [];
let handlerSets = 0, bridgeAvailable = mode !== 'missing-retry', configAttempts = 0;
let active, thrown = new Error('original handler throws'), returnValue = { app: 'return-value' };
function original() { originals.push({ receiver: this, args: [...arguments] }); if(originalThrows) throw thrown; return returnValue; }
active = original;
global.ErrorUtils = { getGlobalHandler: () => active, setGlobalHandler: fn => { handlerSets++; active = fn; } };
const originalConsoleError = console.error;
const oldWarn = console.warn;
console.warn = (...args) => warnings.push(args.join(' '));
process.on('unhandledRejection', x => unhandled.push(String(x)));
const nativeMobile = { sdkConfig(config) { calls.push({ method:'sdkConfig', config }); return Promise.resolve(); } };
const nativeRum = {
 setConfig(config) { configAttempts++;calls.push({method:'setConfig',config});if(mode==='config-retry' && configAttempts===1)return Promise.reject(new Error('config failed'));return Promise.resolve(); },
 addError(...args) { reports.push(args);if(mode==='reject')return Promise.reject(new Error('telemetry rejected'));if(mode==='throw')throw new Error('telemetry throws');if(mode==='never')return new Promise(()=>{});return Promise.resolve(); },
 addErrorWithType() { throw new Error('Unexpected console error capture'); }
};
const natives = { FTMobileReactNative:nativeMobile, FTReactNativeRUM:nativeRum, FTReactNativeLog:{}, FTReactNativeTrace:{} };
const originalLoad = Module._load;
Module._load = function(request,parent,isMain) {
 if(request==='react-native')return { Platform:{OS:platform}, NativeModules:bridgeAvailable?natives:{}, NativeEventEmitter:class{}, TurboModuleRegistry:{ get:name=>bridgeAvailable?natives[name]:null } };
 return originalLoad.apply(this,arguments);
};
const tick = () => new Promise(resolve=>setImmediate(resolve));
(async()=>{
 const app = require('./project/index.js');
 let startRum = require('./project/rum.js').startRum;
 const first = await Promise.all([app.rumReady,startRum(),startRum()]);
 if(mode.endsWith('retry')) {
  assert.deepEqual(first,[false,false,false]);assert.equal(active,original,'failed setup must leave app handler unchanged');assert.equal(console.error,originalConsoleError);
  if(mode==='missing-retry') {
   assert.equal(calls.length,0);assert.equal(await startRum(),false,'missing bridge repeated attempt stays non-fatal');
   bridgeAvailable=true;assert.equal(await startRum(),false,'SDK retains null bridge until module/process reload');assert.equal(active,original);
   for(const key of Object.keys(require.cache))if(key.includes('@cloudcare/react-native-mobile/'))delete require.cache[key];
  }
  assert.equal(await startRum(),true,'retry must recover');
 } else assert.deepEqual(first,[true,true,true]);
 const installed = active;
 const setsBeforeRepeat = handlerSets;
 delete require.cache[require.resolve('./project/rum.js')];startRum=require('./project/rum.js').startRum;
 assert.equal(await startRum(),true);assert.equal(active,installed);assert.equal(handlerSets,setsBeforeRepeat,'repeated startup must not re-wrap');
 assert.equal(calls.filter(x=>x.method==='sdkConfig').length,1);
 assert.equal(calls.filter(x=>x.method==='setConfig').length,mode==='config-retry'?2:1);
 const base=calls.find(x=>x.method==='sdkConfig').config, rum=calls.filter(x=>x.method==='setConfig').at(-1).config;
 assert.equal(base.datakitUrl,'http://127.0.0.1:19529');assert(!('datawayUrl' in base));assert(!('clientToken' in base));
 assert.equal(rum.androidAppId,'eval_rn_android');assert.equal(rum.iOSAppId,'eval_rn_ios');
 assert.equal(rum.enableTrackNativeCrash,false);assert.equal(rum.enableTraceWebView,false);assert.equal(rum.enableNativeUserView,false);
 const error=new TypeError('SECRET_CANARY message');
 error.stack='TypeError: SECRET_CANARY message\n    at render (https://example.invalid/private/SECRET_CANARY/App.js?SECRET_CANARY:42:7)\n    at launch (/private/SECRET_CANARY/index.js:12:9)';
 const receiver={tag:'original receiver'}, extra={tag:'extra argument'};
 if(originalThrows)assert.throws(()=>active.call(receiver,error,true,extra),x=>x===thrown,'original thrown object must propagate');
 else assert.equal(active.call(receiver,error,true,extra),returnValue,'return identity must be preserved');
 assert.equal(originals.length,1,'original handler must run synchronously exactly once');
 assert.equal(originals[0].receiver,receiver);assert.deepEqual(originals[0].args,[error,true,extra]);
 assert.equal(reports.length,0,'report must be independent of original handler execution');
 await tick();await tick();
 assert.equal(originals.length,1);assert.equal(reports.length,1,'one public SDK addError call reaches bridge');
 assert(!JSON.stringify(reports).includes('SECRET_CANARY'),'canary must not enter native payload');
 assert.equal(console.error,originalConsoleError,'console.error identity unchanged');
 assert.equal(rum.enableAutoTrackError,false);
 assert.equal(unhandled.length,0,'telemetry errors handled');
 // Real SDK remains in callback; adapter cleanup and module reload are application-owned.
 const {installRumErrorHandler}=require('./project/rum-error-handler.cjs');
 const dispose=installRumErrorHandler(ErrorUtils,()=>{throw new Error('Duplicate callback should not be installed')});
 assert.equal(active,installed);
 delete require.cache[require.resolve('./project/rum-error-handler.cjs')];
 assert.equal(require('./project/rum-error-handler.cjs').installRumErrorHandler(ErrorUtils,()=>{}),dispose);
 const later=function later(){};ErrorUtils.setGlobalHandler(later);dispose();assert.equal(active,later,'cleanup must preserve later owner');
 ErrorUtils.setGlobalHandler(installed);dispose();assert.equal(active,original,'owned cleanup restores original');dispose();assert.equal(active,original);
 const result={pass:true,platform,mode,originalThrows,sdkVersion:require('./project/node_modules/@cloudcare/react-native-mobile/package.json').version,realSdkJavaScript:true,bridgeDouble:true,nativePlatformSelectionExecuted:false,missingBridgeRecovery:mode==='missing-retry'?'SDK module reload after bridge restored; same-process retry alone stays false':null,first,originalHandlerCalls:originals.length,reports,calls,warnings,unhandled};
 fs.writeFileSync(`logs/${platform}-${mode}-${originalThrows?'throws':'returns'}.json`,JSON.stringify(result,null,2));
 console.log(JSON.stringify({pass:true,platform,mode,originalThrows,originalHandlerCalls:originals.length,reportCalls:reports.length}));
 process.exitCode=0;
})().catch(e=>{process.exitCode=1;fs.writeSync(2,String(e.stack)+'\n');});
