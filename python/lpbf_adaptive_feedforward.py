"""
lpbf_adaptive_feedforward.py — Phase 15: Open-Loop Feed-Forward Power Scaling
==============================================================================
Open-loop (no sensor feedback) per-vector laser power scaling plus optional scan rotation.

Model (screening only, not machine-validated):
  1. Per-vector power scaling from the kinematic peak speed of each vector:
       P_vector = P_nominal * min(1, v_peak / v_nominal)
     One constant S-word per vector; power is NOT ramped along the acceleration /
     deceleration phases inside a vector.
  2. Optional rotation of the toolpath by 67 deg x layer_index about the origin.
     No microstructure or texture effect is computed.
  3. G-code export with one S-word per marking vector; travel moves are emitted
     with an explicit S0 so the laser is commanded off during G0 jumps.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional
from lpbf_toolpath_kinematics import LPBFToolpathParser, ToolpathVector, ScannerProfile, GalvanometerKinematicsEngine


@dataclass
class MitigatedSegment:
    x_start: float
    y_start: float
    x_end: float
    y_end: float
    nominal_power_W: float
    nominal_speed_mms: float
    actual_avg_speed_mms: float
    compensated_power_W: float
    nominal_led_J_mm: float
    mitigated_led_J_mm: float
    energy_saved_pct: float
    is_mitigated: bool
    gcode_command: str


class AdaptiveFeedforwardMitigator:
    """Open-loop per-vector power scaling from scanner kinematics (no sensor feedback)."""

    def __init__(self, profile: Optional[ScannerProfile] = None):
        self.profile = profile or ScannerProfile()
        self.kinematics = GalvanometerKinematicsEngine(self.profile)

    def compensate_vector(self, vec: ToolpathVector) -> MitigatedSegment:
        seg = self.kinematics.simulate_vector(vec)
        dx = vec.x_end - vec.x_start
        dy = vec.y_end - vec.y_start
        dist = math.hypot(dx, dy)

        if not seg.laser_active or dist < 1e-6 or vec.nominal_speed_mms < 1e-6:
            return MitigatedSegment(
                x_start=vec.x_start, y_start=vec.y_start,
                x_end=vec.x_end, y_end=vec.y_end,
                nominal_power_W=0.0,
                nominal_speed_mms=vec.nominal_speed_mms,
                actual_avg_speed_mms=seg.avg_speed_mms,
                compensated_power_W=0.0,
                nominal_led_J_mm=0.0,
                mitigated_led_J_mm=0.0,
                energy_saved_pct=0.0,
                is_mitigated=False,
                gcode_command=f"G0 X{vec.x_end:.3f} Y{vec.y_end:.3f} S0"
            )

        nom_led = vec.nominal_power_W / vec.nominal_speed_mms
        actual_avg_v = seg.avg_speed_mms

        # Inverse Kinematic Compensation based on achievable peak velocity:
        # P_comp = P_nom * min(1.0, v_peak / v_nom)
        speed_ratio = min(1.0, seg.v_peak_mms / vec.nominal_speed_mms)
        compensated_power = vec.nominal_power_W * speed_ratio

        # Linear energy density at the scaled power and peak speed
        mitigated_led = compensated_power / max(seg.v_peak_mms, 1e-4)

        is_mitigated = speed_ratio < 0.99
        energy_saved = (1.0 - speed_ratio) * 100.0 if is_mitigated else 0.0

        # Generate compensated G-code line
        feedrate_min = vec.nominal_speed_mms * 60.0
        gcode = f"G1 X{vec.x_end:.3f} Y{vec.y_end:.3f} S{compensated_power:.1f} F{feedrate_min:.0f}"

        return MitigatedSegment(
            x_start=vec.x_start, y_start=vec.y_start,
            x_end=vec.x_end, y_end=vec.y_end,
            nominal_power_W=vec.nominal_power_W,
            nominal_speed_mms=vec.nominal_speed_mms,
            actual_avg_speed_mms=round(actual_avg_v, 2),
            compensated_power_W=round(compensated_power, 1),
            nominal_led_J_mm=round(nom_led, 4),
            mitigated_led_J_mm=round(mitigated_led, 4),
            energy_saved_pct=round(energy_saved, 1),
            is_mitigated=is_mitigated,
            gcode_command=gcode
        )

    def process_toolpath(
        self,
        vectors: List[ToolpathVector],
        apply_67_deg_rotation: bool = False,
        layer_index: int = 1
    ) -> Dict[str, Any]:
        """Processes entire toolpath, applies adaptive power scaling and rotation."""
        processed_vectors: List[ToolpathVector] = []

        # Interlayer rotation by 67.0 degrees
        rot_angle_rad = math.radians(67.0 * layer_index) if apply_67_deg_rotation else 0.0
        cos_theta = math.cos(rot_angle_rad)
        sin_theta = math.sin(rot_angle_rad)

        for v in vectors:
            if apply_67_deg_rotation and rot_angle_rad != 0.0:
                # Rotate around origin (0, 0)
                rx_start = v.x_start * cos_theta - v.y_start * sin_theta
                ry_start = v.x_start * sin_theta + v.y_start * cos_theta
                rx_end = v.x_end * cos_theta - v.y_end * sin_theta
                ry_end = v.x_end * sin_theta + v.y_end * cos_theta
                processed_vectors.append(ToolpathVector(
                    x_start=rx_start, y_start=ry_start,
                    x_end=rx_end, y_end=ry_end,
                    vector_type=v.vector_type,
                    nominal_power_W=v.nominal_power_W,
                    nominal_speed_mms=v.nominal_speed_mms,
                    layer_idx=layer_index
                ))
            else:
                processed_vectors.append(v)

        mitigated_segments: List[MitigatedSegment] = []
        mitigated_count = 0
        total_nominal_energy_J = 0.0
        total_mitigated_energy_J = 0.0
        gcode_lines = [
            f"; Metalliksa per-vector power-scaled toolpath (Layer {layer_index})",
            f"; Rotation: {math.degrees(rot_angle_rad):.1f} deg | Open-loop per-vector power scaling",
            "; NOT machine-validated: review S-words, travel moves and controller laser mode before use",
            "M3 S0"
        ]

        for pv in processed_vectors:
            mseg = self.compensate_vector(pv)
            mitigated_segments.append(mseg)
            gcode_lines.append(mseg.gcode_command)

            if mseg.is_mitigated:
                mitigated_count += 1

            if mseg.nominal_power_W > 0:
                # E = P * (dist / v_nom)
                dist = math.hypot(pv.x_end - pv.x_start, pv.y_end - pv.y_start)
                t_nom = dist / pv.nominal_speed_mms
                total_nominal_energy_J += pv.nominal_power_W * t_nom
                total_mitigated_energy_J += mseg.compensated_power_W * t_nom

        gcode_lines.append("M5")
        gcode_lines.append("; End of power-scaled layer")

        overall_energy_reduction_pct = (
            ((total_nominal_energy_J - total_mitigated_energy_J) / max(total_nominal_energy_J, 1e-4)) * 100.0
            if total_nominal_energy_J > 0 else 0.0
        )

        return {
            "total_segments": len(mitigated_segments),
            "mitigated_hotspots_count": mitigated_count,
            "overall_energy_reduction_pct": round(overall_energy_reduction_pct, 2),
            "rotation_angle_deg": round(math.degrees(rot_angle_rad), 1),
            "total_mitigated_energy_J": round(total_mitigated_energy_J, 2),
            "mitigated_gcode": "\n".join(gcode_lines),
            "sample_segments": [
                {
                    "nominal_power_W": s.nominal_power_W,
                    "compensated_power_W": s.compensated_power_W,
                    "actual_avg_speed_mms": s.actual_avg_speed_mms,
                    "nominal_led_J_mm": s.nominal_led_J_mm,
                    "mitigated_led_J_mm": s.mitigated_led_J_mm,
                    "is_mitigated": s.is_mitigated,
                    "energy_saved_pct": s.energy_saved_pct
                } for s in mitigated_segments[:25]
            ]
        }
