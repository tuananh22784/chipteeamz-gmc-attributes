"""Read-only GMC and Shopify API clients. No modification endpoints."""
import os
import re
import time
import requests

OFFER_ID = re.compile(r'^shopify_[A-Za-z]{2}_([0-9]+)_([0-9]+)$')

def token():
    import google.auth
    from google.auth.transport.requests import Request
    credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/content'])
    credentials.refresh(Request())
    return credentials.token

def google_request(method, path, **kwargs):
    if not path.startswith('https://'):
        path = 'https://merchantapi.googleapis.com/' + path.lstrip('/')
    for attempt in range(5):
        response = requests.request(method, path, headers={'Authorization': 'Bearer ' + token()}, timeout=90, **kwargs)
        if response.status_code in (429, 500, 502, 503, 504) and attempt < 4:
            time.sleep(min(30, 2 ** attempt))
            continue
        if not response.ok:
            try:
                error = response.json().get('error', {})
                print('Merchant API HTTP:', response.status_code, 'status:', error.get('status', ''), 'message:', str(error.get('message', ''))[:700])
            except ValueError:
                print('Merchant API HTTP:', response.status_code)
        response.raise_for_status()
        return response.json() if response.content else {}

def merchant_page(page_token='', page_size=500):
    account = os.environ['GMC_ACCOUNT_ID'].strip()
    params = {'pageSize': max(1, min(page_size, 1000))}
    if page_token:
        params['pageToken'] = page_token
    payload = google_request('GET', f'products/v1/accounts/{account}/products', params=params)
    return payload.get('products', []), payload.get('nextPageToken', '')

def shopify_graphql(query, variables):
    domain = os.environ['SHOPIFY_SHOP_DOMAIN'].strip()
    version = os.environ.get('SHOPIFY_API_VERSION', '2026-10')
    for attempt in range(4):
        response = requests.post(f'https://{domain}/admin/api/{version}/graphql.json', json={'query': query, 'variables': variables},
                                 headers={'X-Shopify-Access-Token': os.environ['SHOPIFY_ADMIN_TOKEN']}, timeout=90)
        if response.status_code in (429, 500, 502, 503, 504) and attempt < 3:
            time.sleep(2 ** attempt)
            continue
        response.raise_for_status()
        result = response.json()
        if result.get('errors'):
            raise RuntimeError('Shopify GraphQL errors: ' + str(result['errors'])[:500])
        return result['data']

def shopify_descriptions(rows):
    """Verify product and exact variant via a separate node lookup for EVERY variant.

    Avoids old first-100-variants truncation. Uses only Shopify's default description.
    """
    lookup = {}
    for item in rows:
        item['_shopify_status'] = 'UNMATCHED_OFFER_ID'
        m = OFFER_ID.fullmatch(str(item.get('offerId', '')))
        if not m:
            continue
        pid, vid = m.groups()
        item['_shopify_product_id'] = pid
        item['_shopify_variant_id'] = vid
        item['_shopify_status'] = 'SHOPIFY_NOT_FOUND'
        lookup.setdefault((pid, vid), []).append(item)
    if not lookup:
        return
    # Query exact product and exact variant nodes, independently; avoid paginating first N variants.
    query = '''query($ids: [ID!]!) {
      nodes(ids: $ids) {
        ... on Product { __typename id legacyResourceId title descriptionHtml productType }
        ... on ProductVariant { __typename id legacyResourceId product { legacyResourceId } selectedOptions { name value } }
      }
    }'''
    pids = sorted({pid for pid, _ in lookup})
    vids = sorted({vid for _, vid in lookup})
    result_nodes = {}
    for kind, ids in [('Product', pids), ('ProductVariant', vids)]:
        for start in range(0, len(ids), 40):
            chunk = ids[start:start+40]
            data = shopify_graphql(query, {'ids': ['gid://shopify/' + kind + '/' + x for x in chunk]})
            for node in data.get('nodes', []):
                if node and node.get('legacyResourceId'):
                    result_nodes[(kind, str(node['legacyResourceId']))] = node
    for (pid, vid), grouped in lookup.items():
        product = result_nodes.get(('Product', pid))
        variant = result_nodes.get(('ProductVariant', vid))
        if not product:
            continue
        if not variant or str((variant.get('product') or {}).get('legacyResourceId', '')) != pid:
            for item in grouped:
                item['_shopify_status'] = 'VARIANT_NOT_FOUND_OR_WRONG_PRODUCT'
            continue
        colors = [str(option.get('value', '')).strip() for option in variant.get('selectedOptions', [])
                  if str(option.get('name', '')).casefold() in ('color', 'colour')]
        styles = [str(option.get('value', '')).strip() for option in variant.get('selectedOptions', [])
                  if str(option.get('name', '')).casefold() not in ('color', 'colour', 'size')]
        for item in grouped:
            item['_shopify_status'] = 'SHOPIFY_VERIFIED'
            item.setdefault('productAttributes', {})['description'] = product.get('descriptionHtml') or ''
            item['_shopify_title'] = product.get('title') or ''
            item['_shopify_product_type'] = product.get('productType') or ''
            item['_variant_style'] = ' / '.join(styles)
            item['_selected_color'] = colors[0] if len(colors) == 1 else ''
            item['_variant_options'] = ' / '.join(str(o.get('name', '')) + ':' + str(o.get('value', '')) for o in variant.get('selectedOptions', []))
