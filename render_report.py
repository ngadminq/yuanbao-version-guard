"""Render the saved experiment records into a read-only HTML page.

It only reads data/ and answers/; it never calls the search API or the LLM.
"""

import csv
import glob
import html
import json
import re
import statistics
from collections import Counter
from pathlib import Path

from research_client import decode_pages
from version_guard import version_hint

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
NAME = "qwen3.8-27b"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def esc(value):
    return html.escape(str(value if value is not None else ""))


def table(head, rows, cls=""):
    th = "".join(f"<th>{esc(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f'<table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


VERDICT = {"breaking": '<b class="bad">已删除/行为变更</b>', "deprecated": '<b class="warn">已弃用</b>',
           "mentioned": '<span class="dim">提及，无变更描述</span>', "no_evidence": '<span class="dim">未检出</span>',
           "unsupported_lib": '<span class="dim">未配置官方域名</span>'}


def main():
    records = [load(p) for p in glob.glob(str(DATA / "cache" / "*.json"))]
    pages = [p for r in records for p in decode_pages(r["response"])]
    ms = [r["elapsed_ms"] for r in records]
    py = [p for p in pages if "docs.python.org" in p["url"]]
    translated = [p for p in py if re.search(r"docs\.python\.org/[a-z]{2}(?:-[a-z]{2})?/", p["url"])]
    old_py = [p for p in py if re.fullmatch(r"3\.(\d+)", version_hint(p["url"]) or "")
              and int(version_hint(p["url"]).split(".")[1]) <= 11]
    probe = load(DATA / "probe.json")
    run = load(DATA / f"run_{NAME}.json")
    answers = load(BASE / "answers" / f"{NAME}.json")
    review = list(csv.DictReader(open(DATA / f"review_{NAME}.csv", encoding="utf-8-sig")))
    versions = [("v1 初版", DATA / "probe_rules_v1.json", None),
                ("v2 + 替代句规则", DATA / "probe_rules_v2.json", DATA / f"run_{NAME}_rules_v2.json"),
                ("v3 + 代码形态/模块语境", DATA / "probe_rules_v3.json", DATA / f"run_{NAME}_rules_v3.json"),
                ("v4 + 120 字窗口（冻结）", DATA / "probe.json", DATA / f"run_{NAME}.json")]
    s = run["summary"]
    correct = sum(r["human_label"] == "对" for r in review)
    ans_ms = [a["elapsed_ms"] for a in answers.values()]

    overview = table(["项目", "数值"], [
        ["元宝 SearchPro 真实调用（缓存记录）", f"{len(records)} 次，HTTP 200：{sum(r['status'] == 200 for r in records)} 次"],
        ["端到端耗时（本机，含网络）", f"中位数 {statistics.median(ms):.0f} ms，范围 {min(ms)}–{max(ms)} ms"],
        ["返回结果项", f"{len(pages)} 条；docs.python.org {len(py)} 条，其中翻译版 {len(translated)} 条（{len(translated)/len(py):.0%}），3.11 及更早版本 {len(old_py)} 条（{len(old_py)/len(py):.0%}）"],
        ["本地模型", f"Qwen3.8-27B-FP8（vLLM），reasoning_effort=medium，32 题合计 {sum(ans_ms)/1000:.0f} s，单题 {min(ans_ms)}–{max(ans_ms)} ms"],
        ["模型写出过时 API", f"{s['stale_answers']}/{s['changed_cases']}（{s['stale_rate']:.1%}）"],
        ["定向核验检出变更（实验 1）", f"{probe['change_detected']}/{probe['cases']}，状态完全一致 {probe['status_exact']}/{probe['cases']}"],
        ["全自动扫描（实验 2）", f"抓到过时回答 {s['guard_caught_stale']}/{s['stale_answers']}；检查符号 {s['symbols_checked']} 个；标记 {s['flags_total']} 条，复核正确 {correct} 条（{correct/len(review):.1%}）；对照题标记 {s['flags_on_controls']} 条"],
    ])

    probe_rows = [[esc(r["id"]), f"<code>{esc(r['query'])}</code>", esc(r["site"]), esc(r["official_pages"]),
                   VERDICT.get(r["verdict"], esc(r["verdict"])), esc(r["expected"]),
                   "✓" if r["detected"] else "✗", f"<code>{esc((r['request_id'] or '')[:8])}…</code>"]
                  for r in probe["rows"]]

    run_rows = []
    for r in run["results"]:
        caught = "—" if not r["stale"] else ("✓ 抓到" if r["guard_hit_target"] else "✗ 漏掉")
        run_rows.append([esc(r["id"]), esc(r["expected_status"]), '<b class="bad">过时</b>' if r["stale"] else "—",
                         caught, esc(r["symbols_checked"]), esc(r["flags"])])

    review_rows = [[esc(i), esc(r["case"]), f"<code>{esc(r['symbol'])}</code>", esc(r["verdict"]),
                    f'<b class="{"ok" if r["human_label"] == "对" else "bad"}">{esc(r["human_label"])}</b>',
                    esc(r["reason"]), f'<span class="ev">{esc(r["evidence"][:140])}</span>']
                   for i, r in enumerate(review, 1)]

    version_rows = []
    for label, p_path, r_path in versions:
        p = load(p_path)
        rs = load(r_path)["summary"] if r_path else None
        version_rows.append([esc(label), f"{p['change_detected']}/28", f"{p['status_exact']}/28",
                             f"{rs['guard_caught_stale']}/9" if rs else "—",
                             esc(rs["flags_total"]) if rs else "—", esc(rs["flags_on_controls"]) if rs else "—"])

    check_log = (DATA / "logs" / "check_loop_policy.txt").read_text(encoding="utf-8")
    example_code = (BASE / "examples" / "qwen_loop_policy.md").read_text(encoding="utf-8")
    logs = {name: (DATA / "logs" / f"{name}.txt").read_text(encoding="utf-8")
            for name in ("probe", "run", "unittest")}

    page = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>版本核验运行记录</title>
<style>
:root{{--bg:#f7f7f5;--fg:#1d1d1f;--dim:#6e6e73;--card:#fff;--line:#e3e3e0;--bad:#c0392b;--warn:#b7791f;--ok:#2f855a;--code:#f0f0ec}}
body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:24px 16px 64px}}
h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:17px;margin:0 0 10px}}
.sub{{color:var(--dim);margin-bottom:20px}}
section{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin:0 0 18px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}}
th{{background:#fafaf8;font-weight:600}}
code,pre{{background:var(--code);border-radius:4px;font:12px/1.5 Consolas,"Cascadia Mono",monospace}}
code{{padding:1px 4px}} pre{{padding:12px;overflow-x:auto;white-space:pre-wrap;margin:0}}
.bad{{color:var(--bad)}} .warn{{color:var(--warn)}} .ok{{color:var(--ok)}} .dim{{color:var(--dim)}}
.ev{{color:var(--dim);font-size:12px}} .grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.note{{color:var(--dim);font-size:12px;margin-top:8px}}
</style></head><body><main>
<h1>版本核验助手 · 运行记录</h1>
<div class="sub">本页只读取本地保存的真实调用记录（data/cache、data/*.json、answers/），不发送任何请求。记录时间：{esc(probe['recorded_at'][:19])}（实验 1）、{esc(s['recorded_at'][:19])}（实验 2）。</div>
<section id="overview"><h2>运行概览</h2>{overview}</section>
<section id="example"><h2>单条核验：本地 Qwen 给出的 Windows asyncio 修复代码</h2>
<div class="grid"><div><div class="note">模型回答（原样）</div><pre>{esc(example_code.strip())}</pre></div>
<div><div class="note">python version_guard.py check examples/qwen_loop_policy.md</div><pre>{esc(check_log.strip())}</pre></div></div></section>
<section id="probe"><h2>实验 1：定向核验 28 项已知变更（Site 限定官方域名，Cnt=10）</h2>
{table(["用例", "Query", "Site", "官方结果", "工具判定", "标准答案", "检出", "RequestId"], probe_rows)}</section>
<section id="run"><h2>实验 2：全自动扫描本地 Qwen 的 32 份回答</h2>
{table(["用例", "标准答案", "回答是否过时", "工具是否抓到", "检查符号数", "标记数"], run_rows)}</section>
<section id="versions"><h2>规则迭代：每一版都保留了结果</h2>
{table(["规则版本", "实验1 检出", "实验1 状态一致", "实验2 抓到过时", "实验2 标记数", "对照题标记"], version_rows)}
<div class="note">v1、v2 的检出数各含 1 条误中（delim_whitespace 命中的是 pandas 早期版本 GH 6607 的 “Raise ValueError when sep specified…”），扣除后分别为 19、20；v3 起不再计入。规则在同一批数据上调整，数字偏乐观。</div></section>
<section id="review"><h2>标记复核表（{correct}/{len(review)} 正确）</h2>
{table(["#", "用例", "符号", "判定", "复核", "理由", "证据片段"], review_rows)}
<div class="note">复核人：{esc(review[0]['reviewer'])}</div></section>
<section id="logs"><h2>终端输出</h2><div class="grid">
<div><div class="note">python evaluate.py probe</div><pre>{esc(logs['probe'].strip())}</pre></div>
<div><div class="note">python evaluate.py run --name {NAME}</div><pre>{esc(logs['run'].strip()[-2200:])}</pre></div></div>
<div class="note" style="margin-top:12px">python -m unittest -v test_version_guard</div><pre>{esc(logs['unittest'].strip()[-1600:])}</pre></section>
</main></body></html>"""
    out = BASE / "viewer" / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print("written", out)
    print(json.dumps({"translated_share": round(len(translated) / len(py), 3), "old_py_share": round(len(old_py) / len(py), 3),
                      "old_py": len(old_py), "py": len(py), "precision": f"{correct}/{len(review)}"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
