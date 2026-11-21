import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'ops'))
import replay_bgp_coverage_probe as replay
class CoverageLabGuardTest(unittest.TestCase):
    def test_false_eligibility_blocks_lab(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'summary.json').write_text(json.dumps({'eligible_for_full_lab':False}))
            with patch.object(replay,'PROBE',p),patch.object(replay.lab,'prepare') as prepare:
                with self.assertRaisesRegex(RuntimeError,'incomplete'):replay.prepare(p/'out')
                prepare.assert_not_called()
    def test_summary_flag_cannot_override_batfish_coverage_error(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'summary.json').write_text(json.dumps({'eligible_for_full_lab':True}))
            for n in ['precheck.json','syntax.json']:(p/n).write_text('{"status":"pass"}')
            (p/'batfish.json').write_text('{"status":"environment_error"}')
            with patch.object(replay,'PROBE',p),patch.object(replay.lab,'prepare') as prepare:
                with self.assertRaisesRegex(RuntimeError,'not PASS: batfish'):replay.prepare(p/'out')
                prepare.assert_not_called()
    def test_materialized_plan_must_match_the_actual_model_update(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);probe=root/'probe';source=root/'source';probe.mkdir();source.mkdir()
            parent={'version':'bgp-plan-v1','policies':[],'devices':[{'id':'R2','asn':65002,'originate':['192.168.3.0/24'],'peers':[]}]}
            candidate=dict(parent,devices=[dict(parent['devices'][0],originate=[])])
            (source/'ir.json').write_text(json.dumps(parent));(probe/'ir.json').write_text(json.dumps(candidate));(probe/'summary.json').write_text('{"eligible_for_full_lab":true}');(probe/'plan.json').write_text(json.dumps({'version':'bgp-origin-update-single-probe-v1','source_files':{}}))
            for n in ['precheck.json','syntax.json','batfish.json']:(probe/n).write_text('{"status":"pass"}')
            (probe/'update.json').write_text(json.dumps({'version':'bgp-origin-update-v1','updates':[{'device_id':'R2','originate':[]}]}));(probe/'raw-response.json').write_text(json.dumps({'message':{'content':json.dumps({'version':'bgp-origin-update-v1','updates':[]})}}))
            with patch.object(replay,'PROBE',probe),patch.object(replay,'SOURCE',source),patch.object(replay.lab,'prepare') as prepare:
                with self.assertRaisesRegex(RuntimeError,'differs from literal'):replay.prepare(root/'out')
                prepare.assert_not_called()
if __name__=='__main__':unittest.main()
