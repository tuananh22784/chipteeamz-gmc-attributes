"""Offline audit of 31 unresolved rows; no network or file mutation of stored audit."""
import csv,collections,json,argparse
from pathlib import Path
from unified_rules import title_style_fallback,rulebook,augment

def preview(infile,out):
 out=Path(out);out.mkdir(exist_ok=True,parents=True)
 with open(infile,encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
 selected=[r for r in rows if r.get('style_resolution_status') in ('TITLE_INSUFFICIENT','AMBIGUOUS_JERSEY')]
 decisions=[]
 for r in selected:
  style,status,why=title_style_fallback(r)
  decisions.append({'id':r['id'],'product_id':r['shopify_product_id'],'variant_id':r['shopify_variant_id'],'title':r['title'],
       'title_style':style,'title_status':status,'offline_result':'NEEDS_SHOPIFY_REFETCH' if status in ('TITLE_INSUFFICIENT','AMBIGUOUS_JERSEY') else 'REVIEW_CHANGED','explanation':why})
 with (out/'shirt_jersey_offline_31.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(decisions[0]) if decisions else ['id']);w.writeheader();w.writerows(decisions)
 count=collections.Counter(x['title_status'] for x in decisions)
 summary={'source':'existing 59-row offline pending list; 31 Shirt/Jersey rows only', 'target_items':len(decisions),'unique_offers':len({x['id'] for x in decisions}),
          'by_title_status':dict(count),'auto_approved_from_existing_evidence':0,'refetch_needed':sum(x['offline_result']=='NEEDS_SHOPIFY_REFETCH' for x in decisions),
          'note':'The current local audit contains no Shopify Product Type / full Description. Zero new approved entries without fresh evidence.', 'gmc_write':False}
 (out/'shirt_jersey_offline_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--out',required=True);a=p.parse_args();preview(a.input,a.out)
