import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import engine
import live

class ExtractionTests(unittest.TestCase):
    def test_color_compound_and_pattern(self):
        r = engine.extract('Navy Blue Red Geometric Dart Shirt', 'Material: Polyester')
        self.assertEqual(r['proposed_color'], 'Navy Blue/Red')
        self.assertEqual(r['proposed_pattern'], 'Geometric')
    def test_no_generic_pattern(self):
        r = engine.extract('Funny Duck Golf Shirt', 'Try our splatter patterns on other designs')
        self.assertEqual(r['proposed_pattern'], '')
    def test_multi_material_blocked(self):
        r = engine.extract('Cotton Tee', 'Solid colors 100% cotton. Heather colors 52% cotton 48% polyester.', 'T-Shirt')
        self.assertEqual(r['proposed_material'], '')
    def test_hoodie_material_requires_qa(self):
        r = engine.extract('Fishing Shirt', 'Material: polyester', 'Hoodie')
        self.assertEqual(r['proposed_material'], 'Polyester')
        self.assertIn('material_requires_variant_style_confirmation', r['review_reason'])
    def test_flags_not_pattern(self):
        self.assertEqual(engine.extract('American Flag Striped Shirt', '')['proposed_pattern'], '')
    def test_option_color(self):
        self.assertEqual(engine.extract('Golf shirt', '', selected_color='Forest Green')['proposed_color'],'Forest Green')
    def test_not_auto_eligible(self):
        row={'offerId':'shopify_US_1_2','_shopify_status':'SHOPIFY_VERIFIED','_shopify_product_id':'1','_shopify_variant_id':'2',
             '_shopify_title':'Red Camo Shirt','_variant_style':'Polo','productAttributes':{'title':'Red Camo Shirt','description':'Material: Polyester','color':'One color'}}
        with tempfile.TemporaryDirectory() as directory:
            reporter=engine.Reporter(directory)
            reporter.process(row)
            reporter.close()
            summary=reporter.summary()
            self.assertEqual(summary['ready_for_qa'],1)
            self.assertEqual(summary['auto_fix_eligible'],0)
            with (Path(directory)/'ready_for_qa.csv').open(encoding='utf-8-sig') as f:
                self.assertEqual(sum(1 for _ in csv.DictReader(f)),1)
            with (Path(directory)/'auto_fix_eligible.csv').open(encoding='utf-8-sig') as f:
                self.assertEqual(sum(1 for _ in csv.DictReader(f)),0)
    def test_unverified_no_candidates(self):
        row={'offerId':'legacy','productAttributes':{'title':'Red Camo Shirt','description':'100% Polyester'}}
        with tempfile.TemporaryDirectory() as directory:
            reporter=engine.Reporter(directory)
            reporter.process(row)
            reporter.close()
            self.assertEqual(reporter.summary()['has_proposals'] if reporter.counts['has_proposals'] else 0,0)
    @patch('live.shopify_graphql')
    def test_exact_variant_over_100(self, graph):
        def mock(q, params):
            result=[]
            for gid in params['ids']:
                if gid.endswith('/123'):
                    result.append({'__typename':'Product','legacyResourceId':'123','title':'Black Bowling','descriptionHtml':'<p>100% polyester</p>'})
                elif gid.endswith('/999'):
                    result.append({'__typename':'ProductVariant','legacyResourceId':'999',
                                   'product':{'legacyResourceId':'123'},
                                   'selectedOptions':[{'name':'Color','value':'Black'},{'name':'Size','value':'L'}]})
                else:
                    result.append(None)
            return {'nodes':result}
        graph.side_effect=mock
        rows=[{'offerId':'shopify_US_123_999','productAttributes':{'title':'Black Bowling'}}]
        live.shopify_descriptions(rows)
        self.assertEqual(rows[0]['_shopify_status'],'SHOPIFY_VERIFIED')
        self.assertIn('polyester',rows[0]['productAttributes']['description'])
        self.assertEqual(rows[0]['_selected_color'],'Black')
    @patch('live.shopify_graphql')
    def test_reject_variant_different_product(self, graph):
        graph.side_effect=lambda q,p:{'nodes':[({'legacyResourceId':'123','title':'X','descriptionHtml':'100% polyester'} if gid.endswith('/123') else
                {'legacyResourceId':'999','product':{'legacyResourceId':'789'},'selectedOptions':[]}) for gid in p['ids']]}
        rows=[{'offerId':'shopify_US_123_999'}]
        live.shopify_descriptions(rows)
        self.assertEqual(rows[0]['_shopify_status'],'VARIANT_NOT_FOUND_OR_WRONG_PRODUCT')
    @patch('live.shopify_descriptions')
    @patch('live.merchant_page')
    def test_live_two_pages_checkpoint(self, pages, descriptions):
        def enrich(items):
            for row in items:
                row['_shopify_status']='SHOPIFY_VERIFIED'
                row['_shopify_title']=row['productAttributes']['title']
        descriptions.side_effect = enrich
        pages.side_effect=[
            ([{'offerId':'shopify_US_1_10', 'productAttributes':{'title':'Black Camo Shirt','description':'Material: Polyester','color':'One color'}}], 'nexttoken'),
            ([{'offerId':'shopify_US_1_11', 'productAttributes':{'title':'Red Camo Shirt','description':'Material: Polyester','color':'One color'}}], '')]
        from argparse import Namespace
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {'GMC_ACCOUNT_ID':'123'}):
            summary=engine.run_live(Namespace(out=folder,resume=False,page_size=1,max_pages=0))
            self.assertEqual(summary['scanned'],2)
            self.assertEqual(summary['pages'],2)
            self.assertTrue(summary['completed'])
            self.assertEqual(summary['auto_fix_eligible'],0)
            with (Path(folder)/'audit.csv').open(encoding='utf-8-sig') as f:
                self.assertEqual(sum(1 for _ in csv.DictReader(f)),2)
            self.assertEqual(pages.call_args_list[1].args[0], 'nexttoken')

if __name__ == '__main__':
    unittest.main()
