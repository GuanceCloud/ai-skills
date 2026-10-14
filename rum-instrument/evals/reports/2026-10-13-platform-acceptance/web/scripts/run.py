import subprocess,sys,json,os,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
label=sys.argv[1]; args=sys.argv[2:]
env=os.environ.copy();env['PATH']='/Users/oneandonly/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:'+env['PATH']
if args[0]=='npm' and Path('/private/tmp/rum-platform-acceptance/npm-tools/node_modules/npm/bin/npm-cli.js').exists(): args=['node','/private/tmp/rum-platform-acceptance/npm-tools/node_modules/npm/bin/npm-cli.js',*args[1:]]
p=subprocess.run(args,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
(root/'evidence'/f'{label}.log').write_text(p.stdout)
with (root/'evidence/commands.jsonl').open('a') as f:f.write(json.dumps({'label':label,'argv':args,'exit_code':p.returncode,'time':time.time()})+'\n')
print(p.stdout);sys.exit(p.returncode)
