"""Read-only Pattern title + Shopify description precision fallback, V1.3.5.3.
Does not alter Color or Material. Never assumes absent pattern means NOT_APPLICABLE.
"""
import re
from engine import PATTERNS,plain

ALIAS_RX={k:re.compile(v,re.I) for k,v in PATTERNS.items()}
MOTIF_CONFLICT=re.compile(r'\b(?:leopard|zebra|cheetah|plaid|tartan|camouflage|camo|halftone|splatter|tie[ -]?dye|checkerboard|checkered|polka[ -]?dots?)\b',re.I)
MARKETING=re.compile(r'\b(?:other patterns?|other designs?|choose from|shop our|browse our|our collection|such as|for example|e\\.g\\.|lovers|appeals to|inspired by|collection of)\b',re.I)
DESIGN_CONTEXT=re.compile(r'\b(?:pattern|print|graphic|design|background|featured?|featuring|covered|fabric|all[ -]?over|scheme)\b',re.I)

def _pattern_hits(text):
    """Pattern candidates in left-to-right order, excluding known non-design uses."""
    found=[]
    for name,rx in ALIAS_RX.items():
        for m in rx.finditer(text):
            nearby=text[max(0,m.start()-20):min(len(text),m.end()+35)]
            if name=='Striped' and re.search(r'\b(?:striped bass|striper|stars and stripes|american flag)\b',nearby,re.I) and not re.search(r'\b(?:pinstripe|pinstriped|stripe pattern|striped pattern)\b',nearby,re.I):
                continue
            # "abstract ideas" can still be marketing, unless explicitly part of a design pattern.
            if name=='Abstract' and re.search(r'\babstract\s+(?:idea|concept|gift)\b',nearby,re.I):
                continue
            found.append((m.start(),m.end(),name))
    found.sort(key=lambda x:(x[0],x[1]))
    dedup=[]
    for _,_,name in found:
        if name not in dedup:dedup.append(name)
    return dedup

def title_pattern(title):
    title=plain(title)
    hits=_pattern_hits(title)
    if not hits:return '', 'TITLE_NO_PATTERN',''
    # User-approved representative rule: first valid pattern in visible title.
    # Do not treat fishing species (Striped Bass) as a textile motif.
    return hits[0], 'TITLE_FIRST_REPRESENTATIVE' if len(hits)>1 else 'TITLE_SINGLE_EXPLICIT_PATTERN',title[:350]

def description_pattern(description,title=''):
    desc=plain(description)
    if not desc:return '', 'NO_DESCRIPTION',''
    chunks=re.split(r'(?<=[.!?])\s+|[\n\r]+',desc)
    candidates=[]
    for sentence in chunks:
        sentence=sentence.strip()
        if not sentence or len(sentence)>700:continue
        hits=_pattern_hits(sentence)
        if not hits:continue
        # User-approved SEO phrasing: interest in the named pattern is evidence
        # of the associated design, but not in generic site/collection boilerplate.
        if re.search(r'\b(?:other patterns?|other designs?|choose from|shop our|browse our|our collection|such as|for example|collection of)\b',sentence,re.I):continue
        is_seo_lovers=bool(re.search(r'\b(?:appeals? to|for|perfect for|ideal for|made for)\b.{0,90}\b(?:abstract art|[a-z -]+ pattern)\s+(?:lovers?|fans?|enthusiasts?)\b',sentence,re.I))
        has_context=bool(DESIGN_CONTEXT.search(sentence))
        if not has_context and not is_seo_lovers:continue
        # Functional garment features (reflective stripes, anti-slip silicone strip)
        # are not printed patterns, even when descriptions list style/design elsewhere.
        if hits[0]=='Striped' and re.search(r'\b(?:reflective\s+stripes?|silicone\s+strips?|anti[- ]slip\s+strips?)\b',sentence,re.I) and not re.search(r'\b(?:stripes?|striped)\s+(?:pattern|print|design|background)\b|\b(?:pattern|print|design|background)\s+(?:of\s+)?(?:stripes?|striped)\b',sentence,re.I):continue
        # Respect explicit customer decision that 'abstract art lovers' counts.
        if hits[0]=='Abstract' and not (re.search(r'\babstract\s+(?:art|design|pattern|print|graphic)\b',sentence,re.I)):continue
        candidates.append((hits[0],sentence[:350],is_seo_lovers))
    if not candidates:return '', 'DESCRIPTION_NOT_DECISIVE',''
    # Product SEO descriptions list many patterns: take earliest qualified reference.
    val,txt,seo=candidates[0]
    return val,'DESCRIPTION_SEO_PATTERN' if seo else 'DESCRIPTION_FIRST_REPRESENTATIVE' if len({c[0] for c in candidates})>1 else 'DESCRIPTION_DESIGN_SPECIFIC',txt

def apply_pattern_fallback(rows,evidence,trace=None):
    if trace is None:trace={}
    outcome=[];accepted={'GMC_TITLE':0,'SHOPIFY_TITLE':0,'SHOPIFY_DESCRIPTION':0}
    for r in rows:
        if r.get('approved_pattern') or r.get('current_pattern'):continue
        if r.get('shopify_status')!='SHOPIFY_VERIFIED':continue
        ev=evidence.get(r['id'])
        verified= bool(ev and ev.get('evidence_status')=='VERIFIED' and str(ev.get('product_id'))==str(r.get('shopify_product_id')) and str(ev.get('variant_id'))==str(r.get('shopify_variant_id')))
        # Don't trust an apparently cached record with mismatched Product / Variant.
        if ev and not verified:
            outcome.append({'item_id':r['id'],'decision':'EVIDENCE_ID_MISMATCH','pattern':'','source':'','evidence_text':''});continue
        title=(ev.get('shopify_title') if verified else '') or r.get('title','')
        source='SHOPIFY_TITLE' if verified and ev.get('shopify_title') else 'GMC_TITLE'
        val,reason,txt=title_pattern(title)
        if not val and verified:
            dval,dreason,dtxt=description_pattern(ev.get('description',''),title)
            if dval:
                val,reason,txt=dval,dreason,dtxt;source='SHOPIFY_DESCRIPTION'
            elif reason in ('TITLE_NO_PATTERN','MULTIPLE_TITLE_PATTERNS'):
                reason=dreason
        if val:
            r['approved_pattern']=val;r['proposed_pattern']=val
            r['pattern_qa']=('PATTERN_GMC_TITLE_VERIFIED' if source=='GMC_TITLE' else 'PATTERN_SHOPIFY_TITLE_VERIFIED' if source=='SHOPIFY_TITLE' else 'PATTERN_DESIGN_DESCRIPTION_VERIFIED')
            r['pattern_evidence']=('GMC_TITLE_PATTERN' if source=='GMC_TITLE' else 'SHOPIFY_TITLE_PATTERN' if source=='SHOPIFY_TITLE' else 'SHOPIFY_DESCRIPTION_PATTERN')+': '+txt[:220]
            trace[(r['id'],'PATTERN')]={'evidence_source':source,'evidence_text':txt,'rule_id':'PATTERN_TITLE_DESC_V1353'}
            accepted[source]+=1
        outcome.append({'item_id':r['id'],'decision':reason,'pattern':val,'source':source if val else '', 'evidence_text':txt})
    return accepted,outcome
