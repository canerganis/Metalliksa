"""Oracle tests O1-O9 for python/micrograph_measure.py (numpy/scipy only; images generated here).

Every expected value comes from the generating arrays (label maps, true masks) or from a hand
calculation written in the test, never from the module under test. Synthetic images only: this
is software verification, not validation on real micrographs.

Run from the python directory:  python -B -m unittest test_micrograph_measure
"""
import base64
import hashlib
import json
import math
import unittest

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

import micrograph_measure as mm

EIGHT = np.ones((3, 3), dtype=bool)


def payload(grey, *, calibration=None, classes=None, grains=None, manual=None, crop=None, **options):
    """Flat request of python/micrograph_measure.py built from test-friendly arguments."""
    grey = np.ascontiguousarray(grey, dtype=np.uint8)
    out = {"imageWidth": int(grey.shape[1]), "imageHeight": int(grey.shape[0]),
           "imageData": base64.b64encode(grey.tobytes()).decode("ascii")}
    out.update(calibration or {})
    for key, spec in (classes or {}).items():
        if key == "dark":
            out.update(darkMaxGrey=spec["maxGrey"], darkLabel=spec["label"])
        else:
            out.update(brightMinGrey=spec["minGrey"], brightLabel=spec["label"])
    if grains is not None:
        out["boundaryMaxGrey"] = grains["boundaryMaxGrey"]
    if manual is not None:
        out["manualCounts"] = manual["counts"]
        if "clicks" in manual:
            out["manualClicks"] = manual["clicks"]
    out.update(crop or {})
    out.update(options)
    return out


def scale(um_per_px):
    return {"umPerPx": um_per_px, "calibrationNote": "synthetic test image"}


def g_from_lbar_um(lbar_um):
    # ASTM E112: G = -6.643856 log10(l_bar in mm) - 3.288 (written out independently of the module).
    return -6.643856 * math.log10(lbar_um / 1000.0) - 3.288


def square_grid(d=25, n=8, width=2, grain=200, boundary=40, offset=0):
    size = d * n
    g = np.full((size, size), grain, np.uint8)
    for k in range(n):
        c = k * d + d // 2 + offset
        g[:, c:c + width] = boundary
        g[c:c + width, :] = boundary
    return g


def voronoi(n_seeds, seed, w=800, h=540, noise=4.0):
    rng = np.random.default_rng(seed)
    seeds = rng.uniform([0, 0], [w, h], size=(n_seeds, 2))
    yy, xx = np.mgrid[0:h, 0:w]
    _, lab = cKDTree(seeds).query(np.c_[xx.ravel(), yy.ravel()])
    lab = lab.reshape(h, w)
    edge = np.zeros_like(lab, bool)
    edge[:, 1:] |= lab[:, 1:] != lab[:, :-1]
    edge[1:, :] |= lab[1:, :] != lab[:-1, :]
    edge[:, :-1] |= edge[:, 1:].copy()  # about 2 px wide boundary lines
    g = np.full((h, w), 170.0)
    g[edge] = 60.0
    g += rng.normal(0, noise, g.shape)
    return np.clip(np.rint(g), 0, 255).astype(np.uint8), lab


