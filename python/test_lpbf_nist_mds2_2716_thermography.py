"""Tests for python/lpbf_nist_mds2_2716_thermography.py.

Self-contained: synthetic HDF5 inputs are generated deterministically in a
temporary directory by the helpers below (origin: this file). The committed
derived table data/benchmark/nist-amb2022-03/derived/ is checked against its
manifest and the publisher NERDm record committed under official/. Tests that
need the 550 MB NIST raw file skip with an explicit reason when it is absent.
"""

import contextlib
import hashlib
import io
import json
import math
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lpbf_nist_mds2_2716_thermography as m  # noqa: E402

try:
    import h5py  # noqa: F401
    import numpy as np
    HAVE_H5PY = True
except ImportError:  # pragma: no cover - interpreter dependent
    HAVE_H5PY = False

NO_H5PY = "h5py/numpy not installed in this interpreter (%s); set METALLIX_PYTHON to the locked CPython 3.12" % sys.executable
DERIVED = m.DERIVED_DIR / m.DERIVED_NAME
DERIVED_MANIFEST = m.DERIVED_DIR / "manifest.json"
SOURCE_MANIFEST = m.DATASET_DIR / "manifest.json"

# Synthetic hot-spot signal levels by time since the spot passed a pixel (frames).
# Each level spans an integer number of frames, so counts are exact for any sub-frame phase.
LEVELS = [(0, 10, 4095), (10, 15, 3000), (15, 20, 1500), (20, 30, 700), (30, 40, 200)]


def synthetic_line(n_frames=300, a1=400, a2=20, col=10, start_row=50.0, px_per_frame=1.5, t_on=1, t_off=200,
                   quadratic=0.0):
    """Moving saturated spot along a1 in columns col-1..col+1; zeros below 100 DL as in the NIST files."""
    sig = np.zeros((n_frames, a1, a2), dtype=np.uint16)
    rows = np.arange(a1, dtype=float)
    t_pass = (rows - start_row) / px_per_frame + t_on
    if quadratic:
        t_pass = t_on + (np.sqrt(np.maximum(rows - start_row, 0) / quadratic))
    reached = (rows >= start_row) & (t_pass <= t_off)
    for t in range(n_frames):
        tau = t - t_pass
        level = np.zeros(a1)
        for lo, hi, val in LEVELS:
            level[(tau >= lo) & (tau < hi) & reached] = val
        if t > t_off:
            level[level == 4095] = 3000
        for c in (col - 1, col, col + 1):
            sig[t, :, c] = level
    return sig


def write_thermo_h5(path, lines, frame_rate=30000.0, bit_depth=12.0, threshold=100.0):
    with h5py.File(path, "w") as f:
        td = f.create_group("ThermalData")
        td.attrs["frame_rate"] = [frame_rate]
        for name, (sig, power, speed, spot) in lines.items():
            g = td.create_group(name)
            g.attrs["laser_power"] = [power]
            g.attrs["scan_speed"] = [speed]
            g.attrs["spot_size"] = [spot]
            g.attrs["spot_size_measure"] = "D4s"
            ds = g.create_dataset("Signal", data=sig, chunks=(25, 25, 5) if sig.shape[0] >= 25 else None)
            ds.attrs["bit_depth"] = [bit_depth]
            ds.attrs["threshold_level"] = [threshold]
            ds.attrs["threshold_zeros"] = "true"
            ds.attrs["units"] = "digital levels"


def synthetic_xypt(n_tracks=4, on=261, gap=525, lead=10, length=2.5, hatch=0.1087):
    x, y, p, t = [], [], [], []
    x += [0.0] * lead
    y += [0.0] * lead
    p += [0.0] * lead
    t += [0] * lead
    t[-1] = 0
    for k in range(n_tracks):
        x0, x1 = (0.5, 0.5 + length) if k % 2 == 0 else (0.5 + length, 0.5)
        for i in range(on):
            x.append(x0 + (x1 - x0) * i / (on - 1))
            y.append(28.0 + k * hatch)
            p.append(285.0)
            t.append(4 if (k == 0 and i == 0) else 0)
        if k < n_tracks - 1:
            x += [x1] * gap
            y += [28.0 + k * hatch] * gap
            p += [0.0] * gap
            t += [0] * gap
    return {"X": np.array(x, dtype=np.float32), "Y": np.array(y, dtype=np.float32),
            "P": np.array(p, dtype=np.float32), "T": np.array(t, dtype=np.uint8)}


