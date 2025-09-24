#!/usr/bin/env python3
"""
Process a single local repository directory (already downloaded) to compute
Java CLOC and CK metrics, then append to the canonical processed CSVs.

This does NOT clone or delete anything; it only reads the directory.

Usage (PowerShell):
  python sprint2\scripts\process_local.py \
    --repo_name "doocs/leetcode" \
    --repo_dir  "sprint2\\data\\_stream_tmp\\leetcode-main" \
    --out_dir   "sprint2\\data\\processed" \
    --out_suffix "_manual"
"""
import os
import sys
import argparse
from typing import List

# Reuse helpers from process_streaming
from process_streaming import (
    ensure_dir,
    resolve_executable,
    run_cloc_tree,
    run_ck,
    summarize_ck_class,
    append_row,
    find_ck_jar,
)


def main() -> int:
    p = argparse.ArgumentParser(description="Processa um repositório local sem clonar")
    p.add_argument("--repo_name", required=True, help="Nome do repositório (ex.: owner/repo)")
    p.add_argument("--repo_dir", required=True, help="Caminho da pasta local do repositório")
    p.add_argument("--out_dir", type=str, default=os.path.join("sprint2", "data", "processed"))
    p.add_argument("--out_suffix", type=str, default="", help="Sufixo opcional para os CSVs de saída")
    p.add_argument("--ck_jar", type=str, default=None)
    p.add_argument("--git_exe", type=str, default=None)
    p.add_argument("--cloc_exe", type=str, default=None)
    p.add_argument("--java_exe", type=str, default=None)
    args = p.parse_args()

    repo_name = args.repo_name
    repo_dir = os.path.abspath(args.repo_dir)
    if not os.path.isdir(repo_dir):
        print(f"ERRO: repo_dir não existe: {repo_dir}", file=sys.stderr)
        return 2

    try:
        ck_jar = find_ck_jar(args.ck_jar)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 2

    is_windows = os.name == "nt"
    # Resolve executables
    java_home = os.environ.get("JAVA_HOME")
    java_candidates: List[str] = []
    if java_home:
        java_candidates.append(os.path.join(java_home, "bin", "java.exe" if is_windows else "java"))
    if is_windows:
        import glob as _glob
        pats = [
            r"C:\\Program Files\\Eclipse Adoptium\\jdk-21*\\bin\\java.exe",
            r"C:\\Program Files\\Eclipse Adoptium\\jdk-17*\\bin\\java.exe",
            r"C:\\Program Files\\Java\\jdk*\\bin\\java.exe",
            r"C:\\Program Files\\Microsoft\\jdk*\\bin\\java.exe",
        ]
        for pat in pats:
            java_candidates += _glob.glob(pat)
    cloc_candidates: List[str] = []
    if is_windows:
        cloc_candidates = [
            r"C:\\ProgramData\\chocolatey\\bin\\cloc.exe",
            r"C:\\Program Files\\cloc\\cloc.exe",
        ]
    java_exe = resolve_executable("java.exe" if is_windows else "java", args.java_exe, java_candidates)
    cloc_exe = resolve_executable("cloc.exe" if is_windows else "cloc", args.cloc_exe, cloc_candidates)
    if not cloc_exe:
        print("AVISO: cloc não encontrado; métricas de LOC ficarão zeradas.")
    if not java_exe:
        print("AVISO: java não encontrado; CK será pulado.")

    suffix = args.out_suffix or ""
    cloc_out = os.path.join(args.out_dir, f"cloc_summary{suffix}.csv")
    ck_out = os.path.join(args.out_dir, f"ck_summary{suffix}.csv")

    # CLOC
    if cloc_exe:
        try:
            cloc = run_cloc_tree(repo_dir, cloc_exe, java_only=True)
        except Exception as e:
            print(f"[CLOC FAIL] {repo_name}: {e}")
            cloc = {"files": 0, "code": 0, "comment": 0, "blank": 0}
    else:
        cloc = {"files": 0, "code": 0, "comment": 0, "blank": 0}
    append_row(
        cloc_out,
        ["repo", "files", "code", "comment", "blank"],
        {"repo": repo_name, **cloc},
    )

    # CK
    def _count_java_and_best_root(base: str) -> tuple[int, str]:
        total = 0
        counts: dict[str, int] = {}
        base_norm = os.path.normpath(base)
        for root, dirs, files in os.walk(base):
            # prune common build dirs
            dirs[:] = [d for d in dirs if d not in {'.git', '.gradle', 'target', 'build', 'dist', 'node_modules', 'out', 'coverage'}]
            jcount = sum(1 for fn in files if fn.lower().endswith('.java'))
            if jcount:
                total += jcount
                # compute top-level segment under base
                rel = os.path.relpath(root, base_norm)
                top = rel.split(os.sep)[0] if rel not in ('.', '') else '.'
                counts[top] = counts.get(top, 0) + jcount
        # pick best
        if not total:
            return 0, base
        best_top = max(counts.items(), key=lambda kv: kv[1])[0]
        best_root = base if best_top == '.' else os.path.join(base, best_top)
        return total, best_root

    if java_exe:
        try:
            n_java, java_root = _count_java_and_best_root(repo_dir)
            ck_tmp = os.path.join(repo_dir, "_ck_out_local")
            ensure_dir(ck_tmp)
            if n_java == 0:
                raise RuntimeError("nenhum arquivo .java encontrado; pulando CK")
            class_csv = run_ck(ck_jar, java_root, ck_tmp, java_exe)
            n_classes, cbo_mean, cbo_med, cbo_std, dit_mean, dit_med, dit_std, lcom_mean, lcom_med, lcom_std = summarize_ck_class(class_csv)
            ck_row = {
                "repo": repo_name,
                "n_classes": n_classes,
                "cbo_mean": f"{cbo_mean:.6f}",
                "cbo_median": f"{cbo_med:.6f}",
                "cbo_std": f"{cbo_std:.6f}",
                "dit_mean": f"{dit_mean:.6f}",
                "dit_median": f"{dit_med:.6f}",
                "dit_std": f"{dit_std:.6f}",
                "lcom_mean": f"{lcom_mean:.6f}",
                "lcom_median": f"{lcom_med:.6f}",
                "lcom_std": f"{lcom_std:.6f}",
            }
        except Exception as e:
            print(f"[CK FAIL] {repo_name}: {e}")
            ck_row = {
                "repo": repo_name,
                "n_classes": 0,
                "cbo_mean": "nan",
                "cbo_median": "nan",
                "cbo_std": "nan",
                "dit_mean": "nan",
                "dit_median": "nan",
                "dit_std": "nan",
                "lcom_mean": "nan",
                "lcom_median": "nan",
                "lcom_std": "nan",
            }
    else:
        ck_row = {
            "repo": repo_name,
            "n_classes": 0,
            "cbo_mean": "nan",
            "cbo_median": "nan",
            "cbo_std": "nan",
            "dit_mean": "nan",
            "dit_median": "nan",
            "dit_std": "nan",
            "lcom_mean": "nan",
            "lcom_median": "nan",
            "lcom_std": "nan",
        }
    append_row(
        ck_out,
        [
            "repo", "n_classes",
            "cbo_mean", "cbo_median", "cbo_std",
            "dit_mean", "dit_median", "dit_std",
            "lcom_mean", "lcom_median", "lcom_std",
        ],
        ck_row,
    )

    print("[OK] Appended local repo metrics:", repo_name)
    print(" CLOC ->", cloc_out)
    print(" CK   ->", ck_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
