"""Run the saved pd-applymap answer unchanged, then replace applymap with map.

From the project root:
    uv run --python 3.12 --with pandas==3.0.0 python examples/migrate_applymap.py

The three-row input is the original answer's migration demonstration fixture,
not a business sample. No search/model API or credential is used by this script.
Outputs go to validation/migration/, leaving answers/ and data/ unchanged.
"""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import platform
import re
import sys

import pandas as pd


BASE = Path(__file__).resolve().parents[1]
SOURCE = BASE / "answers" / "qwen3.8-27b.json"
CASE_ID = "pd-applymap"
OUT = BASE / "validation" / "migration"


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def run_code(code: str, label: str) -> tuple[dict, dict]:
    namespace = {"__name__": "__migration_example__"}
    stdout = io.StringIO()
    error = None
    with contextlib.redirect_stdout(stdout):
        try:
            exec(compile(code, f"saved-answer:{CASE_ID}:{label}", "exec"), namespace)
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
    return {"success": error is None, "exception": error, "stdout": stdout.getvalue()}, namespace


def main() -> None:
    if pd.__version__ != "3.0.0":
        raise SystemExit("This demonstration requires pandas==3.0.0.")

    source_bytes = SOURCE.read_bytes()
    answer_text = json.loads(source_bytes)[CASE_ID]["text"]
    blocks = re.findall(r"```(?:python|py)\s*\n(.*?)```", answer_text, re.S)
    if len(blocks) != 1:
        raise AssertionError("Expected one complete Python block in the saved answer")
    old_code = blocks[0]
    if old_code.count(".applymap(") != 1:
        raise AssertionError("Expected exactly one .applymap( call")
    new_code = old_code.replace(".applymap(", ".map(")

    old, old_namespace = run_code(old_code, "original")
    new, new_namespace = run_code(new_code, "migrated")
    assert old["exception"] == {
        "type": "AttributeError",
        "message": "'DataFrame' object has no attribute 'applymap'",
    }, old
    assert new["success"], new
    input_data = old_namespace["df"].to_dict(orient="list")
    assert input_data == {"A": [1, 2, 3], "B": [4, 5, 6]}
    assert new_namespace["df"].to_dict(orient="list") == input_data
    result_data = new_namespace["result"].to_dict(orient="list")
    assert result_data == {"A": [2, 4, 6], "B": [8, 10, 12]}
    assert SOURCE.read_bytes() == source_bytes, "The source answer must remain unchanged"

    probe = json.loads((BASE / "data" / "probe.json").read_text(encoding="utf-8"))
    probe_row = next(row for row in probe["rows"] if row["id"] == CASE_ID)
    evidence = probe_row["top_evidence"][0]
    record = {
        "case_id": CASE_ID,
        "scope": "One migration demonstration; not a new 32-case evaluation",
        "environment": {"python": platform.python_version(), "pandas": pd.__version__},
        "portable_reproduction_command":
            "uv run --python 3.12 --with pandas==3.0.0 python examples/migrate_applymap.py",
        "source": {
            "file": "answers/qwen3.8-27b.json",
            "selector": "pd-applymap.text / first fenced Python block",
            "answer_text_sha256": sha256(answer_text.encode("utf-8")),
            "python_block_sha256": sha256(old_code.encode("utf-8")),
            "source_file_sha256_reference_only": sha256(source_bytes),
            "hash_note": "Whole-file hash is reference only: publication may redact endpoint_host metadata; answer text is the stable comparison unit.",
            "answer_text": answer_text,
        },
        "input_note": "The original model answer's fixed three-row migration demonstration input, not business data.",
        "input": input_data,
        "change": {"from": ".applymap(", "to": ".map(", "occurrences_replaced": 1,
                   "function_unchanged": "lambda x: x * 2", "other_code_unchanged": True},
        "old_code": old_code,
        "new_code": new_code,
        "old_run": old,
        "new_run": {**new, "result": result_data},
        "existing_search_evidence": {
            "file": "data/probe.json",
            "selector": "rows[id=pd-applymap].top_evidence[0]",
            "verdict": probe_row["verdict"],
            "url": evidence["url"],
            "sentence": evidence["sentence"],
            "note": "Saved search evidence says deprecated in 2.1; it does not establish removal in target pandas 3.0.",
        },
        "official_migration_sources": [
            {"url": "https://pandas.pydata.org/docs/whatsnew/v3.0.0.html",
             "locator": "Removal of prior version deprecations; GH 52364",
             "fact": "pandas 3.0.0 removes DataFrame.applymap, Styler.applymap and Styler.applymap_index."},
            {"url": "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.map.html",
             "locator": "Added in version 2.1.0 / method description",
             "fact": "DataFrame.applymap was deprecated and renamed to DataFrame.map; map applies a scalar function elementwise."},
        ],
        "checks": {"old_attribute_error_observed": True, "new_run_succeeded": True,
                   "same_input_and_function": True, "source_answer_unchanged": True},
    }
    log_lines = [
        "pd-applymap: one real migration demonstration",
        f"Python {platform.python_version()}; pandas {pd.__version__}",
        "Input: original answer's fixed migration demonstration fixture, not business data",
        json.dumps(input_data, ensure_ascii=False),
        "Source: answers/qwen3.8-27b.json / pd-applymap.text",
        f"answer_text_sha256: {record['source']['answer_text_sha256']}",
        "Change: exactly one .applymap( -> .map(; lambda x: x * 2 unchanged",
        "Old run: " + old["exception"]["type"] + ": " + old["exception"]["message"],
        "New run: success",
        new["stdout"].rstrip(),
        "Checks: same input/function; output equals elementwise doubling; source answer unchanged",
        "Saved search evidence: pandas 2.1 deprecated (not target-version removal proof)",
        "Target-version source: https://pandas.pydata.org/docs/whatsnew/v3.0.0.html (GH 52364)",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "applymap_pandas300.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log = "\n".join(log_lines) + "\n"
    (OUT / "applymap_pandas300.log").write_text(log, encoding="utf-8")
    print(log, end="")
    print("written validation/migration/applymap_pandas300.json")
    print("written validation/migration/applymap_pandas300.log")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
