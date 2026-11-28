"""Conservative Title / all-over-print color approvals (read-only)."""
import re
from engine import color_mentions,plain

GENERIC = {'','one color','one colour','onecolor','unknown'}
COLOR_ALIASES = {"grey":"gray"}
ANIMAL_COLOR = re.compile(r'\b(?:black|white|red|yellow|blue|brown)\s+(?:labrador|lab|retriever|bear|cat|dog|horse|deer|duck|wolf|panther|shepherd|rooster|eagle)\b',re.I)
ARTWORK_ONLY = re.compile(r'\b(?:background|watercolor|illustration|artwork|drawing|logo|graphic|lettering|text|font)\b',re.I)
GMC_SUFFIX = re.compile(r'\s*(?:,|\s+-\s+)\s*[^,]*?\s*/\s*([^/]+?)\s*$')
GARMENT = re.compile(r'\b(?:shirt|polo|jersey|hoodie|t-shirt|tee|quarter[ -]?zip|sweatshirt|dress|sleeve)\b',re.I)
DESIGN = re.compile(r'\b(?:all[ -]?over|aop|3d print|3d all over|gradient|flame pattern|colorblock|colourblock)\b',re.I)

def decide_color(gmc_title,shopify_title='',selected_color='',verified=True):
    """Return (value, reason, text) only for grounded, unambiguous evidence."""
    if not verified:return '', 'SHOPIFY_UNVERIFIED', ''
    gmc=plain(gmc_title); shop=plain(shopify_title)
    colors=color_mentions(shop or gmc)
    # Refuse different GMC and Shopify product titles rather than guessing product identity.
    if shop and gmc and shop.lower() not in gmc.lower():
        return '', 'TITLE_SOURCE_CONFLICT', shop[:220]
    suffix=GMC_SUFFIX.search(gmc)
    if suffix:
        tail=suffix.group(1).strip()
        parsed=color_mentions(tail)
        if len(parsed)==1 and tail.casefold()==parsed[0].casefold():
            return parsed[0], 'TITLE_VARIANT_COLOR_SUFFIX',tail
    # For clear product-title color attributes, not arbitrary graphics, animals or accessories.
    title=shop or gmc
    if ANIMAL_COLOR.search(title):return '', 'AMBIGUOUS_COLOR_OF_SUBJECT', title[:220]
    if not GARMENT.search(title):return '', 'NOT_GARMENT_TITLE', title[:220]
    if ARTWORK_ONLY.search(title) and not DESIGN.search(title):return '', 'DESIGN_COLOR_NOT_PRODUCT',title[:220]
    colors=color_mentions(title)
    if len(colors)==1:
        col=colors[0]
        strong=bool(re.search(r'(?i)\b'+re.escape(col)+r'\b\s+(?:flame|gradient|pattern|shirt|polo|jersey|hoodie|tee|t-?shirt)\b',title))
        strong=strong or bool(re.search(r'(?i)\b(?:shirt|polo|jersey|hoodie|tee|t-?shirt)\s+(?:in|color|colour)\s+'+re.escape(col)+r'\b',title))
        if strong:return col,'TITLE_EXPLICIT_PRODUCT_COLOR',title[:250]
    # All-over garments may use a design palette as the color, but never infer a
    # single dominant color from a multi-color string. Limit to at most 3 shades.
    if 2<=len(colors)<=3 and DESIGN.search(title) and not ARTWORK_ONLY.search(title):
        return '/'.join(colors),'TITLE_AOP_DESIGN_PALETTE',title[:250]
    return '', 'TITLE_COLOR_NOT_DECISIVE',title[:250]

def apply_title_color(rows,evidence,trace=None):
    if trace is None:trace={}
    decisions=[];accepted=0
    for row in rows:
        if row.get('approved_color') or row.get('shopify_status')!='SHOPIFY_VERIFIED':continue
        if row.get('current_color','').strip().strip('\"\'').casefold() not in GENERIC:continue
        ev=evidence.get(row['id'],{})
        if ev and (ev.get('evidence_status')!='VERIFIED' or str(ev.get('product_id'))!=str(row.get('shopify_product_id')) or str(ev.get('variant_id'))!=str(row.get('shopify_variant_id'))):
            decisions.append((row['id'],'','SHOPIFY_EVIDENCE_ID_MISMATCH',row.get('title','')));continue
        val,reason,txt=decide_color(row.get('title',''),ev.get('shopify_title',''),ev.get('selected_color',''),True)
        decisions.append((row['id'],val,reason,txt))
        if not val:continue
        row['approved_color']=val;row['proposed_color']=val
        row['color_qa']='COLOR_TITLE_VERIFIED'
        row['color_evidence']='SHOPIFY_OR_GMC_TITLE_COLOR: '+txt[:200]
        trace[(row['id'],'COLOR')]={'evidence_source':'TITLE','evidence_text':txt,'rule_id':reason}
        accepted+=1
    return accepted,decisions
