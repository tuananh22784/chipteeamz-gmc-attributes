"""ChipteeAmz GMC Attribute Auto-Audit V1.3 - strictly read-only."""
import argparse
import collections
import csv
import html
import io
import json
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)

def plain(s):
    p = TextExtractor()
    p.feed(html.unescape(str(s or '')))
    return re.sub(r'\s+', ' ', ' '.join(p.parts)).strip()

COLOR_TOKENS = [
    ('Navy Blue', r'navy[ -]+blue'), ('Royal Blue', r'royal[ -]+blue'),
    ('Sky Blue', r'sky[ -]+blue'), ('Light Blue', r'light[ -]+blue'),
    ('Dark Blue', r'dark[ -]+blue'), ('Hot Pink', r'hot[ -]+pink'),
    ('Light Pink', r'light[ -]+pink'), ('Forest Green', r'forest[ -]+green'),
    ('Dark Green', r'dark[ -]+green'), ('Olive Green', r'olive[ -]+green'),
    ('Heather Grey', r'heather[ -]+gr[ae]y'), ('Ash Grey', r'ash[ -]+gr[ae]y'),
    ('Black', r'black'), ('White', r'white'), ('Navy', r'navy'), ('Blue', r'blue'),
    ('Red', r'red'), ('Pink', r'pink'), ('Purple', r'purple'), ('Green', r'green'),
    ('Yellow', r'yellow'), ('Orange', r'orange'), ('Gold', r'gold'),
    ('Silver', r'silver'), ('Gray', r'gr[ae]y'), ('Brown', r'brown'),
    ('Beige', r'beige'), ('Maroon', r'maroon'), ('Teal', r'teal'),
    ('Turquoise', r'turquoise'), ('Cream', r'cream'), ('Khaki', r'khaki'),
    ('Olive', r'olive'), ('Burgundy', r'burgundy'), ('Coral', r'coral'), ('Tan', r'tan')
]
PATTERNS = {
    'Camouflage': r'\b(?:camouflage|camo)\b',
    'Splatter': r'\b(?:splatter|paint splashes|paint splash)\b',
    'Halftone': r'\bhalftone\b',
    'Floral': r'\b(?:floral|flower pattern)\b',
    'Striped': r'\b(?:striped|stripes?|pinstripes?)\b',
    'Plaid': r'\bplaid\b',
    'Geometric': r'\bgeometric\b',
    'Tie-Dye': r'\btie[ -]?dye\b',
    'Polka Dot': r'\bpolka[ -]?dots?\b',
    'Checkered': r'\b(?:checkerboard|checkered)\b',
    'Argyle': r'\bargyle\b',
    'Leopard Print': r'\bleopard[ -]?print\b',
    'Abstract': r'\babstract\b',
}
FABRIC = r'(?:polyester|cotton|spandex|nylon|rayon|linen|canvas|acrylic|viscose)'
STYLE_RX = r'hoodie|sweatshirt|t-?shirt|tee|polo|quarter[ -]?zip|zip[ -]?up|tank|face shield|sleeveless|long sleeve|short sleeve|jersey|sun shirt'
OFFER_ID = re.compile(r'^shopify_[A-Za-z]{2}_([0-9]+)_([0-9]+)$')
COLUMNS = ['id','language','feed_label','title','variant_options','variant_style','shopify_product_id','shopify_variant_id',
           'shopify_status','description_source','current_color','current_pattern','current_material',
           'proposed_color','color_evidence','proposed_pattern','pattern_evidence',
           'proposed_material','material_evidence','color_qa','pattern_qa','material_qa','approved_color','approved_pattern','approved_material','qa_status','review_reason']

def color_mentions(s):
    found, taken = [], []
    for name, rx in COLOR_TOKENS:
        for m in re.finditer(r'\b(?:' + rx + r')\b', s, re.I):
            if any(m.start() < e and m.end() > b for b,e in taken):
                continue
            taken.append(m.span())
            found.append((m.start(), name))
    seen = set()
    result = []
    for _, name in sorted(found):
        if name not in seen:
            result.append(name)
            seen.add(name)
    return result