def discs(target_pct, seed, w=800, h=540, rmin=3, rmax=12, inside=15.0, matrix=120.0, noise=6.0):
    rng = np.random.default_rng(seed)
    mask = np.zeros((h, w), bool)
    yy, xx = np.mgrid[0:h, 0:w]
    while mask.mean() * 100 < target_pct:
        r = rng.uniform(rmin, rmax)
        cx, cy = rng.uniform(r, w - r), rng.uniform(r, h - r)
        mask |= (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
    g = np.where(mask, inside, matrix) + rng.normal(0, noise, mask.shape)
    return np.clip(np.rint(g), 0, 255).astype(np.uint8), mask


def runs_along(mask, axis):
    m = mask if axis == 1 else mask.T
    return int((m[:, 1:] & ~m[:, :-1]).sum() + m[:, 0].sum())


class O1SquareGrid(unittest.TestCase):
    """Square grains of pitch d with 2-px boundaries: l_bar = d exactly on 0 and 90 degree lines."""

    def test_exact_intercept_and_g(self):
        d, um = 25, 0.5
        res = mm.measure(payload(square_grid(d), calibration=scale(um), grains={"boundaryMaxGrey": 120},
                                 linesPerDirection=8))
        gs = res["grainSize"]
        lines = res["testLines"]
        h_idx = [ln["index"] for ln in lines if ln["orientation"] == "h"]
        h_counts = [gs["perLineIntersections"][i] for i in h_idx]
        self.assertEqual(h_counts, [8.0] * 8)  # 200 px line crosses 8 boundaries, ends inside grains
        self.assertEqual(sum(ln["lengthPx"] for ln in lines if ln["orientation"] == "h") / sum(h_counts), d)
        self.assertEqual(gs["meanInterceptPx"], d)  # 0 + 90 degrees
        self.assertAlmostEqual(gs["meanIntercept"]["value"], d * um, places=12)
        self.assertAlmostEqual(gs["astmG"]["value"], g_from_lbar_um(d * um), places=9)
        self.assertEqual(gs["perLineIntersectionsPerPx"]["halfWidth"], 0.0)
        self.assertEqual(gs["totalIntersections"], 128.0)
        self.assertEqual(gs["warnings"], [])

    def test_a_test_line_lying_on_a_boundary_scores_zero_and_warns(self):
        # Boundaries shifted by -1 px put row/column 111 (test line 5 of 8 at round(5 * 200 / 9)) on a boundary.
        gs = mm.measure(payload(square_grid(25, offset=-1), grains={"boundaryMaxGrey": 120}))["grainSize"]
        self.assertEqual(gs["perLineIntersections"][4], 0.0)
        self.assertTrue(any("lie entirely on boundary" in w for w in gs["warnings"]), gs["warnings"])

    def test_line_end_on_a_boundary_counts_half(self):
        total, points, along = mm.count_line(np.array([1, 1, 0, 0, 1, 0, 0, 1], bool))
        self.assertEqual(total, 2.0)  # 1/2 (start) + 1 (interior) + 1/2 (end)
        self.assertEqual([w for _, w in points], [0.5, 1.0, 0.5])
        self.assertFalse(along)
        self.assertEqual(mm.count_line(np.ones(5, bool))[0], 0.0)
        self.assertTrue(mm.count_line(np.ones(5, bool))[2])


class O2Voronoi(unittest.TestCase):
    """G within +/-0.15 of the label-map truth counted on the same test lines."""

    def check(self, n_seeds, seed):
        grey, lab = voronoi(n_seeds, seed)
        res = mm.measure(payload(grey, calibration=scale(0.1), grains={"boundaryMaxGrey": 115}))
        crossings, length = 0, 0
        for ln in res["testLines"]:
            prof = lab[ln["position"], :] if ln["orientation"] == "h" else lab[:, ln["position"]]
            crossings += int(np.count_nonzero(np.diff(prof) != 0))
            length += ln["lengthPx"]
        g_true = g_from_lbar_um(length / crossings * 0.1)
        g = res["grainSize"]["astmG"]["value"]
        self.assertLessEqual(abs(g - g_true), 0.15, f"{n_seeds} seeds: G {g:.3f} vs truth {g_true:.3f}")
        return g, g_true, res["grainSize"]

    def test_60_seeds(self):
        self.check(60, 7)

    def test_240_seeds(self):
        g, g_true, gs = self.check(240, 11)
        self.assertGreaterEqual(gs["totalIntersections"], 50)
        self.assertIsNotNone(gs["relativeAccuracyPct"])


class O3ScaleDoubling(unittest.TestCase):
    def test_doubling_um_per_px_lowers_g_by_two(self):
        grey, _ = voronoi(240, 11)
        g1 = mm.measure(payload(grey, calibration=scale(0.1), grains={"boundaryMaxGrey": 115}))["grainSize"]["astmG"]["value"]
        g2 = mm.measure(payload(grey, calibration=scale(0.2), grains={"boundaryMaxGrey": 115}))["grainSize"]["astmG"]["value"]
        self.assertAlmostEqual(g1 - g2, 2.000, delta=0.001)


class O4NoBoundaries(unittest.TestCase):
    def test_flat_image_gives_null_not_a_floor(self):
        rng = np.random.default_rng(3)
        grey = np.clip(np.rint(170 + rng.normal(0, 4, (300, 400))), 0, 255).astype(np.uint8)
        gs = mm.measure(payload(grey, calibration=scale(0.1), grains={"boundaryMaxGrey": 115}))["grainSize"]
        self.assertEqual(gs["totalIntersections"], 0)
        self.assertIsNone(gs["meanIntercept"]["value"])
        self.assertIsNone(gs["astmG"]["value"])
        self.assertIn("no boundary intersections", gs["astmG"]["reason"])

    def test_isolated_pores_trigger_the_network_warning(self):
        grey, _ = discs(2.0, 5)
        gs = mm.measure(payload(grey, calibration=scale(0.1), grains={"boundaryMaxGrey": 67}))["grainSize"]
        self.assertTrue(any("connected network" in w for w in gs["warnings"]), gs["warnings"])


class O5Discs(unittest.TestCase):
    def check(self, pct, seed, noise):
        grey, mask = discs(pct, seed, noise=noise)
        res = mm.measure(payload(grey, calibration=scale(0.1), classes={"dark": {"label": "pores", "maxGrey": 67}},
                                 minAreaPx=4))
        cls = res["classes"]["dark"]
        frac = cls["areaFraction"]["pixelFraction"]["value"]
        self.assertLessEqual(abs(frac * 100 - mask.mean() * 100), 0.01, f"{pct} %: {frac * 100:.4f} vs {mask.mean() * 100:.4f}")
        lab, n_true = ndimage.label(mask, structure=EIGHT)
        self.assertEqual(cls["particles"]["count"], n_true)
        h, w = mask.shape
        interior = [s for s in ndimage.find_objects(lab)
                    if not (s[0].start == 0 or s[1].start == 0 or s[0].stop == h or s[1].stop == w)]
        areas = np.bincount(lab.ravel())[1:]
        edge_ids = {i + 1 for i, s in enumerate(ndimage.find_objects(lab))
                    if s[0].start == 0 or s[1].start == 0 or s[0].stop == h or s[1].stop == w}
        true_ecd = np.mean([2 * math.sqrt(a / math.pi) * 0.1 for i, a in enumerate(areas, 1) if i not in edge_ids])
        self.assertEqual(len(interior), n_true - len(edge_ids))
        mean_ecd = cls["particles"]["meanEcd"]["value"]
        self.assertLessEqual(abs(mean_ecd / true_ecd - 1), 0.02, f"ECD {mean_ecd:.4f} vs {true_ecd:.4f}")
        return res

    def test_half_percent(self):
        self.check(0.5, 21, 6)

    def test_two_percent(self):
        self.check(2.0, 22, 6)

    def test_five_percent_noisier(self):
        self.check(5.0, 23, 12)

    def test_blank_image_has_no_pores_and_null_ecd(self):
        grey = np.full((200, 300), 120, np.uint8)
        p = mm.measure(payload(grey, calibration=scale(0.1), classes={"dark": {"label": "pores", "maxGrey": 67}}))
        part = p["classes"]["dark"]["particles"]
        self.assertEqual(part["count"], 0)
        self.assertIsNone(part["meanEcd"]["value"])
        self.assertEqual(p["classes"]["dark"]["areaFraction"]["pixelFraction"]["value"], 0.0)
        self.assertIsNone(part["meanFreePath"]["value"])

    def test_disc_shape_class_and_circularity(self):
        grey = np.full((101, 101), 120, np.uint8)
        yy, xx = np.mgrid[0:101, 0:101]
        grey[(xx - 50) ** 2 + (yy - 50) ** 2 <= 20 ** 2] = 10
        part = mm.measure(payload(grey, calibration=scale(1.0), classes={"dark": {"label": "pore", "maxGrey": 60}}))
        p = part["classes"]["dark"]["particles"]["particleList"][0]
        self.assertEqual(p["shapeClass"], "near-circular")
        self.assertAlmostEqual(p["circularity"], 1.0, delta=0.08)  # Crofton estimate on a pixelised disc
        self.assertAlmostEqual(p["perimeterPx"], 2 * math.pi * 20, delta=2 * math.pi * 20 * 0.05)
        self.assertAlmostEqual(p["aspectRatio"], 1.0, delta=0.02)
        bar = np.full((60, 200), 120, np.uint8)
        bar[25:35, 20:180] = 10  # 160 x 10 rectangle
        q = mm.measure(payload(bar, classes={"dark": {"label": "stringer", "maxGrey": 60}}))
        self.assertEqual(q["classes"]["dark"]["particles"]["particleList"][0]["shapeClass"], "elongated")


class O6Particles(unittest.TestCase):
    def test_ten_percent_bright_particles(self):
        grey, mask = discs(10.0, 31, rmin=2, rmax=6, inside=175.0, matrix=100.0, noise=5.0)
        res = mm.measure(payload(grey, calibration=scale(0.1), classes={"bright": {"label": "particles", "minGrey": 137}},
                                 minAreaPx=1))
        cls = res["classes"]["bright"]
        self.assertLessEqual(abs(cls["areaFraction"]["pixelFraction"]["value"] * 100 - mask.mean() * 100), 0.05)
        _, n8 = ndimage.label(mask, structure=EIGHT)
        self.assertEqual(cls["particles"]["count"], n8)
        vv = mask.mean()
        n_l = (runs_along(mask, 1) + runs_along(mask, 0)) / (2 * mask.size * 0.1)
        lam_true = (1 - vv) / n_l
        lam = cls["particles"]["meanFreePath"]["value"]
        self.assertLessEqual(abs(lam / lam_true - 1), 0.01, f"lambda {lam:.4f} vs {lam_true:.4f}")
        self.assertGreater(n8, 300)


class O7FieldToFieldCI(unittest.TestCase):
    def test_four_tiles_hand_computed(self):
        grey = np.full((100, 100), 200, np.uint8)
        # 2 x 2 tiles of 50 x 50 = 2500 px with 250 / 500 / 750 / 1000 dark pixels (0.1, 0.2, 0.3, 0.4)
        for (r0, c0), rows in zip(((0, 0), (0, 50), (50, 0), (50, 50)), (5, 10, 15, 20)):
            grey[r0:r0 + rows, c0:c0 + 50] = 10
        res = mm.measure(payload(grey, classes={"dark": {"label": "dark", "maxGrey": 100}}, tiles=2))
        f2f = res["classes"]["dark"]["areaFraction"]["fieldToField"]
        self.assertEqual(sorted(f2f["tileFractions"]), [0.1, 0.2, 0.3, 0.4])
        s = math.sqrt(((0.1 - 0.25) ** 2 + (0.2 - 0.25) ** 2 + (0.3 - 0.25) ** 2 + (0.4 - 0.25) ** 2) / 3)
        t_975_3 = 3.1824  # Student t table, two-sided 95 %, 3 degrees of freedom
        self.assertAlmostEqual(f2f["halfWidth"], t_975_3 * s / math.sqrt(4), delta=1e-4)
        pf = res["classes"]["dark"]["areaFraction"]["pixelFraction"]
        self.assertAlmostEqual(pf["value"], 0.25, places=12)
        self.assertAlmostEqual(pf["ci95"][0], 0.25 - f2f["halfWidth"], places=12)
        sens = res["classes"]["dark"]["areaFraction"]["thresholdSensitivity"]
        self.assertEqual(sens["fractionAtThresholdMinusDelta"], 0.25)  # bimodal 10/200: insensitive to +/-10


class O8Uncalibrated(unittest.TestCase):
    def test_every_length_is_null_and_fractions_remain(self):
        grey, _ = voronoi(60, 7)
        res = mm.measure(payload(grey, classes={"dark": {"label": "boundaries", "maxGrey": 115}},
                                 grains={"boundaryMaxGrey": 115}, manual={"counts": [5] * 16}))
        self.assertIn("calibrationRequired", res)
        dimensional = {"µm", "µm²", "1/mm²"}
        found = []

        def walk(node, path):
            if isinstance(node, dict):
                if node.get("unit") in dimensional and "value" in node:
                    found.append(path)
                    self.assertIsNone(node["value"], path)
                    reason = node.get("reason", "")
                    self.assertTrue("uncalibrated" in reason or "no particle" in reason, f"{path}: {reason}")
                for k, v in node.items():
                    walk(v, f"{path}.{k}")
                    if k.endswith("Um") and isinstance(v, (int, float)):
                        self.fail(f"{path}.{k} is a number without calibration")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}[{i}]")
        walk(res, "result")
        self.assertGreater(len(found), 8)
        self.assertIsNone(res["grainSize"]["astmG"]["value"])
        self.assertIsNone(res["grainSizeManual"]["astmG"]["value"])
        self.assertGreater(res["classes"]["dark"]["areaFraction"]["pixelFraction"]["value"], 0)
        self.assertGreater(res["classes"]["dark"]["particles"]["count"], 0)
        self.assertGreater(res["grainSize"]["meanInterceptPx"], 0)


