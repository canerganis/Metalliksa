#!/usr/bin/env python3
"""LA-7: midpointPenetrationDepth_um uses each layer's own track melt, not the cumulative mask."""
import unittest

import numpy as np

from lpbf_overlap import FieldOverlapTracker

DX = 5e-6
MATERIAL = {"liquidus_K": 1609.0, "solidus_K": 1533.0}


def _run(layer_bottoms_m):
    ax = np.arange(-40, 41) * DX
    z = (np.arange(-8, 16) + 0.5) * DX
    xx, yy, zz = np.meshgrid(ax, ax, z, indexing="ij")
    c = np.column_stack([xx.ravel(), yy.ravel(), zz.ravel()])
    settings = {"tracks": 2, "layers": len(layer_bottoms_m), "hatch_um": 60.0, "layer_um": 40.0,
                "trackLength_um": 300.0, "scanAngle_deg": 0.0, "layerRotation_deg": 0.0}
    t = FieldOverlapTracker(c, DX, MATERIAL, settings)
    for layer, bottom in enumerate(layer_bottoms_m):
        surface = (layer + 1) * 40e-6
        for track, yc in ((0, -30e-6), (1, 30e-6)):
            hot = (np.abs(c[:, 1] - yc) <= 45e-6) & (c[:, 2] >= bottom) & (c[:, 2] < surface)
            t.observe(np.where(hot, 1700.0, 300.0), surface, layer, track)
    return t.finish()


class MidpointPenetrationPerLayerTest(unittest.TestCase):
    def test_shallow_upper_layer_is_reported(self):
        r = _run([-20e-6, 50e-6])  # layer 1 melts only 30 um down
        self.assertAlmostEqual(r["midpointPenetrationDepth_um"], 30.0, places=6)  # was 60 (layer-0 melt)
        self.assertTrue(r["hasInterTrackGap"])
        self.assertTrue(r["interTrackLackOfFusion"])

    def test_melt_touching_previous_layer_is_not_flagged(self):
        r = _run([-20e-6, 40e-6])  # layer 1 melt bottom exactly on the layer-0 surface
        self.assertAlmostEqual(r["midpointPenetrationDepth_um"], 40.0, places=6)
        self.assertFalse(r["interTrackLackOfFusion"])

    def test_both_layers_bonded(self):
        r = _run([-20e-6, 20e-6])
        self.assertAlmostEqual(r["midpointPenetrationDepth_um"], 60.0, places=6)
        self.assertFalse(r["interTrackLackOfFusion"])
        self.assertEqual(r["status"], "fused-inter-track")


if __name__ == "__main__":
    unittest.main()