def write_xypt_h5(path, pads, transpose=False):
    with h5py.File(path, "w") as f:
        cal = f.create_group("Calibration")
        cal.attrs["GalvoCal_Applied"] = "false"
        cal.attrs["LaserCal_Applied"] = "false"
        xy = f.create_group("XYPT")
        for pad, ch in pads.items():
            g = xy.create_group(pad)
            for k, v in ch.items():
                g.create_dataset(k, data=v.reshape(-1, 1) if transpose else v.reshape(1, -1))


def walk_keys(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield prefix + k, k, v
            yield from walk_keys(v, prefix + k + ".")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_keys(v, "%s%d." % (prefix, i))


TEMPERATURE_KEY = re.compile(r"temperature|coolingrate|_C$|_K$|_K_s$", re.I)


def assert_no_temperature(test, obj):
    for path, key, value in walk_keys(obj):
        if TEMPERATURE_KEY.search(key):
            test.assertIn(key, ("temperatureConversion", "temperatureConversionMissingReason"), path)
            if key == "temperatureConversion":
                test.assertIsNone(value, path)
    test.assertEqual(m.temperature_key_paths(obj), [])


class NoTemperatureCheckTests(unittest.TestCase):
    """A9 is computed from the record's keys, not asserted."""

    def test_regex_matches_test_helper(self):
        self.assertEqual(m.TEMPERATURE_KEY.pattern, TEMPERATURE_KEY.pattern)

    def test_clean_record_passes(self):
        rec = {"evidence": {"temperatureConversion": None, "temperatureConversionMissingReason": "x"},
               "lines": [{"tat": 3, "power_W": 285}]}
        out = m.no_temperature_check(rec)
        self.assertEqual(out["result"], "pass")
        self.assertIn("0 offending key(s)", out["detail"])

    def test_planted_temperature_keys_fail_and_are_named(self):
        rec = {"evidence": {"temperatureConversion": "sakuma-hattori"},
               "lines": [{"peak_C": 1400.0}, {"m": {"coolingRate_K_s": 1e6}}]}
        out = m.no_temperature_check(rec)
        self.assertEqual(out["result"], "fail")
        self.assertIn("3 offending key(s)", out["detail"])
        self.assertEqual(m.temperature_key_paths(rec),
                         ["evidence.temperatureConversion", "lines.0.peak_C", "lines.1.m.coolingRate_K_s"])


class GroupNameTests(unittest.TestCase):
    def test_line_and_pad_names(self):
        self.assertEqual(m.parse_group_name("Line_0_2")["caseId"], "0")
        self.assertEqual(m.parse_group_name("Line_0_2")["repeat"], 2)
        info = m.parse_group_name("Line_2_1_3")
        self.assertEqual((info["set"], info["subset"], info["repeat"], info["caseId"]), (2, 1, 3, "2.1"))
        self.assertEqual(m.parse_group_name("X_pad1")["kind"], "pad")
        self.assertTrue(m.parse_group_name("X_pad1")["challenge"])
        ss = m.parse_group_name("Y_pad2_SS")
        self.assertEqual((ss["kind"], ss["challenge"]), ("pad_ss", False))

    def test_bad_names_raise(self):
        for bad in ("Line_4_1_1", "Line_0_4", "Line_1_3_1", "Z_pad1", "line_0_1", "X_pad3", "Line_0_1_1"):
            with self.assertRaisesRegex(ValueError, "unexpected NIST mds2-2716 ThermalData group name"):
                m.parse_group_name(bad)


class PinGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _pins(self, thermo=b"thermo-bytes", xypt=b"xypt-bytes"):
        (self.dir / m.THERMO_NAME).write_bytes(thermo)
        (self.dir / m.XYPT_NAME).write_bytes(xypt)
        return {
            m.THERMO_NAME: {"bytes": 12, "sha256": hashlib.sha256(b"thermo-bytes").hexdigest(),
                            "source_url": "u1", "required": True},
            m.XYPT_NAME: {"bytes": 10, "sha256": hashlib.sha256(b"xypt-bytes").hexdigest(),
                          "source_url": "u2", "required": True},
            "README.txt": {"bytes": 3, "sha256": hashlib.sha256(b"abc").hexdigest(),
                           "source_url": "u3", "required": False},
        }

    def test_right_bytes_pass_and_optional_readme_absent_is_reported(self):
        with mock.patch.dict(m.PINNED, self._pins(), clear=True):
            out = m.verify_inputs(self.dir)
        self.assertEqual(out[m.THERMO_NAME]["status"], "verified")
        self.assertEqual(out["README.txt"]["status"], "absent")
        self.assertIn("reason", out["README.txt"])

    def test_official_readme_name_is_accepted(self):
        (self.dir / "2716_README.txt").write_bytes(b"abc")
        with mock.patch.dict(m.PINNED, self._pins(), clear=True):
            self.assertEqual(m.verify_inputs(self.dir)["README.txt"]["status"], "verified")

    def test_wrong_size_raises(self):
        with mock.patch.dict(m.PINNED, self._pins(thermo=b"thermo-bytes!"), clear=True):
            with self.assertRaisesRegex(ValueError, "size mismatch for AMB2022-03-718-AMMT-StaringCamera_Signal.h5"):
                m.verify_inputs(self.dir)

    def test_wrong_sha_raises(self):
        with mock.patch.dict(m.PINNED, self._pins(xypt=b"XYPT-bytes"), clear=True):
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch for AMB2022-03-AMMT-718-Pad_XYPT.h5"):
                m.verify_inputs(self.dir)

    def test_absent_raw_gives_explicit_reason(self):
        reason = m.raw_absent_reason(self.dir)
        self.assertIn("raw file(s) missing", reason)
        self.assertIn(m.THERMO_NAME, reason)
        with self.assertRaisesRegex(ValueError, "missing"):
            m.verify_inputs(self.dir)

    def test_unconfigured_reason_names_the_conventions(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("METALLIKSA_NIST_2716_DIR", "METALLIKSA_EXTERNAL_DATA")}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(m, "DEFAULT_RAW_DIR", self.dir / "nope"), \
                mock.patch.object(m, "REPO", self.dir):
            reason = m.raw_absent_reason()
        self.assertIn("METALLIKSA_NIST_2716_DIR", reason)
        self.assertIn("not committed to git", reason)

    def test_resolution_order_explicit_env_external(self):
        ext = self.dir / "ext" / m.EXTERNAL_ID
        ext.mkdir(parents=True)
        for name in (m.THERMO_NAME, m.XYPT_NAME):
            (ext / name).write_bytes(b"x")
        env = {k: v for k, v in os.environ.items() if k != "METALLIKSA_NIST_2716_DIR"}
        env["METALLIKSA_EXTERNAL_DATA"] = str(self.dir / "ext")
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(m.resolve_data_dir(), ext)
            self.assertIsNone(m.raw_absent_reason())
            env2 = dict(env, METALLIKSA_NIST_2716_DIR=str(self.dir / "other"))
            with mock.patch.dict(os.environ, env2, clear=True):
                self.assertEqual(m.resolve_data_dir(), self.dir / "other")
                self.assertIn("missing", m.raw_absent_reason())
            self.assertEqual(m.resolve_data_dir(self.dir / "explicit"), self.dir / "explicit")

    def test_external_manifest_entry_matches_pins(self):
        manifest = json.loads((m.REPO / "external-data-manifest.json").read_text(encoding="utf-8"))
        entry = next(d for d in manifest["datasets"] if d["id"] == m.EXTERNAL_ID)
        files = {f["name"]: f for f in entry["files"]}
        for name, local in ((m.THERMO_NAME, m.THERMO_NAME), (m.XYPT_NAME, m.XYPT_NAME), ("2716_README.txt", "README.txt")):
            self.assertEqual((files[name]["sizeBytes"], files[name]["sha256"]),
                             (m.PINNED[local]["bytes"], m.PINNED[local]["sha256"]), name)
            self.assertEqual(files[name]["status"], "downloaded")
        # Above the 200 MB single-file rule: explicitly never fetched, only verified after manual placement.
        self.assertIs(files[m.THERMO_NAME]["manualPlacementOnly"], True)
        self.assertNotIn("manualPlacementOnly", files[m.XYPT_NAME])

    def test_fetch_tool_skips_manual_placement_file_without_network(self):
        sys.path.insert(0, str(m.REPO / "python" / "tools"))
        import fetch_external_data as fx  # noqa: PLC0415
        pin = m.PINNED[m.THERMO_NAME]
        manifest = {"datasets": [{"id": m.EXTERNAL_ID, "files": [
            {"name": m.THERMO_NAME, "url": pin["source_url"], "sizeBytes": pin["bytes"], "sha256": pin["sha256"],
             "status": "downloaded", "manualPlacementOnly": True}]}]}
        out = io.StringIO()
        with mock.patch.object(fx.urllib.request, "urlopen", side_effect=AssertionError("network used")),                 contextlib.redirect_stdout(out):
            self.assertEqual(fx.fetch(manifest, self.dir, None), 0)
        self.assertIn("manual placement only", out.getvalue())
        self.assertFalse((self.dir / m.EXTERNAL_ID / m.THERMO_NAME).exists())

    def test_external_data_directory_is_git_ignored(self):
        # resolve_data_dir looks in <repo>/external-data/nist-mds2-2716; a 550 MB copy there must not be committable.
        lines = (m.REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("/external-data/", [line.strip() for line in lines])

    def test_pins_match_publisher_nerdm_record(self):
        comps = m.nerdm_component_pins()
        self.assertEqual(comps["Thermography/" + m.THERMO_NAME],
                         (m.PINNED[m.THERMO_NAME]["bytes"], m.PINNED[m.THERMO_NAME]["sha256"]))
        self.assertEqual(comps["ScanStrategy/" + m.XYPT_NAME],
                         (m.PINNED[m.XYPT_NAME]["bytes"], m.PINNED[m.XYPT_NAME]["sha256"]))
        self.assertEqual(comps["2716_README.txt"], (m.PINNED["README.txt"]["bytes"], m.PINNED["README.txt"]["sha256"]))

    def test_pins_match_existing_source_manifest(self):
        files = {Path(f["path"]).name: f for f in json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))["files"]}
        for name, pin in m.PINNED.items():
            self.assertEqual((files[name]["bytes"], files[name]["sha256"]), (pin["bytes"], pin["sha256"]), name)


