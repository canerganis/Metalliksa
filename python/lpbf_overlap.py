"""Field-based LPBF inter-track overlap, remelting, and fusion continuity diagnostics.

Calculates actual overlap volume, inter-track gaps, and remelting fractions directly
from the 3D cell enthalpy/temperature field, without relying on idealized geometric
assumptions. Model ID: field-inter-track-overlap-v1.
"""
import math
import numpy as np

OVERLAP_MODEL_ID = "field-inter-track-overlap-v1"


class FieldOverlapTracker:
    """Tracks per-track molten cell envelopes and computes field-based overlap metrics."""

    def __init__(self, coordinates, dx, material, settings):
        self.xyz = np.asarray(coordinates, dtype=float)
        self.dx = float(dx)
        self.m = material
        self.p = settings
        self.tracks = int(self.p.get("tracks", 1))
        self.layers = int(self.p.get("layers", 1))
        self.hatch_m = float(self.p.get("hatch_um", 100.0)) * 1e-6
        self.layer_m = float(self.p.get("layer_um", 40.0)) * 1e-6
        self.track_length_m = float(self.p.get("trackLength_um", 600.0)) * 1e-6
        self.liquidus_K = float(material["liquidus_K"])
        self.solidus_K = float(material["solidus_K"])

        # Per (layer, track) molten cell boolean masks of length N
        self.track_melt = {}
        # Global cumulative masks
        self.ever_melted = np.zeros(len(self.xyz), dtype=bool)
        self.remelted = np.zeros(len(self.xyz), dtype=bool)
        self.was_melted = np.zeros(len(self.xyz), dtype=bool)

    def observe(self, temperature, surface, active_layer, active_track):
        """Record molten cells during active scan of (active_layer, active_track)."""
        temp = np.asarray(temperature, dtype=float).ravel()
        active = self.xyz[:, 2] < surface
        molten = (temp >= self.liquidus_K) & active

        # Track remelting: molten now, melted before, but wasn't molten in previous step
        self.remelted |= molten & self.ever_melted & ~self.was_melted
        self.ever_melted |= molten
        self.was_melted = molten

        key = (int(active_layer), int(active_track))
        if key not in self.track_melt:
            self.track_melt[key] = np.zeros(len(self.xyz), dtype=bool)
        self.track_melt[key] |= molten

    def finish(self, artifact_dir=None):
        """Compute field-based overlap, inter-track gap, and remelt metrics."""
        cell_vol_m3 = self.dx ** 3
        cell_vol_um3 = cell_vol_m3 * 1e18

        total_melted_cells = int(np.count_nonzero(self.ever_melted))
        total_remelted_cells = int(np.count_nonzero(self.remelted))
        total_melt_volume_um3 = total_melted_cells * cell_vol_um3
        total_remelt_volume_um3 = total_remelted_cells * cell_vol_um3
        global_remelt_ratio = (
            float(total_remelted_cells / total_melted_cells)
            if total_melted_cells > 0 else 0.0
        )

        # 1. Single-track case: inter-track overlap is not applicable
        if self.tracks <= 1:
            substrate_mask = self.xyz[:, 2] < 0
            substrate_melted = self.ever_melted & substrate_mask
            sub_count = int(np.count_nonzero(substrate_melted))
            inter_layer_remelt_ratio = (
                float(sub_count / total_melted_cells) if total_melted_cells > 0 else 0.0
            )
            pen_depth_um = (
                max(0.0, -float(self.xyz[substrate_melted, 2].min()) + self.dx * 0.5) * 1e6
                if sub_count > 0 else 0.0
            )

            metrics = {
                "modelId": OVERLAP_MODEL_ID,
                "scope": "single-track",
                "tracks": 1,
                "layers": self.layers,
                "trackOverlapRatio": None,
                "meanInterTrackOverlapRatio": None,
                "minInterTrackOverlapRatio": None,
                "interTrackGapVolume_um3": 0.0,
                "hasInterTrackGap": False,
                "interTrackLackOfFusion": False,
                "interLayerPenetrationDepth_um": pen_depth_um,
                "interLayerRemeltRatio": inter_layer_remelt_ratio,
                "globalRemeltRatio": global_remelt_ratio,
                "totalMeltVolume_um3": total_melt_volume_um3,
                "totalRemeltVolume_um3": total_remelt_volume_um3,
                "status": "single-track-evaluated",
                "note": "Single track simulation; inter-track overlap requires >= 2 tracks.",
            }
            return metrics

        # 2. Multi-track case: evaluate inter-track overlap and fusion gaps
        pairwise_overlaps = []
        gap_volume_um3_total = 0.0
        has_any_gap = False
        min_midpoint_penetration_um = float("inf")
        layer_melt_masks = {}
        for (track_layer, _track), mask in self.track_melt.items():
            if track_layer in layer_melt_masks:
                layer_melt_masks[track_layer] = layer_melt_masks[track_layer] | mask
            else:
                layer_melt_masks[track_layer] = mask.copy()
        empty_mask = np.zeros(len(self.xyz), dtype=bool)
        for layer in range(self.layers):
            layer_melt_masks.setdefault(layer, empty_mask)

        for layer in range(self.layers):
            theta = math.radians(
                float(self.p.get("scanAngle_deg", 0.0)) + layer * float(self.p.get("layerRotation_deg", 67.0))
            )
            cos_t, sin_t = math.cos(theta), math.sin(theta)

            x = self.xyz[:, 0]
            y = self.xyz[:, 1]
            z = self.xyz[:, 2]
            u_coords = x * cos_t + y * sin_t
            v_coords = -x * sin_t + y * cos_t

            layer_bottom_m = layer * self.layer_m
            layer_top_m = (layer + 1) * self.layer_m

            for track in range(self.tracks - 1):
                mask_a = self.track_melt.get((layer, track))
                mask_b = self.track_melt.get((layer, track + 1))

                vol_a = int(np.count_nonzero(mask_a)) if mask_a is not None else 0
                vol_b = int(np.count_nonzero(mask_b)) if mask_b is not None else 0

                if mask_a is not None and mask_b is not None:
                    overlap_mask = mask_a & mask_b
                    overlap_cells = int(np.count_nonzero(overlap_mask))
                    min_track_vol = min(vol_a, vol_b)
                    ratio = float(overlap_cells / min_track_vol) if min_track_vol > 0 else 0.0
                    pairwise_overlaps.append(ratio)
                else:
                    pairwise_overlaps.append(0.0)

                # Inter-track corridor between track centers
                v_a = (track - (self.tracks - 1) / 2.0) * self.hatch_m
                v_b = (track + 1 - (self.tracks - 1) / 2.0) * self.hatch_m
                v_min, v_max = min(v_a, v_b), max(v_a, v_b)
                v_mid = 0.5 * (v_min + v_max)

                # Core region middle 80%
                u_margin = 0.1 * self.track_length_m
                u_min = -0.5 * self.track_length_m + u_margin
                u_max = 0.5 * self.track_length_m - u_margin

                # Cells inside powder layer in inter-track corridor
                in_corridor = (
                    (v_coords >= v_min) & (v_coords <= v_max) &
                    (u_coords >= u_min) & (u_coords <= u_max) &
                    (z >= layer_bottom_m - 1e-12) & (z < layer_top_m - 1e-12)
                )

                unmelted_in_corridor = in_corridor & ~self.ever_melted
                unmelted_count = int(np.count_nonzero(unmelted_in_corridor))
                if unmelted_count > 0:
                    has_any_gap = True
                    gap_volume_um3_total += unmelted_count * cell_vol_um3

                # Midpoint penetration depth check: only cells melted while this layer's own tracks
                # were active count (a later layer's deeper pool must not stand in for this layer).
                half_band = max(self.dx * 0.6, 0.1 * self.hatch_m)
                layer_melt = layer_melt_masks[layer]
                mid_cells = (
                    (np.abs(v_coords - v_mid) <= half_band) &
                    (u_coords >= u_min) & (u_coords <= u_max) &
                    layer_melt
                )
                if np.any(mid_cells):
                    deepest_mid_z = float(z[mid_cells].min())
                    mid_pen_um = max(0.0, layer_top_m - deepest_mid_z + self.dx * 0.5) * 1e6
                    min_midpoint_penetration_um = min(min_midpoint_penetration_um, mid_pen_um)
                else:
                    min_midpoint_penetration_um = 0.0

        if math.isinf(min_midpoint_penetration_um):
            min_midpoint_penetration_um = 0.0

        mean_overlap = float(np.mean(pairwise_overlaps)) if pairwise_overlaps else 0.0
        min_overlap = float(np.min(pairwise_overlaps)) if pairwise_overlaps else 0.0

        # Substrate/inter-layer penetration across entire build
        substrate_mask = self.xyz[:, 2] < 0
        substrate_melted = self.ever_melted & substrate_mask
        sub_count = int(np.count_nonzero(substrate_melted))
        inter_layer_remelt_ratio = (
            float(sub_count / total_melted_cells) if total_melted_cells > 0 else 0.0
        )
        pen_depth_um = (
            max(0.0, -float(self.xyz[substrate_melted, 2].min()) + self.dx * 0.5) * 1e6
            if sub_count > 0 else 0.0
        )

        # 1e-6 um tolerance: a melt bottom on the previous layer surface (cell-centre + dx/2) must not
        # read as 39.999999 < 40 from float round-off.
        lof_screened = has_any_gap or (min_midpoint_penetration_um < float(self.p.get("layer_um", 40.0)) - 1e-6)

        metrics = {
            "modelId": OVERLAP_MODEL_ID,
            "scope": "multi-track-field",
            "tracks": self.tracks,
            "layers": self.layers,
            "trackOverlapRatio": min_overlap,
            "meanInterTrackOverlapRatio": mean_overlap,
            "minInterTrackOverlapRatio": min_overlap,
            "pairwiseOverlapRatios": pairwise_overlaps,
            "interTrackGapVolume_um3": gap_volume_um3_total,
            "hasInterTrackGap": has_any_gap,
            "interTrackLackOfFusion": lof_screened,
            "midpointPenetrationDepth_um": min_midpoint_penetration_um,
            "interLayerPenetrationDepth_um": pen_depth_um,
            "interLayerRemeltRatio": inter_layer_remelt_ratio,
            "globalRemeltRatio": global_remelt_ratio,
            "totalMeltVolume_um3": total_melt_volume_um3,
            "totalRemeltVolume_um3": total_remelt_volume_um3,
            "status": "lack-of-fusion-gap" if has_any_gap else "fused-inter-track",
            "note": (
                "Inter-track lack of fusion gap detected between adjacent tracks."
                if has_any_gap
                else "Adjacent tracks form continuous fused volume across hatch spacing."
            ),
        }
        return metrics
