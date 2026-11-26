import csv
import tempfile
import unittest
from pathlib import Path
import engine

class PatternDescriptionFallbackTests(unittest.TestCase):
    def test_explicit_description_fallback(self):
        r=engine.extract('Funny Duck Bowling Polo', 'This shirt features a camouflage pattern with a duck design.')
        self.assertEqual(r['proposed_pattern'],'Camouflage')
        self.assertTrue(r['pattern_evidence'].startswith('shopify_description:'))
    def test_title_wins_description(self):
        r=engine.extract('Argyle Golf Shirt', 'This shirt features a floral pattern.')
        self.assertEqual(r['proposed_pattern'],'Argyle')
        self.assertTrue(r['pattern_evidence'].startswith('shopify_product_title:'))
    def test_generic_marketing_blocked(self):
        r=engine.extract('Funny Duck Golf Shirt', 'Try our splatter patterns on other designs.')
        self.assertEqual(r['proposed_pattern'],'')
    def test_multiple_description_patterns_blocked(self):
        r=engine.extract('Golf Polo', 'This shirt features a camouflage and plaid pattern.')
        self.assertEqual(r['proposed_pattern'],'')
    def test_no_generic_printed(self):
        r=engine.extract('Printed bowling shirt','High quality sublimation printed apparel.')
        self.assertEqual(r['proposed_pattern'],'')
    def test_flag_exception(self):
        r=engine.extract('American Flag Bowling Shirt', 'This shirt features patriotic striped flag design.')
        self.assertEqual(r['proposed_pattern'],'')
    def test_verified_description_requires_review(self):
        row={'offerId':'shopify_US_1_2','_shopify_status':'SHOPIFY_VERIFIED',
             '_shopify_product_id':'1','_shopify_variant_id':'2',
             '_shopify_title':'Funny Duck Bowling Polo',
             '_variant_style':'Polo',
             'productAttributes':{'title':'Funny Duck Bowling Polo','description':'This shirt features a camouflage pattern.', 'color':'One color'}}
        with tempfile.TemporaryDirectory() as d:
            reporter=engine.Reporter(d)
            reporter.process(row)
            reporter.close()
            with (Path(d)/'audit.csv').open(encoding='utf-8-sig',newline='') as f:
                result=list(csv.DictReader(f))[0]
            self.assertEqual(result['proposed_pattern'],'Camouflage')
            self.assertEqual(result['pattern_qa'],'PATTERN_DESCRIPTION_REVIEW')
            self.assertEqual(result['approved_pattern'],'')
            self.assertIn('pattern_description_requires_qa',result['review_reason'])
    def test_unverified_description_no_inference(self):
        row={'offerId':'legacy','productAttributes':{'title':'Duck Golf','description':'This product features a camouflage pattern.'}}
        with tempfile.TemporaryDirectory() as d:
            reporter=engine.Reporter(d)
            reporter.process(row)
            reporter.close()
            with (Path(d)/'audit.csv').open(encoding='utf-8-sig',newline='') as f:
                result=list(csv.DictReader(f))[0]
            self.assertEqual(result['proposed_pattern'],'')

if __name__=='__main__':unittest.main()
