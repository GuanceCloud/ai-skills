from pathlib import Path
import subprocess,json,datetime,hashlib
base=Path(__file__).resolve().parent
node='/Users/oneandonly/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
results=[]
for version in ['3.3.5','3.3.21']:
 p=base/version
 command=[node,str(p/'node_modules/typescript/bin/tsc'),'--project','tsconfig.json','--pretty','false']
 result=subprocess.run(command,cwd=p,text=True,capture_output=True)
 (p/'tsc.log').write_text(result.stdout+result.stderr)
 versions={name:json.loads((p/'node_modules'/name/'package.json').read_text())['version'] for name in ['@cloudcare/browser-rum','@cloudcare/browser-core','@cloudcare/browser-worker','typescript']}
 record={'cwd':str(p),'versions':versions,'command':command,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr,'lockfile':'package-lock.json','lockfile_sha256':hashlib.sha256((p/'package-lock.json').read_bytes()).hexdigest()}
 results.append(record)
 print(json.dumps(record,ensure_ascii=False,indent=2))
(base/'results.json').write_text(json.dumps({'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'node_version':subprocess.check_output([node,'--version'],text=True).strip(),'results':results},ensure_ascii=False,indent=2)+'\n')
