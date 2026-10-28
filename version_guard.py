"""Check Python code against current official docs using Yuanbao Search.

Usage:
    python version_guard.py check snippet.py      # or a .md file with ```python blocks

Set YUANBAO_API_KEY or enter it at the hidden prompt. Search records are
cached under data/cache; a cached query is never sent again.
"""

import argparse
import ast
import getpass
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

from research_client import collect, decode_pages, is_domain

BASE = Path(__file__).resolve().parent
CACHE = BASE / "data" / "cache"

# Only these domains count as evidence; everything else is ignored.
DOC_SITES = {
    "python": "docs.python.org",
    "pandas": "pandas.pydata.org",
    "numpy": "numpy.org",
    "pydantic": "docs.pydantic.dev",
    "sklearn": "scikit-learn.org",
    "matplotlib": "matplotlib.org",
    "PIL": "pillow.readthedocs.io",
    "flask": "flask.palletsprojects.com",
    "fastapi": "fastapi.tiangolo.com",
    "sqlalchemy": "docs.sqlalchemy.org",
    "torch": "pytorch.org",
    "openai": "developers.openai.com",
    "langchain": "docs.langchain.com",
    "langgraph": "docs.langchain.com",
    "requests": "requests.readthedocs.io",
}
DISPLAY = {"sklearn": "scikit-learn", "PIL": "Pillow"}
STDLIB = set(sys.stdlib_module_names)
# Method names too generic to search for on an unknown receiver.
GENERIC = {
    "get", "set", "run", "create", "update", "delete", "list", "items", "keys",
    "values", "read", "write", "close", "open", "format", "join", "split",
    "strip", "replace", "lower", "upper", "sum", "mean", "head", "tail",
    "loc", "iloc", "shape", "columns", "index", "print", "send", "recv",
    "encode", "decode", "startswith", "endswith", "beta", "chat", "path",
    "name", "parent", "exists", "result", "content", "text", "json", "status_code",
}

PENDING = re.compile(r"will be removed|to be removed|pending removal|scheduled for removal", re.I)
BREAKING = re.compile(
    r"\bremoved\b|\bremove the\b|\bno longer\b|\bnow raises?\b|\bshut ?down\b|\bsunset\b"
    r"|\benforced deprecation\b|已移除|已删除|被移除|不再", re.I)
DEPRECATED = re.compile(r"\bdeprecat\w*|\blegacy\b|弃用|废弃", re.I)
# Migration tables say "trapz  Use np.trapezoid instead" with no status word.
REPLACED = re.compile(r"\buse\b.{1,80}\binstead\b|改用|请使用", re.I)
# A symbol right after "use" is the recommended replacement, not the old API.
RECOMMENDED = re.compile(r"(?:\buse\b|\binstead of\b|改用|替换为|请使用)[\s`'\"(]*(?:[\w.]+\.)?$", re.I)
# Whole-module removals are described as modules ("imp module", "telnetlib --- ...").
MODULE_CONTEXT = re.compile(r"module|package|---|模块|模組", re.I)
VERSION_IN_PATH =re.compile(r"/(?:version/|docs/)?(\d+(?:\.\d+)+|stable|current|latest|dev)/", re.I)
NEAR = 120  # characters on each side of the symbol that may carry its status
RANK = {"breaking": 3, "deprecated": 2, "mentioned": 1, "no_evidence": 0}


def lib_of(dotted: str) -> str:
    """Map a dotted import path to the key used in DOC_SITES."""
    top = dotted.split(".")[0]
    return "python" if top in STDLIB else top


