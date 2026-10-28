"""Collect Yuanbao Search evidence using Python's standard library.

Set YUANBAO_API_KEY or enter it at the hidden prompt. Existing records are
reused by default. --force makes new, potentially billable API calls.
"""

import argparse
import getpass
import json
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

ENDPOINT = "https://api.wsa.cloud.tencent.com/SearchPro"
BASE = Path(__file__).resolve().parent


def decode_pages(response: dict) -> list[dict]:
    """Decode serialized Pages without modifying the original response."""
    root = response.get("Response", response)
    if root.get("Error"):
        raise ValueError(json.dumps(root["Error"], ensure_ascii=False))
    # In the saved Mode=1 no-hit response, Pages was omitted entirely.
    if "Pages" not in root and all(k in root for k in ("RequestId", "Query", "Version")):
        return []
    if not isinstance(root.get("Pages"), list):
        raise ValueError("Response.Pages must be an array")
    pages = []
    for item in root["Pages"]:
        page = json.loads(item) if isinstance(item, str) else item
        if not isinstance(page, dict):
            raise ValueError("Each decoded page must be an object")
        pages.append(page)
    return pages


def is_domain(url: str, domain: str) -> bool:
    """Match a domain and its subdomains, excluding lookalike domains."""
    host = (urlsplit(url).hostname or "").lower()
    domain = domain.lower()
    return host == domain or host.endswith("." + domain)


def canonical_url(url: str) -> str:
    """Remove fragments and tracking parameters, keeping meaningful queries."""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_")]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path,
                       urlencode(query), ""))


def collect(job: dict, api_key: str) -> dict:
    """Make one real request and retain status, timing and raw JSON body."""
    params = job["request"]
    query = params.get("Query", "")
    if not isinstance(query, str) or not query.strip() or len(query) > 64:
        raise ValueError("Use a nonempty Query of no more than 64 characters")
    request = Request(
        ENDPOINT,
        data=json.dumps(params, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + api_key},
        method="POST",
    )
    started_at = datetime.now().astimezone().isoformat()
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=60) as result:
            status, raw = result.status, result.read()
    except HTTPError as error:
        status, raw = error.code, error.read()
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    # Authentication headers are deliberately excluded from evidence files.
    return {"id": job["id"], "label": job["label"], "request": params,
            "status": status, "elapsed_ms": elapsed_ms,
            "recorded_at": started_at, "response": json.loads(raw)}


def summarize(record: dict) -> dict:
    """Describe actual results, distinguishing HTTP and business success."""
    try:
        pages = decode_pages(record["response"])
        error = None
    except (ValueError, TypeError) as exc:
        pages, error = [], str(exc)
    root = record["response"].get("Response", record["response"])
    domain = record["request"].get("Site", "")
    return {"id": record["id"], "label": record["label"],
            "request": record["request"], "http_status": record["status"],
            "business_ok": record["status"] == 200 and error is None,
            "error": error, "request_id": root.get("RequestId"),
            "version": root.get("Version"), "count": len(pages),
            "unique_urls": len({canonical_url(p.get("url", "")) for p in pages
                                 if p.get("url")}),
            "target_domain_matches": sum(is_domain(p.get("url", ""), domain)
                                         for p in pages) if domain else None,
            "with_content": sum(bool(p.get("content")) for p in pages),
            "with_date": sum(bool(p.get("date")) for p in pages),
            "page_item_types": sorted({type(p).__name__ for p in root.get("Pages", [])}),
            "pages_field_present": "Pages" in root,
            "elapsed_ms": record["elapsed_ms"]}


def main() -> None:
    """Collect only missing jobs and write a derived summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=Path, default=BASE / "jobs.json")
    parser.add_argument("--out", type=Path, default=BASE / "data")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    jobs = json.loads(args.jobs.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    key = os.environ.get("YUANBAO_API_KEY", "").strip()
    summary = []
    for job in jobs:
        path = args.out / (job["id"] + ".json")
        if path.exists() and not args.force:
            record = json.loads(path.read_text(encoding="utf-8"))
        else:
            if not key:
                key = getpass.getpass("Yuanbao API Key (hidden): ").strip()
            record = collect(job, key)
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        row = summarize(record)
        summary.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    (args.out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if any(not row["business_ok"] for row in summary):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
