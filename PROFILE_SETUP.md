# Profile assets and public activity

This repository powers the public GitHub profile for `mehmetakifcakr`.
The profile README is written in English and links to the author's own projects.
Project descriptions distinguish implemented functionality from future work.

## Assets

- `assets/header.svg`: static engineering banner, without external asset dependencies.
- `ascii-avatar.svg`: static robotics illustration linked to OpenRobotKit.
- `contrib-heatmap.svg`: generated public contribution calendar.
- `data/contributions.json`: exact public counts and their source/date range.

All SVGs have accessible titles/descriptions and remain visible with animations
disabled. They do not call third-party tracking services.

## Refresh

The GitHub Actions workflow checks the parser and renderer before refreshing the
calendar daily at 03:17 UTC, after profile-source changes, or on manual dispatch.
Only the update job can write generated data back to the repository. Pull request
jobs remain read-only. No API keys or extra Python dependencies are required.

```sh
python -m unittest discover -s tests -v
python scripts/fetch_contributions.py
python scripts/render_heatmap_svg.py
```

Exact counts come from GitHub's public contribution markup. The script associates
each date with its tooltip, checks the calendar range, colors and total, and
fails instead of writing invented zeroes if GitHub's markup changes. An unchanged
calendar does not produce a timestamp-only commit. A failed fetch leaves the
last valid data intact.

The SVG covers the actual calendar dates returned by GitHub; the aligned first
week may include a few days before the trailing-year boundary. Private activity
is not included, so the signed-in native GitHub graph can have a different total.
