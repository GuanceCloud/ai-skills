from pathlib import Path
import subprocess,json,datetime,hashlib
base=Path(__file__).resolve().parent
app=base/'original-web-app'
logs=base/'original-web-app-logs'; logs.mkdir(exist_ok=True)
node='/Users/oneandonly/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
tools=Path('/var/folders/8x/2_sfyjt11tb3y7_n0m9l53lc0000gn/T/rum-full-eval-fsgyxvww/web/test-tools')
files=sorted(str(p.relative_to(app)) for p in (app/'src').rglob('*.ts'))
commands=[('typecheck',[node,str(base/'3.3.21/node_modules/typescript/bin/tsc'),'--noEmit','--strict','--skipLibCheck','false','--target','ES2020','--module','ESNext','--moduleResolution','bundler','--lib','ES2020,DOM',*files]),('bundle',[node,str(tools/'node_modules/esbuild/bin/esbuild'),*files,'--bundle','--format=esm','--splitting','--outdir='+str(base/'original-web-app-build'),'--metafile='+str(logs/'bundle-meta.json')])]
records=[]
for name,command in commands:
 r=subprocess.run(command,cwd=app,text=True,capture_output=True)
 (logs/(name+'.log')).write_text(r.stdout+r.stderr)
 record={'name':name,'cwd':str(app),'command':command,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
 records.append(record)
 print(json.dumps(record,ensure_ascii=False,indent=2))
versions={name:json.loads((app/'node_modules'/name/'package.json').read_text())['version'] for name in ['@cloudcare/browser-rum','@cloudcare/browser-core','@cloudcare/browser-worker','vue']}
versions['typescript']=json.loads((base/'3.3.21/node_modules/typescript/package.json').read_text())['version']
versions['esbuild']=json.loads((tools/'node_modules/esbuild/package.json').read_text())['version']
result={'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'versions':versions,'source_files':files,'source_modifications':False,'existing_type_assertions':[],'existing_explicit_any':[],'existing_ts_error_suppressions':[],'runtime_executed':False,'original_build_scripts_available':False,'independent_npm_ci_performed':True,'independent_npm_ci_exit_code':0,'lockfile_note':'Independent npm ci from the original lockfile succeeded against public npm registry; see original-web-app-logs/npm-ci-result.json.','commands':records,'lockfile_sha256':hashlib.sha256((app/'package-lock.json').read_bytes()).hexdigest()}
(base/'original-web-app-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
