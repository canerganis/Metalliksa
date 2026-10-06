"""Tests for tools/lpbf_powder_layer_analysis.py (pure statistics on a synthetic table, one solver check)."""

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
import lpbf_powder_layer_analysis as pla  # noqa: E402


def row(i, P, v, d, layer, w, dep, balling=0):
    return {"rowId": f"s-{i}", "material": "316L Stainless Steel", "power_W": P, "speed_mm_s": v,
            "beamDiameter_um": d, "layer_um": layer, "preheat_C": 20.0, "width_um": w, "depth_um": dep,
            "balling": balling}


def synthetic():
    rows, i = [], 0
    # 10 matched sets: width at 30 um = 0.9 x bare, depth at 30 um = 1.2 x bare; 60 um = 0.8 / 1.5 x bare
    for n in range(10):
        P, v, d = 100.0 + 10 * n, 500.0, 80.0
        w0, d0 = 100.0 + n, 50.0 + n
        for layer, fw, fd in ((0.0, 1.0, 1.0), (30.0, 0.9, 1.2), (60.0, 0.8, 1.5)):
            rows.append(row(i, P, v, d, layer, w0 * fw, d0 * fd, balling=1 if (layer == 60.0 and n < 3) else 0))
            i += 1
    # one set with a replicate at 0 um (mean must be used) and a set with a single level only
    rows.append(row(i, 100.0, 500.0, 80.0, 0.0, 120.0, 70.0)); i += 1
    rows.append(row(i, 999.0, 500.0, 80.0, 30.0, 1.0, 1.0))
    return rows


def published_zehner_oracle(porosity, k_gas, k_solid, shape_c=1.25):
    """Direct transcription of the published VDI form, independent of the tool implementation."""
    conductivity_ratio = k_solid / k_gas
    shape = shape_c * ((1.0 - porosity) / porosity) ** (10.0 / 9.0)
    N = 1.0 - shape / conductivity_ratio
    logarithmic_contribution = (
        (1.0 - 1.0 / conductivity_ratio)
        * shape
        * math.log(conductivity_ratio / shape)
        / (N**2)
    )
    geometric_contribution = (
        -(shape + 1.0) / 2.0 - (shape - 1.0) / N
    )
    return k_gas * (
        1.0 - math.sqrt(1.0 - porosity)
        + 2.0 * math.sqrt(1.0 - porosity) / N
        * (logarithmic_contribution + geometric_contribution)
    )


