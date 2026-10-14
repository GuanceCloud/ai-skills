import json,sys,subprocess,hashlib
from pathlib import Path
root=Path(__file__).parent;out=root/'evidence'
checks=[]
for run in ['A-baseline','A-hook','A-reject','B-hook']:
 events=json.loads((out/f'{run}-events.json').read_text()); browser=json.loads((out/f'{run}-browser.json').read_text());canary='A_PROHIBITED_QUERY_SYNTHETIC' if run.startswith('A') else 'B_AUTH_TOKEN_SYNTHETIC_NOT_SECRET'
 counts={t:sum(e['measurement']==t for e in events) for t in sorted({e['measurement'] for e in events})}
 hits=[]
 for i,e in enumerate(events):
  for group in ['tags','fields']:
   for k,v in e.get(group,{}).items():
    if canary in str(v):hits.append({'event':i,'measurement':e['measurement'],'field':group+'.'+k})
 checks.append({'run':run,'sdk_version_3_3_21':all(e['tags']['sdk_version']=='3.3.21' for e in events),'counts':counts,'representative_events_present':all(counts.get(t,0)>0 for t in ['view','resource','error']),'single_init':browser['behavior']['initCount']==1,'navigation_preserved':browser['behavior']['url'].endswith('/?page=2&sort=price') and browser['behavior']['page']=='2','request_preserved':any(r['url']=='/api/catalog?page=2&sort=price' for r in browser['api']),'prohibited_query_absent':not hits,'prohibited_query_hits':hits,'query_stripped_from_view_url':all('?' not in e['tags'].get('view_url','') for e in events) if run!='A-baseline' else None,'resource_query_values_retained':any('price' in str(e.get('fields',{}).get('resource_url_query','')) for e in events),'beforeSend_reject_warning':any("Can't dismiss view" in m['text'] for m in browser['consoleMessages'])})
(out/'assertions.json').write_text(json.dumps(checks,indent=2)+'\n')
for check in checks: print(check['run'], 'events',check['counts'],'prohibited_query_absent=',check['prohibited_query_absent'])
if '--require-privacy' in sys.argv:sys.exit(0 if all(c['prohibited_query_absent'] for c in checks if c['run']!='A-baseline') else 1)
assert all(all(c[k] for k in ['sdk_version_3_3_21','representative_events_present','single_init','navigation_preserved','request_preserved']) for c in checks)
assert all(not c['prohibited_query_absent'] for c in checks)
assert next(c for c in checks if c['run']=='A-reject')['beforeSend_reject_warning']
for case in ['A','B']:
 assert json.loads((root/f'{case}-plan-gate.json').read_text())['returncode']==0
 assert json.loads((root/f'{case}-implement-gate.json').read_text())['returncode']==1
 assert not subprocess.check_output(['git','diff','HEAD','--','src','package.json','index.html'],cwd=root/case,text=True).strip()
print('Verified blocker decisions, real non-empty SDK payloads, preserved app behavior, and untouched application source.')
