"""Regression checks for real GitHub tooltip markup and static SVG geometry."""

import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fetch_contributions import build_snapshot, contribution_count, parse_contributions, write_snapshot
from render_heatmap_svg import render_heatmap


FIXTURE = Path(__file__).parent / "fixtures" / "contributions.html"
SVG_NS = {"svg": "http://www.w3.org/2000/svg"}


class ContributionParsingTests(unittest.TestCase):
    def setUp(self):
        self.html = FIXTURE.read_text(encoding="utf-8")

    def test_current_tooltip_markup_preserves_real_positive_count(self):
        days = parse_contributions(self.html)
        self.assertEqual([day["count"] for day in days], [0, 0, 2])
        self.assertEqual(days[-1], {"date": "2026-10-14", "level": 1, "count": 2})

    def test_tooltip_matches_target_id_not_document_order(self):
        html = '''<tool-tip for="b">1 contribution on January 2nd.</tool-tip>
        <tool-tip for="a">No contributions on January 1st.</tool-tip>
        <td data-date="2026-01-01" data-level="0" id="a"></td>
        <td data-date="2026-01-02" data-level="1" id="b"></td>'''
        self.assertEqual([day["count"] for day in parse_contributions(html)], [0, 1])

    def test_nested_text_and_singular_are_parsed(self):
        html = '''<td data-date="2026-01-01" data-level="1" id="a"></td>
        <tool-tip for="a"><strong>1</strong> contribution on January 1st.</tool-tip>'''
        self.assertEqual(parse_contributions(html)[0]["count"], 1)

    def test_legacy_explicit_count_and_aria_label(self):
        html = '''<rect data-date="2026-01-01" data-level="4" data-count="1,234"/>
        <td data-date="2026-01-02" data-level="1" aria-label="1 contribution on January 2nd."></td>'''
        self.assertEqual([day["count"] for day in parse_contributions(html)], [1234, 1])

    def test_no_missing_tooltip_is_silently_changed_to_zero(self):
        html = '<td data-date="2026-01-01" data-level="0" id="missing"></td>'
        with self.assertRaisesRegex(ValueError, "Missing exact"):
            parse_contributions(html)

    def test_missing_and_duplicate_dates_are_rejected(self):
        html = '''<td data-date="2026-01-01" data-level="0" data-count="0"></td>
        <td data-date="2026-01-03" data-level="0" data-count="0"></td>'''
        with self.assertRaisesRegex(ValueError, "missing dates"):
            parse_contributions(html)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            parse_contributions(html.replace("2026-01-03", "2026-01-01"))

    def test_count_level_and_header_inconsistency_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "disagree"):
            parse_contributions(self.html.replace('data-level="1"', 'data-level="0"'))
        with self.assertRaisesRegex(ValueError, "GitHub reports"):
            parse_contributions(self.html.replace("2 contributions in this fixture", "3 contributions in this fixture"))

    def test_unknown_count_format_and_empty_response_fail(self):
        self.assertIsNone(contribution_count("Rate limit exceeded"))
        with self.assertRaisesRegex(ValueError, "No GitHub"):
            parse_contributions("<html>Service unavailable</html>")

    def test_unchanged_snapshot_retains_original_fetch_timestamp(self):
        snapshot = build_snapshot(self.html, "example", "https://github.com/users/example/contributions")
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "contributions.json"
            self.assertTrue(write_snapshot(snapshot, output))
            original = output.read_bytes()
            snapshot["generated_at"] = "2030-01-01T00:00:00+00:00"
            self.assertFalse(write_snapshot(snapshot, output))
            self.assertEqual(output.read_bytes(), original)
            self.assertEqual(json.loads(original)["total_contributions"], 2)


class ContributionRenderingTests(unittest.TestCase):
    def setUp(self):
        self.data = build_snapshot(FIXTURE.read_text(encoding="utf-8"), "example", "source")

    def test_svg_has_static_exactly_counted_cells_and_accessible_summary(self):
        svg = render_heatmap(self.data)
        element = ET.fromstring(svg)
        cells = [cell for cell in element.findall("svg:rect", SVG_NS) if "data-date" in cell.attrib]
        self.assertEqual(len(cells), 3)
        self.assertEqual(sum(int(cell.attrib["data-count"]) for cell in cells), 2)
        self.assertIn("2 contributions across 1 active day", svg)
        self.assertNotIn("<animate", svg)
        self.assertNotIn('opacity="0"', svg)
        self.assertEqual(cells[-1].attrib["fill"], "#0e4429")
        self.assertIsNotNone(element.find("svg:desc", SVG_NS))

    def test_renderer_uses_snapshot_dates_instead_of_host_clock(self):
        svg = render_heatmap(self.data)
        self.assertIn("12 Oct 2026 – 14 Oct 2026", svg)
        self.assertNotIn('data-date="2026-10-15"', svg)
        self.assertNotIn('data-date="2026-10-11"', svg)

    def test_renderer_escapes_external_text(self):
        self.data["username"] = "A&B<name>"
        element = ET.fromstring(render_heatmap(self.data))
        self.assertIn("A&B<name>", element.find("svg:title", SVG_NS).text)

    def test_full_year_grid_cells_fit_viewbox(self):
        from datetime import date, timedelta
        for start in (date(2025, 10, 12), date(2025, 10, 14), date(2024, 2, 29)):
            self.data["days"] = [
                {"date": (start + timedelta(days=i)).isoformat(), "count": 0, "level": 0}
                for i in range(371)
            ]
            element = ET.fromstring(render_heatmap(self.data))
            width, height = int(element.attrib["width"]), int(element.attrib["height"])
            cells = [cell for cell in element.findall("svg:rect", SVG_NS) if "data-date" in cell.attrib]
            for cell in cells:
                self.assertLessEqual(float(cell.attrib["x"]) + float(cell.attrib["width"]), width)
                self.assertLessEqual(float(cell.attrib["y"]) + float(cell.attrib["height"]), height)


if __name__ == "__main__":
    unittest.main()
