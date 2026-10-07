"""Pre-registration guards of LPBF melt-pool calibration v2 (config hash pins, data roles, v1 untouched).

Self-contained: the expected hashes and roles are written here; no fixture outside the repo is needed.
SCREENING ONLY, NOT VALIDATION."""

import json
import sys
import unittest
from pathlib import Path

PYTHON_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PYTHON_DIR))

import lpbf_calibration_config as C1  # noqa: E402
import lpbf_calibration_config_v2 as V  # noqa: E402

REPO_ROOT = PYTHON_DIR.parent
V1_CONFIG_SHA256 = "6926386ddf9ad2a0d9fc787b4dbca7324b20b466e7a806be38b949fbafa1271b"
V2_CONFIG_SHA256 = "8a4b9e68441ba561d3bbe8fcfe973c2b8268b84ae52316ee22146bc3b87d99e9"
DIGITIZED_OR_SPOT_ASSUMED = {"ghosh-in625-2018", "trapp-316l-2017"}


class V2PreRegistrationTests(unittest.TestCase):
    def test_hash_pins(self):
        self.assertEqual(C1.config_sha256(C1.CALIBRATION_CONFIG), V1_CONFIG_SHA256, "v1 config must never change")
        self.assertEqual(V.config_v2_sha256(), V2_CONFIG_SHA256,
                         "the v2 config is pre-registered: a change needs a NEW version (v3), not an edit")
        self.assertNotEqual(V1_CONFIG_SHA256, V2_CONFIG_SHA256)
        self.assertEqual(V.CALIBRATION_CONFIG_V2["supersedes"]["configSha256"], V1_CONFIG_SHA256)

    def test_every_numeric_block_is_carried_verbatim_from_v1(self):
        for key in V.V1_KEYS_CARRIED_VERBATIM:
            self.assertEqual(V.CALIBRATION_CONFIG_V2[key], C1.CALIBRATION_CONFIG[key], key)
        for key in ("gate", "interval", "bootstrap", "rungs", "rungSelection", "prior", "bounds", "fitGrid",
                    "kernelGrid", "absorptanceBands", "beamSensitivityUm", "sourceWeight", "materialDefaults"):
            self.assertIn(key, V.V1_KEYS_CARRIED_VERBATIM)
        r1, r2 = C1.CALIBRATION_CONFIG["dataRoles"], V.CALIBRATION_CONFIG_V2["dataRoles"]
        for key in r1:
            self.assertEqual(r2[key], r1[key], key)

    def test_roles_no_digitized_or_spot_assumed_source_trains(self):
        roles = V.CALIBRATION_CONFIG_V2["dataRoles"]
        self.assertEqual(roles["trainable"], list(C1.TRAINABLE_SOURCES))
        self.assertEqual(set(roles["testOnly"]), DIGITIZED_OR_SPOT_ASSUMED)
        self.assertFalse(set(roles["testOnly"]) & set(roles["trainable"]))
        self.assertFalse(set(roles["testOnly"]) & set(roles["catalogSentinels"]))
        self.assertTrue(roles["digitizedNeverTrains"])
        for sid, role in roles["testOnlyRoles"].items():
            self.assertIn("test-only", role["role"])
            self.assertTrue(role["digitized"] or role["spotAssumed"], sid)
        self.assertTrue(roles["testOnlyRoles"]["trapp-316l-2017"]["digitized"])
        self.assertTrue(roles["testOnlyRoles"]["ghosh-in625-2018"]["spotAssumed"])
        self.assertEqual(roles["testOnlyRoles"]["ghosh-in625-2018"]["nuisance"]["beamDiameter_um"], [140.0, 100.0])

    def test_test_only_sources_never_grant_second_source_credit(self):
        for sid in V.TEST_ONLY_SOURCES:
            self.assertFalse(V.second_source_credit(sid, 1000), sid)
        cfg = json.loads(json.dumps(V.CALIBRATION_CONFIG_V2))
        cfg["dataRoles"]["testOnlyRoles"]["ghosh-in625-2018"].update(spotAssumed=False)
        self.assertFalse(V.second_source_credit("ghosh-in625-2018", 7, cfg))  # < minRowsForCoverage
        self.assertTrue(V.second_source_credit("ghosh-in625-2018", 10, cfg))

    def test_literature_tables_match_the_pinned_hashes_and_row_counts(self):
        import lpbf_literature_datasets as L
        roles = V.CALIBRATION_CONFIG_V2["dataRoles"]["testOnlyRoles"]
        g = L.load_ghosh_in625()
        self.assertEqual(g["provenance"]["fileSha256"], roles["ghosh-in625-2018"]["tableSha256"])
        self.assertEqual(len(g["rows"]), roles["ghosh-in625-2018"]["rowsExpected"])
        self.assertEqual(g["provenance"]["beamDiameterInput_um"], V.GHOSH_SPOT_READINGS_UM[0])
        t = L.load_trapp_316l_tracks()
        self.assertEqual(t["provenance"]["fileSha256"], roles["trapp-316l-2017"]["tableSha256"])
        self.assertEqual(sum(1 for r in t["rows"] if r["depth_um"] is not None), roles["trapp-316l-2017"]["rowsExpected"])
        self.assertTrue(all(r["digitized"] for r in t["rows"]))
        refs = V.CALIBRATION_CONFIG_V2["absorptivityReferences"]["tables"]
        self.assertEqual(L.load_trapp_absorptivity()["provenance"]["fileSha256"], refs["trapp-316l-2017-absorptivity"])
        self.assertEqual(L.load_ye_min_absorptivity()["provenance"]["fileSha256"], refs["ye-2019-absorptivity"])
        self.assertEqual(L.load_rubenchik_powder_absorptivity()["provenance"]["fileSha256"], refs["rubenchik-powder-2015"])

    def test_absorptivity_envelopes_follow_the_declared_rule(self):
        pinned = V.CALIBRATION_CONFIG_V2["absorptivityReferences"]["envelopes"]
        derived = V.derive_absorptivity_envelopes()
        self.assertEqual(set(derived), set(pinned))
        for m, d in derived.items():
            for k in ("lower", "upper", "sides"):
                self.assertEqual(d[k], pinned[m][k], (m, k))
        self.assertIn("never a training target", V.CALIBRATION_CONFIG_V2["absorptivityReferences"]["role"])

    def test_envelope_check(self):
        chk = V.envelope_check("Inconel 625", {"etaW": 0.25, "etaD": 0.5, "etaJoint": None})
        self.assertTrue(chk["flag"])
        self.assertEqual(chk["outside"], [{"param": "etaW", "eta": 0.25, "side": "below"}])
        self.assertFalse(V.envelope_check("Inconel 625", {"etaW": 0.79})["flag"])  # one-sided
        self.assertTrue(V.envelope_check("316L Stainless Steel", {"etaD": 0.80})["flag"])
        self.assertFalse(V.envelope_check("Inconel 718", {"etaD": 0.10})["flag"])  # no envelope

    def test_v1_records_still_verify(self):
        art = json.loads((REPO_ROOT / C1.ARTEFACT_REL_PATH).read_text(encoding="utf-8"))
        self.assertEqual(art["configSha256"], V1_CONFIG_SHA256)
        sys.path.insert(0, str(PYTHON_DIR / "tools"))
        import lpbf_calibration_fit as T
        self.assertEqual(T.check_outputs(REPO_ROOT, art["generatedAt"]), [])

    def test_runtime_layer_refuses_a_v2_config_hash(self):
        import lpbf_calibration_layer as layer
        art = json.loads((REPO_ROOT / C1.ARTEFACT_REL_PATH).read_text(encoding="utf-8"))
        art["configSha256"] = V2_CONFIG_SHA256
        art["config"] = V.CALIBRATION_CONFIG_V2
        art["contentSha256"] = layer.artefact_content_sha256(art)
        import tempfile
        p = Path(tempfile.mkdtemp()) / "v2probe.json"
        p.write_text(json.dumps(art), encoding="utf-8")
        with self.assertRaises(layer.CalibrationError):
            layer.load_calibration(p, expected_impl_hash=art["implementationHash"])

    def test_v2_modules_stay_out_of_the_frozen_manifest(self):
        import lpbf_simulation
        names = set(lpbf_simulation.IMPLEMENTATION_SOURCE_FILES)
        for n in ("lpbf_calibration_config_v2.py", "tools/lpbf_calibration_fit_v2.py", "lpbf_literature_datasets.py"):
            self.assertNotIn(n, names)


if __name__ == "__main__":
    unittest.main()
