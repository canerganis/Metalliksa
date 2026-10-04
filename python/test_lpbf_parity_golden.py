"""LPBF 5c parity goldens (design stage P2/P3): bit equality before and after the bump.

Each case in tools/lpbf_parity_check.py is checked against python/golden/lpbf_parity/.
The goldens were recorded once, twice each, at the pre-bump implementation
7482697c...; they must never be re-recorded during the bump. G2 (real bare-plate
fixture, ~106-140 s) runs only with LPBF_PARITY_SLOW=1; the fast cases take about
1.5 minutes. The mutation tests prove that a changed golden byte, a changed
numerical tolerance, a changed material value and an unpinned implementation
each make the check fail.
"""

import copy
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location("lpbf_parity_check", HERE / "tools" / "lpbf_parity_check.py")
parity = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(parity)

PRE_BUMP_FINGERPRINT = "7482697c458b6c1aa2a77829f2fbce0c4ce4ac9466e9a3583e97b9a799b5e483"
SLOW = os.environ.get("LPBF_PARITY_SLOW") == "1"


class ParityGoldenCaseTests(unittest.TestCase):
    """One test per golden case; all observations must be bit-equal."""


def _case_test(case):
    def test(self):
        if case.slow and not SLOW:
            self.skipTest("slow case: set LPBF_PARITY_SLOW=1 (G2 bare plate, ~106-140 s)")
        outcome = parity.check_case(case, parity.DEFAULT_WORK_ROOT)
        self.assertEqual(outcome["problems"], [], f"{case.id} differs from its golden")
    test.__doc__ = f"{case.group}: {case.description}"
    return test


for _case in parity.CASES:
    setattr(ParityGoldenCaseTests, f"test_{_case.id}", _case_test(_case))


