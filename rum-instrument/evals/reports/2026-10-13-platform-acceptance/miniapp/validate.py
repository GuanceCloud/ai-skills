from pathlib import Path
import subprocess,json
base=Path('/private/tmp/rum-platform-acceptance/miniapp');p=base/'project';out=base/'build';out.mkdir(exist_ok=True)
results=[]
def run(name,cmd):
 try:
  result=subprocess.run(cmd,cwd=p,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=30)
  (base/'logs'/f'{name}.log').write_text(result.stdout);results.append({'name':name,'command':cmd,'exit':result.returncode})
 except subprocess.TimeoutExpired as e: results.append({'name':name,'command':cmd,'exit':'timeout'})
for f in ['app.json','project.config.json','sitemap.json','pages/index/index.json','package.json','package-lock.json']:
 json.loads((p/f).read_text());results.append({'name':'json:'+f,'exit':0})
for f in ['app.js','rum.js','pages/index/index.js','config/rum.example.js','config/rum.local.js']:
 run('syntax-'+f.replace('/','_'),['node','--check',f])
run('wxml-compile',['/Applications/wechatwebdevtools.app/Contents/Resources/package.nw/js/vendor/wcc','-d','-o',str(out/'wxml.js'),'pages/index/index.wxml'])
run('wxss-compile',['/Applications/wechatwebdevtools.app/Contents/Resources/package.nw/js/vendor/wcsc','-lc','-js','-o',str(out/'wxss.js'),'app.wxss','pages/index/index.wxss'])
(base/'logs/static-results.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
raise SystemExit(any(r['exit']!=0 for r in results))
