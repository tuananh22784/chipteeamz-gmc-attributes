"""ChipteeAmz GMC Attribute Auto-Audit V1.2 - strictly read-only."""
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
    'Leopard Print': r'\bleopard[ -]?print\b',
    'Abstract': r'\babstract\b',
}
FABRIC = r'(?:polyester|cotton|spandex|nylon|rayon|linen|canvas|acrylic|viscose)'
STYLE_RX = r'hoodie|sweatshirt|t-?shirt|tee|polo|quarter[ -]?zip|zip[ -]?up|tank|face shield|sleeveless|long sleeve|short sleeve|jersey|sun shirt'
OFFER_ID = re.compile(r'^shopify_[A-Za-z]{2}_([0-9]+)_([0-9]+)$')
COLUMNS = ['id','language','feed_label','title','variant_options','variant_style','shopify_product_id','shopify_variant_id',
           'shopify_status','description_source','current_color','current_pattern','current_material',
           'proposed_color','color_evidence','proposed_pattern','pattern_evidence',
           'proposed_material','material_evidence','qa_status','review_reason']

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
        chosen = product_title.split(' | ')[0][:230]
        colors = color_mentions(chosen)
        if 1 <= len(colors) <= 3:
            result['proposed_color'] = '/'.join(colors)
            result['color_evidence'] = 'shopify_product_title: ' + chosen[:230]
        else:
            reasons.append('color_missing_or_ambiguous')
    chosen = product_title.split(' | ')[0][:250]
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
        # Pattern cannot be inferred from generic marketing text.
        reasons.append('pattern_not_explicit_in_title')
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
        reasons.append('material_requires_variant_style_confirmation')
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
    def __init__(self, out_dir, append=False):
        self.out = Path(out_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.files, self.writers = {}, {}
        names = ['audit','candidates_review','ready_for_qa','needs_review','auto_fix_eligible']
        for name in names:
            path = self.out / (name + '.csv')
            exist = append and path.exists() and path.stat().st_size > 0
            f = path.open('a' if exist else 'w', encoding='utf-8-sig' if not exist else 'utf-8', newline='')
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            if not exist:
                w.writeheader()
            self.files[name], self.writers[name] = f, w
        self.counts = collections.Counter()
        self.seen = set()
        # Preload IDs when resuming to prevent duplicate rows if token was reused.
        if append and (self.out/'audit.csv').exists():
            with (self.out/'audit.csv').open(encoding='utf-8-sig', newline='') as f:
                for row in csv.DictReader(f):
                    self.seen.add((row['id'], row['language'], row['feed_label']))
    def process(self, raw, source='live'):
        item = parse_item(raw)
        identity = (item['id'], item['language'], item['feed_label'])
        if identity in self.seen:
            self.counts['duplicates_skipped'] += 1
            return
        self.seen.add(identity)
        self.counts['scanned'] += 1
        verified = item['shopify_status'] == 'SHOPIFY_VERIFIED'
        self.counts['shopify_verified' if verified else 'shopify_unverified'] += 1
        missing = {'color': is_missing_color(item['color']), 'pattern': not str(item['pattern']).strip(),
                   'material': not str(item['material']).strip()}
        for key, value in missing.items():
            if value:
                self.counts['missing_' + key] += 1
        candidate = extract(item['title'], item['description'] if verified else '',
                            item['variant_style'], item['selected_color'], item['shopify_title']) if verified else {}
        proposals = {key: candidate.get('proposed_' + key, '') if missing[key] else '' for key in missing}
        for key, value in proposals.items():
            if value:
                self.counts['proposed_' + key] += 1
        has_proposal = any(proposals.values())
        if not any(missing.values()):
            status = 'NO_MISSING_FIELDS'
        elif verified and has_proposal:
            status = 'READY_FOR_QA'
        else:
            status = 'NEEDS_REVIEW'
        reasons = []
        if not verified:
            reasons.append(item['shopify_status'] or 'shopify_not_verified')
        if candidate.get('review_reason'):
            reasons.append(candidate['review_reason'])
        row = {
            'id': item['id'], 'language': item['language'], 'feed_label': item['feed_label'],
            'title': item['title'], 'variant_options': item['variant_options'], 'variant_style': item['variant_style'],
            'shopify_product_id': item['shopify_product_id'], 'shopify_variant_id': item['shopify_variant_id'],
            'shopify_status': item['shopify_status'] or 'GMC_EXPORT_UNVERIFIED',
            'description_source': 'Shopify_default_description_API' if verified else 'GMC_or_unverified',
            'current_color': item['color'], 'current_pattern': item['pattern'], 'current_material': item['material'],
            'qa_status': status, 'review_reason': ';'.join(reasons),
        }
        for key in ('color','pattern','material'):
            row['proposed_' + key] = proposals[key]
            row[key + '_evidence'] = candidate.get(key + '_evidence','') if proposals[key] else ''
        self.writers['audit'].writerow(row)
        if has_proposal:
            self.writers['candidates_review'].writerow(row)
            self.counts['has_proposals'] += 1
        if status == 'READY_FOR_QA':
            self.writers['ready_for_qa'].writerow(row)
            self.counts['ready_for_qa'] += 1
        elif status == 'NEEDS_REVIEW':
            self.writers['needs_review'].writerow(row)
            self.counts['needs_review'] += 1
        else:
            self.counts['already_filled'] += 1
    def close(self):
        for f in self.files.values():
            f.close()
    def summary(self, **metadata):
        result = dict(self.counts)
        result.update(metadata)
        result.update({'mode':'READ_ONLY', 'auto_fix_eligible':0, 'qa_policy':'MANUAL_APPROVAL_REQUIRED'})
        (self.out/'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return result

def read_export(path):
    with zipfile.ZipFile(path) as z:
        filename = next((f for f in z.namelist() if f.lower().endswith(('.csv', '.tsv'))), None)
        if not filename:
            raise ValueError('No CSV/TSV in ZIP')
        with z.open(filename) as binary:
            with io.TextIOWrapper(binary, encoding='utf-8-sig', newline='') as fh:
                yield from csv.DictReader(fh, delimiter='\t' if filename.lower().endswith('.tsv') else ',')

def run_live(args):
    from live import merchant_page, shopify_descriptions
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    checkpoint = out/'checkpoint.json'
    cursor, pages, rows_before = '', 0, 0
    append = args.resume and checkpoint.exists()
    if append:
        state = json.loads(checkpoint.read_text(encoding='utf-8'))
        if state.get('account') != __import__('os').environ['GMC_ACCOUNT_ID'].strip():
            raise ValueError('Checkpoint GMC account mismatch')
        if state.get('completed'):
            raise ValueError('Checkpoint already completed; start a new scan')
        cursor = state.get('next_page_token','')
        pages, rows_before = state.get('pages',0), state.get('scanned',0)
        if not cursor:
            raise ValueError('Checkpoint has no cursor; cannot resume')
    reporter = Reporter(out, append=append)
    # Existing counts restored from previous summary; new counts accumulated for this run.
    previous = {}
    if append and (out/'summary.json').exists():
        previous = json.loads((out/'summary.json').read_text(encoding='utf-8'))
    in_run, page_count, completed = 0, 0, False
    try:
        while True:
            items, next_token = merchant_page(cursor, args.page_size)
            if not items and next_token == cursor and next_token:
                raise RuntimeError('Merchant API page cursor did not advance')
            shopify_descriptions(items)
            for raw in items:
                reporter.process(raw)
            in_run += len(items)
            page_count += 1
            pages += 1
            # Persist report before checkpoint, so a completed page has durable output.
            for f in reporter.files.values():
                f.flush()
            cursor = next_token
            completed = not bool(next_token)
            cumulative = collections.Counter({key: int(previous.get(key,0)) for key in reporter.counts})
            cumulative.update(reporter.counts)
            # Avoid overwriting old counter fields not present in the current run.
            for key, val in previous.items():
                if key not in cumulative and isinstance(val, int) and key not in ('pages','scanned'):
                    cumulative[key] = val
            meta = dict(cumulative)
            meta.update({'pages':pages,'completed':completed,'scanned':rows_before + reporter.counts['scanned'],
                         'next_page_token_present':bool(cursor)})
            meta.update({'mode':'READ_ONLY','auto_fix_eligible':0,'qa_policy':'MANUAL_APPROVAL_REQUIRED'})
            (out/'summary.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
            checkpoint.write_text(json.dumps({'account':__import__('os').environ['GMC_ACCOUNT_ID'].strip(),
                 'next_page_token':cursor,'pages':pages,'scanned':meta['scanned'],'completed':completed},indent=2),encoding='utf-8')
            print('Processed page:', pages, 'items this run:', in_run, 'cumulative items:', meta['scanned'], 'complete:', completed)
            if completed or (args.max_pages and page_count >= args.max_pages):
                break
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
