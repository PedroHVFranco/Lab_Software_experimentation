#!/usr/bin/env python3
"""
Run cloc for a single repo and write a simple CSV with totals.

Usage:
  python sprint2/scripts/run_cloc_one.py --repo_dir sprint2/data/repos/00-Evan/shattered-pixel-dungeon --out_csv sprint2/data/processed/00-Evan_cloc.csv --name 00-Evan/shattered-pixel-dungeon
"""
import os
import json
import csv
import subprocess


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def run_cloc(repo_dir: str, include_java_only: bool = False) -> dict:
    """Run cloc on a working tree and return parsed JSON.

    include_java_only: if True, restrict counting to Java files only.
    """
    # Scan working tree directly to avoid external 'unzip' dependency on Windows
    cmd = [
        "cloc",
        "--json",
        "--quiet",
    ]
    if include_java_only:
        cmd += ["--include-lang=Java"]
    # Since we set cwd to repo_dir, pass '.' to ensure correct scanning
    cmd += ["."]
    res = subprocess.run(
        cmd,
        cwd=repo_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=1200,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    if res.returncode != 0:
        raise RuntimeError((res.stderr or "").strip())
    # cloc can sometimes emit UTF-8 BOM or stray whitespace; strip before load
    out = (res.stdout or "").strip()
    return json.loads(out)


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--repo_dir', required=True)
    p.add_argument('--out_csv', required=True)
    p.add_argument('--name', required=True, help='Owner/Repo name for CSV')
    p.add_argument('--java_only', action='store_true', help='Count only Java files (recommended for this lab)')
    args = p.parse_args()

    data = run_cloc(args.repo_dir, include_java_only=args.java_only)

    # Save raw output for troubleshooting
    raw_dir = os.path.join('sprint2', 'data', 'raw_cloc')
    ensure_dir(raw_dir)
    raw_name = args.name.replace('/', '__') + ('.java_only.json' if args.java_only else '.all_langs.json')
    with open(os.path.join(raw_dir, raw_name), 'w', encoding='utf-8') as rf:
        json.dump(data, rf, ensure_ascii=False, indent=2)

    s = data.get('SUM', {})
    # If SUM is missing (rare), compute totals by aggregating languages (exclude header and SUM)
    if not s:
        totals = {"nFiles": 0, "code": 0, "comment": 0, "blank": 0}
        for lang, stats in data.items():
            if lang in ("header", "SUM"):
                continue
            for k in ("nFiles", "code", "comment", "blank"):
                v = stats.get(k)
                if isinstance(v, int):
                    totals[k] += v
        s = totals

    row = {
        'repo': args.name,
        'files': s.get('nFiles', 0),
        'code': s.get('code', 0),
        'comment': s.get('comment', 0),
        'blank': s.get('blank', 0),
    }

    ensure_dir(os.path.dirname(args.out_csv))
    with open(args.out_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['repo', 'files', 'code', 'comment', 'blank'])
        w.writeheader()
        w.writerow(row)

    print(f"Wrote {args.out_csv}")


if __name__ == '__main__':
    main()
