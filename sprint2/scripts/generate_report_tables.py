import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / 'data' / 'processed'
REPORT = ROOT / 'docs' / 'RELATORIO.md'

# Simple CSV reader

def read_csv_rows(path):
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)

# Build markdown tables

def md_table(headers, rows):
    out = []
    out.append('| ' + ' | '.join(headers) + ' |')
    out.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
    for r in rows:
        out.append('| ' + ' | '.join(r.get(h, '') for h in headers) + ' |')
    return '\n'.join(out)

# Extract top-5 from correlations.csv

def top5_correlations(kind='spearman'):
    """Return top-5 rows by |r| for the given kind ('spearman' or 'pearson').
    correlations.csv schema: process,x,y,spearman_r,spearman_p,pearson_r,pearson_p,n
    """
    path = PROCESSED / 'correlations.csv'
    rows = read_csv_rows(path)
    r_key = f'{kind.lower()}_r'
    p_key = f'{kind.lower()}_p'
    # Filter rows that have both r and p numeric and n>=50
    filt = []
    for r in rows:
        try:
            rv = float(r.get(r_key, ''))
            pv = float(r.get(p_key, ''))
            nv = float(r.get('n', '0') or 0)
        except Exception:
            continue
        if not (nv >= 50):
            continue
        r['_rval'] = rv
        r['_pval'] = pv
        filt.append(r)
    filt.sort(key=lambda r: abs(r['_rval']), reverse=True)
    top = filt[:5]
    rows_md = []
    for r in top:
        rows_md.append({
            'x': r.get('x',''),
            'y': r.get('y',''),
            'r': f"{r.get(r_key,'')}",
            'p': f"{r.get(p_key,'')}",
            'n': r.get('n',''),
        })
    return rows_md

# Extract median |Spearman| by process metric from correlations.csv if present

def median_abs_spearman_by_x():
    path = PROCESSED / 'correlations.csv'
    rows = read_csv_rows(path)
    # Compute median of |spearman_r| grouped by x
    from statistics import median
    by_x = {}
    for r in rows:
        x = r.get('x','')
        try:
            val = abs(float(r.get('spearman_r','')))
        except Exception:
            continue
        by_x.setdefault(x, []).append(val)
    data = []
    for x, vals in by_x.items():
        if not vals:
            continue
        try:
            med = median(vals)
        except Exception:
            continue
        data.append({'x': x, 'median_|r|': f"{med:.3f}"})
    data.sort(key=lambda d: float(d['median_|r|']), reverse=True)
    return data

# Patch RELATORIO.md between markers

def replace_between_markers(text, start_mark, end_mark, replacement):
    s = text.find(start_mark)
    e = text.find(end_mark)
    if s == -1 or e == -1 or e < s:
        return text
    return text[:s+len(start_mark)] + '\n' + replacement.strip() + '\n' + text[e:]

if __name__ == '__main__':
    spearman_rows = top5_correlations('spearman')
    pearson_rows = top5_correlations('pearson')
    med_rows = median_abs_spearman_by_x()

    sections = []
    if spearman_rows:
        sections.append('#### <a name="tabela1"></a>Tabela 1. Top-5 Correlações (Spearman)')
        sections.append(md_table(['x','y','r','p','n'], spearman_rows))
    if pearson_rows:
        sections.append('\n#### <a name="tabela2"></a>Tabela 2. Top-5 Correlações (Pearson)')
        sections.append(md_table(['x','y','r','p','n'], pearson_rows))
    if med_rows:
        sections.append('\n#### <a name="tabela3"></a>Tabela 3. Mediana de |Spearman| por métrica de processo')
        sections.append(md_table(['x','median_|r|'], med_rows))

    tables_md = '\n\n'.join(sections)

    report_text = REPORT.read_text(encoding='utf-8')
    start_mark = '<!-- TABLES:BEGIN -->'
    end_mark = '<!-- TABLES:END -->'
    new_text = replace_between_markers(report_text, start_mark, end_mark, tables_md)
    REPORT.write_text(new_text, encoding='utf-8')
    print('Tables inserted into RELATORIO.md')