def _dotted(node: ast.AST) -> list[str] | None:
    """Return ['a', 'b', 'c'] for a.b.c, or None if the chain has calls etc."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return parts[::-1]


def extract_symbols(code: str) -> list[dict]:
    """Statically list modules, attributes, methods and keywords a snippet uses."""
    tree = ast.parse(code)
    aliases, found = {}, {}

    def add(lib, symbol, strict, loose, kind, line):
        found.setdefault((lib, symbol), {"lib": lib, "symbol": symbol, "strict": strict,
                                         "loose": loose, "kind": kind, "line": line})

    def add_module(top, line):
        # Whole-module removals only happen in the stdlib; a third-party
        # top-level package name is too broad to search for.
        if lib_of(top) == "python":
            add("python", top, [top], [top], "module", line)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                aliases[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
                add_module(a.name.split(".")[0], node.lineno)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            top = node.module.split(".")[0]
            add_module(top, node.lineno)
            for a in node.names:
                aliases[a.asname or a.name] = f"{node.module}.{a.name}"
                if a.name != "*":
                    # Functions are matched by name; classes keep their module.
                    strict = [a.name] if a.name[:1].islower() else [f"{node.module.split('.')[-1]}.{a.name}"]
                    add(lib_of(top), f"{node.module}.{a.name}", strict, [a.name], "attr", node.lineno)

    third_party = sorted({lib_of(v) for v in aliases.values()} - {"python"})
    method_libs = third_party[:2] or ["python"]
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}

    def resolve(func):
        parts = _dotted(func)
        if not parts:
            return None, None
        if parts[0] in aliases:
            full = aliases[parts[0]].split(".") + parts[1:]
            return lib_of(full[0]), full
        return None, parts

    # df = pd.read_csv(...) ties df to pandas, so df.append is searched once.
    var_lib = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Call)):
            lib, parts = resolve(node.value.func)
            lib = lib or (var_lib.get(parts[0]) if parts else None)
            if lib:
                var_lib[node.targets[0].id] = lib

    def libs_for(parts):
        return [var_lib[parts[0]]] if parts[0] in var_lib else method_libs

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and not isinstance(parents.get(node), ast.Attribute):
            lib, parts = resolve(node)
            if parts is None:
                continue
            if lib:
                # numpy.trapz is written np.trapz in docs, so a module-level
                # function is matched by name; datetime.utcnow keeps its class.
                strict = [".".join(parts[-2:])] if len(parts) > 2 else [parts[-1]]
                add(lib, ".".join(parts), strict, [parts[-1]], "attr", node.lineno)
            else:
                for name in parts[1:]:
                    if name not in GENERIC and not name.startswith("_"):
                        for m_lib in libs_for(parts):
                            add(m_lib, name, [name], [name], "method", node.lineno)
        if isinstance(node, ast.Call) and node.keywords:
            lib, parts = resolve(node.func)
            if not parts or len(parts) < 2 and not lib:
                continue
            for kw in node.keywords:
                if kw.arg is None:
                    continue
                for k_lib in ([lib] if lib else libs_for(parts)):
                    add(k_lib, f"{parts[-1]}({kw.arg}=)", [parts[-1], kw.arg],
                        [parts[-1], kw.arg], "keyword", node.lineno)
    return sorted(found.values(), key=lambda s: (s["line"], s["symbol"]))


def build_query(sym: dict) -> str:
    """Compose a search query of at most 64 characters."""
    name = DISPLAY.get(sym["lib"], sym["lib"])
    if sym["kind"] == "keyword":
        core = " ".join(sym["strict"])
    elif sym["kind"] == "attr":
        core = sym["strict"][0]
    else:
        core = sym["symbol"]
    return f"{name} {core} deprecated removed"[:64]


def _occurs(token: str, sentence: str, code_like: bool = False) -> int:
    """Position of the first occurrence of token as itself, or -1.

    Skips the recommended replacement and the owner of a member (DataFrame
    in DataFrame.applymap, datetime in "datetime's utcnow()", sys in
    "sys: ... deprecated"). code_like additionally requires `x`, .x or x(
    so prose words don't count."""
    pattern = re.compile(r"(?<![\w])" + re.escape(token) + r"(?![\w])(?!\.\w)(?!'s\b)(?!\s*[:：])")
    for match in pattern.finditer(sentence):
        if RECOMMENDED.search(sentence[max(0, match.start() - 20):match.start()]):
            continue
        before, after = sentence[match.start() - 1:match.start()], sentence[match.end():match.end() + 1]
        if code_like and not (before in ".`" or after in "(`"):
            continue
        return match.start()
    return -1


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?。；;])\s+|\n+", text) if s.strip()]


def classify(sentence: str) -> str | None:
    if PENDING.search(sentence):
        return "deprecated"
    if BREAKING.search(sentence):
        return "breaking"
    if DEPRECATED.search(sentence) or REPLACED.search(sentence):
        return "deprecated"
    return None


def version_hint(url: str) -> str | None:
    match = VERSION_IN_PATH.search(url)
    return match.group(1) if match else None


