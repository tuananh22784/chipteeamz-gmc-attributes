"""ChipteeAmz GMC auditor V1.1. Read only. Never auto-approves or sends attributes."""
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

def plain(value):
    parser = TextExtractor()
    parser.feed(html.unescape(str(value or '')))
    return re.sub(r'\s+', ' ', ' '.join(parser.parts)).strip()

COLOR_TOKENS = [
    ('Navy Blue', r'navy[ -]+blue'), ('Royal Blue', r'royal[ -]+blue'),
    ('Sky Blue', r'sky[ -]+blue'), ('Light Blue', r'light[ -]+blue'),
    ('Dark Blue', r'dark[ -]+blue'), ('Hot Pink', r'hot[ -]+pink'),
    ('Light Pink', r'light[ -]+pink'), ('Dark Green', r'dark[ -]+green'),
    ('Forest Green', r'forest[ -]+green'), ('Olive Green', r'olive[ -]+green'),
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
FABRIC = r'(?:polyester|cotton|spandex|nylon|rayon|linen|canvas)'
OFFER_ID = re.compile(r'^shopify_[A-Za-z]{2}_([0-9]+)_([0-9]+)$')

def color_mentions(value):
    candidates = []
    taken = []
    for name, rx in COLOR_TOKENS:
        for match in re.finditer(r'\b(?:' + rx + r')\b', value, re.I):
            start, end = match.span()
            if any(start < other_end and end > other_start for other_start, other_end in taken):
                continue
            taken.append((start, end))
            candidates.append((start, name, match.group()))
    candidates.sort()
    unique = []
    for _, name, raw in candidates:
        if name not in [v[0] for v in unique]:
            unique.append((name, raw))
    return unique

def extract(title, description, variant='', selected_color=''):
    """Creates candidate evidence, never approval. Pattern only title / explicit product pattern statement."""
    title, description, variant = plain(title), plain(description), plain(variant)
    result = {f'proposed_{x}': '' for x in ('color', 'pattern', 'material')}
    result.update({f'{x}_evidence': '' for x in ('color', 'pattern', 'material')})
    reasons = []

    option = (selected_color or '').strip()
    if not option:
        m = re.search(r'\b(?:colou?r)\s*[:=]\s*([^,;|/]+)', variant, re.I)
        if m:
            option = m.group(1).strip()
    if option and option.casefold() not in ('one color', 'one colour', 'default title'):
        mentions = color_mentions(option)
        if len(mentions) == 1 and len(option) <= 45:
            result['proposed_color'] = mentions[0][0]
            result['color_evidence'] = 'variant_color_option: ' + option[:120]
        else:
            reasons.append('variant_color_not_unambiguous')
    if not result['proposed_color']:
        # Only the explicit design title, not generic marketing copy or size/style variant suffix.
        title_part = title.split(' | ')[0].split(', ')[0][:170]
        mentions = color_mentions(title_part)
        if 1 <= len(mentions) <= 3:
            result['proposed_color'] = '/'.join([m[0] for m in mentions])
            result['color_evidence'] = 'product_title: ' + title_part[:180]
        else:
            reasons.append('color_not_confident_from_title')

    p_title = title.split(' | ')[0].split(', ')[0][:210]
    patterns = [name for name, rx in PATTERNS.items() if re.search(rx, p_title, re.I)]
    if len(patterns) == 1:
        # USA flag, national flags: stripe alone is not necessarily primary pattern.
        if patterns[0] == 'Striped' and re.search(r'\b(?:flag|patriotic|stars and stripes)\b', p_title, re.I):
            reasons.append('pattern_flag_ambiguous')
        else:
            result['proposed_pattern'] = patterns[0]
            result['pattern_evidence'] = 'product_title: ' + p_title[:210]
    elif len(patterns) > 1:
        reasons.append('multiple_patterns_in_title')
    else:
        # Only an explicitly labeled pattern description, never generic paragraphs.
        explicit = re.search(r'\b(?:pattern|design pattern)\s*[:=]\s*([^.;\n]{1,80})', description, re.I)
        if explicit:
            found = [name for name, rx in PATTERNS.items() if re.search(rx, explicit.group(1), re.I)]
            if len(found) == 1:
                result['proposed_pattern'] = found[0]
                result['pattern_evidence'] = 'explicit_description_pattern: ' + explicit.group(0)[:120]
            else:
                reasons.append('pattern_statement_ambiguous')
        else:
            reasons.append('pattern_not_explicit')

    # Treat multi-composition descriptions as variant-dependent and block material proposal.
    composition_matches = list(re.finditer(r'\b\d{1,3}\s*%\s*' + FABRIC + r'\b', description, re.I))
    full_matches = list(re.finditer(r'\b(?:material|fabric composition|main fabric composition)\s*[:=-]\s*(' + FABRIC + r')\b', description, re.I))
    if len(composition_matches) == 1:
        mat = re.search(FABRIC, composition_matches[0].group(), re.I)
        # No second material or blended compositions anywhere near this mention.
        relevant = description[max(0, composition_matches[0].start()-90):composition_matches[0].end()+100]
        other_mats = set(x.lower() for x in re.findall(r'\b' + FABRIC + r'\b', relevant, re.I))
        if len(other_mats) == 1 and not re.search(r'\b(?:hoodie|sweatshirt|heather colors|ash grey|solid colors)\s*:', description, re.I):
            result['proposed_material'] = mat.group().title()
            result['material_evidence'] = 'shopify_description: ' + description[max(0,composition_matches[0].start()-45):composition_matches[0].end()+55][:140]
        else:
            reasons.append('material_variant_or_blend_ambiguous')
    elif len(composition_matches) > 1:
        reasons.append('material_multiple_compositions')
    elif len(full_matches) == 1:
        result['proposed_material'] = full_matches[0].group(1).title()
        result['material_evidence'] = 'shopify_description: ' + full_matches[0].group(0)[:140]
    else:
        reasons.append('material_not_explicit_or_ambiguous')
    result['review_reason'] = ';'.join(reasons)
    return result

def parse_item(data):
    attr = data.get('productAttributes') or {}
    return {
        'id': data.get('offerId') or data.get('id') or '',
        'language': data.get('contentLanguage') or data.get('language') or 'en',
        'feed_label': data.get('feedLabel') or data.get('feed label') or 'US',
        'title': attr.get('title') or data.get('title') or '',
        'description': attr.get('description') or data.get('description') or '',
        'color': attr.get('color') or data.get('color') or '',
        'pattern': attr.get('pattern') or data.get('pattern') or '',
        'material': attr.get('material') or data.get('material') or '',
        'variant': data.get('variant option(name:value)') or '',
        'shopify_product_id': data.get('_shopify_product_id') or data.get('shopify product id') or '',
        'shopify_variant_id': data.get('_shopify_variant_id') or '',
        'shopify_status': data.get('_shopify_status') or '',
        'shopify_error': data.get('_shopify_error') or '',
        'selected_color': data.get('_selected_color') or '',
    }

def is_missing_color(value):
    return str(value or '').strip().strip("'\"").lower() in ('', 'one color', 'one colour', 'onecolor')

COLUMNS = ['id', 'language', 'feed_label', 'title', 'shopify_product_id', 'shopify_variant_id',
           'shopify_status', 'description_source', 'shopify_error', 'current_color', 'current_pattern',
           'current_material', 'proposed_color', 'color_evidence', 'proposed_pattern',
           'pattern_evidence', 'proposed_material', 'material_evidence', 'qa_status', 'review_reason']

def report(items, out_dir, limit=0, source='export'):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    counts = collections.Counter()
    with (out/'audit.csv').open('w', encoding='utf-8-sig', newline='') as audit_file, \
         (out/'candidates_review.csv').open('w', encoding='utf-8-sig', newline='') as candidate_file, \
         (out/'needs_review.csv').open('w', encoding='utf-8-sig', newline='') as needs_file, \
         (out/'auto_fix_eligible.csv').open('w', encoding='utf-8-sig', newline='') as eligible_file:
        writers = [csv.DictWriter(handle, fieldnames=COLUMNS) for handle in
                   (audit_file, candidate_file, needs_file, eligible_file)]
        for writer in writers:
            writer.writeheader()
        for idx, raw in enumerate(items):
            if limit and idx >= limit:
                break
            item = parse_item(raw)
            counts['scanned'] += 1
            source_status = item['shopify_status'] or ('GMC_EXPORT_NOT_VERIFIED' if source == 'export' else 'NOT_VERIFIED')
            if source_status == 'SHOPIFY_VERIFIED':
                counts['shopify_verified'] += 1
            else:
                counts['shopify_unverified'] += 1
            missing = {
                'color': is_missing_color(item['color']),
                'pattern': not str(item['pattern']).strip(),
                'material': not str(item['material']).strip(),
            }
            for key, value in missing.items():
                if value:
                    counts['missing_' + key] += 1
            can_extract = source == 'export' or source_status == 'SHOPIFY_VERIFIED'
            candidates = extract(item['title'], item['description'], item['variant'], item['selected_color']) if can_extract else extract(item['title'], '', item['variant'], item['selected_color'])
            # If Shopify cannot be verified, title matches still require identity review.
            qa_status = 'NO_MISSING_FIELDS' if not any(missing.values()) else 'NEEDS_REVIEW'
            reasons = []
            if source_status != 'SHOPIFY_VERIFIED':
                reasons.append('shopify_not_verified')
            if source == 'export':
                reasons.append('gmc_export_not_shopify_verified')
            if candidates['review_reason']:
                reasons.append(candidates['review_reason'])
            row = {
                'id': item['id'], 'language': item['language'], 'feed_label': item['feed_label'],
                'title': item['title'], 'shopify_product_id': item['shopify_product_id'],
                'shopify_variant_id': item['shopify_variant_id'], 'shopify_status': source_status,
                'description_source': 'Shopify_default_description_API' if source_status == 'SHOPIFY_VERIFIED' else 'GMC_processed_description_or_unknown',
                'shopify_error': item['shopify_error'],
                'current_color': item['color'], 'current_pattern': item['pattern'], 'current_material': item['material'],
                'qa_status': qa_status, 'review_reason': ';'.join(reasons)
            }
            for field in ('color', 'pattern', 'material'):
                row['proposed_' + field] = candidates['proposed_' + field] if missing[field] else ''
                row[field + '_evidence'] = candidates[field + '_evidence'] if missing[field] else ''
                if row['proposed_' + field]:
                    counts['proposed_' + field] += 1
            if qa_status == 'NO_MISSING_FIELDS':
                counts['already_filled'] += 1
            if any(row['proposed_' + key] for key in ('color', 'pattern', 'material')):
                counts['has_proposals'] += 1
                writers[1].writerow(row)
            if qa_status == 'NEEDS_REVIEW':
                writers[2].writerow(row)
                counts['needs_review'] += 1
            # Intentionally ZERO auto-write eligibility until independently validated QA policy.
            writers[0].writerow(row)
    counts['auto_fix_eligible'] = 0
    summary = dict(counts)
    summary['mode'] = 'READ_ONLY'
    summary['qa_policy'] = 'ALL_CANDIDATES_REQUIRE_REVIEW'
    (out/'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary

def iterate_zip(path):
    with zipfile.ZipFile(path) as archive:
        filename = next((n for n in archive.namelist() if n.lower().endswith(('.csv', '.tsv'))), None)
        if not filename:
            raise ValueError('No CSV/TSV in ZIP')
        with archive.open(filename) as binary:
            with io.TextIOWrapper(binary, encoding='utf-8-sig', newline='') as handle:
                yield from csv.DictReader(handle, delimiter='\t' if filename.lower().endswith('.tsv') else ',')

def run():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd', required=True)
    exp = sub.add_parser('audit-export')
    exp.add_argument('--zip', required=True)
    exp.add_argument('--limit', type=int, default=500)
    exp.add_argument('--out', default='out')
    live_parser = sub.add_parser('audit-live')
    live_parser.add_argument('--limit', type=int, default=500)
    live_parser.add_argument('--out', default='out')
    args = parser.parse_args()
    if args.cmd == 'audit-export':
        report(iterate_zip(args.zip), args.out, args.limit, source='export')
    elif args.cmd == 'audit-live':
        from live import merchant_items, shopify_descriptions
        rows = list(merchant_items(args.limit))
        shopify_descriptions(rows)
        report(rows, args.out, source='live')

if __name__ == '__main__':
    run()
