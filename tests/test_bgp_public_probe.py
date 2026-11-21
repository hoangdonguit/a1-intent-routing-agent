"""Protect the single-call diagnostic from retries or edited frozen inputs."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('public_probe',Path(__file__).resolve().parents[1]/'ops/repair_bgp_public_probe.py');probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
class PublicProbeTest(unittest.TestCase):
    def files(self,p):
        (p/'request.json').write_text('{}');(p/'plan.json').write_text(json.dumps({'source_files':{},'request_sha256':probe.sha(p/'request.json')}))
    def test_already_started_probe_cannot_call_model_again(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.files(p);(p/'call-started.json').write_text('{}')
            with patch.object(probe,'OllamaClient') as client:
                with self.assertRaisesRegex(RuntimeError,'never retry'):probe.run(p)
                client.assert_not_called()
    def test_edited_payload_is_rejected_before_any_call(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.files(p);(p/'request.json').write_text('{"changed":true}')
            with patch.object(probe,'OllamaClient') as client:
                with self.assertRaisesRegex(RuntimeError,'Request drift'):probe.run(p)
                client.assert_not_called()
    def test_changed_frozen_source_is_rejected_before_call(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.files(p);(p/'source.txt').write_text('current');r=json.loads((p/'plan.json').read_text());r['source_files']={'source.txt':'incorrect'};(p/'plan.json').write_text(json.dumps(r))
            with patch.object(probe,'ROOT',p),patch.object(probe,'OllamaClient') as client:
                with self.assertRaisesRegex(RuntimeError,'Frozen source changed'):probe.run(p)
                client.assert_not_called()
if __name__=='__main__':unittest.main()
