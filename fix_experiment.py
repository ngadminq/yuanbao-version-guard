"""Experiment 3: can the model fix its own outdated code?

For each answer that used an outdated API, ask the local model to fix it under
two conditions, N times each:
  A  reminder only ("check for deprecated/removed APIs and fix them")
  B  the same reminder + the top official passages Yuanbao returned for that API
Passages come from cached SearchPro records; this script makes no search calls.
Existing trials in data/fix_<name>.json are kept; rerunning only fills in missing ones.
"""

import argparse
import ast
import hashlib
import io
import json
import re
import time
import tokenize
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from research_client import decode_pages, is_domain
from version_guard import DOC_SITES, code_blocks

BASE = Path(__file__).resolve().parent
CASES = {c["id"]: c for c in json.loads((BASE / "cases.json").read_text(encoding="utf-8"))}
SYSTEM = "你是一个 Python 编程助手。只输出一段完整可运行的 Python 代码，放在 ```python 代码块中，不要解释。"
# The query whose results are pasted for each case: the designed probe query,
# or the variant that reached the relevant page (data/query_variants.json).
QUERY = {
    "pd-groupby-axis": "pandas 3.0 whatsnew groupby axis removed",
    "pd-fillna-method": "pandas 3.0 fillna method 参数 移除",
    "py-sqlite-version": "python 3.14 whatsnew sqlite3 version removed",
}
TOP_PAGES = 3


def cached_pages(query: str, site: str) -> tuple[list[dict], str]:
    request = {"Query": query, "Mode": 0, "Cnt": 10, "Site": site}
    key = hashlib.sha1(json.dumps(request, sort_keys=True).encode()).hexdigest()[:16]
    # Query-variant records are kept apart so the 186-record experiment cache stays as published.
    for folder in ("cache", "cache_query_variants"):
        path = BASE / "data" / folder / f"{key}.json"
        if path.exists():
            break
    record = json.loads(path.read_text(encoding="utf-8"))
    pages = [p for p in decode_pages(record["response"]) if is_domain(p.get("url", ""), site)]
    return pages, record["response"]["Response"]["RequestId"]


def evidence_block(case: dict) -> tuple[str, dict]:
    query = QUERY.get(case["id"], case["query"])
    pages, request_id = cached_pages(query, DOC_SITES[case["lib"]])
    chosen = pages[:TOP_PAGES]
    lines = [f"以下是用元宝搜索在官方文档中检索到的资料（查询：{query}）："]
    for i, p in enumerate(chosen, 1):
        lines.append(f"[{i}] {p.get('title', '')}\n来源：{p['url']}\n摘要：{p.get('passage', '')}")
    return "\n\n".join(lines), {"query": query, "request_id": request_id, "urls": [p["url"] for p in chosen]}


def prompt(case: dict, code: str, evidence: str | None) -> str:
    parts = [f"下面这段代码是针对这个需求写的：{case['question']}", f"```python\n{code}\n```"]
    if evidence:
        parts.append(evidence)
    parts.append("请检查这段代码是否用了已弃用或已删除的 API（以各库截至 2026 年的最新版本为准），"
                 "如果有，请改成当前推荐的写法；如果没有，原样输出。输出修正后的完整代码。")
    return "\n\n".join(parts)


def ask(base_url: str, model: str, effort: str, text: str) -> tuple[str, int, dict]:
    body = {"model": model, "reasoning_effort": effort,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}]}
    req = Request(base_url.rstrip("/") + "/chat/completions", data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                  headers={"Content-Type": "application/json"}, method="POST")
    # The local vLLM gateway sometimes answers 502/503 briefly; retry those only.
    for attempt in range(4):
        started = time.perf_counter()
        try:
            with urlopen(req, timeout=900) as resp:
                reply = json.loads(resp.read())
            break
        except HTTPError as error:
            if error.code < 500 or attempt == 3:
                raise
            time.sleep(10 * 2 ** attempt)
    return (reply["choices"][0]["message"].get("content") or "",
            round((time.perf_counter() - started) * 1000), reply.get("usage") or {})


def strip_comments(code: str) -> str:
    """Drop comments so "# telnetlib 已移除，改用 socket" doesn't count as using it."""
    try:
        tokens = [t for t in tokenize.generate_tokens(io.StringIO(code).readline) if t.type != tokenize.COMMENT]
        return tokenize.untokenize(tokens)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return code


def score(case_id: str, text: str) -> dict:
    raw = "\n".join(code_blocks(text))
    try:
        ast.parse(raw)
        parses = True
    except SyntaxError:
        parses = False
    code = strip_comments(raw)
    still = bool(re.search(CASES[case_id]["stale_pattern"], code))
    others = [cid for cid, c in CASES.items()
              if cid != case_id and c["stale_pattern"] and re.search(c["stale_pattern"], code)]
    return {"parses": parses, "still_stale": still, "new_stale": others, "fixed": parses and not still and not others}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="qwen3.8-27b")
    parser.add_argument("--base-url", required=True, help="OpenAI 兼容服务的 base URL，通常以 /v1 结尾")
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    answers = json.loads((BASE / "answers" / f"{args.name}.json").read_text(encoding="utf-8"))
    run = json.loads((BASE / "data" / f"run_{args.name}.json").read_text(encoding="utf-8"))
    stale_ids = [r["id"] for r in run["results"] if r["stale"]]
    out_path = BASE / "data" / f"fix_{args.name}.json"
    out = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {"trials": []}
    done = {(t["case"], t["condition"], t["repeat"]) for t in out["trials"]}
    for cid in stale_ids:
        case = CASES[cid]
        code = "\n".join(code_blocks(answers[cid]["text"]))
        evidence, source = evidence_block(case)
        for condition, ev in (("A_reminder", None), ("B_yuanbao", evidence)):
            for rep in range(args.repeats):
                if (cid, condition, rep) in done:
                    continue
                text, ms, usage = ask(args.base_url, args.model, args.effort, prompt(case, code, ev))
                trial = {"case": cid, "condition": condition, "repeat": rep, "elapsed_ms": ms, "usage": usage,
                         "asked_at": datetime.now().astimezone().isoformat(), "evidence_source": source if ev else None,
                         "text": text, **score(cid, text)}
                out["trials"].append(trial)
                out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"{cid:<20} {condition:<11} #{rep} fixed={trial['fixed']} still={trial['still_stale']} "
                      f"new={trial['new_stale']} {ms}ms", flush=True)
    summary = {}
    for t in out["trials"]:
        s = summary.setdefault(t["condition"], {"trials": 0, "fixed": 0, "still_stale": 0, "new_stale": 0})
        s["trials"] += 1
        s["fixed"] += t["fixed"]
        s["still_stale"] += t["still_stale"]
        s["new_stale"] += bool(t["new_stale"])
    out["summary"] = summary
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
