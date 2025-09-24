#!/usr/bin/env python3
"""
Analyze research questions (RQ01-04) by merging process metrics and CK metrics,
computing descriptive stats per repo and correlations, and generating optional plots.

Inputs (CSV):
- sprint2/data/repos_list.csv          -> repo, url, stars, created_at, releases, age_years
- sprint2/data/processed/cloc_summary.csv -> repo, files, code, comment, blank
- sprint2/data/processed/ck_summary.csv   -> repo, n_classes, cbo_*, dit_*, lcom_*

Outputs:
- sprint2/data/processed/analysis_summary.csv
- sprint2/data/processed/correlations.csv (Spearman & Pearson)
- sprint2/data/processed/plots/*.png (if --plots)

Usage:
  python sprint2/scripts/analyze_rqs.py --plots
"""
import os
from typing import List

import pandas as pd
import numpy as np


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def load_inputs(base: str = "sprint2/data"):
    repos_csv = os.path.join(base, "repos_list.csv")
    cloc_csv = os.path.join(base, "processed", "cloc_summary.csv")
    ck_csv = os.path.join(base, "processed", "ck_summary.csv")
    df_repos = pd.read_csv(repos_csv)
    df_cloc = pd.read_csv(cloc_csv)
    df_ck = pd.read_csv(ck_csv)

    # Normalize types
    for col in ["stars", "releases"]:
        if col in df_repos.columns:
            df_repos[col] = pd.to_numeric(df_repos[col], errors="coerce")
    if "age_years" in df_repos.columns:
        df_repos["age_years"] = pd.to_numeric(df_repos["age_years"], errors="coerce")
    for col in ["files", "code", "comment", "blank"]:
        if col in df_cloc.columns:
            df_cloc[col] = pd.to_numeric(df_cloc[col], errors="coerce")
    if "n_classes" in df_ck.columns:
        df_ck["n_classes"] = pd.to_numeric(df_ck["n_classes"], errors="coerce")
    for col in [
        "cbo_mean", "cbo_median", "cbo_std",
        "dit_mean", "dit_median", "dit_std",
        "lcom_mean", "lcom_median", "lcom_std",
    ]:
        if col in df_ck.columns:
            df_ck[col] = pd.to_numeric(df_ck[col], errors="coerce")

    # Deduplicate per repo by choosing the most complete measurement to avoid Cartesian expansion on merge
    # - For cloc: prefer the row with highest 'code' (fallback to last occurrence)
    # - For CK:   prefer the row with highest 'n_classes' (fallback to last occurrence)
    if "repo" in df_cloc.columns and not df_cloc.empty:
        try:
            if "code" in df_cloc.columns:
                idx = df_cloc.groupby("repo")["code"].idxmax()
                df_cloc = df_cloc.loc[idx]
            else:
                df_cloc = df_cloc.drop_duplicates(subset=["repo"], keep="last")
        except Exception:
            df_cloc = df_cloc.drop_duplicates(subset=["repo"], keep="last")
        df_cloc = df_cloc.reset_index(drop=True)
    if "repo" in df_ck.columns and not df_ck.empty:
        try:
            if "n_classes" in df_ck.columns:
                idx = df_ck.groupby("repo")["n_classes"].idxmax()
                df_ck = df_ck.loc[idx]
            else:
                df_ck = df_ck.drop_duplicates(subset=["repo"], keep="last")
        except Exception:
            df_ck = df_ck.drop_duplicates(subset=["repo"], keep="last")
        df_ck = df_ck.reset_index(drop=True)
    # Merge
    df = df_repos.merge(df_cloc, on="repo", how="left").merge(df_ck, on="repo", how="left")
    return df


def compute_correlations(df: pd.DataFrame) -> pd.DataFrame:
    metrics = {
        "popularity": ["stars"],
        "maturity": ["age_years"],
        "activity": ["releases"],
        "size": ["code", "comment", "files"],
    }
    quality = [
        "cbo_mean", "cbo_median", "cbo_std",
        "dit_mean", "dit_median", "dit_std",
        "lcom_mean", "lcom_median", "lcom_std",
    ]
    rows = []
    from scipy.stats import spearmanr, pearsonr

    for proc_group, proc_cols in metrics.items():
        for pcol in proc_cols:
            if pcol not in df.columns:
                continue
            for qcol in quality:
                if qcol not in df.columns:
                    continue
                sub = df[[pcol, qcol]].dropna()
                if len(sub) < 3:
                    continue
                x = sub[pcol].values
                y = sub[qcol].values
                # Skip if either side is constant (zero variance) to avoid undefined correlations
                try:
                    if np.nanstd(x) == 0 or np.nanstd(y) == 0:
                        continue
                except Exception:
                    # If std computation fails for any reason, skip this pair
                    continue
                try:
                    sp_r, sp_p = spearmanr(x, y)
                except Exception:
                    sp_r, sp_p = np.nan, np.nan
                try:
                    pe_r, pe_p = pearsonr(x, y)
                except Exception:
                    pe_r, pe_p = np.nan, np.nan
                rows.append({
                    "process": proc_group,
                    "x": pcol,
                    "y": qcol,
                    "spearman_r": sp_r,
                    "spearman_p": sp_p,
                    "pearson_r": pe_r,
                    "pearson_p": pe_p,
                    "n": len(sub),
                })
    return pd.DataFrame(rows)


def describe_by_repo(df: pd.DataFrame) -> pd.DataFrame:
    # Already per repo; select and export a summary table helpful for the report
    cols = [
        "repo", "stars", "releases", "age_years", "files", "code", "comment",
        "n_classes",
        "cbo_mean", "cbo_median", "cbo_std",
        "dit_mean", "dit_median", "dit_std",
        "lcom_mean", "lcom_median", "lcom_std",
    ]
    present = [c for c in cols if c in df.columns]
    return df[present]


def make_plots(df: pd.DataFrame, out_dir: str) -> None:
    import seaborn as sns
    import matplotlib.pyplot as plt
    ensure_dir(out_dir)

    pairs = [
        ("stars", "cbo_median"), ("stars", "dit_median"), ("stars", "lcom_median"),
        ("age_years", "cbo_median"), ("releases", "cbo_median"),
        ("code", "cbo_median"), ("code", "dit_median"), ("code", "lcom_median"),
    ]
    for x, y in pairs:
        if x not in df.columns or y not in df.columns:
            continue
        sub = df[[x, y]].dropna()
        if len(sub) < 5:
            continue
        plt.figure(figsize=(6, 4))
        sns.regplot(data=sub, x=x, y=y, scatter_kws={"s": 10, "alpha": 0.5}, line_kws={"color": "red"})
        plt.title(f"{x} vs {y}")
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, f"{x}_vs_{y}.png"), dpi=150)
        plt.close()


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Analyze RQs and generate correlations/plots")
    p.add_argument("--data_dir", type=str, default="sprint2/data")
    p.add_argument("--out_dir", type=str, default="sprint2/data/processed")
    p.add_argument("--plots", action="store_true", help="Generate scatter plots")
    args = p.parse_args()

    df = load_inputs(args.data_dir)
    corr = compute_correlations(df)
    desc = describe_by_repo(df)

    ensure_dir(args.out_dir)
    desc.to_csv(os.path.join(args.out_dir, "analysis_summary.csv"), index=False)
    corr.to_csv(os.path.join(args.out_dir, "correlations.csv"), index=False)

    if args.plots:
        make_plots(df, os.path.join(args.out_dir, "plots"))

    print(f"analysis_summary.csv e correlations.csv gerados em {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