class O9DeterminismAndRecord(unittest.TestCase):
    def test_same_input_same_output_and_sha_echo(self):
        grey, _ = discs(2.0, 22)
        p = payload(grey, calibration={"barLengthUm": 20, "barLengthPx": 160, "calibrationNote": "bar"},
                    classes={"dark": {"label": "pores", "maxGrey": 67}}, grains={"boundaryMaxGrey": 67},
                    crop={"cropBottomPx": 40})
        a, b = mm.measure(p), mm.measure(json.loads(json.dumps(p)))
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertEqual(a["record"]["pixelSha256"], hashlib.sha256(grey.tobytes()).hexdigest())
        cal = a["record"]["calibration"]
        self.assertEqual((cal["method"], cal["barLengthUm"], cal["barLengthPx"]), ("scale-bar", 20.0, 160.0))
        self.assertEqual(cal["umPerPx"], 20 / 160)
        self.assertEqual(a["record"]["roi"], {"x0": 0, "y0": 0, "x1": 800, "y1": 500})
        self.assertEqual(a["methodVersion"], mm.METHOD_VERSION)
        # The banner rows below y1 are excluded: the ROI fraction equals the fraction of those rows.
        frac = a["classes"]["dark"]["areaFraction"]["pixelFraction"]["value"]
        self.assertEqual(frac, float((grey[:500] <= 67).mean()))
        mask = np.unpackbits(np.frombuffer(base64.b64decode(a["classes"]["dark"]["maskPackedBase64"]), np.uint8))
        self.assertEqual(mask[:800 * 500].reshape(500, 800).astype(bool).tolist(), (grey[:500] <= 67).tolist())


