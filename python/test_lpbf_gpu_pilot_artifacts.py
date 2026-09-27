"""Synthetic serialization fixtures; these tests establish no solver parity."""

import copy
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from lpbf_gpu_pilot_artifacts import (
    MAX_CELLS, MAX_STEPS, _state_arrays, pilot_artifact_refs, read_pilot_artifacts, write_pilot_artifacts,
)


def synthetic_state():
    return {"coordinates_m": np.array([[0., 0., -1e-5], [1e-5, 0., 1e-5]]),
            "temperature_K": np.array([310., 290.]), "enthalpy_J_m3": np.array([2e7, -2e7]),
            "density_kg_m3": np.array([8000., 4400.]), "accepted_dt_s": np.array([1e-7, 2e-7]),
            "time_s": 3e-7, "initial_temperature_K": 300., "cell_volume_m3": 1e-15}


class PilotArtifacts(unittest.TestCase):
    def test_writer_rejects_lossy_numeric_sources(self):
        cases = [("int64 array", lambda: np.array([[2 ** 53 + 1, 0, 0], [1, 0, 0]], dtype=np.int64)),
                 ("uint64 array", lambda: np.array([[2 ** 53 + 1, 0, 0], [1, 0, 0]], dtype=np.uint64)),
                 ("mixed Python list", lambda: [[2 ** 53 + 1, 0.0, 0.0], [1.0, 0.0, 0.0]])]
        for name, coordinates in cases:
            with self.subTest(source=name):
                state = synthetic_state()
                state["coordinates_m"] = coordinates()
                expected = "NumPy ndarray" if name == "mixed Python list" else "exact float64"
                with self.assertRaisesRegex(ValueError, expected):
                    _state_arrays(state)

        with self.subTest(source="large scalar int"):
            state = synthetic_state()
            state["time_s"] = 2 ** 53 + 1
            with self.assertRaisesRegex(ValueError, "exact float64"):
                _state_arrays(state)

        with self.subTest(source="string scalar"):
            state = synthetic_state()
            state["time_s"] = "3e-7"
            with self.assertRaisesRegex(ValueError, "finite positive number"):
                _state_arrays(state)

        if np.finfo(np.longdouble).nmant > np.finfo(np.float64).nmant:
            with self.subTest(source="extended scalar float"):
                state = synthetic_state()
                state["time_s"] = np.longdouble(3e-7) + np.finfo(np.longdouble).eps
                with self.assertRaisesRegex(ValueError, "exact float64"):
                    _state_arrays(state)

        for dtype, value in ((np.int64, 2 ** 53 + 1), (np.uint64, 2 ** 53 + 1)):
            with self.subTest(dtype=dtype):
                state = synthetic_state()
                state["coordinates_m"] = np.array([[value, 0, 0], [1, 0, 0]], dtype=dtype)
                with self.assertRaisesRegex(ValueError, "exact float64"):
                    _state_arrays(state)

    def test_resource_bounds_are_checked_before_float64_allocation(self):
        for quantity, oversized in (
                ("coordinates_m", np.zeros((MAX_CELLS + 1, 3), dtype=np.float32)),
                ("accepted_dt_s", np.ones(MAX_STEPS + 1, dtype=np.float32)),
                ("temperature_K", np.ones(MAX_CELLS + 1, dtype=np.float32))):
            with self.subTest(quantity=quantity), tempfile.TemporaryDirectory() as tmp:
                state = synthetic_state()
                state[quantity] = oversized
                with patch("lpbf_gpu_pilot_artifacts.np.ascontiguousarray", wraps=np.ascontiguousarray) as convert:
                    with self.assertRaises(ValueError):
                        write_pilot_artifacts(tmp, state, state)
                    convert.assert_not_called()

    def test_nonadvancing_and_after_final_timesteps_are_rejected(self):
        for timesteps in ([.5, np.nextafter(0., 1.), .5], [1., np.nextafter(0., 1.)]):
            with self.subTest(timesteps=timesteps), tempfile.TemporaryDirectory() as tmp:
                state = synthetic_state()
                state["time_s"] = 1.
                state["accepted_dt_s"] = np.array(timesteps)
                with self.assertRaisesRegex(ValueError, "clock"):
                    write_pilot_artifacts(tmp, state, state)
                state["accepted_dt_s"] = np.full(len(timesteps), 1. / len(timesteps))
                descriptor = write_pilot_artifacts(tmp, state, state)
                ref = descriptor["states"]["gpu"]["fields"]["accepted_dt_s"]
                data = np.array(timesteps, dtype="<f8").tobytes()
                (Path(tmp) / ref["path"]).write_bytes(data)
                ref["sha256"] = hashlib.sha256(data).hexdigest()
                with self.assertRaisesRegex(ValueError, "clock"):
                    read_pilot_artifacts(tmp, descriptor)

    def test_linked_ancestor_is_rejected_for_read_and_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.mkdir()
            job = target / "job"
            job.mkdir()
            descriptor = write_pilot_artifacts(job, synthetic_state(), synthetic_state())
            link = root / "linked"
            try:
                link.symlink_to(target, target_is_directory=True)
            except (NotImplementedError, OSError) as error:
                if os.name != "nt":
                    self.skipTest(f"Directory links unavailable on this host: {error}")
                created = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                                         capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                if created.returncode != 0 or not link.is_junction():
                    self.skipTest(f"Directory symlinks/junctions unavailable on this host: {error}")
            try:
                with self.subTest(operation="read"), self.assertRaisesRegex(ValueError, "link"):
                    read_pilot_artifacts(link / "job", descriptor)
                fresh = target / "fresh"
                fresh.mkdir()
                with self.subTest(operation="write"), self.assertRaisesRegex(ValueError, "link"):
                    write_pilot_artifacts(link / "fresh", synthetic_state(), synthetic_state())
            finally:
                if getattr(link, "is_junction", lambda: False)():
                    link.rmdir()
                else:
                    link.unlink()

    def test_deterministic_lossless_roundtrip_including_different_step_counts(self):
        cpu, gpu = synthetic_state(), synthetic_state()
        cpu["coordinates_m"] = np.asfortranarray(cpu["coordinates_m"]).astype(">f8")
        gpu["accepted_dt_s"] = np.array([3e-7])
        gpu["temperature_K"][0] += .1234567890123
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            descriptor = write_pilot_artifacts(first, cpu, gpu)
            other = write_pilot_artifacts(second, cpu, gpu)
            self.assertEqual(descriptor, other)
            restored = read_pilot_artifacts(first, descriptor)
            refs = pilot_artifact_refs(descriptor)
            self.assertEqual(len(refs), 10)
            for backend, expected in (("cpu", cpu), ("gpu", gpu)):
                for key, value in expected.items():
                    np.testing.assert_array_equal(restored[backend][key], value)
            for ref in refs:
                self.assertEqual((Path(first) / ref["path"]).read_bytes(), (Path(second) / ref["path"]).read_bytes())
            self.assertEqual(descriptor["states"]["cpu"]["fields"]["enthalpy_J_m3"]["units"], "J/m^3")
            coordinates = descriptor["states"]["cpu"]["fields"]["coordinates_m"]
            self.assertEqual((Path(first) / coordinates["path"]).read_bytes(),
                             cpu["coordinates_m"].astype("<f8").tobytes(order="C"))
            with self.assertRaisesRegex(ValueError, "already exists"):
                write_pilot_artifacts(first, cpu, gpu)

    def test_writer_rejects_invalid_states_before_writing(self):
        mutations = [
            ("temperature_K", [310., float("nan")]), ("temperature_K", [310., 0.]),
            ("density_kg_m3", [8000., -1.]), ("accepted_dt_s", [0., 3e-7]),
            ("accepted_dt_s", [1e-7]), ("accepted_dt_s", np.ones(MAX_STEPS + 1)),
            ("coordinates_m", np.zeros((MAX_CELLS + 1, 3))), ("coordinates_m", [[0., 0.]]),
            ("enthalpy_J_m3", [1.]), ("enthalpy_J_m3", [True, False]),
            ("time_s", True), ("time_s", float("inf")), ("cell_volume_m3", 0.),
            ("initial_temperature_K", -1.), ("time_s", 10 ** 1000),
        ]
        for name, value in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                bad = synthetic_state()
                bad[name] = value
                with self.assertRaises(ValueError):
                    write_pilot_artifacts(tmp, synthetic_state(), bad)
                self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_reader_rejects_descriptor_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            descriptor = write_pilot_artifacts(tmp, synthetic_state(), synthetic_state())
            for key, value in (("path", "../outside.bin"), ("shape", [True, 3]),
                               ("shape", [3, 2]), ("units", "J/kg"), ("size_bytes", 1),
                               ("sha256", "A" * 64)):
                with self.subTest(key=key, value=value):
                    bad = copy.deepcopy(descriptor)
                    bad["states"]["cpu"]["fields"]["coordinates_m"][key] = value
                    with self.assertRaises(ValueError):
                        read_pilot_artifacts(tmp, bad)
            bad = copy.deepcopy(descriptor)
            bad["schemaVersion"] = True
            with self.assertRaises(ValueError):
                read_pilot_artifacts(tmp, bad)
            bad = copy.deepcopy(descriptor)
            bad["states"]["gpu"]["time_s"] *= 2
            with self.assertRaisesRegex(ValueError, "final time"):
                read_pilot_artifacts(tmp, bad)
            for key, value in (("cells", MAX_CELLS + 1), ("steps", MAX_STEPS + 1)):
                bad = copy.deepcopy(descriptor)
                bad["states"]["gpu"][key] = value
                with self.assertRaisesRegex(ValueError, "count"):
                    read_pilot_artifacts(tmp, bad)

    def test_reader_checks_bytes_and_rechecks_values_even_with_updated_hash(self):
        for quantity, values in (("temperature_K", [float("nan"), 290.]),
                                 ("density_kg_m3", [8000., 0.]),
                                 ("accepted_dt_s", [1e-7, 1e-7])):
            with self.subTest(quantity=quantity), tempfile.TemporaryDirectory() as tmp:
                descriptor = write_pilot_artifacts(tmp, synthetic_state(), synthetic_state())
                ref = descriptor["states"]["gpu"]["fields"][quantity]
                path = Path(tmp) / ref["path"]
                data = np.array(values, dtype="<f8").tobytes()
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "byte integrity"):
                    read_pilot_artifacts(tmp, descriptor)
                ref["sha256"] = hashlib.sha256(data).hexdigest()
                with self.assertRaises(ValueError):
                    read_pilot_artifacts(tmp, descriptor)
                path.write_bytes(data[:-1])
                with self.assertRaisesRegex(ValueError, "size mismatch"):
                    read_pilot_artifacts(tmp, descriptor)

    def test_endpoint_roundoff_preserves_accepted_dt_bytes(self):
        state = synthetic_state()
        state["time_s"] = np.nextafter(state["time_s"], float("inf"))
        with tempfile.TemporaryDirectory() as tmp:
            descriptor = write_pilot_artifacts(tmp, state, state)
            restored = read_pilot_artifacts(tmp, descriptor)
            np.testing.assert_array_equal(restored["cpu"]["accepted_dt_s"], state["accepted_dt_s"])
            self.assertEqual(restored["cpu"]["time_s"], state["time_s"])

    def test_long_accepted_sequence_replays_the_sequential_solver_clock(self):
        state = synthetic_state()
        state["accepted_dt_s"] = np.full(100_000, 1e-6)
        model_time = 0.
        for dt in state["accepted_dt_s"]:
            model_time += float(dt)
        state["time_s"] = model_time
        with tempfile.TemporaryDirectory() as tmp:
            descriptor = write_pilot_artifacts(tmp, state, state)
            restored = read_pilot_artifacts(tmp, descriptor)
            self.assertEqual(restored["cpu"]["time_s"], model_time)
            np.testing.assert_array_equal(restored["cpu"]["accepted_dt_s"], state["accepted_dt_s"])


if __name__ == "__main__":
    unittest.main()
