#!/usr/bin/env python3
"""
Executa cloc em todos os repositórios clonados e salva resultados:
- JSON por repositório em sprint2/data/raw_cloc/<owner>__<repo>.json
- CSV agregado em sprint2/data/processed/cloc_summary.csv

Uso:
  python sprint2/scripts/run_cloc.py --repos_dir sprint2/data/repos --out_json_dir sprint2/data/raw_cloc --out_csv sprint2/data/processed/cloc_summary.csv --workers 6
"""
import os
import sys
import json
import csv
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple


def list_repos(repos_dir: str) -> List[Tuple[str, str, str]]:
    repos: List[Tuple[str, str, str]] = []
    if not os.path.isdir(repos_dir):
        return repos
    for owner in os.listdir(repos_dir):
        owner_path = os.path.join(repos_dir, owner)
        if not os.path.isdir(owner_path):
            continue
        for repo in os.listdir(owner_path):
            repo_path = os.path.join(owner_path, repo)
            if os.path.isdir(os.path.join(repo_path, ".git")):
                repos.append((owner, repo, repo_path))
    return repos


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def run_cloc_repo(owner: str, repo: str, repo_path: str, out_json_dir: str) -> Tuple[str, bool, str]:
    ensure_dir(out_json_dir)
    out_file = os.path.join(out_json_dir, f"{owner}__{repo}.json")
    # Skip if already exists
    if os.path.isfile(out_file) and os.path.getsize(out_file) > 0:
        return (f"{owner}/{repo}", True, "already")

    cmd = [
        "cloc",
        "--json",
        "--quiet",
        "--vcs=git",
        "--git",
        "HEAD",
    ]
    try:
        res = subprocess.run(cmd, cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
        if res.returncode != 0:
            return (f"{owner}/{repo}", False, res.stderr.decode(errors="ignore").strip())
        data = res.stdout.decode(errors="ignore")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(data)
        return (f"{owner}/{repo}", True, "ok")
    except Exception as e:
        return (f"{owner}/{repo}", False, str(e))


def aggregate_to_csv(out_json_dir: str, out_csv: str):
    rows: List[Dict[str, str]] = []
    for name in os.listdir(out_json_dir):
        if not name.endswith('.json'):
            continue
        path = os.path.join(out_json_dir, name)
        try:
            with open(path, encoding='utf-8') as f:
                j = json.load(f)
        except Exception:
            continue
        # cloc JSON has language keys and a header summary under 'SUM'
        owner_repo = name[:-5].replace('__', '/')
        summary = j.get('SUM') or {}
        # Extract totals
        code = summary.get('code', 0)
        comment = summary.get('comment', 0)
        blank = summary.get('blank', 0)
        n_files = summary.get('nFiles', 0)
        rows.append({
            'repo': owner_repo,
            'files': str(n_files),
            'code': str(code),
            'comment': str(comment),
            'blank': str(blank),
        })

    ensure_dir(os.path.dirname(out_csv))
    with open(out_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['repo', 'files', 'code', 'comment', 'blank'])
        w.writeheader()
        w.writerows(rows)


def main():
    import argparse
    p = argparse.ArgumentParser(description='Run cloc across all repos and aggregate results')
    p.add_argument('--repos_dir', type=str, default='sprint2/data/repos')
    p.add_argument('--out_json_dir', type=str, default='sprint2/data/raw_cloc')
    p.add_argument('--out_csv', type=str, default='sprint2/data/processed/cloc_summary.csv')
    p.add_argument('--workers', type=int, default=6)
    args = p.parse_args()

    repos = list_repos(args.repos_dir)
    print(f"Found {len(repos)} git repos under {args.repos_dir}")

    ok = 0
    skipped = 0
    failed = 0
    fails: List[Tuple[str, str]] = []

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(run_cloc_repo, owner, repo, path, args.out_json_dir) for owner, repo, path in repos]
        for fut in as_completed(futs):
            name, success, msg = fut.result()
            if success and msg == 'already':
                skipped += 1
            elif success:
                ok += 1
                print(f"[CLOC] {name} -> OK")
            else:
                failed += 1
                fails.append((name, msg))
                print(f"[CLOC] {name} -> FAIL: {msg}")

    print(f"CLOC OK: {ok}, Skipped: {skipped}, Failed: {failed}")
    if fails:
        with open('sprint2/data/cloc_failures.log', 'w', encoding='utf-8') as f:
            for name, msg in fails:
                f.write(f"{name}\t{msg}\n")
        print('Falhas registradas em sprint2/data/cloc_failures.log')

    aggregate_to_csv(args.out_json_dir, args.out_csv)
    print(f"Resumo salvo em {args.out_csv}")


if __name__ == '__main__':
    main()
