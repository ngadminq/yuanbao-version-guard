"""Evaluate the version guard on cases.json.

    python evaluate.py probe                       # 28 targeted searches: does Yuanbao reach the official docs?
    python evaluate.py questions                   # write questions.md for manual asking
    python evaluate.py collect --name M --base-url URL --model MODEL   # ask an OpenAI-compatible LLM
    python evaluate.py import-md --name M FILE     # or import answers pasted into a markdown file
    python evaluate.py run --name M                # guard the answers, compute metrics

Search records are cached in data/cache, so reruns cost nothing.
LLM keys come from LLM_API_KEY or a hidden prompt and are never written to disk.
"""

import argparse
import csv
import getpass
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from version_guard import (DOC_SITES, check_code, check_symbol, code_blocks,
                           key_provider)

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
ANSWERS = BASE / "answers"
CASES = json.loads((BASE / "cases.json").read_text(encoding="utf-8"))
FLAGGED = {"breaking", "deprecated"}
SYSTEM = "你是一个 Python 编程助手。只输出一段完整可运行的 Python 代码，放在 ```python 代码块中，不要解释。"


def save(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def probe(_args) -> None:
    """One designed query per changed case; record whether official docs back it."""
    keys, rows = key_provider(), []
    for case in CASES:
        if case["status"] == "current":
            continue
        sym = {"lib": case["lib"], "symbol": case["tokens"][0], "strict": case["tokens"],
               "loose": case["tokens"], "kind": "probe", "line": 0}
        result = check_symbol(sym, keys, query=case["query"])
        expected = case["status"]
        row = {"id": case["id"], "query": case["query"], "site": result["site"],
               "request_id": result.get("request_id"), "returned": result.get("returned"),
               "official_pages": result["official_pages"], "verdict": result["verdict"],
               "expected": expected, "detected": result["verdict"] in FLAGGED,
               "exact": result["verdict"] == expected,
               "top_evidence": result["evidence"][:2], "source": case["source"]}
        rows.append(row)
        print(f"{row['id']:<22} official={row['official_pages']:>2}  verdict={row['verdict']:<11} expected={expected}")
    n = len(rows)
    summary = {
        "recorded_at": datetime.now().astimezone().isoformat(),
        "cases": n,
        "with_official_pages": sum(r["official_pages"] > 0 for r in rows),
        "change_detected": sum(r["detected"] for r in rows),
        "status_exact": sum(r["exact"] for r in rows),
        "rows": rows,
    }
    save(DATA / "probe.json", summary)
    print(f"\n命中官方文档 {summary['with_official_pages']}/{n}，检出变更 {summary['change_detected']}/{n}，"
          f"状态完全一致 {summary['status_exact']}/{n}  → data/probe.json")


def questions(_args) -> None:
    lines = ["# 测试问题（逐条复制给模型，每条新开对话）", "",
             "把回答按下面的标题粘贴到 answers/<模型名>.md，保留 ```python 代码块。", ""]
    for case in CASES:
        lines += [f"## {case['id']}", "", case["question"], ""]
    (BASE / "questions.md").write_text("\n".join(lines), encoding="utf-8")
    print("已写入 questions.md")


def collect(args) -> None:
    """Ask each question once through an OpenAI-compatible chat endpoint."""
    # A local server (vLLM etc.) usually needs no key; --ask-key prompts for one.
    key = os.environ.get("LLM_API_KEY", "").strip()
    if not key and args.ask_key:
        key = getpass.getpass("LLM API Key (hidden): ").strip()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    out = ANSWERS / f"{args.name}.json"
    answers = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    for case in CASES:
        if case["id"] in answers:
            continue
        body = {"model": args.model, "messages": [{"role": "system", "content": SYSTEM},
                                                   {"role": "user", "content": case["question"]}]}
        if args.reasoning_effort:
            body["reasoning_effort"] = args.reasoning_effort
        req = Request(args.base_url.rstrip("/") + "/chat/completions",
                      data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                      headers=headers, method="POST")
        started = time.perf_counter()
        with urlopen(req, timeout=900) as resp:
            reply = json.loads(resp.read())
        answers[case["id"]] = {"model": reply.get("model", args.model),
                               "endpoint_host": urlsplit(args.base_url).hostname,
                               "reasoning_effort": args.reasoning_effort,
                               "asked_at": datetime.now().astimezone().isoformat(),
                               "elapsed_ms": round((time.perf_counter() - started) * 1000),
                               "usage": reply.get("usage"),
                               "text": reply["choices"][0]["message"].get("content") or ""}
        save(out, answers)
        print("answered", case["id"], answers[case["id"]]["elapsed_ms"], "ms", flush=True)
        time.sleep(0.5)


def import_md(args) -> None:
    text = Path(args.file).read_text(encoding="utf-8")
    parts = re.split(r"^##\s+(\S+)\s*$", text, flags=re.M)
    ids = {c["id"] for c in CASES}
    answers = {pid: {"model": args.name, "endpoint_host": "manual", "asked_at": None, "text": body.strip()}
               for pid, body in zip(parts[1::2], parts[2::2]) if pid in ids}
    save(ANSWERS / f"{args.name}.json", answers)
    print(f"导入 {len(answers)} 条回答 → answers/{args.name}.json")


def run(args) -> None:
    answers = json.loads((ANSWERS / f"{args.name}.json").read_text(encoding="utf-8"))
    keys, results, review = key_provider(), [], []
    for case in CASES:
        if case["id"] not in answers:
            continue
        text = answers[case["id"]]["text"]
        code = "\n".join(code_blocks(text))
        stale = bool(case["stale_pattern"] and re.search(case["stale_pattern"], code))
        guard = check_code(text, keys)
        flags = [s for s in guard["symbols"] if s["verdict"] in FLAGGED]
        targets = [t.lower() for t in case["tokens"]]
        hit = any(any(t in s["symbol"].lower() or t in " ".join(s["strict"]).lower() for t in targets)
                  for s in flags)
        results.append({"id": case["id"], "expected_status": case["status"], "stale": stale,
                        "guard_hit_target": hit if stale else None, "flags": len(flags),
                        "symbols_checked": len(guard["symbols"]), "parse_errors": guard["parse_errors"],
                        "symbols": guard["symbols"]})
        for s in flags:
            ev = s["evidence"][0]
            review.append({"case": case["id"], "symbol": s["symbol"], "verdict": s["verdict"],
                           "match": s["match"], "evidence_url": ev["url"], "evidence": ev["sentence"],
                           "request_id": s.get("request_id"), "human_label": "", "reason": "", "reviewer": ""})
        print(f"{case['id']:<22} stale={str(stale):<5} flags={len(flags)} target_hit={hit if stale else '-'}")
    stale_n = sum(r["stale"] for r in results)
    changed = [r for r in results if r["expected_status"] != "current"]
    summary = {
        "model": args.name, "recorded_at": datetime.now().astimezone().isoformat(),
        "answers": len(results), "changed_cases": len(changed),
        "stale_answers": stale_n,
        "stale_rate": round(stale_n / len(changed), 3) if changed else None,
        "guard_caught_stale": sum(bool(r["guard_hit_target"]) for r in results),
        "flags_total": len(review),
        "flags_on_controls": sum(r["flags"] for r in results if r["expected_status"] == "current"),
        "symbols_checked": sum(r["symbols_checked"] for r in results),
    }
    save(DATA / f"run_{args.name}.json", {"summary": summary, "results": results})
    review_path = DATA / f"review_{args.name}.csv"
    # Rerunning must not wipe human review: carry labels over by (case, symbol).
    if review_path.exists():
        old = {(r["case"], r["symbol"]): r for r in csv.DictReader(open(review_path, encoding="utf-8-sig"))}
        for row in review:
            prev = old.get((row["case"], row["symbol"]), {})
            for field in ("human_label", "reason", "reviewer"):
                row[field] = prev.get(field, "")
    with open(review_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(review[0]) if review else ["case"])
        writer.writeheader()
        writer.writerows(review)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"人工复核：data/review_{args.name}.csv（human_label 填 对/错）")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe").set_defaults(fn=probe)
    sub.add_parser("questions").set_defaults(fn=questions)
    p = sub.add_parser("collect")
    p.add_argument("--name", required=True)
    p.add_argument("--base-url", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--reasoning-effort", choices=["low", "medium", "high", "xhigh"])
    p.add_argument("--ask-key", action="store_true")
    p.set_defaults(fn=collect)
    p = sub.add_parser("import-md")
    p.add_argument("--name", required=True)
    p.add_argument("file")
    p.set_defaults(fn=import_md)
    p = sub.add_parser("run")
    p.add_argument("--name", required=True)
    p.set_defaults(fn=run)
    args = parser.parse_args()
    assert set(c["lib"] for c in CASES) <= set(DOC_SITES), "every case lib needs a DOC_SITES entry"
    args.fn(args)


if __name__ == "__main__":
    main()