class ParityHarnessTests(unittest.TestCase):
    def setUp(self):
        self.root = HERE / ".tmp-lpbf-parity-mutation"
        self.root.mkdir(exist_ok=True)
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_every_case_has_a_twice_recorded_pre_bump_golden(self):
        for case in parity.CASES:
            with self.subTest(case=case.id):
                golden = json.loads(parity.golden_path(case).read_text(encoding="utf-8"))
                self.assertEqual(golden["schema"], parity.GOLDEN_SCHEMA)
                self.assertEqual(golden["case"], case.id)
                self.assertEqual(golden["recordedImplementationHash"], PRE_BUMP_FINGERPRINT)
                self.assertEqual(golden["recordedVersion"], "enthalpy-fv-6")
                self.assertTrue(golden["recordedTwice"])
                self.assertGreater(len(golden["observations"]), 0)
        self.assertEqual(sorted(p.stem for p in parity.GOLDEN_DIR.glob("*.json")),
                         sorted(case.id for case in parity.CASES))

    def test_v1_and_bare_plate_goldens_carry_the_bound_identities(self):
        v1 = json.loads(parity.golden_path(parity.CASE_BY_ID["g1_v1_60w_in718"]).read_text(encoding="utf-8"))
        observations = v1["observations"]
        self.assertEqual(observations["result.coreContract.inputSha256"], parity.V1_INPUT_SHA256)
        self.assertTrue(observations["result.coreContract.materialSha256"].startswith("6a8d7bde"))
        self.assertTrue(observations["result.material.materialRevisionSha256"].startswith("5c9179e9"))
        self.assertEqual(observations["result.validationStatus"], "unvalidated")
        self.assertIs(observations["result.productionReady"], False)
        self.assertIs(observations["v1Archive.strippedResultEqual"], True)
        self.assertEqual(observations["result.canonicalSha256"], parity.V1_ARCHIVED_RESULT_STRIPPED_SHA256)
        self.assertEqual(observations["result.implementationHashOccurrencesAfterStrip"], 0)
        self.assertEqual(observations["result.artifactsImplementationHashOccurrences"], 0)
        bare = json.loads(parity.golden_path(
            parity.CASE_BY_ID["g2_bare_plate_100w_corridor"]).read_text(encoding="utf-8"))["observations"]
        self.assertIs(bare["fixture.strippedResultEqual"], True)
        self.assertIs(bare["fixture.npzBytesEqual"], True)
        self.assertEqual(bare["fixture.artifactsMismatched"], [])
        self.assertEqual(bare["fixture.fieldArtifactsCompared"], 67)
        self.assertEqual(bare["fixture.artifactsCompared"], 68)

    def _mutated_golden_dir(self, case_id, mutate):
        directory = Path(tempfile.mkdtemp(dir=self.root))
        for path in parity.GOLDEN_DIR.glob("*.json"):
            shutil.copy2(path, directory / path.name)
        target = directory / f"{case_id}.json"
        golden = json.loads(target.read_text(encoding="utf-8"))
        mutate(golden["observations"])
        target.write_text(json.dumps(golden), encoding="utf-8")
        return directory

    def test_one_changed_golden_digest_character_fails_the_check(self):
        def flip(observations):
            key = "eagarTsai.temperature"
            value = observations[key]
            observations[key] = ("0" if value[0] != "0" else "1") + value[1:]
        directory = self._mutated_golden_dir("g12_analytical_modules", flip)
        with patch.object(parity, "GOLDEN_DIR", directory):
            outcome = parity.check_case(parity.CASE_BY_ID["g12_analytical_modules"], self.root)
        self.assertEqual(len(outcome["problems"]), 1)
        self.assertIn("changed eagarTsai.temperature", outcome["problems"][0])

    def test_removed_golden_observation_fails_the_check(self):
        directory = self._mutated_golden_dir("npz_determinism",
                                             lambda observations: observations.pop("npz.resaveTwiceEqual"))
        with patch.object(parity, "GOLDEN_DIR", directory):
            outcome = parity.check_case(parity.CASE_BY_ID["npz_determinism"], self.root)
        self.assertEqual(outcome["problems"], ["unexpected new observation npz.resaveTwiceEqual"])

    def test_a_few_ulp_material_change_fails_a_solver_case(self):
        # Zero tolerance: absorptivity 0.38 -> 0.38 + 1e-15 (about 18 ulp) must move the
        # transient result. (SOURCE_QUADRATURE_RELATIVE_TOLERANCE cannot serve as the
        # mutation here: the CPU scheduler keeps beam travel per step <= 0.25 radius, so
        # integrated_source never reaches its refinement branch in any CPU case.)
        import four_alloy_materials
        in718 = four_alloy_materials._THERMAL["in718"]
        with patch.dict(in718, {"absorptivity_IR": in718["absorptivity_IR"] + 1e-15}):
            outcome = parity.check_case(parity.CASE_BY_ID["g3_powder_island"], self.root)
        problems = "\n".join(outcome["problems"])
        self.assertIn("changed result.canonicalSha256", problems)
        self.assertIn("changed result.key.metrics", problems)

    def test_changed_numerical_tolerance_in_the_scheduler_fails_a_solver_case(self):
        # The source-limited step accepts dt when allowed >= dt*(1-1e-12); a different
        # sensible-increment cap (25 K -> 24.999999 K) is a tolerance change that must show.
        import lpbf_heat_source
        import lpbf_simulation
        original = lpbf_heat_source.source_limited_step

        def tighter(*args, **kwargs):
            args = list(args)
            args[11] = args[11] * (24.999999 / 25.0)  # capacity scales the 25 K increment cap
            return original(*args, **kwargs)

        with patch.object(lpbf_simulation, "source_limited_step", tighter):
            outcome = parity.check_case(parity.CASE_BY_ID["g3_powder_island"], self.root)
        self.assertTrue(any(p.startswith("changed result.canonicalSha256") for p in outcome["problems"]),
                        outcome["problems"])

    def test_changed_material_value_fails_the_material_golden(self):
        import four_alloy_materials
        in718 = four_alloy_materials._THERMAL["in718"]
        with patch.dict(in718, {"liquidus_C": in718["liquidus_C"] + 1e-9}):
            outcome = parity.check_case(parity.CASE_BY_ID["g9_material_snapshots"], self.root)
        problems = "\n".join(outcome["problems"])
        self.assertIn("changed registry.material.Inconel 718", problems)
        self.assertIn("changed fam.canonical_material_source.in718.sha256", problems)

    def test_unpinned_implementation_fails_the_check(self):
        with patch.object(parity, "pinned_fingerprint", return_value="0" * 64):
            outcome = parity.check_case(parity.CASE_BY_ID["g12_analytical_modules"], self.root)
        self.assertTrue(any("!= pinned" in p for p in outcome["problems"]), outcome["problems"])

    def test_record_refuses_an_unpinned_implementation(self):
        with patch.object(parity, "pinned_fingerprint", return_value="0" * 64):
            self.assertEqual(parity.main(["--record", "--case", "npz_determinism",
                                          "--work-root", str(self.root)]), 2)

    def test_strip_result_removes_only_volatile_and_worker_fields(self):
        result = {"runtime_s": 1.0, "runKind": "transient-thermal", "metrics": {"peak": 1.5},
                  "provenance": {"createdAt": "t", "runtime_s": 2.0, "executionRuntime": {"python": "x"},
                                 "implementationHash": "h", "inputHash": "i"},
                  "artifacts": [{"path": "input.json"}, {"path": "capabilities.json"},
                                {"path": "field-series.json", "sha256": "s"}]}
        original = copy.deepcopy(result)
        stripped, implementation = parity.strip_result(result)
        self.assertEqual(result, original)
        self.assertEqual(implementation, "h")
        self.assertEqual(stripped, {"metrics": {"peak": 1.5}, "provenance": {"inputHash": "i"},
                                    "artifacts": [{"path": "field-series.json", "sha256": "s"}]})

    def test_typed_digest_pins_order_and_types_that_canonical_json_ignores(self):
        pairs = (({"a": 1, "b": 2}, {"b": 2, "a": 1}), ({"x": 1}, {"x": 1.0}),
                 ({"x": (1, 2)}, {"x": [1, 2]}), ({"x": 0.0}, {"x": -0.0}))
        for left, right in pairs:
            with self.subTest(left=left, right=right):
                self.assertNotEqual(parity.typed_sha256(left), parity.typed_sha256(right))
        self.assertEqual(parity.canonical_json_sha256({"a": 1, "b": 2}),
                         parity.canonical_json_sha256({"b": 2, "a": 1}))


if __name__ == "__main__":
    unittest.main()
