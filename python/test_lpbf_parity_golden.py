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
        if outcome["skipped"] is not None:
            self.skipTest(f"NOT VERIFIED: {outcome['skipped']}")
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
        # integrated_source never reaches its refinement branch in a CPU transient; G13 covers
        # that branch directly, see the next test.)
        import four_alloy_materials
        in718 = four_alloy_materials._THERMAL["in718"]
        with patch.dict(in718, {"absorptivity_IR": in718["absorptivity_IR"] + 1e-15}):
            outcome = parity.check_case(parity.CASE_BY_ID["g3_powder_island"], self.root)
        problems = "\n".join(outcome["problems"])
        self.assertIn("changed result.canonicalSha256", problems)
        self.assertIn("changed result.key.metrics", problems)

    def test_changed_source_quadrature_tolerance_fails_the_refinement_case(self):
        # G13 drives integrated_source into its N-vs-2N branch directly; a tighter
        # convergence tolerance adds a refinement level and must change the pinned field.
        import lpbf_core_physics
        case = parity.CASE_BY_ID["g13_source_quadrature_refinement"]
        self.assertEqual(parity.check_case(case, self.root)["problems"], [])
        with patch.object(lpbf_core_physics, "SOURCE_QUADRATURE_RELATIVE_TOLERANCE", 1e-12):
            outcome = parity.check_case(case, self.root)
        problems = "\n".join(outcome["problems"])
        self.assertIn("changed integratedSource.dt2.500e-04.orders", problems)
        self.assertIn("changed integratedSource.dt2.500e-04:", problems)

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

    def test_hash_only_bump_changes_no_result_or_artifact(self):
        # Simulated bump: a different implementation_fingerprint() (and pin) with identical
        # numerics must leave every observation of the solver cases bit-equal, so the
        # fingerprint is carried only by provenance.implementationHash.
        import lpbf_simulation
        fake = "f" * 64
        with patch.object(lpbf_simulation, "implementation_fingerprint", return_value=fake), \
                patch.object(parity, "pinned_fingerprint", return_value=fake):
            for case_id in ("g1_v1_60w_in718", "g3_powder_stripe_multilayer", "g4_layered_plate",
                            "g8_observers"):
                with self.subTest(case=case_id):
                    outcome = parity.check_case(parity.CASE_BY_ID[case_id], self.root)
                    self.assertEqual(outcome["problems"], [])
                    self.assertEqual(outcome["implementationHashes"], [fake])

    def test_expect_unpinned_turns_only_the_pin_mismatch_into_a_warning(self):
        import lpbf_simulation
        moved = "e" * 64
        case = parity.CASE_BY_ID["g3_powder_island"]
        with patch.object(lpbf_simulation, "implementation_fingerprint", return_value=moved):
            strict = parity.check_case(case, self.root)
            bump = parity.check_case(case, self.root, expect_unpinned=True)
        self.assertTrue(any("!= pinned" in p for p in strict["problems"]), strict["problems"])
        self.assertEqual(bump["problems"], [])
        self.assertTrue(any("!= pinned" in w for w in bump["warnings"]), bump["warnings"])
        # A stale result hash and observation diffs stay failures in bump-branch mode.
        problems, _ = parity.check_implementation(case, ["a" * 64], parity.pinned_fingerprint(), moved,
                                                  expect_unpinned=True)
        self.assertTrue(any("provenance.implementationHash" in p for p in problems), problems)
        directory = self._mutated_golden_dir(
            "g12_analytical_modules", lambda observations: observations.update({"fabbro.depth": "0" * 64}))
        with patch.object(parity, "GOLDEN_DIR", directory), \
                patch.object(lpbf_simulation, "implementation_fingerprint", return_value=moved):
            outcome = parity.check_case(parity.CASE_BY_ID["g12_analytical_modules"], self.root,
                                        expect_unpinned=True)
        self.assertEqual(len(outcome["problems"]), 1)
        self.assertIn("changed fabbro.depth", outcome["problems"][0])

    def test_goldens_record_the_full_reference_environment(self):
        for case in parity.CASES:
            with self.subTest(case=case.id):
                recorded = json.loads(parity.golden_path(case).read_text(encoding="utf-8"))["recordedEnvironment"]
                self.assertEqual(set(recorded), {"python", "numpy", "platform", "runtime", "cpu", "numpyRuntime"})
                self.assertIn("simdFound", recorded["numpyRuntime"])
                self.assertIn("blas", recorded["numpyRuntime"])

    def test_other_environment_is_skipped_not_passed_unless_overridden(self):
        case = parity.CASE_BY_ID["g12_analytical_modules"]
        other = dict(parity.environment(), cpu="Some Other CPU")
        with patch.object(parity, "environment", return_value=other):
            skipped = parity.check_case(case, self.root)
            self.assertIn("environment differs from the recording in cpu", skipped["skipped"])
            self.assertEqual(skipped["observations"], {})
            self.assertEqual(parity.main(["--check", "--case", case.id, "--work-root", str(self.root)]), 3)
            compared = parity.check_case(case, self.root, allow_environment_mismatch=True)
        self.assertIsNone(compared["skipped"])
        self.assertEqual(compared["problems"], [])
        self.assertTrue(any("compared despite" in w for w in compared["warnings"]))

    def test_g11_is_skipped_not_passed_when_warp_is_importable(self):
        import importlib.util
        original = importlib.util.find_spec

        def find_spec(name, *args, **kwargs):
            return object() if name == "warp" else original(name, *args, **kwargs)

        with patch.object(importlib.util, "find_spec", find_spec):
            outcome = parity.check_case(parity.CASE_BY_ID["g11_build_job_meltpool"], self.root)
            self.assertIn("warp is importable", outcome["skipped"])
            self.assertEqual(parity.main(["--check", "--case", "g11_build_job_meltpool",
                                          "--work-root", str(self.root)]), 3)

    def test_cfd_case_module_falls_back_only_when_lpbf_cfd_cases_itself_is_missing(self):
        import sys
        with patch.dict(sys.modules, {"lpbf_cfd_cases": None}):
            self.assertEqual(parity._cfd_case_module().__name__, "lpbf_cfd")
        directory = Path(tempfile.mkdtemp(dir=self.root))
        (directory / "lpbf_cfd_cases.py").write_text("import lpbf_missing_dependency_for_test\n",
                                                     encoding="utf-8")
        sys.modules.pop("lpbf_cfd_cases", None)
        with patch.object(sys, "path", [str(directory), *sys.path]):
            with self.assertRaises(ModuleNotFoundError) as raised:
                parity._cfd_case_module()
        sys.modules.pop("lpbf_cfd_cases", None)
        self.assertEqual(raised.exception.name, "lpbf_missing_dependency_for_test")

    def test_bump_record_refuses_same_hash_and_foreign_goldens(self):
        spec = importlib.util.spec_from_file_location("lpbf_bump_record", HERE / "tools" / "lpbf_bump_record.py")
        bump = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bump)
        skeleton = bump.build_record(None, False, False)
        self.assertEqual(skeleton["fromHash"], PRE_BUMP_FINGERPRINT)
        self.assertEqual(skeleton["from"]["manifestCount"], 37)
        self.assertIsNone(skeleton["toHash"])
        with self.assertRaisesRegex(SystemExit, "toHash equals fromHash"):
            bump.build_record("HEAD", False, False)
        dry = bump.build_record("HEAD", False, False, allow_same_hash=True)
        self.assertTrue(dry["dryRunSameHash"])
        directory = self._mutated_golden_dir("npz_determinism", lambda observations: None)
        target = directory / "npz_determinism.json"
        golden = json.loads(target.read_text(encoding="utf-8"))
        golden["recordedImplementationHash"] = "b" * 64
        target.write_text(json.dumps(golden), encoding="utf-8")
        with patch.object(bump, "GOLDEN_DIR", directory):
            with self.assertRaisesRegex(SystemExit, "goldens not recorded at fromHash"):
                bump.build_record(None, False, False)

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
