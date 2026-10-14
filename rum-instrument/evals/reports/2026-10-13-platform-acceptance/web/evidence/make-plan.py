import json,subprocess
from pathlib import Path
r=Path('/private/tmp/rum-platform-acceptance/web')
p=json.loads(Path('/Users/oneandonly/Workspace/ai-skills/rum-instrument/assets/datakit-plan.example.json').read_text())
p['repository']={'root':str(r),'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip(),'initial_status':[]}
p['request']['application_id_input']['reference']['value']='eval_vue_acceptance'
p['request']['receiver']['endpoint']['value']='http://127.0.0.1:19539'
t=p['targets'][0];t.update(id='web:.',platform='web',variants=['browser'],evidence=['index.html','package.json','src/main.ts','src/router.ts'],application_id_slots=['web'],application_ids={'web':{'value':'eval_vue_acceptance'}},application_types={'web':{'value':'web','source':'repository','confidence':'high','verification':'not_applicable','api_value':None}},official_sources=['https://docs.guance.com/real-user-monitoring/web/app-access/'])
t['profile']={'signals':{'rum':True,'logs':False,'tracing':False,'replay':False},'service':{'value':'vue-rum-acceptance','source':'package.json#name via Vite define','confidence':'high'},'version':{'value':'1.2.3','source':'package.json#version via Vite define','confidence':'high'},'env':{'value':'production','source':'Vite import.meta.env.MODE build mode','confidence':'high'},'sampling':{'value':'SDK default','source':'Browser SDK default session sample rate','confidence':'high'}}
t['receiver_mapping']={'applicationId':'VITE_RUM_APP_ID','datakitOrigin':'VITE_RUM_DATAKIT_URL'}
t['privacy']={'evidence':['Reviewed maintained router: static paths / and /details with harmless page=2; no credentials or personal data in URL','Local draft remains component state; no custom context/actions or body/header collection'], 'controls':['No Replay start, Trace, custom context, body capture or URL rewrite'], 'validation':['Verify local draft canary absent from nonempty actual exported payload; ordinary page=2 must remain allowed']}
changes=[('package.json','Add exact @cloudcare/browser-rum 3.3.21 dependency'),('package-lock.json','Lock SDK using public npm'),('.env.example','Document non-secret Vite configuration'),('.env.production','Read supplied non-secret endpoint and application ID through Vite'),('src/rum.ts','Single promise initializer, dynamic SDK import, catch failure, official default sampling'),('src/main.ts','Await bounded SDK startup before Vue mount; preserve application error handler'),('README.md','Document initialization and actual build/configuration usage')]
p['planned_changes']=[]
for i,(f,purpose) in enumerate(changes,1):
 c={'target_id':'web:.','file':f,'order':i,'purpose':purpose,'edits':[purpose],'dependency_decision':{'action':'none'},'validation':['npm ci','npm run build','production Chrome payload and failure tests'],'risk':'Preserve startup and requests','rollback':'Restore baseline commit file or remove newly added file'}
 if f=='package.json':c['dependency_decision']={'action':'add','package':'@cloudcare/browser-rum','version':'3.3.21','official_source':'https://docs.guance.com/real-user-monitoring/web/app-access/'}
 p['planned_changes'].append(c)
p['batches'][0].update(id='web',target_ids=['web:.'])
p['validation']=['Plan and implementation validators before code edits','Public npm clean install, strict vue-tsc incl SDK declarations, Vite production build','Real Chrome: receiver/config/version/env; one init; SPA; resource; error; no optional signals; local draft absent','Repeat integration source audit and dynamic repeated initializer call; SDK chunk aborted and stalled startup survives']
p['risks']=['Local mock collector cannot prove DataKit configuration or remote ingestion','Dynamic import may miss early SDK load interval; startup waiting bounded to 1500ms']
p['handoff']=['Use actual DataKit RUM collector and console to confirm remote ingestion']
(r/'.rum').mkdir(exist_ok=True);data=json.dumps(p,ensure_ascii=False,indent=2,sort_keys=True)+'\n';(r/'.rum/plan.json').write_text(data);(r/'evidence/first-plan.json').write_text(data)
