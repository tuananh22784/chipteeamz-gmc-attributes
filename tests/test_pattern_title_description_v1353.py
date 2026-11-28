import unittest
from pattern_title_description_rules import title_pattern,description_pattern,apply_pattern_fallback
from attribute_sheet_sync import validate_auto_evidence
class TestPatternFallback(unittest.TestCase):
 def test_title(self):
  self.assertEqual(title_pattern('Orange Argyle Golf Shirt')[0],'Argyle')
  self.assertEqual(title_pattern('Striped Bass Fishing Shirt')[0],'')
  self.assertEqual(title_pattern('Camo Splatter Polo')[0],'Camouflage')
  self.assertEqual(title_pattern('Leopard Argyle Outfit')[0],'Argyle')
 def test_description(self):
  self.assertEqual(description_pattern('A pink geometric pattern background.')[0],'Geometric')
  self.assertEqual(description_pattern('Appeals to abstract art lovers.')[0],'Abstract')
  self.assertEqual(description_pattern('Featuring a camouflage and black color scheme.')[0],'Camouflage')
 def test_end_to_end_validate(self):
  row={'id':'test','shopify_status':'SHOPIFY_VERIFIED','shopify_product_id':'1','shopify_variant_id':'2','approved_pattern':'','current_pattern':'','title':'Argyle Pattern Golf Polo'}
  e={'test':{'item_id':'test','product_id':'1','variant_id':'2','evidence_status':'VERIFIED','shopify_title':'Argyle Pattern Golf Polo','description':''}}
  trace={};counts,dec=apply_pattern_fallback([row],e,trace)
  self.assertEqual(counts['SHOPIFY_TITLE'],1)
  change={'item_id':'test','attribute':'PATTERN','previous':'','new_value':row['approved_pattern'],'qa_status':row['pattern_qa'],'evidence':row['pattern_evidence'],**trace[('test','PATTERN')]}
  validate_auto_evidence([row],[change])
 def test_conflict_ids(self):
  row={'id':'test','shopify_status':'SHOPIFY_VERIFIED','shopify_product_id':'1','shopify_variant_id':'2','approved_pattern':'','current_pattern':'','title':'Argyle Pattern Golf Polo'}
  e={'test':{'product_id':'1','variant_id':'3','evidence_status':'VERIFIED','shopify_title':'Argyle Pattern Golf Polo'}}
  counts,dec=apply_pattern_fallback([row],e)
  self.assertEqual(sum(counts.values()),0)
  self.assertEqual(dec[0]['decision'],'EVIDENCE_ID_MISMATCH')
if __name__=='__main__':unittest.main()
