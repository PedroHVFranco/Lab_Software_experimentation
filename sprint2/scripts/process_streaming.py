#!/usr/bin/env python3
"""
Streaming processing: for each repository from repos_list.csv, clone it
shallowly into a temp folder, run cloc and CK, write summary rows to
processed CSVs, then delete the repo folder before moving to the next.

Outputs (append-only, headers auto-managed):
- sprint2/data/processed/cloc_summary.csv -> repo, files, code, comment, blank
- sprint2/data/processed/ck_summary.csv   -> repo, n_classes, cbo_*, dit_*, lcom_*

Usage (PowerShell):
  python sprint2\scripts\process_streaming.py \
    --csv sprint2\data\repos_list.csv \
    --work_dir sprint2\data\_stream_tmp \
    --out_dir sprint2\data\processed \
    --max 100 \
    --ck_jar sprint2\tools\ck\ck-0.7.1-SNAPSHOT-jar-with-dependencies.jar

Notes:
- Repositórios NÃO ficam armazenados. Cada repo é removido ao final.
- Use --filter_regex para testar em subconjuntos.
"""
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterable, List, Optional, Tuple


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def find_ck_jar(explicit_path: Optional[str]) -> str:
    if explicit_path:
        if os.path.isfile(explicit_path):
            return os.path.abspath(explicit_path)
        raise FileNotFoundError(f"CK JAR não encontrado: {explicit_path}")
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools", "ck"))
    if os.path.isdir(base):
        for name in os.listdir(base):
            if name.endswith("-jar-with-dependencies.jar"):
                return os.path.abspath(os.path.join(base, name))
    raise FileNotFoundError("CK JAR não encontrado automaticamente em sprint2/tools/ck. Informe via --ck_jar.")


def _first_existing(paths: List[str]) -> Optional[str]:
    for p in paths:
        if p and os.path.isfile(p):
            return p
    return None


def safe_rmtree(path: str) -> None:
    """Remove a directory tree handling Windows read-only files."""
    import stat
    def onerror(func, p, exc_info):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass
    if os.path.isdir(path):
        shutil.rmtree(path, onerror=onerror)


def resolve_executable(
    name: str,
    explicit: Optional[str],
    candidates: Optional[List[str]] = None,
) -> Optional[str]:
    """Resolve an executable path.

    Order:
    - if explicit is provided and exists, return it
    - try on PATH (Windows: where, POSIX: which)
    - try provided candidates list
    Returns absolute path or None if not found.
    """
    if explicit:
        return explicit if os.path.isfile(explicit) else None

    # Try PATH using shutil.which (cross-platform)
    import shutil as _shutil
    w = _shutil.which(name)
    if w and os.path.isfile(w):
        return w

    # Try candidates
    if candidates:
        found = _first_existing(candidates)
        if found:
            return found
    return None


def iter_repos(csv_path: str, filter_regex: Optional[str] = None) -> Iterable[Tuple[str, str]]:
    pat = re.compile(filter_regex) if filter_regex else None
    # Use utf-8-sig to tolerate BOM from Windows-generated CSVs
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            name = row.get("repo") or ""
            url = row.get("url") or ""
            if not name or not url:
                continue
            if pat and not pat.search(name):
                continue
            yield name, url


def git_shallow_clone(url: str, dest: str, git_exe: str) -> Tuple[bool, str]:
    cmd = [git_exe, "-c", "core.longpaths=true", "clone", "--depth=1", url, dest]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)
        if res.returncode == 0:
            return True, "ok"
        else:
            return False, (res.stderr or res.stdout).decode(errors="ignore").strip()
    except Exception as e:
        return False, str(e)


def _win_sanitize_segment(seg: str) -> str:
    # Replace characters illegal on Windows filenames
    illegal = '<>:"|?*'
    for ch in illegal:
        seg = seg.replace(ch, "_")
    # Strip trailing dots and spaces
    seg = seg.rstrip(". ")
    # Avoid reserved device names
    base = seg.split(".")[0].upper()
    reserved = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
    if base in reserved:
        seg = "_" + seg
    return seg or "_"


def _sanitize_windows_path(rel_path: str) -> str:
    parts = rel_path.replace("\\", "/").split("/")
    parts = [_win_sanitize_segment(p) for p in parts if p not in ("", ".")]
    return "/".join(parts)