@unittest.skipUnless(HAVE_H5PY, NO_H5PY)
class LineMetricTests(unittest.TestCase):
    def test_synthetic_line_recovers_motion_and_exact_counts(self):
        sig = synthetic_line()
        out = m.line_metrics(sig, scan_speed_mm_s=960.0)
        tr = out["track"]
        self.assertEqual(tr["status"], "measured-signal")
        self.assertAlmostEqual(tr["pxPerFrame"], 1.5, delta=0.01)
        self.assertEqual(tr["laserOnFrame"], 1)
        self.assertEqual(tr["a2Column"] in (9, 10, 11), True)
        self.assertEqual((tr["a1TrackStart"], tr["a1TrackEnd"]), (50, 348))
        self.assertAlmostEqual(tr["pixelPitch_um"]["value"], 960 / (30000 * 1.5) * 1000, delta=0.2)
        self.assertEqual(tr["pixelPitch_um"]["status"], "derived-inferred")
        tat = out["timeAboveThreshold"]
        expected = {"4095": 10, "2000": 15, "1000": 20, "500": 30, "100": 40}
        for thr, frames in expected.items():
            st = tat[thr]["frames"]
            self.assertEqual((st["median"], st["p25"], st["p75"]), (frames, frames, frames), thr)
            self.assertAlmostEqual(tat[thr]["seconds_median"], frames / 30000.0, places=12)
        self.assertTrue(tat["4095"]["upperCensored"])
        self.assertFalse(tat["1000"]["upperCensored"])
        decay = out["decayFromSaturation"]
        for key, frames in {"4095to2000": 6, "4095to1000": 11, "4095to500": 21, "4095to100": 31}.items():
            self.assertEqual(decay[key]["frames"]["median"], frames, key)
            self.assertIn("NOT a cooling rate", decay[key]["note"])
        ls = out["saturatedLength"]
        self.assertAlmostEqual(ls["temporal_um"], 10 / 30000 * 960 * 1000, places=6)
        self.assertAlmostEqual(ls["ratioSpatialToTemporal"], 1.0, delta=0.05)
        self.assertEqual(out["censoring"]["nPixelsReenteringAboveFloor"], 0)
        self.assertEqual(out["censoring"]["nPixelsSaturated"], out["steadyWindow"]["nPixels"])
        assert_no_temperature(self, out)

    def test_spatter_outliers_are_rejected_and_counted(self):
        sig = synthetic_line()
        for t, row in ((8, 150), (9, 160), (10, 170)):
            sig[t, row, 10] = 4095
        tr = m.locate_track(sig)
        self.assertEqual(tr["status"], "measured-signal")
        self.assertEqual(tr["nLeadingEdgeOutlierFrames"], 3)
        self.assertAlmostEqual(tr["pxPerFrame"], 1.5, delta=0.01)

    def test_too_few_saturated_frames_is_unavailable_with_reason(self):
        sig = synthetic_line(t_off=30)
        out = m.line_metrics(sig, 960.0)
        self.assertEqual(out["track"]["status"], "unavailable")
        self.assertIn("frames contain saturated pixels", out["track"]["reason"])
        self.assertNotIn("pxPerFrame", out["track"])
        self.assertEqual(set(out), {"track"})

    def test_nonlinear_motion_is_unavailable_with_reason(self):
        sig = synthetic_line(quadratic=0.004, n_frames=400, t_off=300)
        tr = m.locate_track(sig)
        self.assertEqual(tr["status"], "unavailable")
        self.assertRegex(tr["reason"], "not linear|rejected as outliers")

    def test_right_censored_decay_is_counted_and_reasoned(self):
        trace = np.array([0, 4095, 4095, 3000, 1500, 600, 300, 200], dtype=np.uint16)
        pm = m._pixel_metrics(trace)
        self.assertEqual((pm["decay"][2000], pm["decay"][500]), (2, 4))
        self.assertIsNone(pm["decay"][100])  # still >= 100 DL when the video ends
        clean = m.line_metrics(synthetic_line(), 960.0)
        for key, entry in clean["decayFromSaturation"].items():
            self.assertEqual((entry["nRightCensored"], entry["rightCensored"]), (0, False), key)
            self.assertEqual(entry["nSaturatedPixels"], clean["steadyWindow"]["nPixels"])
        # Every touched pixel keeps 200 DL until the end of the video: decay to 100 DL is never observed.
        sig = synthetic_line()
        touched = np.maximum.accumulate(sig > 0, axis=0)
        held = np.maximum(sig, np.where(touched, 200, 0)).astype(np.uint16)
        out = m.line_metrics(held, 960.0)
        self.assertEqual(out["track"]["status"], "measured-signal")
        n = out["steadyWindow"]["nPixels"]
        d100 = out["decayFromSaturation"]["4095to100"]
        self.assertEqual(d100["status"], "unavailable")
        self.assertIn("right-censored", d100["reason"])
        self.assertEqual((d100["nRightCensored"], d100["nSaturatedPixels"], d100["rightCensored"]), (n, n, True))
        d500 = out["decayFromSaturation"]["4095to500"]
        self.assertEqual((d500["status"], d500["nRightCensored"], d500["frames"]["median"]), ("measured-signal", 0, 21))
        rows = [{"caseId": "0", "repeat": r, "name": "Line_0_%d" % r, "laserPower_W": 285.0, "scanSpeed_mm_s": 960.0,
                 "spotD4s_um": 67.0, "metrics": out} for r in (1, 2, 3)]
        case = m.aggregate_cases(rows)[0]
        self.assertEqual(case["decayRightCensoredPixels"]["4095to100"], 3 * n)
        self.assertEqual(case["decayRightCensoredPixels"]["4095to500"], 0)
        self.assertIsNone(case["metrics"]["decay4095to100_frames"])

    def test_floor_reentry_is_counted_not_smoothed(self):
        trace = np.array([0, 4095, 4095, 2500, 900, 0, 0, 150, 0], dtype=np.uint16)
        pm = m._pixel_metrics(trace)
        self.assertTrue(pm["gap"])
        self.assertEqual(pm["tat"][100], 5)
        self.assertEqual(pm["decay"][1000], 2)
        self.assertEqual(pm["decay"][100], 3)

    def test_streaming_reads_at_most_one_chunk(self):
        class FakeDataset:
            shape = (103, 4, 4)

            def __init__(self):
                self.slices = []

            def __getitem__(self, sl):
                self.slices.append((sl.start, sl.stop))
                return np.zeros((sl.stop - sl.start, 4, 4))

        ds = FakeDataset()
        blocks = list(m.iter_frames(ds, start=7))
        self.assertEqual(ds.slices[0], (7, 25))
        self.assertTrue(all(b - a <= m.CHUNK_FRAMES and (a % 25 == 0 or a == 7) for a, b in ds.slices))
        self.assertEqual(sum(b.shape[0] for _, b in blocks), 96)
        self.assertEqual(ds.slices[-1], (100, 103))


