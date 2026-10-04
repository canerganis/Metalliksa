"""Fast unit tests of tools/lpbf_validity_envelope.py with a stubbed run() (no solver run)."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location("lpbf_validity_envelope", HERE / "tools" / "lpbf_validity_envelope.py")
envelope = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(envelope)

DEFAULTS = dict(mode="screening", material="Inconel 718", power_W=200., speed_mm_s=800., mesh_um=20., backend="auto")
BOILING = ("Thermal model validity exceeded at or above the material boiling limit "
           "(specific enthalpy 1 J/kg); evaporation/free-surface CFD required")


def fake_result(power):
    return dict(
        metrics=dict(width_um=80., depth_um=power / 4, length_um=240., peakTemperature_K=2000. + power,
                     thermalGradient_K_m=1e7, coolingRate_K_s=1e6),
        energyBalance=dict(relativeError=1e-16),
        numericalDiagnostics=dict(peakMeltCellCount=3),
        provenance=dict(implementationHash="h", inputHash="i"),
        label="Unvalidated transient thermal", validationStatus="unvalidated")


def stub_run(boil_from):
    def _run(raw):
        if raw["power_W"] >= boil_from:
            raise ValueError(BOILING)
        return fake_result(raw["power_W"])
    return _run


class ClassificationTest(unittest.TestCase):
    def test_boiling_message_is_boiling_stop(self):
        self.assertEqual(envelope.classify_error(BOILING), "boiling-stop")

    def test_other_message_is_other_error(self):
        self.assertEqual(envelope.classify_error("Invalid power_W"), "other-error")

    def test_run_case_statuses(self):
        done = envelope.run_case(dict(power_W=40.), stub_run(100.))
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["peakTemperature_K"], 2040.)
        self.assertEqual(done["implementationHash"], "h")
        stop = envelope.run_case(dict(power_W=120.), stub_run(100.))
        self.assertEqual(stop["status"], "boiling-stop")
        self.assertIn("boiling", stop["message"])

        def other(raw):
            raise ValueError("bad input")
        self.assertEqual(envelope.run_case({}, other)["status"], "other-error")

        def crash(raw):
            raise RuntimeError("boom")
        crashed = envelope.run_case({}, crash)
        self.assertEqual(crashed["status"], "other-error")
        self.assertIn("RuntimeError", crashed["message"])


class SweepTest(unittest.TestCase):
    def test_raw_input_is_defaults_with_overrides(self):
        raw = envelope.build_raw(DEFAULTS, "Ti-6Al-4V", 80., 10.)
        self.assertEqual((raw["mode"], raw["backend"], raw["material"], raw["power_W"], raw["mesh_um"]),
                         ("standard", "reference", "Ti-6Al-4V", 80., 10.))
        self.assertEqual(raw["speed_mm_s"], 800.)

    def test_default_plan_matches_specification(self):
        plan = envelope.default_plan()
        self.assertEqual([(a, m) for a, m, _ in plan],
                         [(a, 20.) for a in envelope.ALLOYS] + [("Inconel 718", 10.)])
        self.assertEqual(plan[-1][2], (40., 60., 80., 100.))
        self.assertEqual(envelope.build_plan(quick=True), [("Inconel 718", 20., envelope.POWERS_20)])

    def test_schema_writer_and_monotone_stop(self):
        calls = []

        def runner(raw):
            calls.append(raw["power_W"])
            return envelope.run_case(raw, stub_run(100.))

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "env.json"
            document = envelope.new_document(dict(python="x"), 900.)
            envelope.sweep([("Inconel 718", 20., envelope.POWERS_20)], DEFAULTS, document, out, runner)
            self.assertEqual(calls, [40., 60., 80., 100., 120.])  # two consecutive stops, then skipped
            written = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(written["schema"], "lpbf-validity-envelope-1")
            self.assertIn("not a process window, not experimental validation", written["scope"])
            statuses = [c["status"] for c in written["cases"]]
            self.assertEqual(statuses[:3], ["completed"] * 3)
            self.assertEqual(statuses[3:5], ["boiling-stop"] * 2)
            self.assertTrue(all(s.startswith("not-run") for s in statuses[5:]))
            self.assertEqual(written["cases"][0]["input"]["mode"], "standard")
            row = written["summary"][0]
            self.assertEqual((row["highestCompletedPower_W"], row["firstBoilingStopPower_W"]), (80., 100.))
            self.assertEqual(row["depth_um"], 20.)

            # Resume: nothing is recomputed.
            calls.clear()
            envelope.sweep([("Inconel 718", 20., envelope.POWERS_20)], DEFAULTS, written, out, runner)
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
