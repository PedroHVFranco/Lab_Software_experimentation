#!/usr/bin/env python3
"""
Fetch top-N Java repositories from GitHub using GraphQL Search API and save to CSV.

Outputs: sprint2/data/repos_list.csv with columns:
- repo (owner/name)
- url
- stars
- created_at (ISO8601)
- releases
- age_years (float)

Usage (PowerShell):
  $env:GITHUB_TOKEN = "<your_token_here>"
  python sprint2/scripts/fetch_repos_graphql.py --max 1000 --out sprint2/data/repos_list.csv

Notes:
- Requires env var GITHUB_TOKEN (classic fine-grained or classic) with public_repo read.
- Paginates in batches of 100 until reaching --max or list ends.
- Sorts by stars (desc) and filters language:Java.
"""
from __future__ import annotations
import os
import sys
import csv
import time
import math
import json
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

import requests

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
BATCH_SIZE = 50


def iso_to_dt(s: str) -> datetime:
    # GitHub returns e.g., "2012-01-01T00:00:00Z"
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def years_between(start: datetime, end: Optional[datetime] = None) -> float:
    end = end or datetime.now(timezone.utc)
    delta = end - start
    return delta.total_seconds() / (365.25 * 24 * 3600)


@dataclass
class RepoItem:
    repo: str
    url: str
    stars: int
    created_at: str
    releases: int
    age_years: float


def build_query(after_cursor: Optional[str]) -> Dict[str, Any]:
    query_str = "language:Java sort:stars"
    query = {
        "query": (
            "query($queryStr: String!, $pageSize: Int!, $cursor: String) {\n"
            "  rateLimit { cost remaining resetAt }\n"
            "  search(query: $queryStr, type: REPOSITORY, first: $pageSize, after: $cursor) {\n"
            "    repositoryCount\n"
            "    pageInfo { hasNextPage endCursor }\n"
            "    edges {\n"
            "      node {\n"
            "        ... on Repository {\n"
            "          nameWithOwner url stargazerCount createdAt isArchived isDisabled\n"
            "          releases { totalCount }\n"
            "          primaryLanguage { name }\n"
            "        }\n"
            "      }\n"
            "    }\n"
            "  }\n"
            "}"
        ),
        "variables": {
            "queryStr": query_str,
            "pageSize": BATCH_SIZE,
            "cursor": after_cursor,
        },
    }
    return query


def graphql_request(session: requests.Session, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    headers = {
        "Authorization": f"bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "sprint2-metrics-script"
    }
    resp = session.post(GITHUB_GRAPHQL_URL, json=payload, headers=headers, timeout=60)
    if resp.status_code == 401:
        raise SystemExit("Unauthorized. Check GITHUB_TOKEN.")
    if resp.status_code == 403:
        # Likely rate limit; surface the message to user
        try:
            data = resp.json()
            msg = data.get("message") or data
        except Exception:
            msg = resp.text
        raise RuntimeError(f"403 Forbidden / Rate limit: {msg}")
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data["data"]


def ensure_parent_dir(path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)


def save_csv(rows: List[RepoItem], out_path: str) -> None:
    ensure_parent_dir(out_path)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["repo", "url", "stars", "created_at", "releases", "age_years"])
        for r in rows:
            w.writerow([r.repo, r.url, r.stars, r.created_at, r.releases, f"{r.age_years:.6f}"])


def fetch_top_java_repos(max_items: int, token: str) -> List[RepoItem]:
    items: List[RepoItem] = []
    after: Optional[str] = None
    session = requests.Session()

    while len(items) < max_items:
        payload = build_query(after)
        data = graphql_request(session, token, payload)
        search = data["search"]
        page_info = search["pageInfo"]
        edges = search.get("edges") or []

        batch_count = 0
        for e in edges:
            node = e.get("node") or {}
            # Filter to Java repos only (redundant due to query) and not disabled/archived
            primary_lang = (node.get("primaryLanguage") or {}).get("name")
            if primary_lang and primary_lang.lower() != "java":
                continue
            if node.get("isDisabled"):
                continue
            name_with_owner = node.get("nameWithOwner")
            url = node.get("url")
            stars = int(node.get("stargazerCount") or 0)
            created_at = node.get("createdAt")
            releases = int(((node.get("releases") or {}).get("totalCount")) or 0)

            try:
                created_dt = iso_to_dt(created_at)
                age = years_between(created_dt)
            except Exception:
                created_dt = None
                age = float("nan")

            items.append(RepoItem(
                repo=name_with_owner,
                url=url,
                stars=stars,
                created_at=created_at,
                releases=releases,
                age_years=age,
            ))
            batch_count += 1
            if len(items) >= max_items:
                break

        if len(items) >= max_items:
            break
        if not page_info.get("hasNextPage"):
            break
        after = page_info.get("endCursor")
        # be nice with API
        time.sleep(2)

    return items


def parse_args(argv: List[str]) -> Dict[str, Any]:
    import argparse
    p = argparse.ArgumentParser(description="Fetch top-N Java repos via GitHub GraphQL")
    p.add_argument("--max", type=int, default=1000, help="Max repositories to fetch (default 1000)")
    p.add_argument("--out", type=str, default="sprint2/data/repos_list.csv", help="Output CSV path")
    p.add_argument("--token", type=str, default=os.environ.get("GITHUB_TOKEN"), help="GitHub token (or set env GITHUB_TOKEN)")
    p.add_argument("--verbose", action="store_true", help="Verbose logging")
    args = p.parse_args(argv)
    return vars(args)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    token = args.get("token")
    if not token:
        print("Error: Provide a GitHub token via --token or env GITHUB_TOKEN", file=sys.stderr)
        return 2

    max_items = max(1, min(1000, int(args.get("max") or 1000)))
    out_path = args.get("out") or "sprint2/data/repos_list.csv"
    verbose = bool(args.get("verbose"))

    if verbose:
        print(f"Fetching up to {max_items} repos...", file=sys.stderr)

    try:
        rows = fetch_top_java_repos(max_items=max_items, token=token)
    except RuntimeError as e:
        print(f"GraphQL error: {e}", file=sys.stderr)
        return 1

    save_csv(rows, out_path)

    if verbose:
        print(f"Saved {len(rows)} rows to {out_path}")
    else:
        print(f"OK: {len(rows)} repos -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
