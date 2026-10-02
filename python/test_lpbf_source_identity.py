import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lpbf_source_identity import (
    CANONICAL_SCHEMA,
    RAW_SCHEMA,
    canonical_source_bytes,
    fingerprint_manifest_entries,
    fingerprint_sources,
    source_identity,
)
import lpbf_simulation


def _write_fixture_tree(root):
    (root / "openfoam" / "Make").mkdir(parents=True)
    (root / "openfoam" / "src").mkdir(parents=True)
    (root / "lpbf_simulation.py").write_bytes(b"thermal = True\n")
    (root / "lpbf_material_registry.py").write_bytes(b"material_revision = 'A'\n")
    (root / "test_solver.py").write_bytes(b"test_value = 1\n")
    (root / "lpbf_worker.py").write_bytes(b"worker_value = 1\n")
    (root / "run_diagnostic.py").write_bytes(b"diagnostic_value = 1\n")
    (root / "openfoam" / "src" / "thermal.C").write_bytes(b"int thermal() { return 1; }\n")
    (root / "openfoam" / "Make" / "files").write_bytes(b"thermal.C\n")
    (root / "openfoam" / "Make" / "options").write_bytes(b"-O2\n")


def _temporary_directory():
    root = Path(__file__).resolve().parents[1] / ".tmp-lpbf-source-identity-fixtures"
    root.mkdir(exist_ok=True)
    return tempfile.TemporaryDirectory(dir=root)


