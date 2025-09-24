#!/usr/bin/env python3
"""
Check which repositories from repos_list.csv are missing in the canonical
processed summaries (CLOC and CK). Optionally write a new CSV with the
union of missing repos for targeted re-processing.

Usage (PowerShell):
  python sprint2\scripts\check_missing.py --write

Outputs (when --write):
  sprint2/data/processed/missing_repos_next.csv
"""
import os
import csv
import argparse
from typing import Set, Tuple


def read_repos_list(csv_path: str) -> Set[Tuple[str, str]]:
    items = set()
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            repo = (row.get("repo") or "").strip()
            url = (row.get("url") or "").strip()
            if repo and url:
                items.add((repo, url))
    return items


def read_repo_set(csv_path: str) -> Set[str]:
    s: Set[str] = set()
    if not os.path.isfile(csv_path):
        return s
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            repo = (row.get("repo") or "").strip()
            if repo:
                s.add(repo)
    return s


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data_dir", type=str, default=os.path.join("sprint2", "data"))
    p.add_argument("--out_dir", type=str, default=os.path.join("sprint2", "data", "processed"))
    p.add_argument("--write", action="store_true", help="Escreve CSV com união dos faltantes (CLOC ∪ CK)")
    args = p.parse_args()

    repos_csv = os.path.join(args.data_dir, "repos_list.csv")
    cloc_csv = os.path.join(args.out_dir, "cloc_summary.csv")
    ck_csv = os.path.join(args.out_dir, "ck_summary.csv")

    all_repos = read_repos_list(repos_csv)
    cloc_done = read_repo_set(cloc_csv)
    ck_done = read_repo_set(ck_csv)

    all_names = {name for (name, _url) in all_repos}
    missing_cloc = sorted(all_names - cloc_done)
    missing_ck = sorted(all_names - ck_done)
    union_missing = sorted(set(missing_cloc) | set(missing_ck))

    print(f"Total repos: {len(all_names)}")
    print(f"CLOC present: {len(cloc_done)}; missing: {len(missing_cloc)}")
    if missing_cloc:
        print("  First 10 missing CLOC:")
        for x in missing_cloc[:10]:
            print("   -", x)
    print(f"CK present:   {len(ck_done)}; missing: {len(missing_ck)}")
    if missing_ck:
        print("  First 10 missing CK:")
        for x in missing_ck[:10]:
            print("   -", x)

    if args.write:
        # Map names back to URLs
        map_url = {name: url for (name, url) in all_repos}
        out_path = os.path.join(args.out_dir, "missing_repos_next.csv")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["repo", "url"])
            w.writeheader()
            for name in union_missing:
                url = map_url.get(name, "")
                if not url:
                    # Skip if URL not known (shouldn't happen)
                    continue
                w.writerow({"repo": name, "url": url})
        print(f"Wrote union missing CSV: {out_path} ({len(union_missing)} repos)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
