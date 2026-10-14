from pathlib import Path
import subprocess,json,shutil,tempfile,hashlib,tarfile,http.server,threading,functools,sys
repo=Path('/Users/oneandonly/Workspace/ai-skills');root=Path(tempfile.mkdtemp(prefix='rum-slim-release-',dir='/private/tmp'));snap=root/'source';snap.mkdir()
files=subprocess.check_output(['git','-C',str(repo),'ls-files','-z','--cached','--others','--exclude-standard']).split(b'\0')
for raw in files:
 if not raw:continue
 rel=Path(raw.decode());p=repo/rel
 if not p.is_file() or p.is_symlink() or '__pycache__' in rel.parts:continue
 target=snap/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
subprocess.run(['git','init','-q',str(snap)],check=True)
subprocess.run(['git','-C',str(snap),'add','.'],check=True)
subprocess.run(['git','-C',str(snap),'-c','user.name=Acceptance','-c','user.email=acceptance@example.invalid','commit','-qm','Isolated release snapshot'],check=True)
version=subprocess.check_output(['git','-C',str(snap),'rev-parse','HEAD'],text=True).strip()
def build(out):subprocess.run([sys.executable,str(snap/'scripts/build_skill_release.py'),'--repo',str(snap),'--output',str(out),'--version',version],check=True)
slim=root/'slim';build(slim)
manifest=snap/'skills-manifest.json';data=json.loads(manifest.read_text());rum=next(x for x in data['skills'] if x['name']=='rum-instrument');rum.pop('package_include');manifest.write_text(json.dumps(data));full=root/'unfiltered';build(full)
archives={name:base/'versions'/version/'skills/rum-instrument.tar.gz' for name,base in [('filtered',slim),('unfiltered',full)]};stats={}
for name,p in archives.items():
 with tarfile.open(p) as t:
  members=[m for m in t.getmembers() if m.isfile()];stats[name]={'archive_bytes':p.stat().st_size,'files':len(members),'uncompressed_bytes':sum(m.size for m in members)}
  if name=='filtered':assert not any('/evals/' in m.name or '/tests/' in m.name for m in members)
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(slim)));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
 dest=root/'installed';cmd=['sh',str(repo/'install.sh'),'--base-url',f'http://127.0.0.1:{server.server_port}','--skill','rum-instrument','--dest',str(dest),'--scope','project','--project-dir',str(root),'--yes']
 result=subprocess.run(cmd,capture_output=True,text=True);(root/'install.log').write_text(result.stdout+result.stderr);assert result.returncode==0,result.stderr
finally:server.shutdown();server.server_close();thread.join()
installed=dest/'rum-instrument';hashes=[]
for p in installed.rglob('*'):
 if not p.is_file() or p.name.startswith('.skill-'):continue
 rel=p.relative_to(installed);original=repo/'rum-instrument'/rel
 assert original.exists() and p.read_bytes()==original.read_bytes(),str(rel)
 hashes.append({'path':str(rel),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
fixture=root/'app';fixture.mkdir();subprocess.run(['git','init','-q',str(fixture)],check=True);(fixture/'.gitignore').write_text('.rum/\n');subprocess.run(['git','-C',str(fixture),'add','.'],check=True);subprocess.run(['git','-C',str(fixture),'-c','user.name=T','-c','user.email=t@example.invalid','commit','-qm','base'],check=True);(fixture/'.rum').mkdir();draft=fixture/'.rum/draft.json';shutil.copy2(installed/'assets/plan-draft.example.json',draft)
commands=[]
for args in [[str(installed/'scripts/validate_contract.py'),str(draft),'--complete-draft',str(fixture/'.rum/plan.json'),'--repository',str(fixture)],[str(installed/'scripts/validate_contract.py'),str(fixture/'.rum/plan.json'),'--phase','implement','--repository',str(fixture)],[str(installed/'scripts/detect_rum_targets.py'),str(fixture),'--pretty'],[str(installed/'scripts/resolve_rum_application.py'),'--help']]:
 r=subprocess.run([sys.executable,*args],capture_output=True,text=True);commands.append({'script':Path(args[0]).name,'arguments':args[1:],'exit_code':r.returncode});assert r.returncode==0,r.stderr
summary={'snapshot_version':version,'stats':stats,'install_passed':True,'runtime_files_matched':len(hashes),'commands':commands,'scope':'isolated snapshot/install; no live credentials or public release'}
(root/'result.json').write_text(json.dumps(summary,indent=2)+'\n');(root/'runtime-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n');print(str(root));print(json.dumps(summary))
