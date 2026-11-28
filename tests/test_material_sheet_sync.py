import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from material_sheet_sync import *

class MaterialSheetSyncTest(unittest.TestCase):
 def test_material(self):
  self.assertEqual(normalize_material('100% Polyester'),'100% Polyester')
  self.assertEqual(normalize_material('96% Polyester, 4% Spandex'),'96% Polyester, 4% Spandex')
  self.assertEqual(normalize_material('90% cotton, 50% poly'), '')
  self.assertEqual(normalize_material('yes'),'')
 def row(self,**kw):
  x={'item_id':'shopify_US_7333767708770_41879469621346','scope':'ITEM','confirmed_style':'T-shirt','resolved_style':'','confirmed_material':'Cotton','status':'APPROVE'};x.update(kw);return x
 def test_review_and_clear(self):
  rest,rules,hist,stats=ingest([self.row()],[],[])
  self.assertEqual(len(rest),0);self.assertEqual(len(rules),1);self.assertEqual(len(hist),1)
  rest2,rules2,hist2,stats2=ingest(rest,rules,hist)
  self.assertEqual(len(rules2),1);self.assertEqual(len(hist2),1)
 def test_unknown_global_rejected(self):
  self.assertEqual(validate_pending(self.row(scope='STYLE',resolved_style='Shirt',confirmed_style='Shirt')), 'GENERIC_STYLE_NOT_GLOBAL')
 def test_conflicting_update(self):
  a=self.row();_,rr,hh,_=ingest([a],[],[])
  b=self.row(confirmed_material='100% Polyester')
  remain,rr2,hh2,stat=ingest([b],rr,hh)
  self.assertEqual(remain[0]['status'],'RULE_CONFLICT');self.assertEqual(len(rr2),1)
 def test_queue(self):
  from tempfile import TemporaryDirectory
  with TemporaryDirectory() as td:
   file=Path(td)/'audit.csv'
   export_csv(file,[{'id':self.row()['item_id'],'approved_material':'','current_material':'','shopify_status':'SHOPIFY_VERIFIED','material_decision':'REVIEW_MISSING_STYLE','shopify_product_id':'7333767708770','shopify_variant_id':'41879469621346','title':'Hunting Shirt'}],['id','approved_material','current_material','shopify_status','material_decision','shopify_product_id','shopify_variant_id','title'])
   queue=build_pending(file);self.assertEqual(len(queue),1)
   self.assertEqual(queue[0]['scope'],'ITEM')
if __name__=='__main__': unittest.main()
