#!/usr/bin/env python3
import pandas as pd
import numpy as np
from pathlib import Path
from textwrap import dedent

def main():
    p = Path('sprint2/data/processed/correlations.csv')
    if not p.exists():
        print(f'ERROR: {p} not found')
        return 2
    df = pd.read_csv(p)
    for col in ['spearman_r','spearman_p','pearson_r','pearson_p','n']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    # Filter to sufficiently large samples
    sig_s = df[(df['n']>=50) & (df['spearman_p'].notna())].copy()
    sig_s['abs_s'] = sig_s['spearman_r'].abs()
    sig_p = df[(df['n']>=50) & (df['pearson_p'].notna())].copy()
    sig_p['abs_p'] = sig_p['pearson_r'].abs()

    top_s = sig_s.sort_values('abs_s', ascending=False).head(8)
    top_p = sig_p.sort_values('abs_p', ascending=False).head(8)

    print('=== Strongest correlations (Spearman, |r|, n>=50) ===')
    if not top_s.empty:
        print(top_s[['process','x','y','spearman_r','spearman_p','n']].to_string(index=False))
    else:
        print('No rows')

    print('\n=== Strongest correlations (Pearson, |r|, n>=50) ===')
    if not top_p.empty:
        print(top_p[['process','x','y','pearson_r','pearson_p','n']].to_string(index=False))
    else:
        print('No rows')

    if not sig_s.empty:
        med = sig_s.groupby('x')['abs_s'].median().sort_values(ascending=False)
        print('\nMedian |Spearman r| by process metric:')
        for k, v in med.items():
            print(f'  {k}: {v:.3f}')

    # Save a short markdown summary
    out_md = Path('sprint2/data/processed/correlations_summary.md')
    lines = ['# Correlations summary', '']
    lines.append('Top Spearman (|r|):')
    if not top_s.empty:
        for _, r in top_s.iterrows():
            lines.append(f"- {r['x']} vs {r['y']} (Spearman r={r['spearman_r']:.3f}, p={r['spearman_p']:.2e}, n={int(r['n'])})")
    lines.append('')
    lines.append('Top Pearson (|r|):')
    if not top_p.empty:
        for _, r in top_p.iterrows():
            lines.append(f"- {r['x']} vs {r['y']} (Pearson r={r['pearson_r']:.3f}, p={r['pearson_p']:.2e}, n={int(r['n'])})")
    lines.append('')
    if not sig_s.empty:
        lines.append('Median |Spearman r| by process metric:')
        for k, v in med.items():
            lines.append(f'- {k}: {v:.3f}')
    out_md.write_text('\n'.join(lines), encoding='utf-8')
    print(f"\nWrote summary to: {out_md}")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
