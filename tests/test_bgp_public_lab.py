"""Do not restore another experiment's lab or replay a started attempt."""
import importlib.util,json,tempfile,unittest,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'ops'))
spec=importlib.util.spec_from_file_location('public_lab',ROOT/'ops/replay_bgp_public_probe.py');lab=importlib.util.module_from_spec(spec);spec.loader.exec_module(lab)
class PublicLabTest(unittest.TestCase):
    def setup_plan(self,d):
        p=Path(d);(p/'plan.json').write_text(json.dumps({'source_files':{}}));return p
    def test_started_attempt_is_not_replayed(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.setup_plan(d);(p/'run-started.json').write_text('{}')
            with patch.object(lab.os,'geteuid',return_value=0),patch.object(lab,'acquire') as acquire,patch.object(lab,'restore') as restore:
                with self.assertRaisesRegex(RuntimeError,'already started'):lab.run(p)
                acquire.assert_not_called();restore.assert_not_called()
    def test_project_lock_rejection_never_triggers_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.setup_plan(d)
            with patch.object(lab.os,'geteuid',return_value=0),patch.object(lab,'acquire',side_effect=RuntimeError('another experiment')),patch.object(lab,'restore') as restore,patch.object(lab.subprocess,'run') as run:
                with self.assertRaisesRegex(RuntimeError,'another experiment'):lab.run(p)
                restore.assert_not_called();run.assert_not_called();self.assertFalse((p/'run-started.json').exists())
    def test_hash_drift_is_rejected_before_lab_or_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.setup_plan(d);(p/'source.txt').write_text('new');(p/'plan.json').write_text(json.dumps({'source_files':{'source.txt':'old'}}))
            with patch.object(lab,'ROOT',p),patch.object(lab.os,'geteuid',return_value=0),patch.object(lab,'acquire') as acquire,patch.object(lab,'restore') as restore:
                with self.assertRaisesRegex(RuntimeError,'source changed'):lab.run(p)
                acquire.assert_not_called();restore.assert_not_called()
if __name__=='__main__':unittest.main()
