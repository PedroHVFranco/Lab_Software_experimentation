#!/usr/bin/env python3
import os
import argparse
import pandas as pd
import numpy as np

BASE = os.path.join('sprint2','data')
PROC = os.path.join(BASE,'processed')

cloc_csv = os.path.join(PROC,'cloc_summary.csv')
ck_csv = os.path.join(PROC,'ck_summary.csv')

cloc = pd.read_csv(cloc_csv)
ck = pd.read_csv(ck_csv)

# Normalize types
for col in ['files','code','comment','blank']:
    if col in cloc.columns:
        cloc[col] = pd.to_numeric(cloc[col], errors='coerce')
if 'n_classes' in ck.columns:
    ck['n_classes'] = pd.to_numeric(ck['n_classes'], errors='coerce')
for col in [
    'cbo_mean','cbo_median','cbo_std',
    'dit_mean','dit_median','dit_std',
    'lcom_mean','lcom_median','lcom_std']:
    if col in ck.columns:
        ck[col] = pd.to_numeric(ck[col], errors='coerce')

# Merge for validations
m = ck.merge(cloc, on='repo', how='left', suffixes=('_ck','_cloc'))

n_total = len(m)

n_ck_zero = int((m['n_classes'].fillna(0) <= 0).sum())
n_cloc_missing = int(m['code'].isna().sum())
n_cloc_zero = int((m['code'].fillna(0) == 0).sum())

suspect_ck_yes_cloc_missing = m[(m['n_classes']>0) & (m['code'].isna())]
suspect_ck_yes_cloc_zero = m[(m['n_classes']>0) & (m['code'].fillna(0)==0)]

suspect_cloc_yes_ck_zero = m[(m['code'].fillna(0)>0) & (m['n_classes'].fillna(0)==0)]

# Outlier inspections
high_lcom_med = m[m['lcom_median'] > 100]
high_cbo_med = m[m['cbo_median'] > 10]
high_dit_med = m[m['dit_median'] > 4]

parser = argparse.ArgumentParser()
parser.add_argument('--write-missing-list', type=str, default=None, help='Write CSV of repos where CK>0 & CLOC==0')
parser.add_argument('--enrich-from', type=str, default=None, help='Path to repos_list.csv to enrich missing list with URLs')
args = parser.parse_args()

print('=== Validation summary ===')
print('Rows total:', n_total)
print('CK n_classes == 0:', n_ck_zero)
print('CLOC code missing (NaN):', n_cloc_missing)
print('CLOC code == 0:', n_cloc_zero)
print('CK>0 & CLOC missing:', len(suspect_ck_yes_cloc_missing))
print('CK>0 & CLOC==0:', len(suspect_ck_yes_cloc_zero))
print('CLOC>0 & CK==0:', len(suspect_cloc_yes_ck_zero))

print('\n=== Examples (up to 10) ===')
print('CK>0 & CLOC missing:')
print(suspect_ck_yes_cloc_missing[['repo','n_classes']].head(10).to_string(index=False))
print('\nCK>0 & CLOC==0:')
print(suspect_ck_yes_cloc_zero[['repo','n_classes','files','code','comment']].head(10).to_string(index=False))
print('\nCLOC>0 & CK==0:')
print(suspect_cloc_yes_ck_zero[['repo','n_classes','files','code','comment']].head(10).to_string(index=False))

print('\n=== Outliers ===')
print('lcom_median > 100:', len(high_lcom_med))
print('cbo_median > 10:', len(high_cbo_med))
print('dit_median > 4:', len(high_dit_med))
print('\nTop 10 lcom_median:')
print(m[['repo','lcom_median','n_classes','code']].sort_values('lcom_median', ascending=False).head(10).to_string(index=False))

# Optionally write list for reprocessing
if args.write_missing_list:
    out_path = args.write_missing_list
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # Build CSV with headers: repo,url, optionally enriching URL from repos_list.csv
    df = suspect_ck_yes_cloc_zero[['repo']].copy()
    if args.enrich_from and os.path.isfile(args.enrich_from):
        import csv as _csv
        url_map = {}
        with open(args.enrich_from, encoding='utf-8-sig', newline='') as fin:
            r = _csv.DictReader(fin)
            for row in r:
                name = (row.get('repo') or '').strip()
                url = (row.get('url') or '').strip()
                if name and url:
                    url_map[name] = url
        df['url'] = df['repo'].map(lambda n: url_map.get(n, ''))
    else:
        df['url'] = ''
    df.to_csv(out_path, index=False)
    info = f" (enriched from {args.enrich_from})" if args.enrich_from else ""
    print(f"\nWrote suspect CK>0 & CLOC==0 list to: {out_path}{info}")
