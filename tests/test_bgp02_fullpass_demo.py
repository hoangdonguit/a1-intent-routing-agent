import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('bgp_proof_demo',ROOT/'scripts/demo_bgp02_fullpass.py');demo=importlib.util.module_from_spec(spec);spec.loader.exec_module(demo)
class FullPassProofTest(unittest.TestCase):
    def fixture(self,p):
        parent={'devices':[{'id':'R2','originate':['192.168.3.0/24'],'export':'none'}]};candidate={'devices':[{'id':'R2','originate':[],'export':'none'}]};update={'version':'bgp-origin-update-v1','updates':[{'device_id':'R2','originate':[]}]}
        data={'fixture-only':{},'parent.json':parent,'ir.json':candidate,'update.json':update,'raw.json':{'message':{'content':json.dumps(update)}},'result.json':{'status':'pass','disagreements':[],'reports':[{'tool':n,'status':'pass','checks':[{'status':'pass','evidence':['fixture-only']}]} for n in ['syntax_checker','protocol_scope','batfish_verifier','lab_ping_tester','bgp_export_tester']]}}
        for n,x in data.items():(p/n).write_text(json.dumps(x))
        return {'final_status':'pass','restore':'pass','final_result':'result.json','final_parent_ir':'parent.json','final_ir':'ir.json','final_update':'update.json','final_raw_model_response':'raw.json','artifact_hashes':{n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in data}}
    def test_valid_evidence_and_literal_update(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.assertEqual(len(demo.verify(p,self.fixture(p))),5)
    def test_changed_artifact_is_not_displayed_as_success(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);proof=self.fixture(p);(p/'raw.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):demo.verify(p,proof)
    def test_extra_manual_edit_is_rejected_even_if_its_hash_is_updated(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);proof=self.fixture(p);candidate=json.loads((p/'ir.json').read_text());candidate['devices'][0]['export']='permit';(p/'ir.json').write_text(json.dumps(candidate));proof['artifact_hashes']['ir.json']=hashlib.sha256((p/'ir.json').read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,'literal model update'):demo.verify(p,proof)
    def test_every_check_evidence_must_be_part_of_the_hash_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);proof=self.fixture(p);proof['artifact_hashes'].pop('fixture-only')
            with self.assertRaisesRegex(ValueError,'Unhashed check evidence'):demo.verify(p,proof)
if __name__=='__main__':unittest.main()
