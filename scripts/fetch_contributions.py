"""Fetch exact public GitHub contribution counts without credentials or dependencies.

GitHub keeps contribution counts in tool-tip elements associated with calendar
cells by ID. Treat missing or inconsistent counts as a fetch failure rather than
overwriting the last good calendar with invented zeroes.
"""

import argparse
import json
import re
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


DEFAULT_USERNAME = "mehmetakifcakr"
USERNAME_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")


def contribution_count(label):
    """Return an exact English GitHub tooltip count, or None if unrecognized."""
    label = " ".join(label.split())
    if re.match(r"^No contributions\b", label, re.IGNORECASE):
        return 0
    match = re.match(r"^(\d[\d,]*)\s+contributions?\b", label, re.IGNORECASE)
    return int(match.group(1).replace(",", "")) if match else None


class ContributionParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cells = []
        self.tooltips = {}
        self.reported_total = None
        self._tooltip_target = None
        self._tooltip_parts = []
        self._heading_parts = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"td", "rect"} and "data-date" in attrs:
            self.cells.append(attrs)
        if tag == "tool-tip" and attrs.get("for"):
            self._tooltip_target = attrs["for"]
            self._tooltip_parts = []
        if tag == "h2" and attrs.get("id") == "js-contribution-activity-description":
            self._heading_parts = []

    def handle_data(self, value):
        if self._tooltip_target is not None:
            self._tooltip_parts.append(value)
        if self._heading_parts is not None:
            self._heading_parts.append(value)

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self._tooltip_target is not None:
            self.tooltips[self._tooltip_target] = "".join(self._tooltip_parts)
            self._tooltip_target = None
            self._tooltip_parts = []
        if tag == "h2" and self._heading_parts is not None:
            self.reported_total = contribution_count("".join(self._heading_parts))
            if self.reported_total is None:
                raise ValueError("The contribution total heading could not be parsed.")
            self._heading_parts = None


def parse_contributions(html):
    """Parse a complete fragment, rejecting gaps and unrecognized count markup."""
    parser = ContributionParser()
    parser.feed(html)
    parser.close()
    if not parser.cells:
        raise ValueError("No GitHub contribution calendar cells were found.")

    by_date = {}
    for attrs in parser.cells:
        day = date.fromisoformat(attrs["data-date"]).isoformat()
        if day in by_date:
            raise ValueError(f"Duplicate contribution date: {day}")
        level = int(attrs["data-level"])
        if not 0 <= level <= 4:
            raise ValueError(f"Invalid contribution level for {day}: {level}")
        if "data-count" in attrs:
            count = int(attrs["data-count"].replace(",", ""))
        else:
            label = parser.tooltips.get(attrs.get("id"), attrs.get("aria-label", ""))
            count = contribution_count(label)
        if count is None:
            raise ValueError(f"Missing exact contribution count for {day}")
        if count < 0 or ((count == 0) != (level == 0)):
            raise ValueError(f"Contribution count and level disagree for {day}")
        by_date[day] = {"date": day, "level": level, "count": count}

    days = [by_date[key] for key in sorted(by_date)]
    start = date.fromisoformat(days[0]["date"])
    end = date.fromisoformat(days[-1]["date"])
    if len(days) != (end - start).days + 1:
        raise ValueError("The contribution calendar has missing dates.")
    total = sum(item["count"] for item in days)
    if parser.reported_total is not None and total != parser.reported_total:
        raise ValueError(
            f"Day counts sum to {total}, but GitHub reports {parser.reported_total}."
        )
    return days


def build_snapshot(html, username, source_url):
    days = parse_contributions(html)
    return {
        "username": username,
        "source_url": source_url,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "start_date": days[0]["date"],
        "end_date": days[-1]["date"],
        "total_contributions": sum(item["count"] for item in days),
        "active_days": sum(item["count"] > 0 for item in days),
        "days": days,
    }


def write_snapshot(snapshot, output):
    """Write atomically, keeping stable content when the public data is unchanged."""
    if output.exists():
        old = json.loads(output.read_text(encoding="utf-8"))
        def without_timestamp(obj):
            return {key: value for key, value in obj.items() if key != "generated_at"}

        if without_timestamp(old) == without_timestamp(snapshot):
            return False
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--output", type=Path, default=Path("data/contributions.json"))
    parser.add_argument("--html-file", type=Path, help="Use a saved fragment for offline checks.")
    args = parser.parse_args()
    if not USERNAME_PATTERN.fullmatch(args.username):
        parser.error("Invalid GitHub username.")
    source_url = f"https://github.com/users/{args.username}/contributions"
    if args.html_file:
        html = args.html_file.read_text(encoding="utf-8")
    else:
        request = Request(source_url, headers={
            "User-Agent": "GitHubProfileCalendar/2.0",
            "Accept": "text/html",
            "Accept-Language": "en-US,en;q=0.9",
        })
        with urlopen(request, timeout=30) as response:
            html = response.read().decode("utf-8")
    snapshot = build_snapshot(html, args.username, source_url)
    if not 350 <= len(snapshot["days"]) <= 380:
        raise ValueError("GitHub returned an incomplete trailing-year calendar.")
    changed = write_snapshot(snapshot, args.output)
    print(
        f"{len(snapshot['days'])} days; {snapshot['total_contributions']} contributions "
        f"across {snapshot['active_days']} active days. "
        f"{'Updated' if changed else 'Unchanged'} {args.output}."
    )


if __name__ == "__main__":
    main()
