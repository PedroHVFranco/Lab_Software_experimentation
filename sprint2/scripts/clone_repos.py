#!/usr/bin/env python3
"""
Clona repositórios listados em repos_list.csv em paralelo, salva em sprint2/data/repos/<owner>/<repo>.

- Usa git clone --depth=1 para cada repo.
- Registra falhas em clone_failures.log.
- Ignora repositórios já clonados.
- Paraleliza com ThreadPoolExecutor (default: 6 workers).

 Observação: força suporte a caminhos longos por clone com
 "git -c core.longpaths=true clone ..." para reduzir falhas no Windows.

Uso:
  python sprint2/scripts/clone_repos.py --csv sprint2/data/repos_list.csv --out sprint2/data/repos --workers 6
"""
import os
import sys
import csv
import time
import subprocess
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

import threading
lock = threading.Lock()


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def parse_csv(csv_path: str) -> List[Tuple[str, str]]:
    # Retorna lista de (owner, repo, url)
    out = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            repo_full = row["repo"]
            url = row["url"]
            if "/" not in repo_full:
                continue
            owner, repo = repo_full.split("/", 1)
            out.append((owner, repo, url))
    return out
def preflight_longpath_checks():
    """Prints info about Windows and Git long path support to help diagnostics."""
    try:
        import platform
        if platform.system().lower() == "windows":
            try:
                import winreg  # type: ignore
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\\CurrentControlSet\\Control\\FileSystem") as k:
                    val, _ = winreg.QueryValueEx(k, "LongPathsEnabled")
                    print(f"Windows LongPathsEnabled registry: {val}")
            except Exception:
                print("Windows LongPathsEnabled registry: not readable")
    except Exception:
        pass

    # Git settings
    try:
        gv = subprocess.run(["git", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        print(gv.stdout.decode(errors="ignore").strip() or "git --version unknown")
    except Exception:
        print("git not found in PATH")
    for scope in ("--system", "--global", "--local"):
        try:
            res = subprocess.run(["git", "config", scope, "--get", "core.longpaths"],
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5)
            if res.returncode == 0:
                print(f"git({scope[2:]}) core.longpaths= {res.stdout.decode().strip()}")
            else:
                print(f"git({scope[2:]}) core.longpaths not set")
        except Exception:
            print(f"git({scope[2:]}) core.longpaths check failed")



def _try_recover_checkout(dest: str) -> bool:
    """Attempt to recover a repo where clone succeeded but checkout failed.
    Uses long path config and a hard reset to repopulate working tree.
    """
    try:
        # Try reset --hard first
        res1 = subprocess.run(["git", "-c", "core.longpaths=true", "-C", dest, "reset", "--hard", "HEAD"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        if res1.returncode == 0:
            return True
        # Fallback to checkout --force
        res2 = subprocess.run(["git", "-c", "core.longpaths=true", "-C", dest, "checkout", "--force", "HEAD"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        return res2.returncode == 0
    except Exception:
        return False


def clone_one(owner: str, repo: str, url: str, out_dir: str) -> Tuple[str, bool, str]:
    dest = os.path.join(out_dir, owner, repo)
    ensure_dir(os.path.dirname(dest))
    if os.path.isdir(dest) and os.path.isdir(os.path.join(dest, ".git")):
        # Try to ensure working tree is checked out (recover from previous checkout failure)
        try:
            if _try_recover_checkout(dest):
                return (f"{owner}/{repo}", True, "already_cloned")
            else:
                # If checkout still fails, fallback to reclone by removing dir
                try:
                    shutil.rmtree(dest, ignore_errors=True)
                except Exception:
                    pass
        except Exception:
            try:
                shutil.rmtree(dest, ignore_errors=True)
            except Exception:
                pass
    # Force long paths support for this clone to mitigate Windows MAX_PATH issues
    cmd = ["git", "-c", "core.longpaths=true", "clone", "--depth=1", url, dest]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
        if res.returncode == 0:
            return (f"{owner}/{repo}", True, "cloned")
        else:
            msg = res.stderr.decode(errors="ignore").strip()
            # If clone succeeded but checkout failed, attempt recovery
            if os.path.isdir(dest) and os.path.isdir(os.path.join(dest, ".git")):
                if _try_recover_checkout(dest):
                    return (f"{owner}/{repo}", True, "cloned_after_recover")
            # Classify long path errors for easier filtering
            if "Filename too long" in msg or "unable to checkout working tree" in msg:
                msg = "Filename too long / checkout failed"
            return (f"{owner}/{repo}", False, msg)
    except Exception as e:
        return (f"{owner}/{repo}", False, str(e))


def main():
    import argparse
    p = argparse.ArgumentParser(description="Clone repos from CSV in parallel")
    p.add_argument("--csv", type=str, default="sprint2/data/repos_list.csv")
    p.add_argument("--out", type=str, default="sprint2/data/repos")
    p.add_argument("--workers", type=int, default=6)
    args = p.parse_args()

    preflight_longpath_checks()
    repos = parse_csv(args.csv)
    print(f"Cloning {len(repos)} repos to {args.out} with {args.workers} workers...")
    ensure_dir(args.out)

    failures = []
    already = 0
    cloned = 0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(clone_one, owner, repo, url, args.out) for owner, repo, url in repos]
        for fut in as_completed(futs):
            name, ok, msg = fut.result()
            with lock:
                if ok and msg == "already_cloned":
                    already += 1
                elif ok:
                    cloned += 1
                    print(f"[OK] {name}")
                else:
                    failures.append((name, msg))
                    print(f"[FAIL] {name}: {msg}")

    print(f"Cloned: {cloned}, Already: {already}, Failures: {len(failures)}")
    if failures:
        with open("sprint2/data/clone_failures.log", "w", encoding="utf-8") as f:
            for name, msg in failures:
                f.write(f"{name}\t{msg}\n")
        print(f"Falhas registradas em sprint2/data/clone_failures.log")

if __name__ == "__main__":
    main()
