#!/usr/bin/env python3
import os
import pandas as pd

BASE = os.path.join('sprint2', 'data')
PROC = os.path.join(BASE, 'processed')

analysis_csv = os.path.join(PROC, 'analysis_summary.csv')
corr_csv = os.path.join(PROC, 'correlations.csv')
plots_dir = os.path.join(PROC, 'plots')

print('=== analysis_summary.csv ===')
if os.path.isfile(analysis_csv):
    df = pd.read_csv(analysis_csv)
    print('Rows:', len(df))
    cols = [c for c in ['stars','releases','age_years','files','code','comment','n_classes','cbo_median','dit_median','lcom_median'] if c in df.columns]
    print('Columns present:', cols)
    print('Describe:')
    with pd.option_context('display.max_columns', None, 'display.width', 120):
        print(df[cols].describe(include='all'))
else:
    print('File not found:', analysis_csv)

print('\n=== correlations.csv ===')
if os.path.isfile(corr_csv):
    c = pd.read_csv(corr_csv)
    print('Rows:', len(c))
    c_sp = c.dropna(subset=['spearman_r','spearman_p'])
    c_pe = c.dropna(subset=['pearson_r','pearson_p'])
    print('Non-null Spearman rows:', len(c_sp))
    print('Non-null Pearson rows:', len(c_pe))
    sig_sp = c_sp[c_sp['spearman_p'] < 0.05]
    sig_pe = c_pe[c_pe['pearson_p'] < 0.05]
    print('Significant Spearman (p<0.05):', len(sig_sp))
    print('Significant Pearson  (p<0.05):', len(sig_pe))

    def top_abs(df, rcol, pcol, k=10):
        t = df[df[pcol] < 0.05].copy()
        t['abs_r'] = t[rcol].abs()
        t = t.sort_values('abs_r', ascending=False).head(k)
        return t[['process','x','y',rcol,pcol,'n']]

    print('\nTop Spearman (|r|, p<0.05):')
    with pd.option_context('display.max_rows', None):
        print(top_abs(c_sp, 'spearman_r', 'spearman_p', k=10))
    print('\nTop Pearson (|r|, p<0.05):')
    with pd.option_context('display.max_rows', None):
        print(top_abs(c_pe, 'pearson_r', 'pearson_p', k=10))
else:
    print('File not found:', corr_csv)

print('\n=== plots ===')
if os.path.isdir(plots_dir):
    files = [f for f in os.listdir(plots_dir) if f.lower().endswith('.png')]
    files.sort()
    print('PNG count:', len(files))
    for f in files[:20]:
        p = os.path.join(plots_dir, f)
        try:
            sz = os.path.getsize(p)
        except Exception:
            sz = -1
        print(f' - {f} ({sz} bytes)')
else:
    print('Plots dir not found:', plots_dir)
