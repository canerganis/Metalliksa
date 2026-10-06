"""Independent discrete extraction oracles, not measured LPBF evidence."""
from pathlib import Path
import io
import os
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
from lpbf_peak import PeakMeltTracker


class PeakContract(unittest.TestCase):
    @unittest.skipIf(os.name == 'nt', 'OpenFOAM dispatch is Linux-only')
    def test_previous_peak_extraction_binary_rejected(self):
        from lpbf_openfoam import thermal
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/'openfoam-case'; folder.mkdir()
            def launch(*args, **kwargs):
                (folder/'numerical-diagnostics.json').write_text(
                    '{"sourceIntegration":"cell-integrated-gaussian-gl2-v1",'
                    '"solidificationExtraction":"linear-liquidus-crossing-v1"}')
                return SimpleNamespace(stdout=io.StringIO(''), wait=lambda: 0)
            with patch('lpbf_openfoam.BINARY', Path(__file__)), patch('lpbf_openfoam.generate_case', return_value=(1., [])), patch('lpbf_openfoam.subprocess.Popen', side_effect=launch):
                with self.assertRaisesRegex(ValueError, 'melt pool extraction contract mismatch'):
                    thermal({}, {}, artifact_dir=tmp)

    def test_reference_observes_every_step_and_matches_independent_oracle(self):
        from lpbf_simulation import validate, transient
        p, m = validate(dict(power_W=40, mesh_um=40, trackLength_um=200, cooling_s=.0001, dwell_s=0))
        observed = []
        class AuditedTracker(PeakMeltTracker):
            def observe(self, temperature, surface, angle, time, step, sampled=False):
                count = sum(float(t) >= m['liquidus_K'] and float(z) < surface
                            for t, z in zip(temperature.ravel(), self.xyz[:, 2]))
                observed.append((step, time, count, sampled))
                super().observe(temperature, surface, angle, time, step, sampled)
        with patch('lpbf_simulation.PeakMeltTracker', AuditedTracker):
            r = transient(p, m)
        self.assertEqual([o[0] for o in observed], list(range(1, r['discretization']['steps']+1)))
        expected = max(observed, key=lambda o: o[2])
        d = r['numericalDiagnostics']
        self.assertEqual(d['peakMeltStep'], expected[0])
        self.assertEqual(d['peakMeltTime_s'], expected[1])
        self.assertAlmostEqual(r['metrics']['volume_um3'], expected[2]*r['discretization']['mesh_m']**3*1e18)
        sampled = max(o[2] for o in observed if o[3])
        self.assertAlmostEqual(d['peakMeltSamplingLossFraction'], (expected[2]-sampled)/expected[2])

    def test_unsampled_peak_tie_and_saved_field(self):
        xyz = np.array([[0, 0, -1], [2, 0, -1], [0, 2, -1], [0, 0, 3]])*1e-6
        m = dict(solidus_K=900., liquidus_K=1000.)
        tracker = PeakMeltTracker(xyz, 2e-6, m)
        with tempfile.TemporaryDirectory() as tmp:
            for step, count in enumerate([1, 3, 3, 2], 1):
                t = np.full(4, 800.); t[:count] = 1000.; t[3] = 2000.
                tracker.observe(t, 0., 45., step*.1, step, sampled=step in (1, 4))
                t[:] = 300.  # Tracker must own its selected field.
            metrics, d = tracker.finish(tmp, 4)
            self.assertAlmostEqual(metrics['volume_um3'], 24.)
            self.assertAlmostEqual(metrics['length_um'], 3*np.sqrt(2))
            self.assertAlmostEqual(metrics['width_um'], 4*np.sqrt(2))
            self.assertAlmostEqual(metrics['depth_um'], 2.)
            self.assertAlmostEqual(metrics['crossSectionArea_um2'], 8.)
            self.assertEqual(d['peakMeltStep'], 2)
            self.assertEqual(d['peakMeltTime_s'], .2)
            self.assertEqual(d['peakMeltCellCount'], 3)
            self.assertEqual(d['equalMaximumEndpointCount'], 2)
            self.assertEqual(d['firstEqualMaximumTime_s'], .2)
            self.assertAlmostEqual(d['lastEqualMaximumTime_s'], .3)
            self.assertAlmostEqual(d['sampledPeakMeltVolume_um3'], 16.)
            self.assertAlmostEqual(d['peakMeltSamplingLossFraction'], 1/3)
            with np.load(Path(tmp)/'peak-field.npz') as field:
                self.assertEqual(field['step'], 2)
                self.assertEqual(np.count_nonzero((field['T_K'] >= 1000)&field['active']), 3)
                self.assertEqual(field['liquid_fraction'][-1], 0.)
                self.assertEqual(field['surface_m'], 0.)
                self.assertEqual(field['scanAngle_deg'], 45.)

    def test_zero_melt_removes_stale_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'peak-field.npz'; path.write_text('stale')
            for name in ('temperature-slice.svg', 'phase-slice.svg'):
                (Path(tmp)/name).write_text('stale')
            tracker = PeakMeltTracker(np.array([[0., 0., 0.]]), 1e-6,
                                      dict(solidus_K=900., liquidus_K=1000.))
            tracker.observe(np.array([800.]), 1e-6, 90., .1, 1, sampled=True)
            metrics, d = tracker.finish(tmp, 1)
            self.assertFalse(path.exists())
            self.assertTrue(all(v == 0 for v in metrics.values()))
            self.assertIsNone(d['peakMeltTime_s'])
            self.assertIsNone(d['peakMeltStep'])
            self.assertEqual(d['peakMeltCellCount'], 0)
            self.assertEqual(d['equalMaximumEndpointCount'], 0)
            self.assertIsNone(d['firstEqualMaximumTime_s'])
            self.assertIsNone(d['lastEqualMaximumTime_s'])
            self.assertEqual(d['peakMeltSamplingLossFraction'], 0.)
            from lpbf_evidence import write_artifacts
            result = {}
            write_artifacts(result, tmp)
            self.assertEqual(result['artifacts'], [])

    def test_step_surface_and_rotation_are_retained(self):
        tracker = PeakMeltTracker(np.array([[0., 0., 1e-6], [2e-6, 0., 1e-6]]),
                                  2e-6, dict(solidus_K=900., liquidus_K=1000.))
        tracker.observe(np.array([1000., 1000.]), 2e-6, 90., .1, 1)
        metrics, d = tracker.finish(None, 1)
        self.assertAlmostEqual(metrics['length_um'], 2.)
        self.assertAlmostEqual(metrics['width_um'], 4.)
        self.assertAlmostEqual(metrics['depth_um'], 2.)


if __name__ == '__main__':
    unittest.main()
