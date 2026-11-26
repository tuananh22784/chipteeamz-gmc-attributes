import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unified_rules
import engine

class UnifiedRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules=unified_rules.rulebook()

    def row(self,style,item_id='shopify_US_1_2',**kwargs):
        row=dict(id=item_id,language='en',feed_label='US',shopify_status='SHOPIFY_VERIFIED',
                 variant_style=style,current_material='',current_pattern='',current_color='One color',
                 proposed_material='',approved_material='',approved_color='',approved_pattern='',
                 proposed_color='',proposed_pattern='',qa_status='NEEDS_REVIEW',material_qa='',review_reason='')
        row.update(kwargs)
        return row

    def test_every_confirmation_has_status(self):
        self.assertEqual(len(self.rules[2]),49)
        self.assertTrue(all(d['decision'] for d in self.rules[2]))

    def test_quarter_zip_100_polyester(self):
        for variant in ("Women's Short Sleeve Quarter-Zip", "Women's Short sleeve Quarter-zip", "Women's Short Sleeve Quarter Zip"):
            r=unified_rules.augment(self.row(variant),self.rules)
            self.assertEqual(r['approved_material'],'100% polyester')
            self.assertEqual(r['material_qa'],'MATERIAL_MASTER_VERIFIED')

    def test_women_polo_direct_confirmation(self):
        r=unified_rules.augment(self.row('Women Polo shirt'),self.rules)
        self.assertEqual(r['approved_material'],'100% polyester')

    def test_zip_hoodie_and_regular_hoodie_differ(self):
        a=unified_rules.augment(self.row('Zip Up Hoodie'),self.rules)
        b=unified_rules.augment(self.row('Hoodie'),self.rules)
        self.assertEqual(a['approved_material'],'100% polyester')
        self.assertEqual(b['approved_material'],'Cotton')

    def test_component_is_not_fabric_average(self):
        x=unified_rules.augment(self.row('Long sleeves UPF + Face shield'),self.rules)
        self.assertEqual(x['approved_material'],'')
        self.assertIn('100% polyester',x['material_component_1'])
        self.assertIn('95% polyester+5% spandex',x['material_component_2'])

    def test_non_apparel(self):
        x=unified_rules.augment(self.row('Duck / Tumbler Cup'),self.rules)
        self.assertEqual(x['material_decision'],'NON_APPAREL')

    def test_generic_not_globally_applied(self):
        x=unified_rules.augment(self.row('Unisex'),self.rules)
        self.assertEqual(x['approved_material'],'')

    def test_color_dependent_premium(self):
        x=unified_rules.augment(self.row('Unisex Premium T-shirt'),self.rules)
        self.assertEqual(x['material_decision'],'COLOR_DEPENDENT_REVIEW')

    def test_bare_cycling_jersey_not_polo(self):
        x=unified_rules.augment(self.row('Men Short Sleeve Jersey'),self.rules)
        self.assertEqual(x['material_decision'],'CONFLICTING_PRODUCT_FAMILY')

    def test_keeps_existing_material(self):
        x=unified_rules.augment(self.row('Hoodie',current_material='Linen'),self.rules)
        self.assertEqual(x['approved_material'],'')
        self.assertEqual(x['material_decision'],'KEEP_EXISTING')

    def test_unverified_never_approves(self):
        x=unified_rules.augment(self.row('Hoodie',shopify_status='SHOPIFY_NOT_FOUND'),self.rules)
        self.assertEqual(x['approved_material'],'')

    def test_migration_and_resume_schema(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            original=dict(self.row('Hoodie'),title='Hoodie',variant_options='Style:Hoodie',
                          shopify_product_id='1',shopify_variant_id='2',description_source='Shopify_default_description_API',
                          proposed_color='',proposed_pattern='',proposed_material='',color_evidence='',pattern_evidence='',
                          material_evidence='',color_qa='',pattern_qa='',material_qa='',review_reason='')
            with (out/'audit.csv').open('w',newline='',encoding='utf-8-sig') as f:
                w=csv.DictWriter(f,fieldnames=engine.COLUMNS[:-7]);w.writeheader();w.writerow(original)
            (out/'checkpoint.json').write_text(json.dumps(dict(schema=3,account='123',page_size=500,
                             next_page_token='next',pages=1,scanned=1,completed=False)))
            unified_rules.rebuild(out)
            with (out/'audit.csv').open(encoding='utf-8-sig') as f:
                result=list(csv.DictReader(f))
            self.assertEqual(len(result),1)
            self.assertEqual(result[0]['approved_material'],'Cotton')
            self.assertEqual(json.loads((out/'checkpoint.json').read_text())['scanned'],1)
            rr=engine.Reporter(out,append=True)
            try:
                self.assertEqual(rr.counts['scanned'],1)
            finally:
                rr.close()

if __name__=='__main__':unittest.main()
