import csv
import json
import tempfile
import unittest
from pathlib import Path
from run_refetch_batches import run

class BoundedRefetchTests(unittest.TestCase):
    def make_fixture(self, root):
        p=Path(root)
        with (p/'audit.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=['id','approved_color','approved_pattern','approved_material'])
            w.writeheader(); w.writerow({'id':'abc','approved_material':'Cotton'})
        (p/'checkpoint.json').write_text(json.dumps({'scanned':1,'pages':9,'next_page_token':'xyz'}))
        return p

    def test_three_batches_no_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.make_fixture(d)
            calls=[]
            def mock(out,limit):
                calls.append(limit)
                return {'eligible_total':1500-(len(calls)-1)*500,'fetched_now':500,'cached_total':len(calls)*500,'result':{'VERIFIED':500},'gmc_write':False}
            res=run(p,batches=3,fetcher=mock)
            self.assertEqual(calls,[500,500,500])
            self.assertEqual(res['cached_total'],1500)
            self.assertEqual(json.loads((p/'checkpoint.json').read_text())['pages'],9)
    def test_stop_on_exhaustion(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.make_fixture(d)
            calls=[]
            def mock(out,limit):
                calls.append(1)
                return {'fetched_now':60,'cached_total':60,'result':{'VERIFIED':60}}
            self.assertEqual(run(p,batches=3,fetcher=mock)['executed_batches'],1)
    def test_reject_mutating_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.make_fixture(d)
            def mock(out,limit):
                (p/'checkpoint.json').write_text('{}')
                return {'fetched_now':1,'cached_total':1,'result':{'VERIFIED':1}}
            with self.assertRaisesRegex(RuntimeError,'CHECKPOINT_MUTATED'):
                run(p,fetcher=mock)
    def test_bad_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.make_fixture(d)
            for n in [0,4]:
                with self.assertRaises(ValueError):run(p,batches=n)
if __name__=='__main__':unittest.main()
