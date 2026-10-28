"""Render the article's three static charts from the saved evaluation data.

Run from any directory with a Python environment that has Pillow installed:
    python article_charts.py

Only redrawing these charts needs Pillow; the core reproduction uses the Python
standard library. These are charts of frozen data, not original run screenshots.
This script makes no network requests. It reads the final probe, scan and review
files, checks that the detailed rows agree with their summaries, and writes only
images/article-{probe,scan,alerts}.png. The counts describe this saved sample.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo


BASE = Path(__file__).resolve().parent
OUTPUT = BASE / "images"
WIDTH, HEIGHT = 1440, 1040
SCALE = 2

# Fixed semantics: green = supported result, amber = detected but wrong status,
# gray = not detected, red = an alert that the review did not support.
PAPER = "#FFFDF7"
INK = "#242820"
DIM = "#656B61"
LINE = "#E1E2D9"
GREEN = "#2F8058"
AMBER = "#AD741E"
GRAY = "#767C72"
GRAY_LIGHT = "#E2E5DC"
RED = "#B8493D"


def read_json(name: str) -> dict:
    return json.loads((BASE / "data" / name).read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_counts() -> dict:
    probe = read_json("probe.json")
    run = read_json("run_qwen3.8-27b.json")
    with (BASE / "data" / "review_qwen3.8-27b.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        review = list(csv.DictReader(handle))

    probe_rows = probe["rows"]
    total = len(probe_rows)
    detected = sum(bool(row["detected"]) for row in probe_rows)
    exact = sum(bool(row["exact"]) for row in probe_rows)
    require(total == probe["cases"], "Probe total disagrees with its rows")
    require(detected == probe["change_detected"], "Probe detection count disagrees")
    require(exact == probe["status_exact"], "Probe status count disagrees")
    require(
        all(not row["exact"] or row["detected"] for row in probe_rows),
        "Exact-status cases must be a subset of detected cases",
    )

    results, summary = run["results"], run["summary"]
    stale = sum(bool(row["stale"]) for row in results)
    caught = sum(bool(row["stale"] and row["guard_hit_target"]) for row in results)
    flags = sum(row["flags"] for row in results)
    require(stale == summary["stale_answers"], "Stale-answer count disagrees")
    require(caught == summary["guard_caught_stale"], "Caught-answer count disagrees")
    require(flags == summary["flags_total"], "Alert count disagrees")
    labels = Counter(row["human_label"] for row in review)
    require(set(labels) <= {"对", "错"}, "All alerts need a final review label")
    require(len(review) == flags, "Final review must cover every alert")

    return {
        "probe_total": total,
        "probe_detected": detected,
        "probe_exact": exact,
        "probe_mismatch": detected - exact,
        "probe_missed": total - detected,
        "stale": stale,
        "caught": caught,
        "missed": stale - caught,
        "flags": flags,
        "valid": labels["对"],
        "invalid": labels["错"],
        "probe_date": probe["recorded_at"][:10],
        "scan_date": summary["recorded_at"][:10],
    }


def font_file(bold: bool) -> Path:
    candidates = (
        [Path("C:/Windows/Fonts/msyhbd.ttc"), Path("C:/Windows/Fonts/Dengb.ttf")]
        if bold
        else [Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/Deng.ttf")]
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("Install Microsoft YaHei or DengXian before rendering")


class Chart:
    def __init__(self, kicker: str, title: str):
        self.image = Image.new("RGB", (WIDTH * SCALE, HEIGHT * SCALE), PAPER)
        self.draw = ImageDraw.Draw(self.image)
        self.fonts: dict[tuple[int, bool], ImageFont.FreeTypeFont] = {}
        self.text(80, 66, kicker, 38, DIM)
        self.text(80, 145, title, 62, INK, bold=True)

    def font(self, size: int, bold: bool) -> ImageFont.FreeTypeFont:
        key = (size, bold)
        if key not in self.fonts:
            self.fonts[key] = ImageFont.truetype(str(font_file(bold)), size * SCALE)
        return self.fonts[key]

    def text(
        self,
        x: float,
        y: float,
        text: str,
        size: int,
        color: str,
        bold: bool = False,
        center: bool = False,
    ) -> None:
        face = self.font(size, bold)
        length = self.draw.textlength(text, font=face)
        if center:
            x -= length / SCALE / 2
        require(x >= 0 and x * SCALE + length <= WIDTH * SCALE, f"Text clips: {text}")
        self.draw.text((x * SCALE, y * SCALE), text, font=face, fill=color)

    def line(self, points: list[tuple[float, float]], color: str, width: int = 2) -> None:
        self.draw.line(
            [(round(x * SCALE), round(y * SCALE)) for x, y in points],
            fill=color,
            width=width * SCALE,
        )

    def metric(self, numerator: int, denominator: int, label: str) -> None:
        self.text(80, 280, f"{numerator} / {denominator}", 128, GREEN, bold=True)
        self.text(84, 447, label, 42, DIM)

    def bar(self, parts: list[tuple[int, str, str, str]], total: int) -> None:
        x0, width, top, bottom = 80, 1280, 625, 755
        offset = 0
        for value, label, fill, text_color in parts:
            left = x0 + width * offset / total
            right = x0 + width * (offset + value) / total
            self.draw.rectangle(
                [round(left * SCALE), top * SCALE, round(right * SCALE), bottom * SCALE],
                fill=fill,
            )
            middle = (left + right) / 2
            self.text(middle, 641, str(value), 78, text_color, bold=True, center=True)
            label_color = GRAY if fill == GRAY_LIGHT else fill
            self.text(middle, 797, label, 48, label_color, bold=True, center=True)
            self.text(middle, 865, f"{value} / {total}", 40, DIM, center=True)
            offset += value
        require(offset == total, "Bar parts must partition the denominator")

    def save(self, name: str, date: str, description: str) -> Path:
        self.line([(80, 959), (1360, 959)], LINE)
        self.text(80, 979, "数据来源：配套实验结果与复核表", 32, DIM)
        metadata = PngInfo()
        metadata.add_text("Description", description)
        metadata.add_text("Source", f"Saved local evaluation data, {date}")
        result = self.image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        path = OUTPUT / name
        result.save(path, pnginfo=metadata, optimize=True)
        return path


def render_probe(counts: dict) -> Path:
    detected, exact, total = (
        counts["probe_detected"], counts["probe_exact"], counts["probe_total"]
    )
    chart = Chart(
        f"主动核验 · {total} 项已知变更",
        f"检出 {detected} 项，其中 {exact} 项状态一致",
    )
    chart.metric(detected, total, "已检出 / 全部已知变更")
    chart.text(770, 316, f"{exact} 项状态一致", 50, GREEN, bold=True)
    chart.text(770, 391, f"+ {counts['probe_mismatch']} 项状态不符", 50, AMBER, bold=True)
    # This bracket encloses green + amber. Exact status is never added to the
    # detected total as a separate, disjoint category.
    bracket_right = 80 + 1280 * detected / total
    chart.line([(80, 605), (80, 577), (bracket_right, 577), (bracket_right, 605)], DIM, 3)
    chart.text((80 + bracket_right) / 2, 518, f"已检出 {detected} 项", 42, DIM, center=True)
    chart.bar(
        [
            (exact, "状态一致", GREEN, PAPER),
            (counts["probe_mismatch"], "状态不符", AMBER, PAPER),
            (counts["probe_missed"], "未检出", GRAY_LIGHT, GRAY),
        ],
        total,
    )
    return chart.save(
        "article-probe.png", counts["probe_date"],
        f"Known-change probe: {detected}/{total} detected, including {exact} exact-status "
        f"and {counts['probe_mismatch']} wrong-status cases; {counts['probe_missed']} missed.",
    )


def render_scan(counts: dict) -> Path:
    caught, total = counts["caught"], counts["stale"]
    chart = Chart("回答扫描 · 按回答计", f"{total} 份过时回答，检出 {caught} 份")
    chart.metric(caught, total, "已检出 / 全部过时回答")
    chart.text(785, 344, f"漏检 {counts['missed']} 份", 60, GRAY, bold=True)
    chart.text(80, 543, f"{total} 份已确认的过时回答", 42, DIM)
    chart.bar(
        [
            (caught, "已检出", GREEN, PAPER),
            (counts["missed"], "漏检", GRAY_LIGHT, GRAY),
        ],
        total,
    )
    return chart.save(
        "article-scan.png", counts["scan_date"],
        f"Answer-level scan: {caught}/{total} stale answers detected; "
        f"{counts['missed']}/{total} missed.",
    )


def render_alerts(counts: dict) -> Path:
    valid, total = counts["valid"], counts["flags"]
    chart = Chart("告警复核 · 按告警计", f"{total} 条告警，{valid} 条复核成立")
    chart.metric(valid, total, "复核成立 / 全部告警")
    chart.text(745, 344, f"{counts['invalid']} 条不成立", 60, RED, bold=True)
    chart.text(80, 543, f"{total} 条告警逐条复核", 42, DIM)
    chart.bar(
        [
            (valid, "复核成立", GREEN, PAPER),
            (counts["invalid"], "复核不成立", RED, PAPER),
        ],
        total,
    )
    return chart.save(
        "article-alerts.png", counts["scan_date"],
        f"Alert-level review: {valid}/{total} supported alerts; "
        f"{counts['invalid']}/{total} unsupported alerts.",
    )


def main() -> None:
    counts = load_counts()
    OUTPUT.mkdir(exist_ok=True)
    for renderer in [render_probe, render_scan, render_alerts]:
        path = renderer(counts)
        print(f"{path.name}: {WIDTH} x {HEIGHT}")
    print(
        f"Verified data: probe {counts['probe_detected']}/{counts['probe_total']} "
        f"(exact {counts['probe_exact']}); scan {counts['caught']}/{counts['stale']}; "
        f"alerts {counts['valid']}/{counts['flags']}."
    )


if __name__ == "__main__":
    main()
