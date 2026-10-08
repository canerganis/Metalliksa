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
            # LA-6: at 45 deg the three cells project to 0, sqrt2, sqrt2 um; extent = 2*sqrt2 um, so
            # rint(0.5) = 0 puts all three in one slab: 3*dx^2*dx/extent = 3*4*2/(2*sqrt2) = 8.485...
            self.assertAlmostEqual(metrics['crossSectionArea_um2'], 8.485281374238568, places=12)
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

    def test_cross_section_is_scan_normal(self):
        dx = 10e-6
        axis = (np.arange(200)+.5)*dx-1e-3
        z_axis = -(np.arange(40)+.5)*dx
        xyz = np.array(np.meshgrid(axis, axis, z_axis, indexing='ij')).reshape(3, -1).T
        reference = np.pi/4*100*50  # 3926.99 um2, W 100 / D 50 um
        for angle in (0., 67., 90., 102.):
            c, s = np.cos(np.radians(angle)), np.sin(np.radians(angle))
            u, v, z = xyz[:, 0]*c+xyz[:, 1]*s, -xyz[:, 0]*s+xyz[:, 1]*c, xyz[:, 2]
            inside = (u/200e-6)**2+(v/50e-6)**2+(z/50e-6)**2 <= 1
            tracker = PeakMeltTracker(xyz, dx, dict(solidus_K=900., liquidus_K=1000.))
            tracker.observe(np.where(inside, 1000., 300.), 0., angle, .1, 1)
            metrics, _ = tracker.finish(None, 1)
            ratio = metrics['crossSectionArea_um2']/reference
            self.assertTrue(.97 <= ratio <= 1.07, (angle, ratio))
            if angle in (0., 90.):
                planes = np.rint((xyz[inside, 0]-xyz[:, 0].min())/dx).astype(int)  # former global-x rule
                former = float(np.bincount(planes).max())*dx**2*1e12
                self.assertAlmostEqual(metrics['crossSectionArea_um2'], 4000.0, places=9)
                if angle == 0.:
                    self.assertEqual(metrics['crossSectionArea_um2'], former)

    def test_cross_section_g3_stripe_cells(self):
        # Six peak cells of the G3 stripe case (dx 40 um, peak on layer 2 at 102 deg).
        xyz = np.array([[20, 60, 60], [20, 100, 60], [60, -60, 60], [60, -20, 60],
                        [60, 20, 60], [60, 60, 60]])*1e-6
        for angle, expected in ((102., 2698.010144007103), (0., 6400.0)):
            tracker = PeakMeltTracker(xyz, 40e-6, dict(solidus_K=900., liquidus_K=1000.))
            tracker.observe(np.full(6, 1000.), 80e-6, angle, .1, 1)
            metrics, _ = tracker.finish(None, 1)
            self.assertAlmostEqual(metrics['crossSectionArea_um2'], expected, delta=1e-6, msg=str(angle))


if __name__ == '__main__':
    unittest.main()