class PowderLayerAnalysisTests(unittest.TestCase):
    def test_grouping_and_levels(self):
        rows = synthetic()
        sets = pla.group_sets(rows)
        self.assertEqual(len(sets), 11)
        self.assertEqual(sum(1 for v in sets.values() if len(v) >= 2), 10)
        self.assertEqual(len(sets[(100.0, 500.0, 80.0)][0.0]), 2)

    def test_paired_stats_exact(self):
        sets = pla.group_sets(synthetic())
        s = pla.paired_summary(sets, 30.0, 0.0)
        self.assertEqual(s["nSets"], 10)
        self.assertEqual(s["nRowsHigh"], 10)
        self.assertEqual(s["nRowsLow"], 11)  # replicate row counted in n
        self.assertFalse(s["lowN"])
        # all sets but the replicate one have exact ratios 0.9 / 1.2 (replicate set: bare mean 110 vs 100)
        self.assertAlmostEqual(s["widthRatio"]["median"], 0.9, places=9)
        self.assertAlmostEqual(s["depthRatio"]["median"], 1.2, places=9)
        lo, hi = s["widthRatio"]["ci95"]
        self.assertLessEqual(lo, 0.9 + 1e-9)
        self.assertGreaterEqual(hi, 0.9 - 1e-9)
        s2 = pla.paired_summary(sets, 60.0, 30.0)
        self.assertAlmostEqual(s2["widthRatio"]["median"], 0.8 / 0.9, places=9)
        self.assertAlmostEqual(s2["depthRatio"]["median"], 1.5 / 1.2, places=9)
        self.assertEqual(s2["widthRatio"]["fractionAbove1"], 0.0)
        # replicate mean is used for the replicate set: bare width mean = (100 + 120) / 2 = 110
        pv = {p["key"]: p for p in pla.paired_values(sets, 30.0, 0.0)}
        self.assertAlmostEqual(pv[(100.0, 500.0, 80.0)]["w_lo"], 110.0)

    def test_bootstrap_determinism_and_seed(self):
        cols = [[0.8, 0.9, 1.0, 1.1, 0.95, 0.85, 1.2, 0.7], [1.0, 1.1, 1.2, 1.3, 0.9, 1.0, 1.4, 1.05]]
        a = pla.cluster_bootstrap_medians(cols)
        b = pla.cluster_bootstrap_medians(cols)
        c = pla.cluster_bootstrap_medians(cols, seed=1)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        for lo, hi in a:
            self.assertLessEqual(lo, hi)

    def test_balling_and_regime_split(self):
        rows = synthetic()
        bf = pla.balling_fractions(rows)
        self.assertEqual(bf["60"]["ballingFlagged"], 3)
        self.assertEqual(bf["0"]["ballingFlagged"], 0)
        regimes = {k: ("conduction" if k[0] < 150 else "keyhole") for k in pla.group_sets(rows)}
        m = pla.analyse_matched_sets(rows, regimes)
        self.assertEqual(m["all"]["nSets"], 10)
        self.assertEqual(set(m["byRegime"]), {"conduction", "keyhole"})
        self.assertEqual(m["byRegime"]["conduction"]["nSets"] + m["byRegime"]["keyhole"]["nSets"], 10)
        self.assertEqual(set(m["bySpot_um"]), {"80"})

    def test_zehner_schlunder_limit(self):
        # Equal phase conductivities give that same conductivity at any porosity.
        self.assertAlmostEqual(pla.zehner_schlunder(0.4, 1.0, 1.0), 1.0, places=12)
        # porosity -> 1 is all gas; solid packing fraction -> 1 (porosity -> 0) is all solid.
        self.assertAlmostEqual(pla.zehner_schlunder(1.0 - 1e-7, 0.0177, 16.3), 0.0177, delta=1e-6)
        self.assertAlmostEqual(pla.zehner_schlunder(1e-9, 0.0177, 16.3), 16.3, delta=1e-4)

    def test_zehner_schlunder_independent_published_oracle(self):
        cases = ((0.45, 0.0177, 16.3), (0.4, 0.021, 2.5), (0.3, 0.1, 0.5))
        for args in cases:
            with self.subTest(args=args):
                self.assertAlmostEqual(
                    pla.zehner_schlunder(*args), published_zehner_oracle(*args), places=12
                )

    def test_reference_reuse_rejects_stale_identity_and_settings(self):
        settings = pla.reference_settings(900.0)
        valid = {"schema": pla.SCHEMA, "implementationHash": "impl", "datasets": [{"sha256": "data"}],
                 "referenceTransient": {"settings": settings, "rows": [], "counts": {"cases": 0}}}
        self.assertEqual(pla.validate_reused_reference(valid, "impl", "data", settings),
                         valid["referenceTransient"])
        stale_variants = []
        for key, value in (("schema", "old-schema"), ("implementationHash", "old-impl")):
            stale = dict(valid)
            stale[key] = value
            stale_variants.append(stale)
        stale_hash = dict(valid)
        stale_hash["datasets"] = [{"sha256": "old-data"}]
        stale_variants.append(stale_hash)
        stale_settings = dict(valid)
        stale_settings["referenceTransient"] = {**valid["referenceTransient"],
                                                  "settings": {**settings, "mesh_um": 10}}
        stale_variants.append(stale_settings)
        for source in stale_variants:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    pla.validate_reused_reference(source, "impl", "data", settings)

    def test_reference_reuse_rejects_malformed_blocks(self):
        settings = pla.reference_settings(900.0)
        base = {"schema": pla.SCHEMA, "implementationHash": "impl", "datasets": [{"sha256": "data"}]}
        for block in (None, [], {"settings": []}, {"settings": settings},
                      {"settings": settings, "rows": {}, "counts": {}}):
            source = {**base, "referenceTransient": block}
            with self.subTest(block=block):
                with self.assertRaises(ValueError):
                    pla.validate_reused_reference(source, "impl", "data", settings)

    def test_kernel_sensitivity_one_row(self):
        rows = [row(0, 200.0, 800.0, 80.0, 30.0, 100.0, 60.0)]
        ks = pla.kernel_sensitivity(rows)
        self.assertEqual(len(ks["cases"]), 3)
        self.assertEqual(ks["maxRelativeDifference"], 0.0)
        self.assertTrue(ks["layerIgnored"])
        self.assertEqual(ks["fallbackWarnings"], ks["solverCalls"])  # flat-plate path was the realized one


if __name__ == "__main__":
    unittest.main()