class ManualMode(unittest.TestCase):
    def test_manual_counts_match_the_automatic_square_grid(self):
        grid = square_grid(25)
        res = mm.measure(payload(grid, calibration=scale(0.5), grains={"boundaryMaxGrey": 120},
                                 manual={"counts": [8] * 16, "clicks": [{"line": 0, "x": 12.5, "y": 22, "weight": 1}]}))
        auto, manual = res["grainSize"], res["grainSizeManual"]
        self.assertEqual(manual["astmG"]["value"], auto["astmG"]["value"])
        self.assertEqual(manual["clicks"][0]["line"], 0)

    def test_manual_rejects_bad_counts(self):
        grid = square_grid(25)
        for counts in ([8] * 15, [-1] + [8] * 15, [0.3] + [8] * 15):
            with self.assertRaises(mm.MeasureInputError):
                mm.measure(payload(grid, manual={"counts": counts}))


class InputValidation(unittest.TestCase):
    def test_rejections(self):
        grid = square_grid(25)
        good = payload(grid, classes={"dark": {"label": "d", "maxGrey": 100}})
        bad = dict(good, imageWidth=199)
        cases = [
            bad,
            payload(grid, classes={"dark": {"label": "d", "maxGrey": 150}, "bright": {"label": "b", "minGrey": 150}}),
            payload(grid, classes={"dark": {"label": "d", "maxGrey": 100}}, crop={"cropLeftPx": 100, "cropRightPx": 96}),
            payload(grid, classes={"dark": {"label": "d", "maxGrey": 100}}, calibration={"umPerPx": 0.1}),
            payload(grid, classes={"dark": {"label": "d", "maxGrey": 100}},
                    calibration={"barLengthUm": 0, "barLengthPx": 100}),
            payload(grid, classes={"dark": {"label": "d", "maxGrey": 100}},
                    calibration={"barLengthUm": 10, "barLengthPx": 100, "umPerPx": 0.1, "calibrationNote": "x"}),
            dict(payload(grid, classes={"dark": {"label": "d", "maxGrey": 100}}), unknownKey=1),
            payload(grid, classes={"dark": {"label": "d", "maxGrey": 100}}, manual={"counts": [1] * 16, "clicks": [3]}),
            payload(grid),
        ]
        for i, p in enumerate(cases):
            with self.assertRaises(mm.MeasureInputError, msg=f"case {i}"):
                mm.measure(p)
        with self.assertRaises(mm.MeasureInputError):
            mm.decode_image(5000, 1, "")

    def test_no_property_or_process_inference_keys(self):
        grey, _ = voronoi(60, 7)
        res = mm.measure(payload(grey, calibration=scale(0.1), classes={"dark": {"label": "b", "maxGrey": 115}},
                                 grains={"boundaryMaxGrey": 115}))
        res.pop("limitations")  # the limitations text names what is NOT inferred
        text = json.dumps(res).lower()
        for word in ("hardness", "yield", "tensile", "hall", "cooling", "sdas", "dendrite", "confidence",
                     "qualified", "certified", "compliant", "\"validated\""):
            self.assertNotIn(word, text)


class WorkerRpc(unittest.TestCase):
    def test_rpc_dispatch(self):
        import lpbf_worker_rpc as rpc
        grid = square_grid(25)
        p = payload(grid, calibration=scale(0.5), grains={"boundaryMaxGrey": 120})
        self.assertIn("micrograph-measure", rpc.method_names())
        out = rpc.dispatch({"method": "micrograph-measure", "payload": p}, queue=None, capabilities_handler=None)
        self.assertEqual(out["grainSize"]["meanInterceptPx"], 25)


if __name__ == "__main__":
    unittest.main()