def judge(pages: list[dict], site: str, strict: list[str], loose: list[str],
          kind: str = "probe") -> dict:
    """Decide from official pages whether the symbol is breaking/deprecated.

    kind "probe" (designed test queries) matches tokens anywhere; symbols
    extracted from code must look like code (the first token), and module
    names must be described as modules."""
    official = [p for p in pages if site and is_domain(p.get("url", ""), site)]
    code_like = kind in ("attr", "method", "keyword")

    def window(tokens, sentence):
        """Text around the first token; snippets often lack sentence breaks,
        so the status word must be near the symbol, not anywhere in a blob."""
        if kind == "module" and not MODULE_CONTEXT.search(sentence):
            return None
        positions = [_occurs(t, sentence, code_like and i == 0) for i, t in enumerate(tokens)]
        if min(positions) < 0:
            return None
        return sentence[max(0, positions[0] - NEAR):positions[0] + NEAR]

    for level, tokens in (("strict", strict), ("loose", loose)):
        evidence = []
        for page in official:
            text = "\n".join(str(page.get(k) or "") for k in ("title", "passage", "content"))
            for sentence in split_sentences(text):
                near = window(tokens, sentence)
                if near is not None:
                    evidence.append({"url": page.get("url"), "title": page.get("title"),
                                     "date": page.get("date"), "version": version_hint(page.get("url", "")),
                                     "status": classify(near) or "mentioned",
                                     "sentence": near.strip()})
        if evidence:
            best = max(evidence, key=lambda e: RANK[e["status"]])
            return {"verdict": best["status"], "match": level, "official_pages": len(official),
                    "evidence": sorted(evidence, key=lambda e: -RANK[e["status"]])[:5]}
        if tokens == loose and strict == loose:
            break
    return {"verdict": "no_evidence", "match": None, "official_pages": len(official), "evidence": []}


def search(query: str, site: str | None, api_key_fn) -> dict:
    """Return a cached record or make one real SearchPro call."""
    request = {"Query": query, "Mode": 0, "Cnt": 10}
    if site:
        request["Site"] = site
    key = hashlib.sha1(json.dumps(request, sort_keys=True).encode()).hexdigest()[:16]
    path = CACHE / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    CACHE.mkdir(parents=True, exist_ok=True)
    record = collect({"id": key, "label": query, "request": request}, api_key_fn())
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    time.sleep(0.1)
    return record


def check_symbol(sym: dict, api_key_fn, query: str | None = None) -> dict:
    site = DOC_SITES.get(sym["lib"])
    if not site:
        return {**sym, "site": None, "query": None, "verdict": "unsupported_lib",
                "match": None, "official_pages": 0, "evidence": []}
    query = query or build_query(sym)
    record = search(query, site, api_key_fn)
    try:
        pages = decode_pages(record["response"])
        error = None
    except (ValueError, TypeError) as exc:
        pages, error = [], str(exc)
    request_id = record["response"].get("Response", {}).get("RequestId")
    return {**sym, "site": site, "query": query, "request_id": request_id,
            "http_status": record["status"], "error": error, "returned": len(pages),
            **judge(pages, site, sym["strict"], sym["loose"], sym["kind"])}


def code_blocks(text: str) -> list[str]:
    """Pull python code out of markdown, or treat the whole text as code."""
    blocks = re.findall(r"```(?:python|py)?[^\n]*\n(.*?)```", text, re.S)
    return blocks or [text]


def check_code(text: str, api_key_fn) -> dict:
    symbols, errors = [], []
    for block in code_blocks(text):
        try:
            symbols += extract_symbols(block)
        except SyntaxError as exc:
            errors.append(f"SyntaxError line {exc.lineno}: {exc.msg}")
    unique = list({(s["lib"], s["symbol"]): s for s in symbols}.values())
    return {"symbols": [check_symbol(s, api_key_fn) for s in unique], "parse_errors": errors}


def key_provider():
    """Ask for the key once, only when a real call is needed."""
    cache = {"key": os.environ.get("YUANBAO_API_KEY", "").strip()}

    def get():
        if not cache["key"]:
            cache["key"] = getpass.getpass("Yuanbao API Key (hidden): ").strip()
        return cache["key"]
    return get


LABEL = {"breaking": "❌ 已删除/行为变更", "deprecated": "⚠️ 已弃用", "mentioned": "· 文档提及，无变更描述",
         "no_evidence": "· 官方文档未检出", "unsupported_lib": "· 未配置官方域名"}


def render(result: dict) -> str:
    lines = ["| 位置 | 符号 | 判定 | 证据 |", "|---|---|---|---|"]
    for s in sorted(result["symbols"], key=lambda s: -RANK.get(s["verdict"], -1)):
        ev = s["evidence"][0] if s["evidence"] else None
        proof = f"{ev['sentence'][:120]} ({ev['url']})" if ev and s["verdict"] in ("breaking", "deprecated") else ""
        lines.append(f"| L{s['line']} | `{s['symbol']}` | {LABEL.get(s['verdict'], s['verdict'])} | {proof} |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check")
    check.add_argument("file", type=Path)
    check.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = check_code(args.file.read_text(encoding="utf-8"), key_provider())
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(render(result))
    for err in result["parse_errors"]:
        print("解析失败：", err)


if __name__ == "__main__":
    main()