def description_pattern_candidates(description):
    """Return a single well-evidenced design pattern from a product description.

    Do not use generalized marketing/cross-sell sentences or infer generic Printed.
    This fallback only proposes candidates; never auto-approves description evidence.
    """
    desc = plain(description)
    found = []
    sentences = re.split(r'(?<=[.!?])\s+|[\n\r]+', desc)
    marketing = re.compile(
        r'\b(?:other designs?|other patterns?|shop our|browse our|our collection|'
        r'choose from|available in|for example|e\.g\.|such as|different designs?|'
        r'variety of patterns?|inspired by|mix and match)\b', re.I)
    design_context = re.compile(
        r'\b(?:pattern|design|graphic|print|printed|features?|featuring|'
        r'showcases?|decorated|all[ -]?over)\b', re.I)
    for sentence in sentences:
        if marketing.search(sentence) or not design_context.search(sentence):
            continue
        # A long general description is not reliable pattern evidence.
        if len(sentence) > 400:
            continue
        matches = [name for name, rx in PATTERNS.items() if re.search(rx, sentence, re.I)]
        if not matches:
            continue
        if len(matches) != 1:
            return '', '', 'multiple_description_patterns'
        pattern = matches[0]
        if pattern == 'Striped' and re.search(r'\b(?:flag|patriotic|stars and stripes)\b', sentence, re.I):
            return '', '', 'description_flag_stripes_ambiguous'
        found.append((pattern, sentence.strip()))
    if not found:
        return '', '', 'pattern_not_explicit_in_title_or_description'
    if len(set(p for p, _ in found)) != 1:
        return '', '', 'multiple_description_patterns'
    pattern, evidence = found[0]
    return pattern, 'shopify_description: ' + evidence[:240], ''

def extract(title, description, variant_style='', selected_color='', shopify_title=''):
    """Conservative candidates, never automatic approval. Evidence must be auditable."""
    title, description, variant_style = plain(title), plain(description), plain(variant_style)
    product_title = plain(shopify_title) or title
    result = {f'proposed_{x}': '' for x in ('color','pattern','material')}
    result.update({f'{x}_evidence': '' for x in ('color','pattern','material')})
    reasons = []
    option = (selected_color or '').strip()
    if option and option.casefold() not in ('one color','one colour','default title'):
        colors = color_mentions(option)
        if len(colors) == 1 and len(option) <= 45:
            result['proposed_color'] = colors[0]
            result['color_evidence'] = 'shopify_color_option: ' + option[:100]
        else:
            reasons.append('ambiguous_variant_color')
    if not result['proposed_color']:
        # Shopify title is preferred; GMC may append style/size variant data.
        chosen = product_title[:500]
        colors = color_mentions(chosen)
        if 1 <= len(colors) <= 3:
            result['proposed_color'] = '/'.join(colors)
            result['color_evidence'] = 'shopify_product_title: ' + chosen[:230]
        else:
            reasons.append('color_missing_or_ambiguous')
    chosen = product_title[:500]
    patterns = [name for name, rx in PATTERNS.items() if re.search(rx, chosen, re.I)]
    if len(patterns) == 1:
        if patterns[0] == 'Striped' and re.search(r'\b(?:flag|patriotic|stars and stripes)\b', chosen, re.I):
            reasons.append('flag_stripes_ambiguous')
        else:
            result['proposed_pattern'] = patterns[0]
            result['pattern_evidence'] = 'shopify_product_title: ' + chosen[:220]
    elif len(patterns) > 1:
        reasons.append('multiple_patterns_no_primary')
    else:
        # Title has no explicit pattern; extract only from credible design-specific description statements.
        pat, pat_evidence, warning = description_pattern_candidates(description)
        if pat:
            result['proposed_pattern'] = pat
            result['pattern_evidence'] = pat_evidence
        elif warning:
            reasons.append(warning)
    compositions = list(re.finditer(r'\b\d{1,3}\s*%\s*' + FABRIC + r'\b', description, re.I))
    labeled = list(re.finditer(r'\b(?:material|fabric composition|main fabric composition)\s*[:=-]\s*(' + FABRIC + r')\b', description, re.I))
    all_fabrics = set(x.casefold() for x in re.findall(r'\b' + FABRIC + r'\b', description, re.I))
    # Any multi-style description or material-dependent color must be reviewed before proposing a specific composition.
    enumerated_styles = set(re.findall(r'\b(?:hoodie|sweatshirt|t-?shirt|polo|quarter[ -]?zip|tank top|face shield)\b', description, re.I))
    has_variant_dependent = bool(re.search(r'\b(?:solid colors?|heather colors?|ash gr[ae]y|depending on (?:style|color)|hoodies? and sweatshirts?)\b', description, re.I))
    conflicting_composition = len({m.group().casefold().replace(' ', '') for m in compositions}) > 1
    if has_variant_dependent or conflicting_composition or (len(enumerated_styles) > 1 and len(all_fabrics) > 1):
        reasons.append('variant_dependent_or_multiple_materials')
    elif len(compositions) == 1 and len(all_fabrics) == 1:
        match = compositions[0]
        material = re.search(FABRIC, match.group(), re.I).group().title()
        result['proposed_material'] = material
        result['material_evidence'] = 'shopify_description: ' + description[max(0,match.start()-90):match.end()+90][:240]
    elif len(labeled) == 1 and len(all_fabrics) == 1:
        match = labeled[0]
        result['proposed_material'] = match.group(1).title()
        result['material_evidence'] = 'shopify_description: ' + description[max(0,match.start()-80):match.end()+80][:240]
    else:
        reasons.append('material_not_explicit_or_ambiguous')
    # Material may be mentioned in a template applied to many styles; flag for variant-specific QA.
    if result['proposed_material'] and re.search(STYLE_RX, variant_style, re.I):
        reasons.append('material_variant_unverified')
    result['review_reason'] = ';'.join(reasons)
    return result

