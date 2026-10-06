import numpy as np
import pytest

from lpbf_peak import PeakMeltTracker


def _rectangular_liquidus_field(x, y, z, bounds, liquidus):
    x_bounds, y_bounds, z_bounds = bounds
    excess = np.minimum.reduce((
        x_bounds[1]-x, x-x_bounds[0], y_bounds[1]-y, y-y_bounds[0],
        z_bounds[1]-z, z-z_bounds[0]))
    return (liquidus+excess).ravel()


def _independent_edge_oracle(coordinates, temperature, dx, surface, liquidus):
    """Independent structured-grid edge walk for a manufactured liquidus box."""
    xyz = np.asarray(coordinates, dtype=float)
    axes = [np.unique(xyz[:, axis]) for axis in range(3)]
    shape = tuple(len(axis) for axis in axes)
    values = np.asarray(temperature, dtype=float).reshape(shape)
    points = xyz.reshape((*shape, 3))
    active = points[..., 2] < surface
    molten = (values >= liquidus) & active
    assert not (molten[0].any() or molten[-1].any() or molten[:, 0].any()
                or molten[:, -1].any() or molten[:, :, 0].any())
    crossings = []
    for i in range(shape[0]):
        for j in range(shape[1]):
            for k in range(shape[2]):
                for axis in range(3):
                    index = [i, j, k]
                    if index[axis]+1 >= shape[axis]:
                        continue
                    other = index.copy()
                    other[axis] += 1
                    a, b = tuple(index), tuple(other)
                    if active[a] and active[b] and ((values[a] >= liquidus) != (values[b] >= liquidus)):
                        fraction = (liquidus-values[a])/(values[b]-values[a])
                        crossings.append(points[a]+fraction*(points[b]-points[a]))
    crossings = np.asarray(crossings)
    return float(np.ptp(crossings[:, 1])*1e6), float((surface-crossings[:, 2].min())*1e6)


def test_opt_in_tied_contours_match_independent_manufactured_oracle():
    liquidus, dx = 1700.0, 10e-6
    axes = [np.arange(-50e-6, 51e-6, dx), np.arange(-50e-6, 51e-6, dx),
            np.arange(-100e-6, 1e-6, dx)]
    x, y, z = np.meshgrid(*axes, indexing="ij")
    coordinates = np.column_stack((x.ravel(), y.ravel(), z.ravel()))
    material = {"liquidus_K": liquidus, "solidus_K": liquidus-100.0}
    tracker = PeakMeltTracker(coordinates, dx, material, track_tied_contours=True)
    first = _rectangular_liquidus_field(x, y, z,
                                        ((-12e-6, 8e-6), (-15e-6, 15e-6),
                                         (-55e-6, -25e-6)), liquidus)
    second = _rectangular_liquidus_field(x, y, z,
                                         ((-15e-6, 15e-6), (-12e-6, 8e-6),
                                          (-55e-6, -25e-6)), liquidus)
    for index, field in enumerate((first, second, first)):
        tracker.observe(field, 0.0, 0.0, index*1e-6, index+1)
    metrics, diagnostics = tracker.finish(None, 3)
    baseline = PeakMeltTracker(coordinates, dx, material)
    for index, field in enumerate((first, second, first)):
        baseline.observe(field, 0.0, 0.0, index*1e-6, index+1)
    baseline_metrics, baseline_diagnostics = baseline.finish(None, 3)

    diagnostic = diagnostics["tiedPeakContourSpread"]
    oracle = [_independent_edge_oracle(coordinates, field, dx, 0.0, liquidus)
              for field in (first, second, first)]
    assert [len(np.flatnonzero(field >= liquidus)) for field in (first, second, first)] == [18, 18, 18]
    assert diagnostic["endpointCount"] == diagnostic["observedContourCount"] == 3
    assert diagnostic["width_um"]["min"] == pytest.approx(20.0)
    assert diagnostic["width_um"]["median"] == pytest.approx(30.0)
    assert diagnostic["width_um"]["max"] == pytest.approx(30.0)
    assert diagnostic["depth_um"]["min"] == pytest.approx(55.0)
    assert diagnostic["depth_um"]["median"] == pytest.approx(55.0)
    assert diagnostic["depth_um"]["max"] == pytest.approx(55.0)
    assert diagnostic["first"]["width_um"] == pytest.approx(oracle[0][0])
    assert diagnostic["last"]["width_um"] == pytest.approx(oracle[-1][0])
    assert oracle[0] == pytest.approx((30.0, 55.0))
    assert oracle[1] == pytest.approx((20.0, 55.0))
    assert metrics["width_um"] == pytest.approx(30.0)
    assert metrics == baseline_metrics
    assert {key: diagnostics[key] for key in baseline_diagnostics} == baseline_diagnostics


def test_tied_contour_tracking_is_off_by_default_and_first_state_is_preserved():
    liquidus, dx = 1700.0, 10e-6
    axes = [np.arange(-40e-6, 41e-6, dx), np.arange(-40e-6, 41e-6, dx),
            np.arange(-100e-6, 1e-6, dx)]
    x, y, z = np.meshgrid(*axes, indexing="ij")
    coordinates = np.column_stack((x.ravel(), y.ravel(), z.ravel()))
    material = {"liquidus_K": liquidus, "solidus_K": liquidus-100.0}
    field = _rectangular_liquidus_field(
        x, y, z, ((-12e-6, 8e-6), (-15e-6, 15e-6), (-55e-6, -25e-6)), liquidus)
    tracker = PeakMeltTracker(coordinates, dx, material)
    tracker.observe(field, 0.0, 0.0, 1e-6, 1)
    tracker.observe(field, 0.0, 0.0, 2e-6, 2)
    metrics, diagnostics = tracker.finish(None, 2)
    assert "tiedPeakContourSpread" not in diagnostics
    assert diagnostics["peakMeltStep"] == 1
    assert diagnostics["equalMaximumEndpointCount"] == 2
    assert metrics["width_um"] == pytest.approx(30.0)
