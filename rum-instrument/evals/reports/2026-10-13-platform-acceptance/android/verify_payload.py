from pathlib import Path
import json,re,sys,hashlib
root=Path(__file__).parent;e=root/'evidence';p=root/'project'
entries=[json.loads(line) for line in (e/'payloads.jsonl').read_text().splitlines()]
body='\n'.join(x['body'] for x in entries if x['path']=='/v1/write/rum' and x['body'])
measurements={k:len(re.findall('^'+k+',',body,re.M)) for k in ('view','resource','error')}
requests=[json.loads(l) for l in (e/'resource-requests.jsonl').read_text().splitlines()]
markers=re.findall(r'\s(\d+)\s+\d+ I RUMAcceptance: SDK_INITIALIZED count=(\d+) appId=(\S+)',(e/'initialization.log').read_text())
checks={
 'nonempty_real_sdk_payload':bool(body),
 'view_resource_error_present':all(measurements.values()),
 'correct_application_id':'app_id=eval_android_acceptance' in body and set(re.findall(r'app_id=([^, ]+)',body))=={'eval_android_acceptance'},
 'sdk_version_1_7_5':'sdk_version=1.7.5' in body,
 'configuration_consumed':all(s in body for s in ['service=com.example.rumacceptance','env=acceptance','version=1.0-acceptance']),
 'representative_http_success':'resource_status=200' in body and 'resource_method=POST' in body,
 'error_stack_preserved':'IllegalStateException' in body and 'MainActivity.onCreate' in body,
 'bounded_view':'view_name=AcceptanceHome' in body,
 'canaries_absent':all(s not in body for s in ['INPUT_CANARY_ANDROID_ACCEPTANCE','HEADER_CANARY_ANDROID_ACCEPTANCE','BODY_CANARY_ANDROID_ACCEPTANCE']),
 'request_behavior_preserved':all(x['synthetic_header_seen'] and x['synthetic_body_seen'] for x in requests),
 'trace_headers_absent':all(not x['trace_headers'] for x in requests),
 'authorization_masked':'Authorization: ██' in body,
 'single_initializer_source':(p/'app/src/main/java/com/example/rumacceptance/App.java').read_text().count('FTSdk.install(')==1,
 'one_initializer_per_process':len(markers)==2 and len({x[0] for x in markers})==2 and all(x[1]=='1' and x[2]=='eval_android_acceptance' for x in markers),
 'device_arm64_api34':(e/'device-abi.log').read_text().strip()=='arm64-v8a' and (e/'device-api.log').read_text().strip()=='34',
 'runtime_no_app_crash':'FATAL EXCEPTION' not in (e/'app-logcat-launch2.log').read_text(),
}
result={'status':'passed' if all(checks.values()) else 'failed','checks':checks,'measurement_counts':measurements,'cold_start_count':len(markers),'process_ids':[x[0] for x in markers],'remote_ingestion_verified':False,'limitations':['Manual core View and Error APIs; no plugin-based automatic Activity/Fragment instrumentation claim','Real OkHttp Resource interceptor; synthetic request only','No crash capture, Replay, Trace, Logs, release signing or physical-device coverage','DataKit-protocol local mock only; no real DataKit or remote ingestion verification']}
(e/'payload-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2));sys.exit(0 if all(checks.values()) else 1)
