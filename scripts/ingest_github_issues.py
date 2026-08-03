"""
ingest_github_issues.py

One-time ingestion script: pulls all issues (open + closed) from the
digitalocean/doctl GitHub repository and freezes them into a local JSON
corpus. Run this once (or manually re-run to refresh) -- the application
itself should only ever read the persisted JSON output, never call GitHub
live at request time. This keeps the corpus stable across eval runs.

Usage:
    export GITHUB_TOKEN=ghp_xxxxxxxx   # optional but strongly recommended
    python scripts/ingest_github_issues.py --out data/corpus.json

Notes:
    - GitHub's REST /issues endpoint returns both issues AND pull requests.
      PRs are filtered out (they have a "pull_request" key).
    - Unauthenticated requests are rate-limited to 60/hr; authenticated
      requests get 5000/hr. Pass a token via GITHUB_TOKEN or --token.
    - This is intentionally simple: no retries beyond basic backoff on
      rate limiting, no incremental sync. Re-run from scratch if you need
      a fresh pull.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import urllib.request
import urllib.error

REPO_OWNER = "digitalocean"
REPO_NAME = "doctl"
API_BASE = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues"
PER_PAGE = 100


def build_request(url: str, token: str | None) -> urllib.request.Request:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "doctl-issue-ingest-script",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, headers=headers)


def fetch_page(url: str, token: str | None, max_retries: int = 3):
    for attempt in range(1, max_retries + 1):
        req = build_request(url, token)
        try:
            with urllib.request.urlopen(req) as resp:
                body = resp.read()
                link_header = resp.headers.get("Link", "")
                remaining = resp.headers.get("X-RateLimit-Remaining")
                return json.loads(body), link_header, remaining
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                # Likely rate-limited. Check reset header, back off, retry.
                reset = e.headers.get("X-RateLimit-Reset")
                wait = 5
                if reset:
                    wait = max(1, int(reset) - int(time.time()) + 1)
                print(
                    f"[rate limit] HTTP {e.code}, waiting {wait}s "
                    f"(attempt {attempt}/{max_retries})",
                    file=sys.stderr,
                )
                time.sleep(min(wait, 60))
                continue
            raise
    raise RuntimeError(f"Failed to fetch {url} after {max_retries} retries")


def parse_next_link(link_header: str) -> str | None:
    """Parse GitHub's Link header to find the 'next' page URL, if any."""
    if not link_header:
        return None
    parts = link_header.split(",")
    for part in parts:
        segments = part.split(";")
        if len(segments) < 2:
            continue
        url_part = segments[0].strip().strip("<>")
        rel_part = segments[1].strip()
        if rel_part == 'rel="next"':
            return url_part
    return None


def normalize_issue(raw: dict) -> dict:
    """Extract the fields relevant to classification, drop the rest."""
    labels = [lbl["name"] for lbl in raw.get("labels", [])]
    return {
        "issue_id": raw["number"],
        "title": raw.get("title", "") or "",
        "body": raw.get("body", "") or "",
        "state": raw.get("state"),  # "open" / "closed"
        "maintainer_labels": labels,
        "created_at": raw.get("created_at"),
        "closed_at": raw.get("closed_at"),
        "comments_count": raw.get("comments", 0),
        "url": raw.get("html_url"),
        # Filled in later by the labeling step -- left null at ingestion time.
        "ground_truth_label": None,
        "is_scored": False,
    }


def ingest(token: str | None, state: str = "all") -> list[dict]:
    issues = []
    url = f"{API_BASE}?state={state}&per_page={PER_PAGE}&sort=created&direction=asc"
    page_num = 1

    while url:
        print(f"Fetching page {page_num}...", file=sys.stderr)
        data, link_header, remaining = fetch_page(url, token)

        for raw in data:
            # Skip pull requests -- the /issues endpoint includes them.
            if "pull_request" in raw:
                continue
            issues.append(normalize_issue(raw))

        if remaining is not None and int(remaining) < 3:
            print("[rate limit] Low remaining quota, pausing 30s...", file=sys.stderr)
            time.sleep(30)

        url = parse_next_link(link_header)
        page_num += 1

    return issues


def main():
    parser = argparse.ArgumentParser(description="Ingest doctl GitHub issues into a stable JSON corpus.")
    parser.add_argument("--out", default="data/corpus.json", help="Output JSON file path")
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub personal access token (or set GITHUB_TOKEN env var). Optional but raises rate limit from 60/hr to 5000/hr.",
    )
    parser.add_argument(
        "--state",
        default="all",
        choices=["all", "open", "closed"],
        help="Which issues to pull (default: all)",
    )
    args = parser.parse_args()

    if not args.token:
        print(
            "[warning] No GITHUB_TOKEN provided -- limited to 60 requests/hr. "
            "For ~500 issues at 100/page this is fine, but set GITHUB_TOKEN if you hit limits.",
            file=sys.stderr,
        )

    issues = ingest(args.token, args.state)

    # Dedup safety net (shouldn't be needed, but cheap to guarantee).
    seen = {}
    for issue in issues:
        seen[issue["issue_id"]] = issue
    issues = sorted(seen.values(), key=lambda x: x["issue_id"])

    output = {
        "meta": {
            "repo": f"{REPO_OWNER}/{REPO_NAME}",
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "total_issues": len(issues),
            "state_filter": args.state,
        },
        "issues": issues,
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nDone. Wrote {len(issues)} issues to {args.out}", file=sys.stderr)
    print(
        "This file is now your frozen corpus -- the app should read from it, "
        "not call the GitHub API at runtime.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()