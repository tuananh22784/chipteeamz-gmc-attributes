"""Independent read-only verification of prior approval evidence against saved audit.
Does not approve, revoke, or modify any GMC attributes. New evidence fields are checked
when present; old format is flagged if supporting text is not available.
"""
import argparse,csv,json,re
from pathlib import Path
from engine import PATTERNS

def check(audit,evidence,output):
    with open(audit,encoding='utf-8-sig',newline='') as f:items={r['id']:r for r in csv.DictReader(f)}
    with open(evidence,encoding='utf-8-sig',newline='') as f:approvals=list(csv.DictReader(f))
    results=[]
    for a in approvals:
        item=items.get(a['item_id']);src=a.get('evidence_source','') or ('TITLE' if a.get('evidence','')=='SHOPIFY_TITLE_EXPLICIT_PATTERN' else 'VARIANT' if 'VARIANT_COLOR' in a.get('evidence','') else 'UNCONFIRMED')
        status='PASS';why=''
        if not item:status='REVIEW';why='ITEM_NOT_IN_AUDIT'
        elif a['attribute']=='PATTERN':
            if src=='TITLE':
                title=a.get('evidence_text') or item['title']
                term=a['new_value'];rx=PATTERNS.get(term)
                # Only 1 pattern candidate and explicit label is robust evidence; old
                # audit title is an approximation when exact Shopify title is absent.
                explicitly=bool(rx and (re.search(r'(?i)(?:'+rx+r')\s+(?:pattern|print)\b',title) or re.search(r'(?i)\b(?:pattern|print)\s*[:\-]?\s*(?:'+rx+r')',title)))
                if not explicitly:status='REVIEW';why='TITLE_DOES_NOT_EXPLICITLY_LABEL_PATTERN'
                if a.get('qa_status')=='PATTERN_EXPLICIT_DESCRIPTION_VERIFIED':
                    why+=';LEGACY_QA_LABEL_MISMATCH' if why else 'LEGACY_QA_LABEL_MISMATCH'
                    if status=='PASS':status='LABEL_FIX_ONLY'
            elif src=='DESCRIPTION' and not a.get('evidence_text'):
                status='REVIEW';why='MISSING_DESCRIPTION_EVIDENCE_TEXT'
        results.append({'item_id':a['item_id'],'attribute':a['attribute'],'new_value':a['new_value'],
                        'status':status,'reason':why,'source':src,'audit_title':item.get('title','') if item else ''})
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    fields=['item_id','attribute','new_value','status','reason','source','audit_title']
    with (output/'prior_approval_provenance_check.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(results)
    counts={s:sum(x['status']==s for x in results) for s in ('PASS','LABEL_FIX_ONLY','REVIEW')}
    counts['total']=len(results);counts['write_mode']='READ_ONLY'
    (output/'prior_approval_provenance_summary.json').write_text(json.dumps(counts,indent=2),encoding='utf-8')
    return counts
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--audit',required=True);p.add_argument('--evidence',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();print(json.dumps(check(a.audit,a.evidence,a.out),indent=2))
