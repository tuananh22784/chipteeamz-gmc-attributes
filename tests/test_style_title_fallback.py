import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from unified_rules import title_style_fallback,augment,rulebook

class TitleFallbackTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.rules=rulebook()
 def row(self,title,style='',current_material='',verified='SHOPIFY_VERIFIED'):
  return dict(id='shopify_US_1_2',shopify_product_id='1',shopify_variant_id='2',shopify_status=verified,variant_style=style,title=title,
              current_material=current_material,current_color='One color',current_pattern='',
              approved_color='',approved_pattern='',approved_material='',proposed_color='',
              proposed_pattern='',proposed_material='',review_reason='')
 def test_cotton_tshirt(self):
  r=augment(self.row('Bowling Team Standard T-Shirt, M / Black'),self.rules)
  self.assertEqual(r['approved_material'],'Cotton')
  self.assertEqual(r['style_resolution_source'],'GMC_TITLE_FALLBACK')
 def test_cotton_sweatshirt(self):
  r=augment(self.row('Standard Crew Neck Sweatshirt, M / Red'),self.rules)
  self.assertEqual(r['approved_material'],'Cotton')
 def test_cotton_long_sleeves(self):
  self.assertEqual(augment(self.row('Fishing Standard Long Sleeve / L'),self.rules)['approved_material'],'Cotton')
 def test_upf_tshirt_not_cotton(self):
  self.assertEqual(augment(self.row('Our brand T-Shirt UV protection, M / White'),self.rules)['approved_material'],'100% polyester')
 def test_hoodie_ambiguous(self):
  r=augment(self.row('Bowling Standard Hoodie, L / Black'),self.rules)
  self.assertEqual(r['approved_material'],'')
  self.assertEqual(r['style_resolution_status'],'HOODIE_NEEDS_DESCRIPTION')
 def test_unqualified_polo(self):
  r=augment(self.row('Funny Shark Bowling Performance Polo Bowling Shirts',style=''),self.rules)
  self.assertEqual(r['approved_material'],'100% polyester')
  self.assertEqual(r['style_resolution_status'],'TITLE_EXPLICIT_USER_POLO_RULE')
 def test_hoodie_cotton_evidence(self):
  r=self.row('Bowling Standard Hoodie, L / Black')
  ev={r['id']:{'shopify_product_id':'1','shopify_variant_id':'2','cotton_present':'YES'}}
  self.assertEqual(augment(r,self.rules,ev)['approved_material'],'Cotton')
 def test_hoodie_non_cotton_evidence(self):
  r=self.row('Bowling Standard Hoodie, L / Black')
  ev={r['id']:{'shopify_product_id':'1','shopify_variant_id':'2','cotton_present':'NO'}}
  self.assertEqual(augment(r,self.rules,ev)['approved_material'],'100% polyester')
 def test_hoodie_wrong_variant_evidence_fails_closed(self):
  r=self.row('Bowling Standard Hoodie, L / Black')
  ev={r['id']:{'shopify_product_id':'1','shopify_variant_id':'999','cotton_present':'NO'}}
  self.assertEqual(augment(r,self.rules,ev)['approved_material'],'')
 def test_non_apparel(self):
  r=augment(self.row('Personalized Infinity Canvas, 10x8in'),self.rules)
  self.assertEqual(r['material_decision'],'NON_APPAREL')
 def test_generic_shirt_hold(self):
  r=augment(self.row('Funny darts shirts for men and women, Red / 2XL'),self.rules)
  self.assertEqual(r['material_decision'],'REVIEW_MISSING_STYLE')
 def test_variant_wins_title(self):
  r=augment(self.row('Funny Hoodie',style='Long Sleeve UPF'),self.rules)
  self.assertEqual(r['approved_material'],'100% polyester')
  self.assertEqual(r['style_resolution_source'],'SHOPIFY_VARIANT')
 def test_unverified(self):
  r=augment(self.row('Standard T-shirt',verified='SHOPIFY_NOT_FOUND'),self.rules)
  self.assertEqual(r['approved_material'],'')
 def test_existing_material(self):
  r=augment(self.row('Standard T-shirt',current_material='Linen'),self.rules)
  self.assertEqual(r['approved_material'],'')
