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
if __name__=='__main__':unittest.main()
