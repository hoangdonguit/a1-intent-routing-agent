import importlib.util,json,tempfile,unittest,sys
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('finish_pilot',Path(__file__).resolve().parents[1]/'ops/finish_bgp_pilot.py');finish=importlib.util.module_from_spec(spec);spec.loader.exec_module(finish)
class FinishPilotTest(unittest.TestCase):
    def state(self,keys):return {'calls':len(keys),'trajectories':{k:{'status':'environment_error','rounds':[{'index':0}]} for k in keys},'last_restore':{'status':'pass'}}
    def invoke(self,d,state,child=None):
        (d/'state.json').write_text(json.dumps(state))
        with patch.object(finish,'OUT',d),patch.object(finish.os,'geteuid',return_value=0),patch.object(sys,'argv',['finish']),patch.object(finish.subprocess,'run',side_effect=child) as run:
            finish.main();return run
    def test_six_terminal_verdicts_are_never_reopened(self):
        with tempfile.TemporaryDirectory() as d:
            run=self.invoke(Path(d),self.state(finish.EXPECTED));run.assert_not_called()
    def test_uncertain_inflight_is_not_retried(self):
        with tempfile.TemporaryDirectory() as d:
            state=self.state(['dev_ebgp_prefix_01--B1']);state['trajectories']['dev_ebgp_prefix_01--B1']['inflight']='uncertain'
            with self.assertRaisesRegex(RuntimeError,'Uncertain'):self.invoke(Path(d),state)
    def test_stop_marker_prevents_generation(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);(d/'STOP').touch();run=self.invoke(d,self.state([]));run.assert_not_called()
    def test_only_missing_trajectories_are_completed_in_bounded_sessions(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);old=self.state(sorted(k for k in finish.EXPECTED if 'prefix_01' in k));remaining=sorted(finish.EXPECTED-set(old['trajectories']))
            def child(argv,**kw):
                self.assertIn('run',argv);self.assertNotIn('resume',argv);self.assertEqual(argv[-2:],['--calls','2'])
                s=json.loads((d/'state.json').read_text())
                for key in remaining:
                    if key not in s['trajectories']:
                        s['trajectories'][key]={'status':'fail','rounds':[{'index':0}]};s['calls']+=1;break
                (d/'state.json').write_text(json.dumps(s))
                return type('Result',(),{'returncode':0})()
            run=self.invoke(d,old,child);self.assertEqual(run.call_count,3)
            after=json.loads((d/'state.json').read_text())
            for key,value in old['trajectories'].items():self.assertEqual(after['trajectories'][key],value)
if __name__=='__main__':unittest.main()
