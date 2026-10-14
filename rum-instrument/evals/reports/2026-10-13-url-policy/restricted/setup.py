from pathlib import Path
import shutil, subprocess, json, hashlib
root=Path('/private/tmp/rum-url-policy-eval/restricted'); fixture=Path('/Users/oneandonly/Workspace/ai-skills/rum-instrument/evals/files/web-url-policy'); skill=Path('/private/tmp/rum-url-policy-eval/skills/rum-instrument')
for case in ['A','B']:
 p=root/case; shutil.copytree(fixture,p)
 if case=='A':
  (p/'AGENTS.md').write_text('项目策略：所有 URL 查询参数值不得进入任何 RUM 字段。\n')
 else:
  (p/'src/auth-callback.js').write_text('''// Maintained authorization callback contract; synthetic fixture, no real credential.\nlet authSession = null;\nexport function handleAuthorizationCallback() {\n  const token = new URL(window.location.href).searchParams.get('access_token');\n  if (token) authSession = { accessToken: token };\n  return Boolean(authSession);\n}\n// Intentionally retains the URL, matching the app behavior being assessed.\n''')
  (p/'src/main.js').write_text("import { handleAuthorizationCallback } from './auth-callback.js';\nif (location.pathname === '/auth/callback') handleAuthorizationCallback();\n"+(p/'src/main.js').read_text())
 for args in [['git','init'],['git','add','.'],['git','-c','user.name=Eval','-c','user.email=eval@example.invalid','commit','-m','Synthetic baseline']]: subprocess.run(args,cwd=p,check=True,capture_output=True)
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=p,text=True).strip()
 detection=subprocess.run(['python3',str(skill/'scripts/detect_rum_targets.py'),str(p),'--pretty'],text=True,capture_output=True)
 (root/f'{case}-detection.json').write_text(detection.stdout)
 reason=('Explicit project requirement prohibits all query values in every RUM field; 3.3.21 beforeSend cannot modify view.url_query; remedy must be verified before initialization.' if case=='A' else 'Maintained /auth/callback flow reads access_token into in-memory authentication state without clearing URL; standard view.url_query would capture credential material; supported remedy must be verified before initialization.')
 plan=json.loads((skill/'assets/datakit-plan.example.json').read_text()); plan['repository'].update(root=str(p),commit=head);plan['request']['application_id_input']['reference']['value']='eval_catalog'; plan['request']['receiver']['endpoint']['value']='http://127.0.0.1:19529'
 t=plan['targets'][0];t.update(id='web:.',platform='web',variants=['browser'],evidence=['package.json','index.html','src/main.js']+(['AGENTS.md'] if case=='A' else ['src/auth-callback.js']),application_id_slots=['web'],application_ids={'web':{'value':'eval_catalog'}},application_types={'web':{'value':'web','source':'repository','confidence':'high','verification':'not_applicable','api_value':None}},official_sources=['https://docs.guance.com/real-user-monitoring/web/app-access/'],disposition='blocked',blockers=[reason],receiver_mapping={'applicationId':'eval_catalog','datakitOrigin':'http://127.0.0.1:19529'},privacy={'requirement':reason,'remedy':'Verify actual SDK exports before application initialization; do not rewrite routes or SDK.'})
 plan['planned_changes']=[];plan['approval'].update(status='pending',blockers=[reason]);plan['batches']=[{'id':'web','target_ids':['web:.'],'depends_on':[],'approval':plan['approval'].copy()}];plan['validation']=['Actual SDK 3.3.21 Chrome local payload capability probe outside application checkout'];plan['risks']=[reason]
 (p/'.rum').mkdir();(p/'.rum/plan.json').write_text(json.dumps(plan,indent=2)+'\n')
 (root/f'{case}-first-decision.json').write_text(json.dumps({'scenario':case,'commit':head,'first_plan_disposition':'blocked','first_implementation_gate':'pending technical remedy verification','new_initializer_in_application':False,'business_question_count':0,'approval_question_count':0,'reason':reason,'fixture_is_synthetic':True},indent=2)+'\n')
print('Created isolated A/B git fixtures and initial blocked plans; no application initializer created.')
