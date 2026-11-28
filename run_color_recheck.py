import csv,collections,sys,json,copy
from pathlib import Path
from color_title_rules import apply_title_color,decide_color
src=Path('/mnt/data/audit(20261128-075019).csv')
evsrc=Path('/mnt/data/attribute_shopify_evidence.csv')
out=Path('/mnt/data/gmc_v1352_color_recheck');out.mkdir(exist_ok=True)
with src.open(encoding='utf-8-sig',newline='') as f:
 rd=csv.DictReader(f);fieldnames=rd.fieldnames; rows=list(rd)
with evsrc.open(encoding='utf-8-sig',newline='') as f:evidence={r['item_id']:r for r in csv.DictReader(f)}
pre=sum(bool(r['approved_color']) for r in rows)
changed,decisions=apply_title_color(rows,evidence)
post=sum(bool(r['approved_color']) for r in rows)
with (out/'audit_color_rechecked.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fieldnames);w.writeheader();w.writerows(rows)
with (out/'color_title_rule_decisions.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['item_id','approved_color','decision','title_evidence']);w.writerows(decisions)
assert len(rows)==4500 and changed==post-pre
assert len(set(r['id'] for r in rows))==len(rows)
counts=collections.Counter(x[2] for x in decisions)
summary={'scanned':len(rows),'before_approved_color':pre,'after_approved_color':post,'newly_approved_title_color':changed,'missing_color_after':len(rows)-post,'missing_color_percentage':round(100*(len(rows)-post)/len(rows),4),'color_coverage_percentage':round(100*post/len(rows),4),'decisions':dict(counts),'shopify_evidence_cached':len(evidence),'gmc_write':False,'note':'Offline only; no GMC/Google Sheets writes. Existing approvals preserved.'}
(out/'color_recheck_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
print('new approvals',[(r['id'],r['approved_color'],r['title'][:100]) for r in rows if r['color_qa']=='COLOR_TITLE_VERIFIED'])
for title,expected in [('Blue Flame Bowling Shirt','Blue'),('Black Labrador Hunting Shirt',''),('Black and red gradient Womens golf polo shirts','Black/Red')]:
 print('EXAMPLE',title,decide_color(title))
