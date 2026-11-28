import sys,unittest,tempfile,csv
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from attribute_sheet_sync import *

ID='shopify_US_7275390697570_41632324517986'
def row(**updates):
 d={'id':ID,'shopify_product_id':'7275390697570','shopify_variant_id':'41632324517986',
    'shopify_status':'SHOPIFY_VERIFIED','title':'Bowling Shirt','current_color':'One color','current_pattern':'',
    'approved_color':'','approved_pattern':'','proposed_color':'','proposed_pattern':'','color_qa':'UNKNOWN_OR_AMBIGUOUS','pattern_qa':'UNKNOWN_OR_AMBIGUOUS'}
 d.update(updates);return d
class TestAttributeSync(unittest.TestCase):
 def test_queue_product_scope_and_color_item_scope(self):
  r=[row(),row(id='shopify_US_7275390697570_41632324517987',shopify_variant_id='41632324517987')]
  evidence={x['id']:{'evidence_status':'VERIFIED','shopify_title':x['title'],'description':''} for x in r}
  self.assertEqual(len(build_pending(r,'PATTERN',evidence=evidence)),1)
  self.assertEqual(len(build_pending(r,'COLOR',evidence=evidence)),2)
 def test_apply_approved_rules_and_not_applicable(self):
  r=[row()];rules=[{'rule_key':'COLOR:ITEM:'+ID,'confirmed_value':'Blue'},
                    {'rule_key':'PATTERN:PRODUCT:7275390697570','confirmed_value':'NOT_APPLICABLE'}]
  self.assertEqual(apply_rules(r,rules),2)
  self.assertEqual(r[0]['approved_color'],'Blue')
  self.assertEqual(r[0]['pattern_qa'],'STAFF_NOT_APPLICABLE')
  self.assertEqual(len(build_pending(r,'PATTERN',rules=rules,evidence={ID:{'evidence_status':'VERIFIED'}})),0)
 def test_validates_identity_and_blocks_bad_values(self):
  src=row()
  p={'attribute':'COLOR','scope':'ITEM','item_id':ID,'product_id':src['shopify_product_id'],
     'variant_id':src['shopify_variant_id'],'confirmed_value':'Blue','status':'APPROVE'}
  self.assertEqual(validate(p,src),'VALID')
  self.assertEqual(validate({**p,'confirmed_value':'One color'},src),'MISSING_OR_GENERIC_VALUE')
  self.assertEqual(validate({**p,'product_id':'999'},src),'INVALID_IMMUTABLE_IDS')
  self.assertEqual(validate({**p,'status':'NOT_APPLICABLE'},src),'NA_NOT_ALLOWED_FOR_COLOR')
 def test_ingest_idempotent(self):
  src=row();p={'attribute':'PATTERN','scope':'PRODUCT','item_id':ID,'product_id':src['shopify_product_id'],
     'variant_id':src['shopify_variant_id'],'confirmed_value':'Floral','status':'APPROVE'}
  left,r,h,_=ingest([p],[],[],{ID:src});self.assertFalse(left);self.assertEqual(len(r),1)
  left2,r2,h2,_=ingest([p],r,h,{ID:src});self.assertFalse(left2);self.assertEqual(len(r2),1);self.assertEqual(len(h2),1)
 def test_preserve_staff_edits_if_evidence_cache_lost(self):
  old={"item_id":ID,"confirmed_value":"Blue","status":"APPROVE"}
  queue=build_pending([row()],"COLOR",old=[old]);self.assertEqual(queue[0]["confirmed_value"],"Blue")
 def test_refetch_gate(self):
  self.assertEqual(len(build_pending([row()],'PATTERN')),0)
 def test_description_only_explicit(self):
  self.assertEqual(explicit_color_description('garment color: Navy Blue. Decorative red logo'), 'Navy Blue')
  self.assertEqual(explicit_color_description('Blue red fishing graphic'),'')
if __name__=='__main__':unittest.main()
