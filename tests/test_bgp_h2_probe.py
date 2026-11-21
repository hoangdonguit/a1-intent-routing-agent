import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'ops'))
import replay_bgp_h2_probe as replay
import repair_bgp_h2_probe as repair
class H2ProbeGuardTest(unittest.TestCase):
    def fixture(self,root):
        probe=root/'probe';source=root/'source';probe.mkdir();source.mkdir()
        plan={'version':'bgp-plan-v1','policies':[{'id':'out','rules':[],'default':'deny'}],'devices':[{'id':'R4','asn':65004,'originate':['192.168.2.0/24'],'peers':[{'id':'toR3','address':'10.6.3.1','remote_as':65003,'ipv4':True,'import':'out','export':'out'}]}]}
        for p in [probe,source]:(p/'ir.json').write_text(json.dumps(plan))
        (probe/'summary.json').write_text(json.dumps({'eligible_for_target_lab':True}));(probe/'plan.json').write_text(json.dumps({'source_files':{}}));(probe/'repair-scope.json').write_text('{}');(probe/'feedback.json').write_text(json.dumps({'errors':[{'device':'R4','property':'deny_export:192.168.2.0/24','observed':{'peer':'10.6.3.1'}}]}));return probe,source,plan
    def test_not_eligible_never_calls_lab_preparation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);probe,source,_=self.fixture(root);(probe/'summary.json').write_text(json.dumps({'eligible_for_target_lab':False}))
            with patch.object(replay,'PROBE',probe),patch.object(replay,'SOURCE',source),patch.object(replay.lab,'prepare') as prepare:
                with self.assertRaisesRegex(RuntimeError,'did not satisfy'):replay.prepare(root/'out')
                prepare.assert_not_called()
    def test_network_edit_is_rejected_even_if_summary_claims_eligible(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);probe,source,plan=self.fixture(root);plan['devices'][0]['asn']=999;(probe/'ir.json').write_text(json.dumps(plan))
            with patch.object(replay,'PROBE',probe),patch.object(replay,'SOURCE',source),patch.object(replay.lab,'prepare') as prepare:
                with self.assertRaisesRegex(RuntimeError,'Network decisions changed'):replay.prepare(root/'out')
                prepare.assert_not_called()
    def test_policy_permit_cannot_be_hidden_by_summary_flag(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);probe,source,plan=self.fixture(root);plan['policies'][0]['default']='permit';(probe/'ir.json').write_text(json.dumps(plan))
            with patch.object(replay,'PROBE',probe),patch.object(replay,'SOURCE',source),patch.object(replay.lab,'prepare') as prepare:
                with self.assertRaisesRegex(RuntimeError,'still permits'):replay.prepare(root/'out')
                prepare.assert_not_called()
    def test_started_model_probe_does_not_rewrite_its_summary_or_retry(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'request.json').write_text('{}');(p/'plan.json').write_text(json.dumps({'source_files':{},'request_sha256':repair.engine.sha(p/'request.json')}));(p/'call-started.json').write_text('{}');(p/'summary.json').write_text('{"original":true}')
            with patch.object(repair.engine,'OllamaClient') as client:
                with self.assertRaisesRegex(RuntimeError,'never retry'):repair.run(p)
                client.assert_not_called();self.assertEqual((p/'summary.json').read_text(),'{"original":true}')
if __name__=='__main__':unittest.main()
