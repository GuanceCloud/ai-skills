import subprocess,json,pathlib,sys
r=pathlib.Path(__file__).resolve().parent
node='/Users/oneandonly/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
results=[]
for platform in ['android','ios']:
 for mode in ['success','reject','throw','never','config-retry','missing-retry']:
  for outcome in ['original-returns','original-throws']:
   cmd=[node,str(r/'verify.cjs'),platform,mode,outcome]
   try:
    run=subprocess.run(cmd,cwd=r,text=True,capture_output=True,timeout=10)
    result={'command':cmd,'exit':run.returncode,'stdout':run.stdout,'stderr':run.stderr}
   except subprocess.TimeoutExpired:
    result={'command':cmd,'exit':124,'stderr':'Timeout (test did not complete)'}
   results.append(result)
   (r/'logs'/f'{platform}-{mode}-{outcome}.log').write_text(json.dumps(result,indent=2)+'\n')
   print(platform,mode,outcome,result['exit'])
(r/'test-results.json').write_text(json.dumps(results,indent=2)+'\n')
sys.exit(0 if all(x['exit']==0 for x in results) else 1)