class LpbfSourceIdentityTests(unittest.TestCase):
    def test_crlf_is_canonicalized_without_changing_bom_or_lone_cr(self):
        raw = b"\xef\xbb\xbfalpha\r\nbeta\rgamma\n"
        self.assertEqual(
            canonical_source_bytes("solver.py", raw),
            b"\xef\xbb\xbfalpha\nbeta\rgamma\n",
        )

    def test_openfoam_text_and_make_manifest_files_use_text_normalization(self):
        for path in (
            "solver.C",
            "include/solver.h",
            "include/solver.H",
            "openfoam/Make/files",
            "openfoam/Make/options",
        ):
            with self.subTest(path=path):
                self.assertEqual(canonical_source_bytes(path, b"a\r\nb\n"), b"a\nb\n")

    def test_unknown_binary_extension_preserves_every_byte(self):
        raw = b"\x00\xff\r\n\x80"
        self.assertEqual(canonical_source_bytes("opaque.dat", raw), raw)

    def test_invalid_utf8_in_known_source_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            canonical_source_bytes("solver.py", b"value = '\xff'\n")

    def test_canonical_manifest_hash_is_equal_for_lf_and_crlf_sources(self):
        lf = [("solver.py", b"value = 1\nnext = 2\n")]
        crlf = [("solver.py", b"value = 1\r\nnext = 2\r\n")]
        self.assertEqual(
            fingerprint_manifest_entries(lf, "enthalpy-fv-test"),
            fingerprint_manifest_entries(crlf, "enthalpy-fv-test"),
        )

    def test_raw_v2_schema_retains_the_historical_byte_framing(self):
        entries = [("z.py", b"x=2\r\n"), ("a.py", b"x=1\n")]
        # Fixed compatibility vector for schema\0version\0 + sorted framed raw bytes.
        self.assertEqual(
            fingerprint_manifest_entries(entries, "solver-v6", schema=RAW_SCHEMA),
            "f3cf15f2b01b5d5f35dc7fbd6ec23e1eadc5d952ab72d6777c80a688ce8e5ad7",
        )
        self.assertNotEqual(
            fingerprint_manifest_entries(entries, "solver-v6", schema=RAW_SCHEMA),
            fingerprint_manifest_entries(entries, "solver-v6", schema=CANONICAL_SCHEMA),
        )

    def test_manifest_hash_is_order_independent_but_path_and_version_bound(self):
        entries = [("b.py", b"b\n"), ("a.py", b"a\n")]
        digest = fingerprint_manifest_entries(entries, "v1")
        self.assertEqual(digest, fingerprint_manifest_entries(list(reversed(entries)), "v1"))
        self.assertNotEqual(digest, fingerprint_manifest_entries(
            [("renamed.py", b"b\n"), ("a.py", b"a\n")], "v1"))
        self.assertNotEqual(digest, fingerprint_manifest_entries(entries, "v2"))

    def test_material_dependency_content_is_identity_bearing(self):
        original = [("lpbf_material_registry.py", b"revision = 'A'\n")]
        changed = [("lpbf_material_registry.py", b"revision = 'B'\n")]
        self.assertNotEqual(
            fingerprint_manifest_entries(original, "solver-v1"),
            fingerprint_manifest_entries(changed, "solver-v1"),
        )

    def test_unmanifested_test_worker_and_diagnostic_files_do_not_change_identity(self):
        with _temporary_directory() as directory:
            root = Path(directory)
            (root / "lpbf_material_registry.py").write_bytes(b"revision = 1\n")
            sources = ("lpbf_material_registry.py",)
            before = fingerprint_sources(root, sources, "solver-v1")
            (root / "test_solver.py").write_bytes(b"test_only = True\n")
            (root / "lpbf_worker.py").write_bytes(b"worker_only = True\n")
            (root / "run_diagnostic.py").write_bytes(b"diagnostic_only = True\n")
            self.assertEqual(before, fingerprint_sources(root, sources, "solver-v1"))

    def test_source_identity_reports_raw_and_canonical_file_digests(self):
        with _temporary_directory() as directory:
            root = Path(directory)
            raw = b"version = 1\r\n"
            (root / "solver.py").write_bytes(raw)
            identity = source_identity(root, ("solver.py",), "solver-v1")
            self.assertEqual(identity["schema"], CANONICAL_SCHEMA)
            self.assertEqual(identity["rawSchema"], RAW_SCHEMA)
            self.assertEqual(identity["version"], "solver-v1")
            self.assertEqual(identity["rawFileSha256"]["solver.py"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(
                identity["canonicalFileSha256"]["solver.py"],
                hashlib.sha256(b"version = 1\n").hexdigest(),
            )
            self.assertEqual(
                identity["implementationHash"],
                fingerprint_manifest_entries((("solver.py", raw),), "solver-v1"),
            )

    def test_raw_source_identity_matches_independent_pinned_v2_fixture(self):
        with _temporary_directory() as directory:
            root = Path(directory)
            (root / "z.py").write_bytes(b"x=2\r\n")
            (root / "a.py").write_bytes(b"x=1\n")
            identity = source_identity(root, ("z.py", "a.py"), "solver-v6")
            self.assertEqual(
                identity["rawByteImplementationHash"],
                "f3cf15f2b01b5d5f35dc7fbd6ec23e1eadc5d952ab72d6777c80a688ce8e5ad7",
            )

    def test_bom_and_lone_cr_remain_identity_bearing(self):
        plain = fingerprint_manifest_entries((("solver.py", b"x = 1\n"),), "v1")
        bom = fingerprint_manifest_entries((("solver.py", b"\xef\xbb\xbfx = 1\n"),), "v1")
        lone_cr = fingerprint_manifest_entries((("solver.py", b"x = 1\r"),), "v1")
        self.assertNotEqual(plain, bom)
        self.assertNotEqual(plain, lone_cr)

    def test_unknown_schema_is_rejected(self):
        with self.assertRaises(ValueError):
            fingerprint_manifest_entries((("solver.py", b"x\n"),), "v1", schema="future-unknown")

    def test_fingerprint_sources_rejects_symlink_escape_when_supported(self):
        with _temporary_directory() as directory, _temporary_directory() as outside:
            root = Path(directory)
            target = Path(outside) / "solver.py"
            target.write_bytes(b"outside = True\n")
            link = root / "solver.py"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"symlink creation unavailable on this host: {error}")
            with self.assertRaises((ValueError, FileNotFoundError)):
                fingerprint_sources(root, ("solver.py",), "v1")

    def test_thermal_cache_identity_is_lf_crlf_stable_and_bound_to_sources_version_and_inputs(self):
        with _temporary_directory() as directory:
            root = Path(directory)
            _write_fixture_tree(root)
            with (
                patch.object(lpbf_simulation, "__file__", str(root / "lpbf_simulation.py")),
                patch.object(lpbf_simulation, "IMPLEMENTATION_SOURCE_FILES", (
                    "lpbf_simulation.py", "lpbf_material_registry.py",
                    "openfoam/src/thermal.C", "openfoam/Make/files", "openfoam/Make/options",
                )),
                patch.object(lpbf_simulation, "VERSION", "solver-v1"),
            ):
                p = {"mode": "standard", "backend": "reference", "power_W": 100}
                material = {"materialId": "in718", "version": "revision-A"}
                baseline = lpbf_simulation.fingerprint(p, material)

                source = root / "lpbf_material_registry.py"
                source.write_bytes(b"material_revision = 'A'\r\n")
                self.assertEqual(baseline, lpbf_simulation.fingerprint(p, material))
                source.write_bytes(b"material_revision = 'B'\n")
                changed_source = lpbf_simulation.fingerprint(p, material)
                self.assertNotEqual(baseline, changed_source)

                self.assertNotEqual(changed_source, lpbf_simulation.fingerprint(
                    {**p, "power_W": 101}, material))
                self.assertNotEqual(changed_source, lpbf_simulation.fingerprint(
                    p, {**material, "version": "revision-B"}))
                with patch.object(lpbf_simulation, "VERSION", "solver-v2"):
                    self.assertNotEqual(changed_source, lpbf_simulation.fingerprint(p, material))

    def test_thermal_cache_ignores_unmanifested_test_worker_and_diagnostic_edits(self):
        with _temporary_directory() as directory:
            root = Path(directory)
            _write_fixture_tree(root)
            with (
                patch.object(lpbf_simulation, "__file__", str(root / "lpbf_simulation.py")),
                patch.object(lpbf_simulation, "IMPLEMENTATION_SOURCE_FILES", (
                    "lpbf_simulation.py", "lpbf_material_registry.py",
                    "openfoam/src/thermal.C", "openfoam/Make/files", "openfoam/Make/options",
                )),
            ):
                p, material = {"mode": "standard"}, {"materialId": "in718"}
                before = lpbf_simulation.fingerprint(p, material)
                for name in ("test_solver.py", "lpbf_worker.py", "run_diagnostic.py"):
                    (root / name).write_bytes(b"changed unrelated source\r\n")
                self.assertEqual(before, lpbf_simulation.fingerprint(p, material))

    def test_nonthermal_jobtypes_retain_exact_legacy_broad_raw_cache_hash(self):
        with _temporary_directory() as directory:
            root = Path(directory)
            _write_fixture_tree(root)
            p = {"jobType": "gpu-thermal-pilot", "mode": "standard"}
            material = {"materialId": "in718", "version": "A"}

            def legacy_hash():
                h = hashlib.sha256()
                for source in sorted(root.glob("*.py")):
                    h.update(source.name.encode())
                    h.update(source.read_bytes())
                for source in sorted((root / "openfoam").glob("*.C")):
                    h.update(source.name.encode())
                    h.update(source.read_bytes())
                for source in sorted((root / "openfoam" / "Make").glob("*")):
                    if source.is_file():
                        h.update(source.name.encode())
                        h.update(source.read_bytes())
                import json
                h.update(json.dumps([lpbf_simulation.VERSION, p, material],
                                    sort_keys=True, allow_nan=False).encode())
                return h.hexdigest()

            with patch.object(lpbf_simulation, "__file__", str(root / "lpbf_simulation.py")):
                for job_type in ("gpu-thermal-pilot", "build-job", "future-unknown"):
                    p["jobType"] = job_type
                    self.assertEqual(lpbf_simulation.fingerprint(p, material), legacy_hash())
                    before = lpbf_simulation.fingerprint(p, material)
                    (root / "lpbf_worker.py").write_bytes(f"worker_value = {job_type!r}\n".encode())
                    self.assertNotEqual(before, lpbf_simulation.fingerprint(p, material))

    def test_real_screening_result_records_canonical_identity_schema(self):
        result = lpbf_simulation.run({"mode": "screening"})
        self.assertEqual(
            result["provenance"]["implementationFingerprintSchema"],
            lpbf_simulation.IMPLEMENTATION_FINGERPRINT_SCHEMA,
        )
        self.assertRegex(result["provenance"]["implementationHash"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            result["provenance"]["implementationHash"],
            lpbf_simulation.implementation_fingerprint(),
        )
        self.assertFalse(result["productionReady"])
        self.assertEqual(result["validationStatus"], "unvalidated")

    def test_manifest_rejects_empty_duplicate_and_noncanonical_paths(self):
        for entries in (
            [],
            [("solver.py", b"a"), ("solver.py", b"b")],
            [("../solver.py", b"a")],
            [(".", b"a")],
            [("C:/solver.py", b"a")],
            [("C:solver.py", b"a")],
            [("folder\\solver.py", b"a")],
            [("./solver.py", b"a")],
        ):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                fingerprint_manifest_entries(entries, "solver-v1")

    def test_missing_source_fails_closed(self):
        with _temporary_directory() as directory:
            with self.assertRaises(FileNotFoundError):
                fingerprint_sources(Path(directory), ("missing.py",), "solver-v1")


if __name__ == "__main__":
    unittest.main()
