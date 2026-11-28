import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from refresh_shirt_jersey import classify
from unified_rules import augment,rulebook

class ShirtJerseyTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.rules=rulebook()
 def row(self,title):
  return dict(id='shopify_US_123_456',shopify_product_id='123',shopify_variant_id='456',shopify_status='SHOPIFY_VERIFIED',variant_style='',title=title,current_material='',current_color='One color',current_pattern='',approved_color='',approved_pattern='',approved_material='',proposed_color='',proposed_pattern='',proposed_material='',review_reason='')
 def test_generic_shirt_remains_review(self):
  self.assertEqual(classify('Funny darts shirts for men','','Great gift for dart fans')[1],'NO_VERIFIED_SUBTYPE')
 def test_bowling_jersey_remains_review(self):
  self.assertEqual(classify('Bowling Jerseys','','')[1],'BOWLING_JERSEY_REVIEW')
 def test_explicit_tshirt(self):
  self.assertEqual(classify('','T-shirts','')[0],'T-shirt')
 def test_labelled_description(self):
  self.assertEqual(classify('','', 'Product Type: T-shirt\nFabric: Cotton')[0],'T-shirt')
 def test_description_marketing_is_not_enough(self):
  self.assertEqual(classify('','', 'Wear your favorite t-shirt to the party')[1],'NO_VERIFIED_SUBTYPE')
 def test_conflict(self):
  self.assertEqual(classify('T-shirt','Polo Shirt','')[1],'CONFLICTING_STYLE_REVIEW')
 def test_refetch_allows_explicit(self):
  r=self.row('Funny darts shirts for men')
  ev={r['id']:{'shopify_product_id':'123','shopify_variant_id':'456','status':'SHOPIFY_VERIFIED','decision':'EXPLICIT_STYLE','resolved_style':'T-shirt','evidence_excerpt':'PRODUCT_TYPE t-shirt'}}
  result=augment(r,self.rules,shirt_evidence=ev)
  self.assertEqual(result['approved_material'],'Cotton')
  self.assertEqual(result['style_resolution_status'],'REFETCH_EXPLICIT_STYLE')
 def test_refetch_wrong_variant(self):
  r=self.row('Funny darts shirts for men')
  ev={r['id']:{'shopify_product_id':'123','shopify_variant_id':'999','status':'SHOPIFY_VERIFIED','decision':'EXPLICIT_STYLE','resolved_style':'T-shirt'}}
  self.assertEqual(augment(r,self.rules,shirt_evidence=ev)['approved_material'],'')
 def test_refetch_cannot_override_bowling_jersey_from_title(self):
  r=self.row('Bowling Jerseys IPHW')
  ev={r['id']:{'shopify_product_id':'123','shopify_variant_id':'456','status':'SHOPIFY_VERIFIED','decision':'BOWLING_JERSEY_REVIEW','resolved_style':''}}
  self.assertEqual(augment(r,self.rules,shirt_evidence=ev)['approved_material'],'')
if __name__=='__main__':unittest.main()