@unittest.skipUnless(HAVE_H5PY, NO_H5PY)
class ScanStrategyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_layouts_agree_and_trigger_and_speed(self):
        pads = {"Xpad": synthetic_xypt()}
        write_xypt_h5(self.dir / "row.h5", pads)
        write_xypt_h5(self.dir / "col.h5", pads, transpose=True)
        a = m.read_xypt(path=self.dir / "row.h5")
        b = m.read_xypt(path=self.dir / "col.h5")
        ta = m.segment_tracks(a["Xpad"], commanded_speed_mm_s=960.0)
        tb = m.segment_tracks(b["Xpad"], commanded_speed_mm_s=960.0)
        self.assertEqual(ta, tb)
        self.assertEqual(len(ta), 4)
        self.assertEqual([t["direction"] for t in ta], ["+X", "-X", "+X", "-X"])
        self.assertEqual(m.camera_trigger_index(a["Xpad"]), 10)
        self.assertEqual(ta[0]["startSample"], 10)
        self.assertAlmostEqual(ta[0]["vImplied_mm_s"], 2.5 / (260 * 1e-5), places=2)
        self.assertAlmostEqual(ta[0]["gapToNext_s"], 525e-5, places=9)
        self.assertIsNone(ta[-1]["gapToNext_s"])
        s = m.summarize_pad_tracks(ta, 960.0)
        self.assertEqual(s["status"], "derived-commanded")
        self.assertAlmostEqual(s["impliedSpeedResidualRel"], 2.5 / (260e-5) / 960 - 1, places=6)
        self.assertTrue(s["impliedSpeedWithinReadmeUncertainty"])
        self.assertAlmostEqual(s["medianHatch_mm"], 0.1087, places=4)
        self.assertEqual(a["Xpad"]["galvoCalApplied"], "false")

    def test_mismatched_channel_lengths_raise(self):
        pads = {"Xpad": synthetic_xypt()}
        pads["Xpad"]["T"] = pads["Xpad"]["T"][:-1]
        write_xypt_h5(self.dir / "bad.h5", pads)
        with self.assertRaisesRegex(ValueError, "different lengths"):
            m.read_xypt(path=self.dir / "bad.h5")


