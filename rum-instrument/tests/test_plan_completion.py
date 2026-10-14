"""Draft completion must reduce bookkeeping without weakening execution gates."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_validate_contract import VALIDATOR as V
from test_onboarding import v3_plan, add_target

SKILL = Path(__file__).resolve().parents[1]


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / '.gitignore').write_text('.rum/\n.env.local\n')
        subprocess.run(['git', '-C', str(self.root), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'baseline'], check=True)
        (self.root / '.rum').mkdir()
        self.draft = json.loads((SKILL / 'assets/plan-draft.example.json').read_text())

    def complete(self, draft=None):
        return V.complete_plan_draft(self.draft if draft is None else draft, self.root)

    def test_complete_input_needs_no_schema_repair(self):
        plan = self.complete()
        self.assertEqual([], V.validate_plan(plan, 'plan')[0])
        self.assertEqual([], V.validate_plan(plan, 'implement')[0])
        self.assertEqual([], V.validate_repository_state(plan, self.root))
        self.assertEqual('approved', plan['batches'][0]['approval']['status'])
        self.assertEqual('preserve', plan['targets'][0]['profile']['signals']['replay'])
        self.assertNotIn('repository', self.draft)

    def test_missing_input_is_not_guessed(self):
        for mutation in [lambda p:p['request']['receiver'].pop('endpoint'), lambda p:p['targets'][0].pop('application_ids')]:
            draft=copy.deepcopy(self.draft);mutation(draft)
            self.assertTrue(V.validate_plan(self.complete(draft), 'plan')[0])

    def test_dependency_evidence_must_be_supplied(self):
        self.draft['planned_changes'][0]['dependency_decision']={'action':'add','package':'example'}
        self.assertTrue(V.validate_plan(self.complete(), 'plan')[0])

    def test_no_manufactured_authorization(self):
        del self.draft['request']['authorization_evidence']
        with self.assertRaises(ValueError):self.complete()
        for intent in ['plan','audit','validate']:
            self.draft['request']['intent']=intent
            plan=self.complete()
            self.assertEqual('pending',plan['batches'][0]['approval']['status'])
            self.assertTrue(V.validate_plan(plan,'implement')[0])

    def test_existing_and_repeat_preserve_baseline_and_decisions(self):
        plan=self.complete();t=plan['targets'][0]
        t['disposition']='existing';plan['planned_changes']=[]
        plan['repository']['initial_status']=[' M user.txt']
        again=self.complete(plan)
        self.assertEqual(plan,again)
        self.assertEqual([],V.validate_plan(again,'implement')[0])

    def test_public_dataway_still_requires_runtime_state(self):
        draft=v3_plan();draft['request']['authorization_evidence']='Please integrate RUM.'
        for key in ['approval','batches']:draft.pop(key)
        plan=self.complete(draft)
        self.assertEqual([],V.validate_plan(plan,'plan')[0])
        self.assertEqual(draft['request']['receiver']['client_tokens'],plan['request']['receiver']['client_tokens'])
        # Completion creates no credentials, checkpoints or verified remote state.
        self.assertEqual([],list((self.root/'.rum').iterdir()))

    def test_public_dataway_example_completes_but_cannot_skip_resolution(self):
        draft = json.loads((SKILL / 'assets/public-dataway-draft.example.json').read_text())
        draft['request']['authorization_evidence'] = 'Synthetic request to integrate core RUM.'
        plan = self.complete(draft)
        self.assertEqual([], V.validate_plan(plan, 'plan')[0])
        self.assertEqual([], V.validate_plan(plan, 'implement')[0])
        self.assertEqual('preserve', plan['targets'][0]['profile']['signals']['replay'])
        path = self.root / '.rum/plan.json'
        path.write_text(json.dumps(plan))
        result = subprocess.run([sys.executable, '-B', V.__file__, str(path),
            '--phase', 'implement', '--repository', str(self.root)], capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn('--execution-state', result.stderr)
        self.assertFalse((self.root / '.env.local').exists())

    def test_multi_target_blocked_and_shared_batches_keep_original_gates(self):
        draft=v3_plan();add_target(draft,blocked=True)
        draft['request']['authorization_evidence']='Integrate all applications.'
        draft.pop('approval')
        for b in draft['batches']:b.pop('approval')
        plan=self.complete(draft)
        self.assertEqual('pending',plan['approval']['status'])
        self.assertEqual([],V.validate_plan(plan,'implement',['web:.'])[0])
        self.assertTrue(V.validate_plan(plan,'implement')[0])
        draft.pop('batches')
        with self.assertRaises(ValueError):self.complete(draft)

    def test_supplied_pending_approval_not_upgraded(self):
        plan=self.complete();plan['batches'][0]['approval'].update(status='pending',blockers=['actual overlap'])
        self.assertEqual(plan,self.complete(plan))
        self.assertTrue(V.validate_plan(self.complete(plan),'implement')[0])

    def test_pending_summary_cannot_be_bypassed_by_generated_batch(self):
        self.draft['approval']={'status':'pending','basis':'explicit_implementation_request','blockers':['actual overlap'],'revision':1}
        plan=self.complete()
        self.assertEqual(self.draft['approval'],plan['batches'][0]['approval'])
        self.assertTrue(V.validate_plan(plan,'implement')[0])

    def test_existing_file_conflict_not_hidden(self):
        (self.root/'app.js').write_text('user work')
        plan=self.complete()
        self.assertTrue(V.validate_repository_state(plan,self.root))

    def test_new_draft_captures_missing_and_existing_source_baselines(self):
        plan = self.complete()
        self.assertEqual('missing', plan['planned_changes'][0]['before_sha256'])
        (self.root / 'app.js').write_text('user created this after planning\n')
        self.assertTrue(V.validate_repository_state(plan, self.root))
        # Re-completion preserves the original missing-file baseline.
        self.assertEqual('missing', self.complete(plan)['planned_changes'][0]['before_sha256'])
        self.assertTrue(V.validate_repository_state(self.complete(plan), self.root))

    def test_draft_never_reads_source_through_symlink(self):
        outside = self.root / '.rum/outside.js'
        outside.write_text('outside source\n')
        (self.root / 'app.js').symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.complete()

    def cli(self,draft,output):
        source=self.root/'.rum/draft.json';source.write_text(json.dumps(draft))
        return subprocess.run([sys.executable,str(SKILL/'scripts/validate_contract.py'),str(source),'--complete-draft',str(output),'--repository',str(self.root)],capture_output=True,text=True)

    def test_cli_validates_before_writing_and_never_overwrites(self):
        out=self.root/'.rum/plan.json'
        bad=copy.deepcopy(self.draft);bad['request']['receiver']['endpoint']={'value':''}
        self.assertNotEqual(0,self.cli(bad,out).returncode);self.assertFalse(out.exists())
        result=self.cli(self.draft,out);self.assertEqual(0,result.returncode,result.stderr)
        before=out.read_bytes()
        self.assertNotEqual(0,self.cli(self.draft,out).returncode);self.assertEqual(before,out.read_bytes())

    def test_output_cannot_escape_or_follow_symlinks(self):
        out=self.root.parent/(self.root.name+'-outside.json')
        self.assertNotEqual(0,self.cli(self.draft,out).returncode);self.assertFalse(out.exists())
        try:(self.root/'linked').symlink_to(self.root/'.rum',target_is_directory=True)
        except OSError:self.skipTest('symlink privilege unavailable')
        self.assertNotEqual(0,self.cli(self.draft,self.root/'linked/plan.json').returncode)
        self.assertFalse((self.root/'.rum/plan.json').exists())

if __name__=='__main__':unittest.main()
