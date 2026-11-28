import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from refresh_hoodie_descriptions import refresh
from unified_rules import augment,rulebook,description_evidence

class HoodieDescriptionEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules=rulebook()
    def data(self, title, vid):
        return dict(id=f'shopify_US_123_{vid}',shopify_product_id='123',shopify_variant_id=str(vid),
                    title=title,shopify_status='SHOPIFY_VERIFIED',variant_style='',
                    current_color='One color',current_pattern='',current_material='',
                    approved_material='',approved_color='',approved_pattern='',
                    proposed_color='',proposed_pattern='',proposed_material='',
                    review_reason='')
    @patch('refresh_hoodie_descriptions.shopify_descriptions')
    def test_live_refetch_classification_without_raw_description_persistence(self, fetch):
        rows=[self.data('Standard Hoodie 1',10),self.data('Standard Hoodie 2',11),self.data('Standard Hoodie 3',12)]
        def fake(items):
            for item in items:
                vid=item['offerId'].rsplit('_',1)[-1]
                item['_shopify_status']='SHOPIFY_VERIFIED'
                item['_shopify_product_id']='123'
                item['_shopify_variant_id']=vid
                item['productAttributes']['description']={
                    '10':'<p>100% Cotton classic hoodie</p>',
                    '11':'<p>Polyester air layer hoodie</p>',
                    '12':''}[vid]
        fetch.side_effect=fake
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)
            with (path/'audit.csv').open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
            refresh(path)
            evidence=description_evidence(path)
            self.assertEqual(augment(rows[0],self.rules,evidence)['approved_material'],'Cotton')
            self.assertEqual(augment(rows[1],self.rules,evidence)['approved_material'],'100% polyester')
            self.assertEqual(augment(rows[2],self.rules,evidence)['approved_material'],'')
            self.assertNotIn('100% Cotton',(path/'style_description_evidence.csv').read_text())

if __name__=='__main__': unittest.main()
