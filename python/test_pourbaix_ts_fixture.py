"""The TypeScript parity fixture (tests/fixtures/pourbaix-grid-200x200.json) is current and correct.

Run from python/:  python -B -m unittest test_pourbaix_ts_fixture

The TypeScript test (tests/pourbaix-equilibrium.test.ts) classifies this grid with its port and
compares cell by cell; this module guarantees that the committed fixture is exactly what the
engine produces today and that the independent oracle agrees with it.
"""

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "tools"))

import pourbaix_oracle as oracle  # noqa: E402
import pourbaix_species_25c as table  # noqa: E402
import pourbaix_ts_fixture as fixture  # noqa: E402


def decode(row):
    cells = []
    for token in row.split(","):
        name, count = token.split(":")
        cells.extend([name] * int(count))
    return cells


class TsFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = fixture.FIXTURE.read_text(encoding="utf-8").replace("\r\n", "\n")
        cls.data = json.loads(cls.text)

    def test_committed_fixture_is_byte_identical_to_a_fresh_build(self):
        self.assertEqual(self.text, fixture.emit_text(),
                         "stale: run python tools/pourbaix_ts_fixture.py --emit from python/")

    def test_every_available_element_and_activity_is_covered(self):
        got = {(c["element"], c["log10Activity"]) for c in self.data["cases"]}
        want = {(e, a) for e in table.available_elements() for a in fixture.LOG_ACTIVITIES}
        self.assertEqual(got, want)
        self.assertEqual(self.data["n"], 200)

    def test_grid_shape_and_every_species_with_area_appears(self):
        for case in self.data["cases"]:
            rows = [decode(r) for r in case["rows"]]
            self.assertEqual(len(rows), 200)
            self.assertTrue(all(len(r) == 200 for r in rows))
            used = {case["speciesIds"][int(c)] for r in rows for c in r if c != "."}
            domains = set(oracle.polygons(case["element"], case["log10Activity"]))
            if case["log10Activity"] == -6.0:
                self.assertEqual(used, domains, case["element"])  # the grid reaches every domain at the default activity

    def test_boundary_cells_are_rare(self):
        for case in self.data["cases"]:
            near = sum(c == "." for r in case["rows"] for c in decode(r))
            self.assertLess(near / 40000, 0.01, (case["element"], case["log10Activity"]))

    def test_oracle_brute_force_agrees_with_every_compared_cell(self):
        phs, es = fixture.cell_centres()
        for case in self.data["cases"]:
            element, log_a = case["element"], case["log10Activity"]
            ids = case["speciesIds"]
            for j, row in enumerate(case["rows"]):
                for i, token in enumerate(decode(row)):
                    if token == ".":
                        continue
                    self.assertEqual(ids[int(token)], oracle.dominant(element, phs[i], es[j], log_a),
                                     (element, log_a, phs[i], es[j]))

    def test_compared_cells_are_at_least_one_millivolt_from_a_boundary(self):
        phs, es = fixture.cell_centres()
        for case in self.data["cases"]:
            element, log_a = case["element"], case["log10Activity"]
            for j in range(0, 200, 7):
                for i, token in enumerate(decode(case["rows"][j])):
                    if i % 5 == 0 and token != ".":
                        self.assertGreaterEqual(oracle.margin_V(element, phs[i], es[j], log_a), 1e-3 - 1e-12)


if __name__ == "__main__":
    unittest.main()
