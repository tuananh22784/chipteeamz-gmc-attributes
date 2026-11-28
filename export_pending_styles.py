"""Read-only reporting for unresolved style identity. Does not alter checkpoint."""
import argparse
import collections
import csv
import json
from pathlib import Path

FIELDS=['id','shopify_product_id','shopify_variant_id','title','variant_options','variant_style',
        'style_resolution_source','style_resolution_status','material_decision','material_reason']

def report(out):
    out=Path(out)
    pending=[]
    with (out/'audit.csv').open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            if row.get('material_decision')=='REVIEW_MISSING_STYLE':
                pending.append({k:row.get(k,'') for k in FIELDS})
    with (out/'missing_style_after_hoodie_polo.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();writer.writerows(pending)
    counts=collections.Counter(x['style_resolution_status'] for x in pending)
    summary={'unresolved_missing_style':len(pending),'by_style_status':dict(counts),
             'description_refetch_required':counts.get('HOODIE_NEEDS_DESCRIPTION',0),
             'source':'existing audit.csv (read-only)', 'gmc_write':False}
    (out/'missing_style_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',default='out')
    args=parser.parse_args();report(args.out)
