"""Refetch verified Shopify description for missing-style hoodies only. Read-only.
Stores classification, never the full product description or API credentials.
"""
import argparse
import csv
import os
import re
from pathlib import Path
from engine import plain
from live import shopify_descriptions
from unified_rules import title_style_fallback, DESCRIPTION_EVIDENCE

FIELDS=['id','shopify_product_id','shopify_variant_id','status','cotton_present','evidence_source']

def refresh(out, batch_size=40):
    out=Path(out)
    target=[]
    with (out/'audit.csv').open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            if (row.get('shopify_status')=='SHOPIFY_VERIFIED' and not row.get('variant_style')
                    and not row.get('current_material')
                    and title_style_fallback(row)[1]=='HOODIE_NEEDS_DESCRIPTION'):
                target.append(row)
    existing={}
    path=out/DESCRIPTION_EVIDENCE
    if path.exists():
        with path.open(encoding='utf-8-sig',newline='') as f:
            existing={row['id']:row for row in csv.DictReader(f)}
    for start in range(0,len(target),batch_size):
        chunk=target[start:start+batch_size]
        records=[{'offerId':x['id'],'productAttributes':{}} for x in chunk]
        shopify_descriptions(records)
        for orig,rec in zip(chunk,records):
            description=plain((rec.get('productAttributes') or {}).get('description',''))
            status=rec.get('_shopify_status','')
            verified=(status=='SHOPIFY_VERIFIED' and
                      str(rec.get('_shopify_product_id',''))==orig.get('shopify_product_id') and
                      str(rec.get('_shopify_variant_id',''))==orig.get('shopify_variant_id'))
            yesno='YES' if re.search(r'\bcotton\b',description,re.I) else 'NO'
            if not verified or not description:
                yesno='UNKNOWN'
            existing[orig['id']]={'id':orig['id'],
                'shopify_product_id':orig['shopify_product_id'],
                'shopify_variant_id':orig['shopify_variant_id'],
                'status':status if verified else 'NOT_VERIFIED',
                'cotton_present':yesno,
                'evidence_source':'SHOPIFY_DEFAULT_DESCRIPTION_EXACT_VARIANT'}
    tmp=path.with_suffix('.tmp')
    with tmp.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader()
        writer.writerows(existing.values())
    tmp.replace(path)
    total=[existing[row['id']] for row in target]
    print('Hoodie descriptions targeted:',len(target))
    print('Verified cotton:',sum(x['cotton_present']=='YES' for x in total))
    print('Verified non-cotton:',sum(x['cotton_present']=='NO' for x in total))
    print('Description missing/unverified:',sum(x['cotton_present']=='UNKNOWN' for x in total))
    return total

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--out',default='out')
    a=p.parse_args()
    refresh(a.out)
