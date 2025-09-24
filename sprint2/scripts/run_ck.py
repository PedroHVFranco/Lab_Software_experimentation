#!/usr/bin/env python3
"""
Run CK (Java code metrics) for all cloned repositories and store raw CSV outputs.

This script discovers the CK JAR under sprint2/tools/ck and executes it for each
git repository under sprint2/data/repos/<owner>/<repo>. The CK tool typically
produces CSV files (class.csv, method.csv, field.csv, variable.csv) in the
current working directory. We run CK with the working directory set to a
repository-specific folder under sprint2/data/raw_ck/<owner>__<repo>/ so the
outputs are collected per repo.

Notes:
- We don't rely on specific CK CLI flags beyond the basic invocation to avoid
  version-specific differences. If the CK version in use requires different
  flags, you can pass them via --extra_args.
- After execution, we verify that class.csv exists. If not, we also probe the
  repo path for outputs and move them if found.

Usage:
  python sprint2/scripts/run_ck.py \
    --repos_dir sprint2/data/repos \
    --ck_jar sprint2/tools/ck/ck-0.7.1-SNAPSHOT-jar-with-dependencies.jar \
    --out_dir sprint2/data/raw_ck \
    --workers 4

Dependencies: Java 11+, CK JAR built via sprint2/scripts/setup_ck.ps1
"""
import os
import sys
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def find_ck_jar(explicit_path: Optional[str]) -> str:
    if explicit_path:
        if os.path.isfile(explicit_path):
            return explicit_path
        raise FileNotFoundError(f"CK JAR não encontrado: {explicit_path}")
    # Try to auto-discover under tools/ck
    base = os.path.join(os.path.dirname(__file__), "..", "tools", "ck")
    base = os.path.abspath(base)
    if os.path.isdir(base):
        for name in os.listdir(base):
            if name.endswith("-jar-with-dependencies.jar"):
                return os.path.join(base, name)
    raise FileNotFoundError("CK JAR não encontrado automaticamente em sprint2/tools/ck. Informe via --ck_jar.")


def list_git_repos(repos_dir: str) -> List[Tuple[str, str, str]]:
    out: List[Tuple[str, str, str]] = []
    if not os.path.isdir(repos_dir):
        return out
    for owner in os.listdir(repos_dir):
        owner_path = os.path.join(repos_dir, owner)
        if not os.path.isdir(owner_path):
            continue
        for repo in os.listdir(owner_path):
            repo_path = os.path.join(owner_path, repo)
            if os.path.isdir(os.path.join(repo_path, ".git")):
                out.append((owner, repo, repo_path))
    return out


def run_ck_one(ck_jar: str, owner: str, repo: str, repo_path: str, out_dir: str, extra_args: Optional[List[str]] = None) -> Tuple[str, bool, str]:
    name = f"{owner}/{repo}"
    repo_out = os.path.join(out_dir, f"{owner}__{repo}")
    ensure_dir(repo_out)

    # If already processed (class.csv exists and non-empty), skip
    class_csv = os.path.join(repo_out, "class.csv")
    if os.path.isfile(class_csv) and os.path.getsize(class_csv) > 0:
        return name, True, "already"

    # Build command. CK usually supports: java -jar ck.jar <path> true 0 false
    cmd = [
        "java",
        "-jar",
        ck_jar,
        repo_path,
        "true",
        "0",
        "false",
    ]
    if extra_args:
        cmd.extend(extra_args)

    try:
        # Run with cwd=repo_out so outputs (CSV) land here
        res = subprocess.run(cmd, cwd=repo_out, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3600)
        if res.returncode != 0:
            msg = (res.stderr or res.stdout).decode(errors="ignore")
            # As a fallback, check if class.csv appeared in repo_path (some CK builds write to target repo)
            fallback = os.path.join(repo_path, "class.csv")
            if os.path.isfile(fallback):
                shutil.move(fallback, class_csv)
                # move other known files if present
                for n in ("method.csv", "field.csv", "variable.csv"):
                    p = os.path.join(repo_path, n)
                    if os.path.isfile(p):
                        shutil.move(p, os.path.join(repo_out, n))
                return name, True, "ok_fallback"
            return name, False, f"CK exit {res.returncode}: {msg.strip()}"

        # Verify output exists
        if not os.path.isfile(class_csv):
            # Some CK versions may output to the repo directory; try moving them
            fallback = os.path.join(repo_path, "class.csv")
            if os.path.isfile(fallback):
                shutil.move(fallback, class_csv)
                for n in ("method.csv", "field.csv", "variable.csv"):
                    p = os.path.join(repo_path, n)
                    if os.path.isfile(p):
                        shutil.move(p, os.path.join(repo_out, n))
        if os.path.isfile(class_csv) and os.path.getsize(class_csv) > 0:
            return name, True, "ok"
        else:
            return name, False, "class.csv não gerado"
    except Exception as e:
        return name, False, str(e)


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Run CK across all repos and collect raw CSVs")
    p.add_argument("--repos_dir", type=str, default="sprint2/data/repos")
    p.add_argument("--out_dir", type=str, default="sprint2/data/raw_ck")
    p.add_argument("--ck_jar", type=str, default=None, help="Path to CK JAR; auto-detect if omitted")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--extra_args", nargs="*", help="Extra args to append to CK command, if needed")
    args = p.parse_args()

    try:
        ck_jar = find_ck_jar(args.ck_jar)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 2

    repos = list_git_repos(args.repos_dir)
    print(f"CK JAR: {ck_jar}")
    print(f"Repos encontrados: {len(repos)}")
    ensure_dir(args.out_dir)

    ok = skipped = fail = 0
    failures: List[Tuple[str, str]] = []

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(run_ck_one, ck_jar, owner, repo, path, args.out_dir, args.extra_args) for owner, repo, path in repos]
        for fut in as_completed(futs):
            name, success, msg = fut.result()
            if success and msg == "already":
                skipped += 1
            elif success:
                ok += 1
                print(f"[CK] {name} -> {msg}")
            else:
                fail += 1
                failures.append((name, msg))
                print(f"[CK] {name} -> FAIL: {msg}")

    print(f"CK OK: {ok}, Skipped: {skipped}, Failed: {fail}")
    if failures:
        with open("sprint2/data/ck_failures.log", "w", encoding="utf-8") as f:
            for name, msg in failures:
                f.write(f"{name}\t{msg}\n")
        print("Falhas registradas em sprint2/data/ck_failures.log")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
