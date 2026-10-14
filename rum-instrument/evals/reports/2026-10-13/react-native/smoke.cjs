const assert=require('assert');
const fs=require('fs');
const Module=require('module');
const path=require('path');
const platform=process.argv[2]||'android';
const mode=process.argv[3]||'normal';
const calls=[],warnings=[];
let originalErrorHandlerCalls=0, installedErrorHandler;
const originalErrorHandler=()=>{originalErrorHandlerCalls++};
global.ErrorUtils={getGlobalHandler:()=>originalErrorHandler,setGlobalHandler:f=>{installedErrorHandler=f}};
const originalLoad=Module._load;
let nativeRumAttempts=0;
const nativeMobile={sdkConfig:async config=>{calls.push({method:'sdkConfig',config})}};
const nativeRum={
 setConfig:async config=>{nativeRumAttempts++;calls.push({method:'setConfig',config});if(mode==='partial-failure'&&nativeRumAttempts===1)throw new Error('synthetic native bridge failure')},
 addError:async(...args)=>{calls.push({method:'addError',args})},
 addErrorWithType:async(...args)=>{calls.push({method:'addErrorWithType',args})}
};
const natives={FTMobileReactNative:nativeMobile,FTReactNativeRUM:nativeRum,FTReactNativeLog:{},FTReactNativeTrace:{}};
Module._load=function(request,parent,isMain){
 if(request==='react-native')return {Platform:{OS:platform},NativeModules:natives,NativeEventEmitter:class {},TurboModuleRegistry:{get:name=>mode==='missing-bridge'?null:natives[name]}};
 return originalLoad.apply(this,arguments);
};
const oldWarn=console.warn;console.warn=(...args)=>{warnings.push(args.join(' '));oldWarn.apply(console,args)};
(async()=>{
 const app=require('./project/index.js');const {startRum}=require('./project/rum.js');
 const initial=await Promise.all([app.rumReady,startRum(),startRum()]);
 if(mode==='missing-bridge'){
  assert.deepEqual(initial,[false,false,false]);assert.equal(calls.length,0);
 }else if(mode==='partial-failure'){
  assert.deepEqual(initial,[false,false,false]);assert.equal(await startRum(),true);
  assert.equal(calls.filter(x=>x.method==='sdkConfig').length,1);
  assert.equal(calls.filter(x=>x.method==='setConfig').length,2);
 }else{
  assert.deepEqual(initial,[true,true,true]);
  delete require.cache[require.resolve('./project/rum.js')];
  assert.equal(await require('./project/rum.js').startRum(),true);
  assert.equal(calls.filter(x=>x.method==='sdkConfig').length,1);
  assert.equal(calls.filter(x=>x.method==='setConfig').length,1);
  const base=calls[0].config, rum=calls[1].config;
  assert.equal(base.datakitUrl,'http://127.0.0.1:19529');assert(!('datawayUrl' in base));assert(!('clientToken' in base));
  assert.equal(rum.androidAppId,'eval_rn_android');assert.equal(rum.iOSAppId,'eval_rn_ios');assert.notEqual(rum.androidAppId,rum.iOSAppId);
  assert.equal(rum.enableTraceWebView,false);assert.equal(rum.enableTrackNativeCrash,false);assert.equal(rum.enableNativeUserView,false);
  installedErrorHandler(new Error('Synthetic JS error'),true);
  await new Promise(r=>setImmediate(r));
 }
 const result={platform,mode,actual_sdk:require('./project/node_modules/@cloudcare/react-native-mobile/package.json').version,real_sdk_javascript:true,native_bridge_mocked:true,actual_native_platform_selection_executed:false,initial_results:initial,calls,warnings,original_error_handler_preserved:mode==='normal'?originalErrorHandlerCalls===1:null,original_error_handler_calls:originalErrorHandlerCalls};
 fs.writeFileSync(`logs/smoke-${platform}-${mode}.json`,JSON.stringify(result,null,2));
 console.log(JSON.stringify(result,null,2));
})().catch(e=>{console.error(e);process.exitCode=1});