@unittest.skipUnless(HAVE_H5PY, NO_H5PY)
class SyntheticPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        sig = synthetic_line()
        lines = {"Line_0_%d" % r: (sig, 285.0, 960.0, 67.0) for r in (1, 2, 3)}
        write_thermo_h5(self.dir / m.THERMO_NAME, lines)
        write_xypt_h5(self.dir / m.XYPT_NAME, {"Xpad": synthetic_xypt(), "Ypad": synthetic_xypt(n_tracks=2)})

    def tearDown(self):
        self.tmp.cleanup()

    def test_build_without_pins_gives_labelled_record(self):
        rec = m.build_metrics(self.dir, verify=False)
        self.assertEqual(rec["inputVerification"], "not-run")
        ev = rec["evidence"]
        self.assertIs(ev["experimentalValidation"], False)
        self.assertIs(ev["opticalOperatorMatched"], False)
        self.assertIs(ev["modelAcceptance"], False)
        self.assertIsNone(ev["temperatureConversion"])
        self.assertEqual(len(rec["lines"]), 3)
        case = rec["cases"][0]
        self.assertEqual(case["repeats"], ["Line_0_1", "Line_0_2", "Line_0_3"])
        self.assertEqual(case["metrics"]["tat4095_frames"]["mean"], 10)
        self.assertEqual(case["metrics"]["tat4095_frames"]["sd"], 0)
        self.assertEqual(case["decayRightCensoredPixels"], {"4095to2000": 0, "4095to1000": 0, "4095to500": 0,
                                                            "4095to100": 0})
        self.assertEqual(rec["source"]["nerdmVersion"], "1.3.1")
        checks = {c["id"]: c["result"] for c in rec["checks"]}
        self.assertEqual(checks["A3-attributes"], "pass")
        self.assertEqual(checks["A6-repeats"], "pass")
        self.assertEqual(checks["A7-xypt"], "flag")  # synthetic pads do not have 47/24 tracks
        self.assertEqual(checks["A8-pad-alignment"], "skipped")
        assert_no_temperature(self, rec)
        for item in rec["unavailable"]:
            self.assertEqual(item["status"], "unavailable")
            self.assertTrue(item["reason"])
        self.assertEqual(m.serialize(rec), m.serialize(m.build_metrics(self.dir, verify=False)))

    def test_attribute_disagreement_raises_specific_message(self):
        write_thermo_h5(self.dir / "bad.h5", {"Line_0_1": (synthetic_line(n_frames=30), 285.0, 960.0, 67.0)},
                        frame_rate=25000.0)
        with h5py.File(self.dir / "bad.h5", "r") as f:
            with self.assertRaisesRegex(ValueError, "frame_rate attribute 25000.0 != 30000.0"):
                m.check_thermal_attrs(f)
        write_thermo_h5(self.dir / "bad2.h5", {"Line_0_1": (synthetic_line(n_frames=30), 285.0, 960.0, 67.0)},
                        threshold=50.0)
        with h5py.File(self.dir / "bad2.h5", "r") as f:
            with self.assertRaisesRegex(ValueError, "threshold_level 50.0 on Line_0_1 != 100"):
                m.check_thermal_attrs(f)


