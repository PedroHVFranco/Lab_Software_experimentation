#!/usr/bin/env python3
import csv
from pathlib import Path

def to_float(s):
    try:
        return float(s)
    except Exception:
        return float('nan')

def median(vals):
    vals = sorted(vals)
    n = len(vals)
    if n == 0:
        return float('nan')
    m = n // 2
    if n % 2:
        return vals[m]
    else:
        return 0.5 * (vals[m-1] + vals[m])

def main():
    p = Path('sprint2/data/processed/correlations.csv')
    if not p.exists():
        print(f'ERROR: {p} not found')
        return 2
    rows = []
    with p.open(encoding='utf-8', newline='') as f:
        r = csv.DictReader(f)
        for row in r:
            row = {**row}
            row['spearman_r'] = to_float(row.get('spearman_r',''))
            row['spearman_p'] = to_float(row.get('spearman_p',''))
            row['pearson_r'] = to_float(row.get('pearson_r',''))
            row['pearson_p'] = to_float(row.get('pearson_p',''))
            row['n'] = int(to_float(row.get('n','0')) or 0)
            rows.append(row)
    # Filters
    sig_s = [r for r in rows if r['n']>=50 and not (r['spearman_p']!=r['spearman_p'])]  # p not NaN
    for r in sig_s:
        r['abs_s'] = abs(r['spearman_r'])
    sig_p = [r for r in rows if r['n']>=50 and not (r['pearson_p']!=r['pearson_p'])]
    for r in sig_p:
        r['abs_p'] = abs(r['pearson_r'])
    # Top 10
    top_s = sorted(sig_s, key=lambda r: r['abs_s'], reverse=True)[:10]
    top_p = sorted(sig_p, key=lambda r: r['abs_p'], reverse=True)[:10]
    print('=== Strongest Spearman (|r|, n>=50) ===')
    for r in top_s:
        print(f"- {r['x']} vs {r['y']} | r={r['spearman_r']:.3f}, p={r['spearman_p']:.2e}, n={r['n']}")
    print('\n=== Strongest Pearson (|r|, n>=50) ===')
    for r in top_p:
        print(f"- {r['x']} vs {r['y']} | r={r['pearson_r']:.3f}, p={r['pearson_p']:.2e}, n={r['n']}")
    # Median abs Spearman by x
    byx = {}
    for r in sig_s:
        byx.setdefault(r['x'], []).append(r['abs_s'])
    print('\nMedian |Spearman r| by process metric (x):')
    for k, vals in sorted(((k, median(v)) for k,v in byx.items()), key=lambda kv: kv[1], reverse=True):
        print(f"- {k}: {vals:.3f}")

if __name__ == '__main__':
    raise SystemExit(main())
