"""Run bounded, resumable Shopify evidence refetch batches without GMC writes.

This only calls refetch_color_pattern.refetch on the existing audit/cache. The
Google Sheets attribute sync runs once afterwards in the workflow.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
from refetch_color_pattern import refetch


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def validate_audit(path: Path, expected: int | None = None):
    with path.open(encoding='utf-8-sig', newline='') as f:
        rows = csv.DictReader(f)
        ids = [r['id'] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('DUPLICATE_AUDIT_ITEM_ID')
    if expected is not None and len(ids) != expected:
        raise ValueError('AUDIT_COUNT_CHANGED')
    return len(ids)


def run(out: str | Path, batches: int = 1, batch_size: int = 500, fetcher=refetch):
    if not 1 <= batches <= 3:
        raise ValueError('BATCH_COUNT_MUST_BE_1_TO_3')
    if not 1 <= batch_size <= 500:
        raise ValueError('BATCH_SIZE_MUST_BE_1_TO_500')
    base = Path(out)
    audit = base / 'audit.csv'
    checkpoint = base / 'checkpoint.json'
    if not audit.is_file() or not checkpoint.is_file():
        raise FileNotFoundError('MISSING_AUDIT_OR_CHECKPOINT')
    audit_hash = sha256_file(audit)
    checkpoint_hash = sha256_file(checkpoint)
    audit_count = validate_audit(audit)
    checkpoint_data = json.loads(checkpoint.read_text(encoding='utf-8'))
    if int(checkpoint_data.get('scanned', -1)) != audit_count:
        raise ValueError('CHECKPOINT_SCANNED_MISMATCH')
    batch_results = []
    for index in range(batches):
        stats = fetcher(base, limit=batch_size)
        if sha256_file(audit) != audit_hash or sha256_file(checkpoint) != checkpoint_hash:
            raise RuntimeError('AUDIT_OR_CHECKPOINT_MUTATED_BY_REFETCH')
        fetched = int(stats.get('fetched_now', 0))
        valid = int((stats.get('result') or {}).get('VERIFIED', 0))
        if fetched < 0 or fetched > batch_size or valid > fetched:
            raise ValueError('INVALID_REFETCH_COUNTS')
        batch_results.append({'batch': index + 1, **stats})
        # Stop when source has no more rows, but allow retry of unverified products
        # only in a subsequent run (avoid immediately retrying failures forever).
        if fetched == 0 or fetched < batch_size:
            break
        if valid < fetched:
            break
    result = {
        'requested_batches': batches,
        'executed_batches': len(batch_results),
        'batch_size': batch_size,
        'audit_count_unchanged': audit_count,
        'checkpoint_unchanged': True,
        'batch_results': batch_results,
        'cached_total': batch_results[-1]['cached_total'] if batch_results else 0,
        'gmc_write': False,
    }
    (base / 'refetch_batch_progress.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='out')
    parser.add_argument('--batches', type=int, default=1)
    parser.add_argument('--batch-size', type=int, default=500)
    args = parser.parse_args()
    print(json.dumps(run(args.out, args.batches, args.batch_size), indent=2))
