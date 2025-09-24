#!/usr/bin/env python3
"""
Summarize CK outputs (class.csv) per repository into a single CSV with
central tendency and dispersion metrics for CBO, DIT, and LCOM.

Input structure (produced by run_ck.py):
  sprint2/data/raw_ck/<owner>__<repo>/class.csv

Output:
  sprint2/data/processed/ck_summary.csv with columns:
    repo, n_classes,
    cbo_mean, cbo_median, cbo_std,
    dit_mean, dit_median, dit_std,
    lcom_mean, lcom_median, lcom_std

Note: Different CK versions may vary column headers. We try common variants:
  - CBO: 'cbo' or 'cboModified' (prefer 'cbo')
  - DIT: 'dit'
  - LCOM: 'lcom' or 'lcom*' (prefer 'lcom')
"""
import os
import sys
import csv
from typing import Dict, List, Optional, Tuple

import math


def list_class_csvs(raw_ck_dir: str) -> List[Tuple[str, str]]:
    files: List[Tuple[str, str]] = []
    if not os.path.isdir(raw_ck_dir):
        return files
    for name in os.listdir(raw_ck_dir):
        repo_dir = os.path.join(raw_ck_dir, name)
        if not os.path.isdir(repo_dir):
            continue
        path = os.path.join(repo_dir, "class.csv")
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            repo = name.replace("__", "/")
            files.append((repo, path))
    return files


def parse_float(v: str) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None


def safe_stats(values: List[float]) -> Tuple[float, float, float]:
    if not values:
        return float("nan"), float("nan"), float("nan")
    n = len(values)
    mean = sum(values) / n
    # median
    s = sorted(values)
    if n % 2 == 1:
        med = s[n // 2]
    else:
        med = 0.5 * (s[n // 2 - 1] + s[n // 2])
    # sample std (n-1), fallback to 0 if n<2
    if n < 2:
        std = 0.0
    else:
        var = sum((x - mean) ** 2 for x in values) / (n - 1)
        std = math.sqrt(max(var, 0.0))
    return mean, med, std


def read_ck_class_csv(path: str) -> Dict[str, List[float]]:
    cbo_vals: List[float] = []
    dit_vals: List[float] = []
    lcom_vals: List[float] = []
    with open(path, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        # Detect available columns once
        fieldnames = [fn.lower() for fn in (r.fieldnames or [])]
        # Map common variants
        def col(*cands: str) -> Optional[str]:
            for c in cands:
                if c.lower() in fieldnames:
                    # Return the original case from r.fieldnames
                    idx = fieldnames.index(c.lower())
                    return r.fieldnames[idx]  # type: ignore[index]
            return None

        cbo_col = col("cbo", "cbomodified")
        dit_col = col("dit")
        lcom_col = col("lcom", "lcom*", "lcomstar", "lcoms")

        for row in r:
            if cbo_col:
                v = parse_float(row.get(cbo_col, ""))
                if v is not None:
                    cbo_vals.append(v)
            if dit_col:
                v = parse_float(row.get(dit_col, ""))
                if v is not None:
                    dit_vals.append(v)
            if lcom_col:
                v = parse_float(row.get(lcom_col, ""))
                if v is not None:
                    lcom_vals.append(v)

    return {"cbo": cbo_vals, "dit": dit_vals, "lcom": lcom_vals}


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Summarize CK class.csv per repo")
    p.add_argument("--raw_ck_dir", type=str, default="sprint2/data/raw_ck")
    p.add_argument("--out_csv", type=str, default="sprint2/data/processed/ck_summary.csv")
    args = p.parse_args()

    pairs = list_class_csvs(args.raw_ck_dir)
    print(f"Repos com class.csv: {len(pairs)}")

    rows: List[Dict[str, str]] = []
    for repo, path in pairs:
        metrics = read_ck_class_csv(path)
        cbo_mean, cbo_med, cbo_std = safe_stats(metrics.get("cbo", []))
        dit_mean, dit_med, dit_std = safe_stats(metrics.get("dit", []))
        lcom_mean, lcom_med, lcom_std = safe_stats(metrics.get("lcom", []))
        n_classes = len(metrics.get("cbo", [])) or len(metrics.get("dit", [])) or len(metrics.get("lcom", []))

        rows.append({
            "repo": repo,
            "n_classes": str(n_classes),
            "cbo_mean": f"{cbo_mean:.6f}",
            "cbo_median": f"{cbo_med:.6f}",
            "cbo_std": f"{cbo_std:.6f}",
            "dit_mean": f"{dit_mean:.6f}",
            "dit_median": f"{dit_med:.6f}",
            "dit_std": f"{dit_std:.6f}",
            "lcom_mean": f"{lcom_mean:.6f}",
            "lcom_median": f"{lcom_med:.6f}",
            "lcom_std": f"{lcom_std:.6f}",
        })

    ensure_dir(os.path.dirname(args.out_csv))
    with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "repo", "n_classes",
                "cbo_mean", "cbo_median", "cbo_std",
                "dit_mean", "dit_median", "dit_std",
                "lcom_mean", "lcom_median", "lcom_std",
            ],
        )
        w.writeheader()
        w.writerows(rows)

    print(f"Resumo CK salvo em {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
