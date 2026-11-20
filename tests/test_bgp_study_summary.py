"""Reporting must not fabricate unsampled repair rounds or missing costs."""
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('bgp_study',Path(__file__).resolve().parents[1]/'ops/bgp_plan_study.py')
study=importlib.util.module_from_spec(spec);spec.loader.exec_module(study)
class StudySummaryTest(unittest.TestCase):
    def test_stagnation_does_not_impute_unobserved_milestones(self):
        rounds=[{'index':i,'status':'fail','metrics':{'input_tokens':10,'output_tokens':20,'api_total_seconds':1}} for i in [0,1]]
        state={'calls':2,'trajectories':{'case--A2':{'status':'fail','stop_reason':'stagnated','rounds':rounds}}}
        row=study.summary(state)['trajectories'][0]
        self.assertEqual(row['repair_milestones_observed'],{'1':'fail','3':None,'5':None})
        self.assertEqual(row['metrics']['input_tokens'],20)
        self.assertEqual(row['generations_observed'],2)
    def test_missing_token_measurement_stays_unavailable(self):
        state={'calls':1,'trajectories':{'case--B1':{'status':'fail','rounds':[{'index':0,'status':'fail','metrics':{}}]}}}
        row=study.summary(state)['trajectories'][0]
        self.assertIsNone(row['metrics']['input_tokens'])
        self.assertEqual(row['repair_milestones_observed'],{'1':None,'3':None,'5':None})
if __name__=='__main__':unittest.main()
