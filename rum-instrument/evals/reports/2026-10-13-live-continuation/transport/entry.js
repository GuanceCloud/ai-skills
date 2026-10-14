import { fetchStrategyWithFallback } from '/private/tmp/rum-platform-acceptance/web/node_modules/@cloudcare/browser-core/esm/transport/httpRequest.js'
import { sendWithRetryStrategy, newRetryState } from '/private/tmp/rum-platform-acceptance/web/node_modules/@cloudcare/browser-core/esm/transport/sendWithRetryStrategy.js'
window.runTransport = async (mode, name) => {
  const events=[];const state=newRetryState(0)
  const url='http://127.0.0.1:19642/'+name
  if(mode.startsWith('native')){
    const response=await fetch(url,{method:'POST',mode:'cors',body:'synthetic-nonsecret-data',headers:{'x-client-timestamp':String(Date.now())}})
    events.push({status:response.status,type:response.type});if(mode==='native-read'){try{events.push({jsBodyReadable:true,length:(await response.text()).length})}catch(error){events.push({jsBodyReadable:false,error:error.name})}}
  } else {
    sendWithRetryStrategy({data:'synthetic-nonsecret-data',bytesCount:24},state,(payload,onResponse)=>fetchStrategyWithFallback(url,payload,response=>{events.push(response);onResponse(response)}),url,error=>events.push({report:error.message}))
  }
  await new Promise(r=>setTimeout(r,800))
  return {mode,name,events,state:{transportStatus:state.transportStatus,pending:state.queuedPayloads.size(),ongoing:state.bandwidthMonitor.ongoingRequestCount}}
}
