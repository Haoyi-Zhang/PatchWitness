import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from bounded_decision import pack_retained,Budget
from consumer_policy import decide,direct
from checker import Invalid
class ConsumerPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.specs={s['id']:s for s in json.loads((ROOT/'data/functional-programs.json').read_text())['cases']}
        retained={s['id']:s for s in json.loads((ROOT/'results/functional-diagnostics/cases.json').read_text())}
        cls.records={key:pack_retained(spec,retained[key]) for key,spec in cls.specs.items()}
    def test_policy_requires_more_than_global_refinement(self):
        spec=self.specs['F08'];record=self.records['F08']
        self.assertTrue(record['bounded_refinement'])
        base=dict(require_repair=True,allow_old_faults=True,required_inputs=[])
        self.assertTrue(decide(spec,record,base)['approved'])
        total=dict(base,allow_old_faults=False)
        self.assertFalse(decide(spec,record,total)['approved'])
        fault=next(row['input'] for row in record['rows'] if row['after'][0]=='fault')
        self.assertFalse(decide(spec,record,dict(base,required_inputs=[fault]))['approved'])
    def test_same_information_direct_result_on_every_pair(self):
        for key,spec in self.specs.items():
            for allow in (False,True):
                policy=dict(require_repair=True,allow_old_faults=allow,required_inputs=[])
                self.assertEqual(decide(spec,self.records[key],policy),direct(spec,policy))
    def test_required_inputs_are_typed_unique_and_in_the_authoritative_domain(self):
        spec=self.specs['F01'];record=self.records['F01']
        for inputs in ([[True]],[[0],[0]],[[10**9]],[[0,0]]):
            with self.assertRaises(Invalid):decide(spec,record,dict(require_repair=True,allow_old_faults=True,required_inputs=inputs))
        with self.assertRaises(Invalid):decide(spec,record,dict(require_repair=1,allow_old_faults=True,required_inputs=[]))
    def test_record_exhaustion_does_not_supply_policy_approval(self):
        with self.assertRaises(RuntimeError):decide(self.specs['F01'],self.records['F01'],dict(require_repair=True,allow_old_faults=True,required_inputs=[]),Budget(0))
    def test_complete_record_replay_precedes_policy_interpretation(self):
        spec=self.specs['F08'];bad=copy.deepcopy(self.records['F08']);bad['rows'].pop()
        with self.assertRaises(Invalid):decide(spec,bad,dict(require_repair=False,allow_old_faults=True,required_inputs=[]))
    def test_direct_policy_does_not_share_the_checked_policy_interpreter(self):
        spec=self.specs['F08'];record=self.records['F08']
        policy=dict(require_repair=True,allow_old_faults=False,required_inputs=[])
        expected=direct(spec,policy)
        self.assertFalse(expected['approved'])
        with patch('consumer_policy.interpret',return_value={'approved':True}):
            self.assertTrue(decide(spec,record,policy)['approved'])
            self.assertEqual(direct(spec,policy),expected)
if __name__=='__main__':unittest.main()
