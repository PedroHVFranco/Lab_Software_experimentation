#!/usr/bin/env python3
"""
Merge shard CSVs produced by process_streaming.py (using --out_suffix)
into the canonical outputs:
  - sprint2/data/processed/cloc_summary.csv
  - sprint2/data/processed/ck_summary.csv

Usage (PowerShell):
  python sprint2\scripts\merge_summaries.py \
    --in_dir sprint2\data\processed \
    --out_dir sprint2\data\processed

It will find all files matching cloc_summary*.csv and ck_summary*.csv,
concatenate them (preserving header once), and write canonical files.
Duplicates by repo are allowed; the analysis script will dedupe.
"""
import os
import csv
import glob
import argparse
from typing import Dict, List


def merge_shards(base_path: str, shard_pattern: str, out_path: str) -> int:
    shard_files = sorted(glob.glob(shard_pattern))
    total = 0
    header = None
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # Write to temp then replace to avoid partial files
    tmp_path = out_path + ".tmp"
    # We'll load rows into memory to allow per-repo de-duplication safely (datasets ~1k rows)
    rows_acc: List[List[str]] = []

    def _append_file(fp: str):
        nonlocal header
        with open(fp, encoding="utf-8", newline="") as fin:
            reader = csv.reader(fin)
            rows = list(reader)
            if not rows:
                return
            if header is None:
                header = rows[0]
            start = 1 if rows and rows[0] == header else 0
            for r in rows[start:]:
                rows_acc.append(r)
    # 1) Append base canonical file first if exists
    if os.path.isfile(base_path):
        _append_file(base_path)
    # 2) Append all shard files (skip out_path and base_path to avoid self-include)
    for fp in shard_files:
        if os.path.abspath(fp) in {os.path.abspath(out_path), os.path.abspath(base_path)}:
            continue
        _append_file(fp)
    # De-duplicate by repo, keeping the "best" row
    # Determine column indices
    if not header:
        return 0
    col_index: Dict[str, int] = {name: idx for idx, name in enumerate(header)}
    is_cloc = "files" in col_index and "code" in col_index
    is_ck = "n_classes" in col_index

    def _parse_int(x: str) -> int:
        try:
            return int(float(x))
        except Exception:
            return -1

    best_by_repo: Dict[str, List[str]] = {}
    for r in rows_acc:
        repo = r[col_index.get("repo", 0)] if r else ""
        if not repo:
            continue
        cur_best = best_by_repo.get(repo)
        if cur_best is None:
            best_by_repo[repo] = r
            continue
        # Compare
        if is_cloc:
            code_new = _parse_int(r[col_index["code"]])
            code_old = _parse_int(cur_best[col_index["code"]])
            if code_new > code_old:
                best_by_repo[repo] = r
            elif code_new == code_old:
                files_new = _parse_int(r[col_index["files"]])
                files_old = _parse_int(cur_best[col_index["files"]])
                if files_new > files_old:
                    best_by_repo[repo] = r
        elif is_ck:
            n_new = _parse_int(r[col_index["n_classes"]])
            n_old = _parse_int(cur_best[col_index["n_classes"]])
            if n_new > n_old:
                best_by_repo[repo] = r
        else:
            # Fallback: keep first
            pass

    dedup_rows = list(best_by_repo.values())
    total = len(dedup_rows)

    # Write
    with open(tmp_path, "w", newline="", encoding="utf-8") as fout:
        writer = csv.writer(fout)
        writer.writerow(header)
        writer.writerows(dedup_rows)

    # Replace atomically
    try:
        os.replace(tmp_path, out_path)
    except Exception:
        # Fallback to remove and rename
        try:
            if os.path.exists(out_path):
                os.remove(out_path)
        except Exception:
            pass
        os.rename(tmp_path, out_path)
    return total


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--in_dir", type=str, default="sprint2/data/processed")
    p.add_argument("--out_dir", type=str, default="sprint2/data/processed")
    args = p.parse_args()

    cloc_total = merge_shards(
        os.path.join(args.in_dir, "cloc_summary.csv"),
        os.path.join(args.in_dir, "cloc_summary*.csv"),
        os.path.join(args.out_dir, "cloc_summary.csv"),
    )
    ck_total = merge_shards(
        os.path.join(args.in_dir, "ck_summary.csv"),
        os.path.join(args.in_dir, "ck_summary*.csv"),
        os.path.join(args.out_dir, "ck_summary.csv"),
    )
    print(f"Merged CLOC rows: {cloc_total}; CK rows: {ck_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
