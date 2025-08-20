# -*- coding: utf-8 -*-
import os, json, csv, time, datetime, pathlib, urllib.request, urllib.error, random

API = "https://api.github.com/graphql"
TOKEN = os.environ.get("GITHUB_TOKEN")

OUT = pathlib.Path("data"); OUT.mkdir(parents=True, exist_ok=True)
JSON_PATH = OUT / "top100.json"
CSV_PATH  = OUT / "top100.csv"

QUERY_PATH = pathlib.Path("queryLab1.graphql") 

QUERY = QUERY_PATH.read_text(encoding="utf-8")

##chamada para o graphQL "TESTE"
def call(query: str, variables: dict, timeout=60) -> dict:
    if not TOKEN:
        raise RuntimeError("Defina GITHUB_TOKEN.")
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "lab01-graphql-stdlib/1.0",
        "Connection": "close",
    }
    req = urllib.request.Request(API, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if "errors" in data:
        msg = json.dumps(data["errors"], ensure_ascii=False)
        if "timeout" in msg.lower() or "went wrong while executing your query" in msg.lower():
            raise RuntimeError(f"HEAVY_QUERY: {msg[:300]}")
        raise RuntimeError(msg)
    return data["data"]

##Teste de contorno erro 502
def try_fetch(after=None, page_size=100, max_shrinks=5):
    shrinks = 0
    cur_size = page_size 
    base = 0.8 #obs: tempo de espera a cada tentatica

    while True:
        try:
            time.sleep(base + random.uniform(0, 0.25)) 
            data = call(QUERY, {"after": after, "pageSize": cur_size})
            return data, cur_size
        except urllib.error.HTTPError as e:
            status = e.code
            txt = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
            if status in (502, 503, 504) and shrinks < max_shrinks:
                shrinks += 1
                cur_size = [60, 40, 25, 15, 10][min(shrinks-1, 4)]
                base *= 1.4
                print(f"[warn] HTTP {status}. Diminuindo pageSize para {cur_size} e tentando de novo.")
                continue
            raise RuntimeError(f"HTTP {status}: {txt[:400]}")
        except RuntimeError as re:
            msg = str(re)
            if msg.startswith("HEAVY_QUERY") and shrinks < max_shrinks:
                shrinks += 1
                cur_size = [60, 40, 25, 15, 10][min(shrinks-1, 4)]
                base *= 1.4
                print(f"[warn] Query pesada. pageSize→{cur_size}.")
                continue
            raise

def iso_to_dt(s: str | None):
    if not s: return None
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))

def normalize(nodes):
    now = datetime.datetime.now(datetime.timezone.utc)
    rows = []
    for r in nodes:
        created = iso_to_dt(r.get("createdAt"))
        updated = iso_to_dt(r.get("updatedAt")) or iso_to_dt(r.get("pushedAt"))
        idade_dias = (now - created).days if created else None
        dias_ult = (now - updated).days if updated else None
        issues_total  = (r.get("issues") or {}).get("totalCount", 0)
        issues_closed = (r.get("closedIssues") or {}).get("totalCount", 0)
        closed_ratio  = (issues_closed / issues_total) if issues_total else 0.0
        rows.append({
            "owner": (r.get("owner") or {}).get("login"),
            "name": r.get("name"),
            "url": r.get("url"),
            "stars": r.get("stargazerCount", 0),
            "createdAt": r.get("createdAt"),
            "idade_dias": idade_dias,
            "updatedAt": r.get("updatedAt") or r.get("pushedAt"),
            "dias_desde_ultima_atualizacao": dias_ult,
            "releases": (r.get("releases") or {}).get("totalCount", 0),
            "prsMerged": (r.get("pullRequests") or {}).get("totalCount", 0),
            "issuesTotal": issues_total,
            "issuesClosed": issues_closed,
            "closedRatio": round(closed_ratio, 4),
            "primaryLanguage": (r.get("primaryLanguage") or {}).get("name"),
        })
    return rows

##FUNC PARA SALVAR CSV
def save_csv(rows, path: pathlib.Path):
    cols = ["owner","name","url","stars","createdAt","idade_dias",
            "updatedAt","dias_desde_ultima_atualizacao","releases","prsMerged",
            "issuesTotal","issuesClosed","closedRatio","primaryLanguage"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)

##MAIN 
def main(target=1000, start_page_size=20):
    all_nodes = []
    seen_ids = set()
    after = None
    page_size = start_page_size

    while len(all_nodes) < target:
        data, used_size = try_fetch(after=after, page_size=page_size)
        rl = data.get("rateLimit", {})
        search = data["search"]
        page_nodes = search["nodes"]
        print(f"[ok] pageSize={used_size}  got={len(page_nodes)}  remaining={rl.get('remaining')}  resetAt={rl.get('resetAt')}")

        # trecho para parar de duplicar
        for n in page_nodes:
            if n["id"] not in seen_ids:
                all_nodes.append(n)
                seen_ids.add(n["id"])
                if len(all_nodes) >= target:
                    break

        # trecho para continuar as pags
        if len(all_nodes) >= target: break
        if not search["pageInfo"]["hasNextPage"]:
            break
        after = search["pageInfo"]["endCursor"]
        page_size = used_size  #para manter o tamanho funcional

    
    all_nodes = all_nodes[:target] # removedo excesso

    #convertendo e salvando em 2 arquvos
    rows = normalize(all_nodes)
    JSON_PATH.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    save_csv(rows, CSV_PATH)
    # teste
    print(f"[salvo] {len(rows)} linhas em\n  - {JSON_PATH}\n  - {CSV_PATH}")

   # teste
    print(json.dumps(rows[:3], indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main(target=1000, start_page_size=20)
