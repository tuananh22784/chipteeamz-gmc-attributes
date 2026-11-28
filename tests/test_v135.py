import unittest, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from attribute_sheet_sync import strict_auto_candidates,explicit_pattern_title,explicit_pattern_description,reconcile_pending,PENDING_FIELDS

class TestV135(unittest.TestCase):
 def row(self):
  return dict(id='shopify_US_10_20',shopify_product_id='10',shopify_variant_id='20',shopify_status='SHOPIFY_VERIFIED',current_color='One color',current_pattern='',approved_color='',approved_pattern='',review_reason='color_missing_or_ambiguous; pattern_not_explicit_in_title')
 def evidence(self,desc):return {'shopify_US_10_20':dict(item_id='shopify_US_10_20',product_id='10',variant_id='20',evidence_status='VERIFIED',description=desc)}
 def test_approved_explicit(self):
  r=self.row();d=self.evidence('Garment color: Navy Blue. Pattern: camouflage. Fish graphic in red.')
  self.assertEqual(strict_auto_candidates([r],d),{'COLOR':1,'PATTERN':1})
  self.assertEqual(r['approved_color'],'Navy Blue');self.assertEqual(r['approved_pattern'],'Camouflage')
 def test_ambiguous_not_auto(self):
  r=self.row();d=self.evidence('Blue and red fish on the shirt with abstract inspiration and floral motifs')
  self.assertEqual(strict_auto_candidates([r],d),{'COLOR':0,'PATTERN':0})
 def test_source_id_mismatch(self):
  r=self.row();d=self.evidence('garment color: Black. Pattern: plaid')
  d[r['id']]['variant_id']='999'
  self.assertEqual(strict_auto_candidates([r],d),{'COLOR':0,'PATTERN':0})
 def test_pattern_multiple_conflict(self):self.assertEqual(explicit_pattern_description('Pattern: plaid. Pattern: striped.'),'')
 def test_explicit_title_pattern(self):
  self.assertEqual(explicit_pattern_title('Camouflage Pattern Bowling Shirt'), 'Camouflage')
  self.assertEqual(explicit_pattern_title('Bowling Shirt, Blue Stars and Red Flowers'), '')
 def test_title_description_conflict(self):
  r=self.row();e=self.evidence('Pattern: plaid.')
  e[r['id']]['shopify_title']='Camouflage Pattern Bowling Shirt'
  self.assertEqual(strict_auto_candidates([r],e)['PATTERN'],0)
 def test_pending_concurrent_guard(self):
  class Sheet:
   def get_tab(self,*_):return [{'item_id':'now edited'}]
  with self.assertRaisesRegex(RuntimeError,'CONCURRENT_SHEET_CHANGE'):
   reconcile_pending(Sheet(),'Pending_Color',[{'item_id':'old'}],[],PENDING_FIELDS)

if __name__=='__main__':unittest.main()