class CommittedDerivedTests(unittest.TestCase):
    """The committed derived table is the fixture: its bytes are pinned by the committed manifest."""

    @classmethod
    def setUpClass(cls):
        cls.raw = DERIVED.read_bytes()
        cls.rec = json.loads(cls.raw.decode("utf-8"))
        cls.manifest = json.loads(DERIVED_MANIFEST.read_text(encoding="utf-8"))

    def test_hash_and_size_pinned_by_manifest(self):
        self.assertEqual(self.manifest["derived"]["bytes"], len(self.raw))
        self.assertEqual(self.manifest["derived"]["sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertLess(len(self.raw), 300 * 1024)
        self.assertNotIn(b"\r\n", self.raw)
        pin = self.manifest["sourceRecord"]
        data = m.NERDM_PATH.read_bytes()
        self.assertEqual((pin["bytes"], pin["sha256"]), (len(data), hashlib.sha256(data).hexdigest()))

    def test_inputs_equal_pins(self):
        got = {i["name"]: (i["bytes"], i["sha256"]) for i in self.manifest["inputs"]}
        self.assertEqual(got, {k: (v["bytes"], v["sha256"]) for k, v in m.PINNED.items()})
        self.assertEqual({k: (v["bytes"], v["sha256"]) for k, v in self.rec["inputs"].items()}, got)
        self.assertEqual(self.rec["inputVerification"],
                         {m.THERMO_NAME: "verified", m.XYPT_NAME: "verified", "README.txt": "verified"})

    def test_labels_statuses_and_no_temperature(self):
        ev = self.rec["evidence"]
        self.assertIs(ev["experimentalValidation"], False)
        self.assertIs(ev["opticalOperatorMatched"], False)
        self.assertIs(ev["modelAcceptance"], False)
        self.assertIsNone(ev["temperatureConversion"])
        self.assertEqual(self.manifest["evidence"], ev)
        assert_no_temperature(self, self.rec)
        for path, key, value in walk_keys(self.rec):
            if key == "status":
                self.assertIn(value, m.STATUSES, path)
            if isinstance(value, dict) and value.get("status") == "unavailable":
                self.assertTrue(value.get("reason"), path)
        for item in self.rec["unavailable"]:
            self.assertTrue(item["reason"])
        self.assertNotIn('"compared"', self.raw.decode("utf-8"))

    def test_recorded_facts(self):
        self.assertEqual(len(self.rec["groups"]), 27)
        self.assertEqual(len(self.rec["lines"]), 21)
        self.assertEqual(len(self.rec["cases"]), 7)
        self.assertEqual(sum(1 for g in self.rec["groups"] if not g["challenge"]), 2)
        for line in self.rec["lines"]:
            tr = line["metrics"]["track"]
            self.assertEqual(tr["status"], "measured-signal", line["name"])
            expect = {800.0: 1.25, 960.0: 1.50, 1200.0: 1.88}[line["scanSpeed_mm_s"]]
            self.assertAlmostEqual(tr["pxPerFrame"], expect, delta=0.02)
            self.assertAlmostEqual(tr["pixelPitch_um"]["value"], 21.3, delta=0.3)
            self.assertAlmostEqual(tr["trackExtent_mm"]["value"], 10.0, delta=0.5)
            self.assertEqual(tr["laserOnFrame"], 1)
        pads = self.rec["scanStrategy"]
        self.assertEqual(pads["Xpad"]["summary"]["nTracks"], 47)
        self.assertEqual(pads["Ypad"]["summary"]["nTracks"], 24)
        self.assertEqual((pads["Xpad"]["cameraTriggerIndex"], pads["Ypad"]["cameraTriggerIndex"]), (497, 182))
        self.assertEqual((pads["Xpad"]["galvoCalApplied"], pads["Xpad"]["laserCalApplied"]), ("false", "false"))
        self.assertEqual(len(pads["Xpad"]["tracks"]) + len(pads["Ypad"]["tracks"]), 71)
        checks = {c["id"]: c["result"] for c in self.rec["checks"]}
        self.assertEqual(checks, {"A3-attributes": "pass", "lines-located": "pass",
                                  "A4-speed-pitch-consistency": "pass", "A5-track-length": "pass",
                                  "A6-repeats": "pass", "A7-xypt": "pass", "A8-pad-alignment": "skipped",
                                  "A9-no-temperature": "pass"})

    def test_citation_matches_nerdm_record(self):
        nerdm = json.loads(m.NERDM_PATH.read_text(encoding="utf-8"))
        src = self.rec["source"]
        self.assertEqual(src, m.source_from_nerdm())
        self.assertEqual([a["familyName"] for a in src["authors"]], [a["familyName"] for a in nerdm["authors"]])
        self.assertEqual([a["familyName"] for a in src["authors"]],
                         ["Deisenroth", "Mekhontsev", "Lane", "Weaver", "Yeung"])
        self.assertEqual(src["title"], nerdm["title"])
        self.assertEqual(src["nerdmVersion"], nerdm["version"])
        self.assertEqual("doi:" + src["doi"], nerdm["doi"])
        self.assertEqual((src["versionIssued"], src["firstReleased"]), ("2026-01-06", "2022-07-15"))
        cite = src["citation"]
        self.assertIn(nerdm["title"], cite)
        self.assertNotIn("et al.", cite)
        positions = [cite.index(a["familyName"] + ", ") for a in nerdm["authors"]]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("(2026)", cite)
        self.assertIn("Version 1.3.1; first released 2022-07-15", cite)
        self.assertIn("National Institute of Standards and Technology", cite)
        self.assertTrue(cite.endswith("https://doi.org/10.18434/mds2-2716"))

    def test_headline_does_not_claim_a_comparison(self):
        self.assertTrue(self.rec["headline"].startswith("Signal-unit metrics only, not validation"))
        self.assertIn("no model comparison is run in this record", self.rec["headline"])

    def test_trigger_is_single_sample_at_first_laser_on(self):
        for pad, expect in (("Xpad", 497), ("Ypad", 182)):
            info = self.rec["scanStrategy"][pad]
            self.assertEqual(info["cameraTriggerIndex"], expect)
            self.assertEqual(info["firstLaserOnIndex"], expect)
            self.assertEqual(info["cameraTriggerHighSamples"], 1)
            self.assertIs(info["cameraTriggerAtFirstLaserOn"], True)
        self.assertIn("not one sample before laser-on", self.rec["conventions"]["cameraTrigger"])

    def test_right_censoring_reported_per_metric(self):
        for line in self.rec["lines"]:
            for key, entry in line["metrics"]["decayFromSaturation"].items():
                self.assertIn("nRightCensored", entry, (line["name"], key))
                self.assertIs(entry["rightCensored"], entry["nRightCensored"] > 0)
        for case in self.rec["cases"]:
            self.assertEqual(set(case["decayRightCensoredPixels"]), {"4095to%d" % t for t in m.DECAY_TARGETS_DL})

    def test_a9_detail_is_computed(self):
        a9 = next(c for c in self.rec["checks"] if c["id"] == "A9-no-temperature")
        self.assertIn("0 offending key(s)", a9["detail"])
        self.assertEqual(m.temperature_key_paths(self.rec), [])

    def test_case_stats_use_all_three_repeats(self):
        for case in self.rec["cases"]:
            self.assertEqual(len(case["repeats"]), 3)
            self.assertEqual(case["nRepeatsWithMetrics"], 3)
            for name, stat in case["metrics"].items():
                self.assertEqual(stat["n"], 3, (case["caseId"], name))
                self.assertFalse(math.isnan(stat["mean"]))


RAW_REASON = m.raw_absent_reason()


@unittest.skipUnless(HAVE_H5PY, NO_H5PY)
@unittest.skipIf(RAW_REASON is not None, "real-data check skipped: %s" % RAW_REASON)
class RealDataTests(unittest.TestCase):
    """Reproduces committed rows from the pinned NIST file (about 5 s)."""

    def test_rebuild_matches_committed_rows(self):
        names = ["Line_0_1", "Line_2_1_1", "Line_2_2_1"]
        rec = m.build_metrics(lines_only=names)
        committed = json.loads(DERIVED.read_text(encoding="utf-8"))
        self.assertEqual(rec["inputVerification"],
                         {m.THERMO_NAME: "verified", m.XYPT_NAME: "verified", "README.txt": "verified"})
        by_name = {r["name"]: r for r in committed["lines"]}
        for row in rec["lines"]:
            self.assertEqual(json.dumps(row, sort_keys=True), json.dumps(by_name[row["name"]], sort_keys=True))
        self.assertEqual(rec["scanStrategy"], committed["scanStrategy"])
        self.assertEqual(rec["groups"], committed["groups"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
