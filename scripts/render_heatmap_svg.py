"""Render the exact fetched calendar as an accessible, static GitHub profile SVG."""

import argparse
import calendar
import json
from datetime import date, timedelta
from html import escape
from pathlib import Path


PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]


def render_heatmap(data):
    days = sorted(data["days"], key=lambda item: item["date"])
    if not days:
        raise ValueError("A contribution calendar cannot be empty.")
    start = date.fromisoformat(days[0]["date"])
    end = date.fromisoformat(days[-1]["date"])
    grid_start = start - timedelta(days=(start.weekday() + 1) % 7)
    columns = (end - grid_start).days // 7 + 1
    total = sum(int(item["count"]) for item in days)
    active = sum(int(item["count"]) > 0 for item in days)
    active_label = "active day" if active == 1 else "active days"
    username = escape(data["username"])
    cell, step, left, top = 12, 17, 56, 84
    width = left + columns * step + 28
    height = 248
    range_label = f"{start.strftime('%d %b %Y')} – {end.strftime('%d %b %Y')}"
    accessible = f"{username}: {total} contributions across {active} {active_label}; {range_label}."
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">',
        f'<title id="title">{username} · Public GitHub activity</title>',
        f'<desc id="description">{accessible} Source: GitHub public contribution calendar.</desc>',
        f'<rect x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="14" '
        'fill="#0d1117" stroke="#30363d"/>',
        '<style>text {font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;}</style>',
        '<text x="24" y="31" fill="#f0f6fc" font-size="16" font-weight="600">Public GitHub activity</text>',
        f'<text x="{width-24}" y="31" text-anchor="end" fill="#8b949e" font-size="11">{range_label}</text>',
        f'<text x="24" y="54" fill="#8b949e" font-size="12">'
        f'<tspan fill="#39d353" font-weight="600">{total:,}</tspan> contributions '
        f'· <tspan fill="#c9d1d9">{active}</tspan> {active_label}</text>',
    ]
    for label, row in [("Mon", 1), ("Wed", 3), ("Fri", 5)]:
        svg.append(f'<text x="24" y="{top+row*step+10}" fill="#8b949e" font-size="10">{label}</text>')

    month_columns = [(0, start.month)]
    for item in days:
        current = date.fromisoformat(item["date"])
        if current.day == 1 and current > start:
            column = (current - grid_start).days // 7
            if column - month_columns[-1][0] >= 2:
                month_columns.append((column, current.month))
    for column, month in month_columns:
        svg.append(f'<text x="{left+column*step}" y="{top-9}" fill="#8b949e" font-size="10">{calendar.month_abbr[month]}</text>')

    for item in days:
        current = date.fromisoformat(item["date"])
        offset = (current - grid_start).days
        x, y = left + (offset // 7) * step, top + (offset % 7) * step
        count, level = int(item["count"]), int(item["level"])
        if count < 0 or not 0 <= level <= 4 or ((count == 0) != (level == 0)):
            raise ValueError(f"Invalid contribution count/level for {current}.")
        label = f"{current.isoformat()}: {count} {'contribution' if count == 1 else 'contributions'}"
        svg.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" '
                   f'fill="{PALETTE[level]}" data-date="{current}" data-count="{count}">'
                   f'<title>{label}</title></rect>')

    svg.append('<text x="24" y="226" fill="#8b949e" font-size="10">Public GitHub contribution activity · Refreshed daily</text>')
    legend_x = width - 134
    svg.append(f'<text x="{legend_x-31}" y="226" fill="#8b949e" font-size="10">Less</text>')
    for i, color in enumerate(PALETTE):
        svg.append(f'<rect x="{legend_x+i*15}" y="216" width="11" height="11" rx="2" fill="{color}"/>')
    svg.append(f'<text x="{legend_x+79}" y="226" fill="#8b949e" font-size="10">More</text>')
    svg.append('</svg>')
    return "\n".join(svg) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/contributions.json"))
    parser.add_argument("--output", type=Path, default=Path("contrib-heatmap.svg"))
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    rendered = render_heatmap(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Created {args.output} from {data['days'][0]['date']} to {data['days'][-1]['date']}.")


if __name__ == "__main__":
    main()