def clone_and_extract_java_only(url: str, dest: str, git_exe: str) -> Tuple[bool, str]:
    """Windows-safe fallback: clone with no checkout and extract only .java files
    into sanitized paths so we can run CLOC/CK even if repo contains invalid filenames.
    """
    try:
        # Ensure dest parent exists
        ensure_dir(os.path.dirname(dest))
        # Fresh dir
        if os.path.isdir(dest):
            safe_rmtree(dest)
        cmd = [git_exe, "-c", "core.longpaths=true", "clone", "--depth=1", "--no-checkout", url, dest]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)
        if res.returncode != 0:
            return False, (res.stderr or res.stdout).decode(errors="ignore").strip()
        # Verify HEAD
        rev = subprocess.run([git_exe, "-C", dest, "rev-parse", "--verify", "HEAD"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        if rev.returncode != 0:
            return False, (rev.stderr or rev.stdout).decode(errors="ignore").strip()
        # List tree
        ls = subprocess.run([git_exe, "-C", dest, "ls-tree", "-r", "--name-only", "HEAD"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300, text=True, encoding="utf-8", errors="ignore")
        if ls.returncode != 0:
            return False, (ls.stderr or ls.stdout)
        files = [ln.strip() for ln in ls.stdout.splitlines() if ln.strip().lower().endswith(".java")]
        extracted = 0
        for fp in files:
            san = _sanitize_windows_path(fp)
            out_fp = os.path.join(dest, *san.split("/"))
            ensure_dir(os.path.dirname(out_fp))
            show = subprocess.run([git_exe, "-C", dest, "show", f"HEAD:{fp}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
            if show.returncode == 0:
                try:
                    with open(out_fp, "wb") as fout:
                        fout.write(show.stdout)
                    extracted += 1
                except Exception:
                    # Skip write errors for pathological paths
                    pass
        if extracted == 0:
            # No Java files extracted, still consider it ok so pipeline can write zeros
            return True, "ok (no .java files)"
        return True, f"ok ({extracted} .java files)"
    except Exception as e:
        return False, str(e)


def run_cloc_tree(repo_dir: str, cloc_exe: str, java_only: bool = True) -> Dict[str, int]:
    import json
    import tempfile as _tmp
    import os as _os

    def _parse(res_out: str) -> Dict[str, object]:
        try:
            return json.loads((res_out or "").strip())
        except Exception as e:
            raise RuntimeError(f"cloc JSON inválido: {e}")

    # Common excludes to avoid scanning build artifacts and VCS dirs
    exclude_dirs = [".git", ".gradle", "target", "build", "dist", "node_modules", "out", "coverage"]
    exclude_arg = ",".join(exclude_dirs)

    # Extended mode toggles more exhaustive strategies for stubborn repos
    extended = getattr(run_cloc_tree, "_extended", False)

    # Attempt 1: filesystem scan with excludes
    cmd = [cloc_exe, "--json", "--quiet", "--exclude-dir", exclude_arg]
    if java_only:
        cmd += ["--include-lang=Java"]
    cmd += ["."]
    res = subprocess.run(cmd, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1800, text=True, encoding="utf-8", errors="ignore")
    if res.returncode != 0:
        # Attempt 2: git-based file list (more stable on Windows paths)
        cmd2 = [cloc_exe, "--json", "--quiet", "--vcs=git", "--exclude-dir", exclude_arg]
        if java_only:
            cmd2 += ["--include-lang=Java"]
        res2 = subprocess.run(cmd2, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1800, text=True, encoding="utf-8", errors="ignore")
        if res2.returncode != 0:
            raise RuntimeError((res.stderr or res.stdout or res2.stderr or res2.stdout).strip())
        data = _parse(res2.stdout)
    else:
        data = _parse(res.stdout)
    s = data.get("SUM", {})
    if not s:
        # agrega se necessário
        totals = {"nFiles": 0, "code": 0, "comment": 0, "blank": 0}
        for lang, stats in data.items():
            if lang in ("header", "SUM"):
                continue
            for k in totals:
                v = stats.get(k)
                if isinstance(v, int):
                    totals[k] += v
        s = totals

    # Fallback 3: se Java-only e totais continuam zero, gera file-list com *.java
    if java_only and int(s.get("nFiles", 0) or 0) == 0 and int(s.get("code", 0) or 0) == 0:
        exclude_dirs = {".git", ".gradle", "target", "build", "dist", "node_modules", "out", "coverage"}
        java_files: List[str] = []
        for root, dirs, files in _os.walk(repo_dir):
            # podar diretórios comuns de build
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for fn in files:
                if fn.lower().endswith('.java'):
                    java_files.append(_os.path.join(root, fn))
        if java_files:
            with _tmp.NamedTemporaryFile('w', delete=False, encoding='utf-8', newline='\n') as lf:
                for p in java_files:
                    lf.write(p + "\n")
                list_path = lf.name
            try:
                cmd3 = [cloc_exe, "--json", "--quiet", f"--list-file={list_path}"]
                res3 = subprocess.run(cmd3, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1800, text=True, encoding="utf-8", errors="ignore")
                if res3.returncode == 0:
                    try:
                        data3 = json.loads((res3.stdout or '').strip())
                    except Exception:
                        data3 = {}
                    s3 = data3.get("SUM", {})
                    if not s3:
                        totals3 = {"nFiles": 0, "code": 0, "comment": 0, "blank": 0}
                        for lang, stats in data3.items():
                            if lang in ("header", "SUM"):
                                continue
                            for k in totals3:
                                v = stats.get(k)
                                if isinstance(v, int):
                                    totals3[k] += v
                        s3 = totals3
                    s = s3
                else:
                    # Fallback da lista falhou: tenta varredura por diretórios com --match-f para *.java
                    # 1) Seleciona raízes de módulos (pais do 'src' quando existir), reduzindo subpaths redundantes
                    roots = set()
                    for fp in java_files:
                        rp = _os.path.relpath(fp, repo_dir)
                        parts = rp.replace('\\', '/').split('/')
                        try:
                            idx = parts.index('src')
                            root_rel = '/'.join(parts[:idx]) or '.'
                        except ValueError:
                            root_rel = parts[0] if parts and parts[0] not in ('.', '') else '.'
                        roots.add(root_rel)
                    # remove subpaths redundantes
                    roots = sorted(roots, key=lambda p: (p.count('/'), len(p)))
                    pruned: list[str] = []
                    for r in roots:
                        if any((r + '/').startswith(p + '/') for p in pruned if p != '.'):
                            continue
                        pruned.append(r)
                    if not pruned:
                        pruned = ['.']
                    # limita quantidade de raízes para performance (mais alto em modo extendido)
                    pruned = pruned[:50] if extended else pruned[:10]
                    # 2) Executa cloc em cada raiz acumulando SUM
                    total = {"nFiles": 0, "code": 0, "comment": 0, "blank": 0}
                    for root in pruned:
                        cmd4 = [cloc_exe, "--json", "--quiet", "--match-f=\\.java$", root]
                        # em modo normal mantém exclusões; no modo extendido escaneia completo
                        if not extended:
                            cmd4[3:3] = ["--exclude-dir", exclude_arg]
                        res4 = subprocess.run(cmd4, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1800, text=True, encoding="utf-8", errors="ignore")
                        if res4.returncode != 0:
                            # se alguma raiz falhar, continue; ainda assim podemos obter parciais
                            continue
                        try:
                            data4 = json.loads((res4.stdout or '').strip())
                        except Exception:
                            data4 = {}
                        s4 = data4.get("SUM", {})
                        if not s4:
                            # agrega manualmente
                            tmp = {"nFiles": 0, "code": 0, "comment": 0, "blank": 0}
                            for lang, stats in data4.items():
                                if lang in ("header", "SUM"):
                                    continue
                                for k in tmp:
                                    v = stats.get(k)
                                    if isinstance(v, int):
                                        tmp[k] += v
                            s4 = tmp
                        for k in total:
                            total[k] += int(s4.get(k, 0) or 0)
                    s = total
                    # Último recurso no modo extendido: varrer árvore inteira com --match-f sem exclusões
                    if extended and (int(s.get("nFiles", 0) or 0) == 0 and int(s.get("code", 0) or 0) == 0):
                        cmd5 = [cloc_exe, "--json", "--quiet", "--match-f=\\.java$", "."]
                        res5 = subprocess.run(cmd5, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1800, text=True, encoding="utf-8", errors="ignore")
                        if res5.returncode == 0:
                            try:
                                data5 = json.loads((res5.stdout or '').strip())
                            except Exception:
                                data5 = {}
                            s5 = data5.get("SUM", {})
                            if not s5:
                                totals5 = {"nFiles": 0, "code": 0, "comment": 0, "blank": 0}
                                for lang, stats in data5.items():
                                    if lang in ("header", "SUM"):
                                        continue
                                    for k in totals5:
                                        v = stats.get(k)
                                        if isinstance(v, int):
                                            totals5[k] += v
                                s5 = totals5
                            s = s5
                    # Fallback extendido adicional: quebrar lista de arquivos em chunks e somar resultados
                    if extended and (int(s.get("nFiles", 0) or 0) == 0 and int(s.get("code", 0) or 0) == 0) and java_files:
                        chunk_total = {"nFiles": 0, "code": 0, "comment": 0, "blank": 0}
                        CHUNK = 2000
                        for i in range(0, len(java_files), CHUNK):
                            chunk = java_files[i:i+CHUNK]
                            with _tmp.NamedTemporaryFile('w', delete=False, encoding='utf-8', newline='\n') as lf2:
                                for p in chunk:
                                    lf2.write(p + "\n")
                                list2 = lf2.name
                            try:
                                cmd6 = [cloc_exe, "--json", "--quiet", f"--list-file={list2}"]
                                res6 = subprocess.run(cmd6, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1800, text=True, encoding="utf-8", errors="ignore")
                                if res6.returncode == 0:
                                    try:
                                        data6 = json.loads((res6.stdout or '').strip())
                                    except Exception:
                                        data6 = {}
                                    s6 = data6.get("SUM", {})
                                    if not s6:
                                        tmp6 = {"nFiles": 0, "code": 0, "comment": 0, "blank": 0}
                                        for lang, stats in data6.items():
                                            if lang in ("header", "SUM"):
                                                continue
                                            for k in tmp6:
                                                v = stats.get(k)
                                                if isinstance(v, int):
                                                    tmp6[k] += v
                                        s6 = tmp6
                                    for k in chunk_total:
                                        chunk_total[k] += int(s6.get(k, 0) or 0)
                            finally:
                                try:
                                    _os.remove(list2)
                                except Exception:
                                    pass
                        s = chunk_total
            finally:
                try:
                    _os.remove(list_path)
                except Exception:
                    pass
    return {
        "files": int(s.get("nFiles", 0) or 0),
        "code": int(s.get("code", 0) or 0),
        "comment": int(s.get("comment", 0) or 0),
        "blank": int(s.get("blank", 0) or 0),
    }


def run_ck(ck_jar: str, repo_dir: str, out_dir: str, java_exe: str, jvm_xms: str = "256m", jvm_xmx: str = "1024m") -> str:
    """Executa CK e garante que class.csv exista em out_dir.

    Melhorias:
    - Silencia log4j 1.x passando um log4j.properties via -Dlog4j.configuration.
    - Ajusta memória da JVM para maior estabilidade.

    # If Java-only requested and totals are still zero, try a file-list fallback (*.java)
    if java_only and int(s.get("nFiles", 0) or 0) == 0 and int(s.get("code", 0) or 0) == 0:
        # Enumerate *.java excluding known build dirs
        exclude_set = set(exclude_dirs)
        java_files: List[str] = []
        for root, dirs, files in os.walk(repo_dir):
            # prune excluded dirs in-place for performance
            dirs[:] = [d for d in dirs if d not in exclude_set]
            for fn in files:
                if fn.lower().endswith('.java'):
                    java_files.append(os.path.join(root, fn))
        if java_files:
            # Write list file and invoke cloc on it
            with _tmp.NamedTemporaryFile('w', delete=False, encoding='utf-8', newline='\n') as lf:
                for p in java_files:
                    lf.write(p + "\n")
                list_path = lf.name
            try:
                cmd3 = [cloc_exe, "--json", "--quiet", f"--list-file={list_path}"]
                res3 = subprocess.run(cmd3, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1800, text=True, encoding="utf-8", errors="ignore")
                if res3.returncode == 0:
                    data3 = _parse(res3.stdout)
                    s3 = data3.get("SUM", {})
                    if not s3:
                        totals3 = {"nFiles": 0, "code": 0, "comment": 0, "blank": 0}
                        for lang, stats in data3.items():
                            if lang in ("header", "SUM"):
                                continue
                            for k in totals3:
                                v = stats.get(k)
                                if isinstance(v, int):
                                    totals3[k] += v
                        s3 = totals3
                    s = s3
            finally:
                try:
                    os.remove(list_path)
                except Exception:
                    pass
    - Em caso de falha, tenta novamente apontando para src/main/java ou src.
    """
    ensure_dir(out_dir)
    class_csv = os.path.join(out_dir, "class.csv")
    if os.path.isfile(class_csv) and os.path.getsize(class_csv) > 0:
        return class_csv

    # Opções da JVM e log4j
    log4j_prop = os.path.join(os.path.dirname(ck_jar), "log4j.properties")
    jvm_opts: List[str] = [f"-Xms{jvm_xms}", f"-Xmx{jvm_xmx}"]
    if os.path.isfile(log4j_prop):
        jvm_opts.append(f"-Dlog4j.configuration=file:{log4j_prop}")

    def _invoke(path: str) -> Tuple[int, bytes, bytes]:
        cmd = [java_exe, *jvm_opts, "-jar", ck_jar, path, "true", "0", "false"]
        res = subprocess.run(cmd, cwd=out_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3600)
        return res.returncode, res.stdout, res.stderr

    def _try_move_fallback(src_root: str) -> None:
        # alguns CK gravam class.csv no diretório do projeto
        fallback = os.path.join(src_root, "class.csv")
        if os.path.isfile(fallback):
            shutil.move(fallback, class_csv)

    # 1ª tentativa: raiz do repositório
    code, out, err = _invoke(repo_dir)
    if code == 0:
        _try_move_fallback(repo_dir)
    else:
        _try_move_fallback(repo_dir)
        if not os.path.isfile(class_csv):
            # 2ª tentativa: src/main/java ou src
            candidates = [
                os.path.join(repo_dir, "src", "main", "java"),
                os.path.join(repo_dir, "src"),
            ]
            alt = next((p for p in candidates if os.path.isdir(p)), None)
            if alt:
                code2, out2, err2 = _invoke(alt)
                if code2 == 0:
                    _try_move_fallback(alt)
                else:
                    _try_move_fallback(alt)
                    if not os.path.isfile(class_csv):
                        msg = (err2 or out2 or err or out).decode(errors="ignore")
                        raise RuntimeError(f"CK falhou: {msg.strip()}")
            else:
                msg = (err or out).decode(errors="ignore")
                raise RuntimeError(f"CK falhou: {msg.strip()}")

    if not os.path.isfile(class_csv):
        # último fallback
        _try_move_fallback(repo_dir)
    if not os.path.isfile(class_csv):
        raise RuntimeError("CK não gerou class.csv")
    return class_csv


def parse_float_safe(s: str) -> Optional[float]:
    try:
        return float(s)
    except Exception:
        return None


def summarize_ck_class(class_csv: str) -> Tuple[int, float, float, float, float, float, float, float, float]:
    # Retorna: n_classes, cbo_mean, cbo_med, cbo_std, dit_mean, dit_med, dit_std, lcom_mean, lcom_med, lcom_std
    import math
    vals_cbo: List[float] = []
    vals_dit: List[float] = []
    vals_lcom: List[float] = []
    with open(class_csv, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        fields = [fn.lower() for fn in (r.fieldnames or [])]
        def pick(*cands: str) -> Optional[str]:
            for c in cands:
                if c.lower() in fields:
                    return r.fieldnames[fields.index(c.lower())]  # type: ignore[index]
            return None
        c_cbo = pick("cbo", "cbomodified")
        c_dit = pick("dit")
        c_lcom = pick("lcom", "lcom*", "lcomstar", "lcoms")
        for row in r:
            if c_cbo:
                v = parse_float_safe(row.get(c_cbo, ""))
                if v is not None:
                    vals_cbo.append(v)
            if c_dit:
                v = parse_float_safe(row.get(c_dit, ""))
                if v is not None:
                    vals_dit.append(v)
            if c_lcom:
                v = parse_float_safe(row.get(c_lcom, ""))
                if v is not None:
                    vals_lcom.append(v)
    def stats(a: List[float]) -> Tuple[float, float, float]:
        if not a:
            return float("nan"), float("nan"), float("nan")
        n = len(a)
        mean = sum(a) / n
        s = sorted(a)
        med = s[n//2] if n % 2 else 0.5*(s[n//2-1] + s[n//2])
        if n < 2:
            std = 0.0
        else:
            var = sum((x-mean)**2 for x in a)/(n-1)
            std = math.sqrt(var if var > 0 else 0.0)
        return mean, med, std
    cbo_mean, cbo_med, cbo_std = stats(vals_cbo)
    dit_mean, dit_med, dit_std = stats(vals_dit)
    lcom_mean, lcom_med, lcom_std = stats(vals_lcom)
    n_classes = len(vals_cbo) or len(vals_dit) or len(vals_lcom)
    return n_classes, cbo_mean, cbo_med, cbo_std, dit_mean, dit_med, dit_std, lcom_mean, lcom_med, lcom_std


def append_row(path: str, fieldnames: List[str], row: Dict[str, object]) -> None:
    # Single-writer lock so multiple workers don't interleave writes
    if not hasattr(append_row, "_lock"):
        append_row._lock = threading.Lock()  # type: ignore[attr-defined]
    with append_row._lock:  # type: ignore[attr-defined]
        ensure_dir(os.path.dirname(path))
        file_exists = os.path.isfile(path) and os.path.getsize(path) > 0
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                w.writeheader()
            w.writerow({k: row.get(k) for k in fieldnames})


def process_one(
    idx: int,
    name: str,
    url: str,
    work_parent: str,
    cloc_out: str,
    ck_out: str,
    git_exe: str,
    cloc_exe: Optional[str],
    java_exe: Optional[str],
    ck_jar: str,
    skip_cloc: bool = False,
    skip_ck: bool = False,
    keep_temp: bool = False,
) -> bool:
    print(f"[{idx}] Processando {name}...")
    repo_dir = os.path.join(work_parent, name.replace('/', '__'))
    try:
        # Cleanup any leftover dir
        if os.path.isdir(repo_dir):
            safe_rmtree(repo_dir)

        ok, msg = git_shallow_clone(url, repo_dir, git_exe)
        if not ok:
            # Fallback: Windows-safe .java-only extraction for repos with invalid paths
            print(f"[CLONE FAIL] {name}: {msg}")
            print(f"[CLONE RETRY] {name}: tentando extrair apenas .java com caminhos sanitizados...")
            ok2, msg2 = clone_and_extract_java_only(url, repo_dir, git_exe)
            if not ok2:
                print(f"[CLONE RETRY FAIL] {name}: {msg2}")
                return False

        # cloc
        if skip_cloc:
            print(f"[CLOC SKIP] {name}: skip_cloc flag enabled")
        elif cloc_exe:
            try:
                cloc = run_cloc_tree(repo_dir, cloc_exe, java_only=True)
                append_row(
                    cloc_out,
                    ["repo", "files", "code", "comment", "blank"],
                    {"repo": name, **cloc},
                )
            except Exception as e:
                print(f"[CLOC FAIL] {name}: {e}")
                append_row(
                    cloc_out,
                    ["repo", "files", "code", "comment", "blank"],
                    {"repo": name, "files": 0, "code": 0, "comment": 0, "blank": 0},
                )
        else:
            print(f"[CLOC SKIP] {name}: cloc não disponível")
            append_row(
                cloc_out,
                ["repo", "files", "code", "comment", "blank"],
                {"repo": name, "files": 0, "code": 0, "comment": 0, "blank": 0},
            )

        # CK
        if skip_ck:
            print(f"[CK SKIP] {name}: skip_ck flag enabled")
        elif java_exe:
            try:
                ck_tmp = os.path.join(repo_dir, "_ck_out")
                class_csv = run_ck(ck_jar, repo_dir, ck_tmp, java_exe, jvm_xms=process_one._ck_xms, jvm_xmx=process_one._ck_xmx)  # type: ignore[attr-defined]
                n_classes, cbo_mean, cbo_med, cbo_std, dit_mean, dit_med, dit_std, lcom_mean, lcom_med, lcom_std = summarize_ck_class(class_csv)
                append_row(
                    ck_out,
                    [
                        "repo", "n_classes",
                        "cbo_mean", "cbo_median", "cbo_std",
                        "dit_mean", "dit_median", "dit_std",
                        "lcom_mean", "lcom_median", "lcom_std",
                    ],
                    {
                        "repo": name,
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
                    },
                )
            except Exception as e:
                print(f"[CK FAIL] {name}: {e}")
                append_row(
                    ck_out,
                    [
                        "repo", "n_classes",
                        "cbo_mean", "cbo_median", "cbo_std",
                        "dit_mean", "dit_median", "dit_std",
                        "lcom_mean", "lcom_median", "lcom_std",
                    ],
                    {
                        "repo": name,
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
                    },
                )
        else:
            print(f"[CK SKIP] {name}: java não disponível")
            append_row(
                ck_out,
                [
                    "repo", "n_classes",
                    "cbo_mean", "cbo_median", "cbo_std",
                    "dit_mean", "dit_median", "dit_std",
                    "lcom_mean", "lcom_median", "lcom_std",
                ],
                {
                    "repo": name,
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
                },
            )
        print(f"[OK] {name}")
        return True
    finally:
        # Delete repo unless keep_temp is requested (debug/deep-dive)
        if not keep_temp:
            try:
                safe_rmtree(repo_dir)
            except Exception:
                pass


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Streaming: clone, medir cloc/CK, salvar sumários e deletar repo")
    p.add_argument("--csv", type=str, default="sprint2/data/repos_list.csv")
    p.add_argument("--work_dir", type=str, default="sprint2/data/_stream_tmp")
    p.add_argument("--out_dir", type=str, default="sprint2/data/processed")
    p.add_argument("--out_suffix", type=str, default="", help="Sufixo opcional para nomes dos CSVs (ex.: _shardA). Útil para rodar múltiplos processos em paralelo sem conflito de escrita.")
    p.add_argument("--ck_jar", type=str, default=None)
    p.add_argument("--git_exe", type=str, default=None, help="Caminho para git.exe (opcional)")
    p.add_argument("--cloc_exe", type=str, default=None, help="Caminho para cloc.exe (opcional)")
    p.add_argument("--java_exe", type=str, default=None, help="Caminho para java.exe (opcional)")
    p.add_argument("--max", type=int, default=1000)
    p.add_argument("--start_at", type=int, default=0, help="Pula os N primeiros da lista após filtro")
    p.add_argument("--filter_regex", type=str, default=None, help="Processa apenas repositórios cujo 'owner/repo' casa com regex")
    p.add_argument("--keep_temp", action="store_true", help="Não deletar pasta temporária do repo (debug)")
    p.add_argument("--workers", type=int, default=1, help="Número de repositórios processados em paralelo")
    p.add_argument("--shard_mod", type=int, default=1, help="Divisor para sharding por índice global (ex.: 3)")
    p.add_argument("--shard_idx", type=int, default=0, help="Índice deste shard no intervalo [0, shard_mod)")
    p.add_argument("--skip_ck", action="store_true", help="Pular execução do CK (apenas CLOC)")
    p.add_argument("--skip_cloc", action="store_true", help="Pular execução do CLOC (apenas CK)")
    p.add_argument("--ck_xms", type=str, default="256m", help="Memória inicial da JVM para CK (ex.: 256m)")
    p.add_argument("--ck_xmx", type=str, default="1024m", help="Memória máxima da JVM para CK (ex.: 1024m ou 2g)")
    p.add_argument("--cloc_extended", action="store_true", help="Ativa varreduras mais exaustivas do CLOC para casos problemáticos")
    args = p.parse_args()

    try:
        ck_jar = find_ck_jar(args.ck_jar)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 2

    # Validar sharding
    if args.shard_mod < 1:
        print("ERRO: --shard_mod deve ser >= 1", file=sys.stderr)
        return 2
    if not (0 <= args.shard_idx < args.shard_mod):
        print("ERRO: --shard_idx deve estar em [0, --shard_mod)", file=sys.stderr)
        return 2

    # Resolver executáveis (robusto em Windows)
    is_windows = os.name == "nt"
    java_home = os.environ.get("JAVA_HOME")
    java_candidates: List[str] = []
    if java_home:
        java_candidates.append(os.path.join(java_home, "bin", "java.exe" if is_windows else "java"))
    # Common install locations
    if is_windows:
        java_candidates += [
            r"C:\\Program Files\\Eclipse Adoptium\\jdk-21*\\bin\\java.exe",
            r"C:\\Program Files\\Eclipse Adoptium\\jdk-17*\\bin\\java.exe",
            r"C:\\Program Files\\Java\\jdk*\\bin\\java.exe",
            r"C:\\Program Files\\Microsoft\\jdk*\\bin\\java.exe",
        ]
        # Expand globs
        expanded: List[str] = []
        import glob as _glob
        for pat in java_candidates:
            if "*" in pat:
                expanded += _glob.glob(pat)
            else:
                expanded.append(pat)
        java_candidates = expanded

    git_candidates = []
    if is_windows:
        git_candidates = [
            r"C:\\Program Files\\Git\\bin\\git.exe",
            r"C:\\Program Files\\Git\\cmd\\git.exe",
            r"C:\\Program Files (x86)\\Git\\bin\\git.exe",
            r"C:\\Program Files (x86)\\Git\\cmd\\git.exe",
        ]

    cloc_candidates = []
    if is_windows:
        # Include common Chocolatey and WinGet shim locations
        cloc_candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\\Microsoft\\WinGet\\Links\\cloc.exe"),
            r"C:\\ProgramData\\chocolatey\\bin\\cloc.exe",
            r"C:\\Program Files\\cloc\\cloc.exe",
        ]

    git_exe = resolve_executable("git.exe" if is_windows else "git", args.git_exe, git_candidates)
    # cloc may be installed as 'cloc' (winget) or 'cloc.exe' (choco). Try both.
    if is_windows:
        cloc_exe = resolve_executable("cloc", args.cloc_exe, cloc_candidates)
        if not cloc_exe:
            cloc_exe = resolve_executable("cloc.exe", args.cloc_exe, cloc_candidates)
    else:
        cloc_exe = resolve_executable("cloc", args.cloc_exe, cloc_candidates)
    java_exe = resolve_executable("java.exe" if is_windows else "java", args.java_exe, java_candidates)

    if not git_exe:
        print("ERRO: git não encontrado no PATH. Informe --git_exe ou instale o Git for Windows.", file=sys.stderr)
        return 2
    if not cloc_exe:
        print("AVISO: cloc não encontrado; pulando métricas de LOC. Você pode instalar com sprint2/scripts/setup_cloc.ps1 ou informar --cloc_exe.")
    if not java_exe:
        print("AVISO: java não encontrado; CK será pulado. Ajuste JAVA_HOME ou informe --java_exe.")

    print(f"git: {git_exe}")
    print(f"cloc: {cloc_exe or 'NOT FOUND'}")
    print(f"java: {java_exe or 'NOT FOUND'}")

    # Pré-gera caminhos de saída (permite sufixo para sharding seguro)
    suffix = args.out_suffix or ""
    cloc_out = os.path.join(args.out_dir, f"cloc_summary{suffix}.csv")
    ck_out = os.path.join(args.out_dir, f"ck_summary{suffix}.csv")

    # Prepare work plan
    work_parent = os.path.abspath(args.work_dir)
    ensure_dir(work_parent)
    selected: List[Tuple[int, str, str]] = []
    for i, (name, url) in enumerate(iter_repos(args.csv, args.filter_regex)):
        if i < args.start_at:
            continue
        # apply modulo sharding based on global index i
        if ((i - args.start_at) % args.shard_mod) != args.shard_idx:
            continue
        if len(selected) >= args.max:
            break
        selected.append((i, name, url))

    total = len(selected)
    if total == 0:
        print("Nada para processar no intervalo selecionado.")
        return 0

    print(f"Iniciando {total} repositórios com {max(1, args.workers)} worker(s)...")

    processed = 0
    # Stash CK memory opts on function for easy access inside workers without changing many signatures
    process_one._ck_xms = args.ck_xms  # type: ignore[attr-defined]
    process_one._ck_xmx = args.ck_xmx  # type: ignore[attr-defined]
    # Toggle extended cloc behavior
    run_cloc_tree._extended = args.cloc_extended  # type: ignore[attr-defined]
    if args.workers <= 1:
        for idx, name, url in selected:
            ok = process_one(idx, name, url, work_parent, cloc_out, ck_out, git_exe, cloc_exe, java_exe, ck_jar, skip_cloc=args.skip_cloc, skip_ck=args.skip_ck, keep_temp=args.keep_temp)
            processed += 1 if ok else 0
    else:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
            futures = [
                ex.submit(process_one, idx, name, url, work_parent, cloc_out, ck_out, git_exe, cloc_exe, java_exe, ck_jar, args.skip_cloc, args.skip_ck, args.keep_temp)
                for idx, name, url in selected
            ]
            for fut in as_completed(futures):
                try:
                    ok = fut.result()
                    processed += 1 if ok else 0
                except Exception as e:
                    print(f"[WORKER FAIL] {e}")

    print(f"Concluído. Processados: {processed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