def parse_item(data):
    attr = data.get('productAttributes') or {}
    return {
      'id': data.get('offerId') or data.get('id') or '',
      'language': data.get('contentLanguage') or data.get('language') or 'en',
      'feed_label': data.get('feedLabel') or data.get('feed label') or 'US',
      'title': attr.get('title') or data.get('title') or '',
      'shopify_title': data.get('_shopify_title') or '',
      'description': attr.get('description') or data.get('description') or '',
      'color': attr.get('color') or data.get('color') or '',
      'pattern': attr.get('pattern') or data.get('pattern') or '',
      'material': attr.get('material') or data.get('material') or '',
      'variant_style': data.get('_variant_style') or '',
      'variant_options': data.get('_variant_options') or '',
      'shopify_product_id': data.get('_shopify_product_id') or '',
      'shopify_variant_id': data.get('_shopify_variant_id') or '',
      'shopify_status': data.get('_shopify_status') or '',
      'selected_color': data.get('_selected_color') or '',
    }

def is_missing_color(value):
    return str(value or '').strip().strip("'\"").casefold() in ('','one color','one colour','onecolor')

class Reporter:
    """CSV output and per-attribute decisions. No write endpoint exists."""
    NAMES = ('audit','candidates_review','ready_for_qa','needs_review','auto_fix_eligible','approved_attributes')
    def __init__(self, out_dir, append=False):
        self.out = Path(out_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.files, self.writers = {}, {}
        self.counts = collections.Counter()
        self.seen = set()
        if append:
            audit = self.out/'audit.csv'
            if not audit.exists():
                raise ValueError('Resume requires existing audit.csv')
            with audit.open(encoding='utf-8-sig',newline='') as f:
                r = csv.DictReader(f)
                if r.fieldnames != COLUMNS:
                    raise ValueError('Resume CSV schema mismatch; use new scan, not append')
                for row in r:
                    identity=(row['id'],row['language'],row['feed_label'])
                    if identity in self.seen:
                        raise ValueError('Existing audit contains duplicate identities')
                    self.seen.add(identity)
                    self._count_row(row)
        for name in self.NAMES:
            path=self.out/(name+'.csv')
            exist=append and path.exists() and path.stat().st_size>0
            if append and not exist:
                raise ValueError('Resume requires all CSV files; missing '+name)
            f=path.open('a' if exist else 'w',encoding='utf-8' if exist else 'utf-8-sig',newline='')
            w=csv.DictWriter(f,fieldnames=COLUMNS)
            if not exist:
                w.writeheader()
            self.files[name],self.writers[name]=f,w

    def _count_row(self, row):
        self.counts['scanned']+=1
        verified=row['shopify_status']=='SHOPIFY_VERIFIED'
        self.counts['shopify_verified' if verified else 'shopify_unverified']+=1
        for key in ('color','pattern','material'):
            missing=is_missing_color(row['current_color']) if key=='color' else not str(row['current_'+key]).strip()
            if missing: self.counts['missing_'+key]+=1
            if row['proposed_'+key]: self.counts['proposed_'+key]+=1
            if row['approved_'+key]: self.counts['approved_'+key]+=1
        if any(row['proposed_'+k] for k in ('color','pattern','material')):
            self.counts['has_proposals']+=1
        if any(row['approved_'+k] for k in ('color','pattern','material')):
            self.counts['approved_items']+=1
        if row['qa_status']=='READY_FOR_QA':self.counts['ready_for_qa']+=1
        elif row['qa_status']=='NEEDS_REVIEW':self.counts['needs_review']+=1
        elif row['qa_status']=='NO_MISSING_FIELDS':self.counts['already_filled']+=1

    def process(self,raw,source='live'):
        item=parse_item(raw)
        identity=(item['id'],item['language'],item['feed_label'])
        if identity in self.seen:
            self.counts['duplicates_skipped']+=1
            return
        self.seen.add(identity)
        verified=item['shopify_status']=='SHOPIFY_VERIFIED'
        missing={'color':is_missing_color(item['color']),
                 'pattern':not str(item['pattern']).strip(),
                 'material':not str(item['material']).strip()}
        candidate=extract(item['title'],item['description'] if verified else '',
                          item['variant_style'],item['selected_color'],item['shopify_title']) if verified else {}
        proposals={k:candidate.get('proposed_'+k,'') if missing[k] else '' for k in missing}
        reasons=[]
        if not verified:reasons.append(item['shopify_status'] or 'shopify_not_verified')
        if candidate.get('review_reason'):reasons.append(candidate['review_reason'])
        qa={}
        approved={k:'' for k in missing}
        for key in missing:
            proposal=proposals[key]
            evidence=candidate.get(key+'_evidence','')
            if not missing[key]:
                qa[key]='NOT_MISSING'
            elif not verified:
                qa[key]='SHOPIFY_UNVERIFIED'
            elif not proposal:
                qa[key]='UNKNOWN_OR_AMBIGUOUS'
            elif key=='material':
                qa[key]='MATERIAL_NEEDS_REVIEW'
            elif key=='color' and evidence.startswith('shopify_color_option: '):
                qa[key]='COLOR_VARIANT_VERIFIED'
                approved[key]=proposal
            elif key=='color' and evidence.startswith('shopify_product_title: '):
                qa[key]='COLOR_TITLE_VERIFIED'
                approved[key]=proposal
            elif key=='pattern' and evidence.startswith('shopify_product_title: '):
                qa[key]='PATTERN_TITLE_VERIFIED'
                approved[key]=proposal
            elif key=='pattern' and evidence.startswith('shopify_description: '):
                qa[key]='PATTERN_DESCRIPTION_REVIEW'
                reasons.append('pattern_description_requires_qa')
            else:
                qa[key]='NEEDS_REVIEW'
        has_proposal=any(proposals.values())
        if not any(missing.values()):status='NO_MISSING_FIELDS'
        elif verified and has_proposal:status='READY_FOR_QA'
        else:status='NEEDS_REVIEW'
        row={'id':item['id'],'language':item['language'],'feed_label':item['feed_label'],
             'title':item['title'],'variant_options':item['variant_options'],'variant_style':item['variant_style'],
             'shopify_product_id':item['shopify_product_id'],'shopify_variant_id':item['shopify_variant_id'],
             'shopify_status':item['shopify_status'] or 'GMC_EXPORT_UNVERIFIED',
             'description_source':'Shopify_default_description_API' if verified else 'GMC_or_unverified',
             'current_color':item['color'],'current_pattern':item['pattern'],'current_material':item['material'],
             'qa_status':status,'review_reason':';'.join(reasons)}
        for key in missing:
            row['proposed_'+key]=proposals[key]
            row[key+'_evidence']=candidate.get(key+'_evidence','') if proposals[key] else ''
            row[key+'_qa']=qa[key]
            row['approved_'+key]=approved[key]
        self.writers['audit'].writerow(row)
        if has_proposal:self.writers['candidates_review'].writerow(row)
        if status=='READY_FOR_QA':self.writers['ready_for_qa'].writerow(row)
        elif status=='NEEDS_REVIEW':self.writers['needs_review'].writerow(row)
        if any(approved.values()):self.writers['approved_attributes'].writerow(row)
        self._count_row(row)

    def sync(self):
        import os
        for f in self.files.values():
            f.flush()
            os.fsync(f.fileno())
    def close(self):
        for f in self.files.values():f.close()
    def summary(self,**metadata):
        result=dict(self.counts)
        result.update(metadata)
        result.update({'mode':'READ_ONLY','auto_fix_eligible':0,'qa_policy':'TITLE_APPROVED_DESCRIPTION_PATTERN_REVIEW_MATERIAL_REVIEW'})
        atomic_json(self.out/'summary.json',result)
        return result

def atomic_json(path,obj):
    import os
    path=Path(path)
    temp=path.with_suffix(path.suffix+'.tmp')
    with temp.open('w',encoding='utf-8') as f:
        json.dump(obj,f,indent=2,ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp,path)

def read_export(path):
    with zipfile.ZipFile(path) as z:
        filename = next((f for f in z.namelist() if f.lower().endswith(('.csv', '.tsv'))), None)
        if not filename:
            raise ValueError('No CSV/TSV in ZIP')
        with z.open(filename) as binary:
            with io.TextIOWrapper(binary, encoding='utf-8-sig', newline='') as fh:
                yield from csv.DictReader(fh, delimiter='\t' if filename.lower().endswith('.tsv') else ',')

def run_live(args):
    import os
    from live import merchant_page, shopify_descriptions
    out=Path(args.out)
    out.mkdir(parents=True,exist_ok=True)
    checkpoint=out/'checkpoint.json'
    account=os.environ['GMC_ACCOUNT_ID'].strip()
    cursor=''
    pages=0
    if args.resume:
        if not checkpoint.exists():
            raise ValueError('Resume requested but checkpoint.json missing. Refusing to restart silently.')
        state=json.loads(checkpoint.read_text(encoding='utf-8'))
        if state.get('schema')!=3 or state.get('account')!=account:
            raise ValueError('Checkpoint schema/account mismatch. Start new V1.3 scan.')
        if state.get('completed'):raise ValueError('Scan completed; start new scan instead')
        if int(state.get('page_size',-1))!=args.page_size:
            raise ValueError('Resume page_size differs from checkpoint')
        cursor=state.get('next_page_token','')
        pages=int(state['pages'])
        if not cursor:raise ValueError('Checkpoint cursor empty; cannot resume')
    else:
        # Explicit new scan, remove stale prior data before writing.
        for file in (*Reporter.NAMES,'summary'):
            path=out/(file+'.json' if file=='summary' else file+'.csv')
            if path.exists():path.unlink()
        if checkpoint.exists():checkpoint.unlink()
    reporter=Reporter(out,append=args.resume)
    if args.resume and reporter.counts['scanned'] != int(state.get('scanned',-1)):
        reporter.close()
        raise ValueError('CSV/checkpoint row count mismatch; refusing unsafe resume')
    page_count=0
    try:
        while True:
            if args.max_pages and page_count>=args.max_pages:break
            items,next_token=merchant_page(cursor,args.page_size)
            if next_token and next_token==cursor:
                raise RuntimeError('Merchant API cursor did not advance')
            shopify_descriptions(items)
            for raw in items:reporter.process(raw)
            reporter.sync()
            pages+=1
            page_count+=1
            completed=not bool(next_token)
            summary=reporter.summary(pages=pages,completed=completed,
                                    next_page_token_present=bool(next_token),
                                    page_size=args.page_size,
                                    account=account)
            atomic_json(checkpoint,{'schema':3,'account':account,'page_size':args.page_size,
                        'next_page_token':next_token,'pages':pages,
                        'scanned':summary['scanned'],'completed':completed})
            print('Committed page',pages,'unique items',summary['scanned'],'complete',completed,flush=True)
            cursor=next_token
            if completed:break
    finally:
        reporter.close()
    return json.loads((out/'summary.json').read_text(encoding='utf-8'))

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='action',required=True)
    live = sub.add_parser('audit-live')
    live.add_argument('--out',default='out')
    live.add_argument('--page-size',type=int,default=500)
    live.add_argument('--max-pages',type=int,default=1, help='0 means all pages')
    live.add_argument('--resume',action='store_true')
    exp = sub.add_parser('audit-export')
    exp.add_argument('--zip',required=True)
    exp.add_argument('--limit',type=int,default=500)
    exp.add_argument('--out',default='out')
    args = p.parse_args()
    if args.action == 'audit-live':
        print(json.dumps(run_live(args),indent=2))
    else:
        reporter = Reporter(args.out)
        try:
            for i,row in enumerate(read_export(args.zip)):
                if args.limit and i >= args.limit:
                    break
                reporter.process(row,source='export')
        finally:
            reporter.close()
        print(json.dumps(reporter.summary(completed=True,source='GMC_EXPORT_UNVERIFIED'),indent=2))
if __name__=='__main__':
    main()
