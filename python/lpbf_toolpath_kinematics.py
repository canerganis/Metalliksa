"""
lpbf_toolpath_kinematics.py — Phase 12: Rigorous LPBF Toolpath Ingestion & Scanner Kinematics
=============================================================================================
Physics-grounded Galvanometer Kinematics Engine for Laser Powder Bed Fusion (LPBF).

Theoretical References:
  1. Löber, L., et al. (2013). "Comparison of selective laser melting and selective electron beam melting."
  2. Yeung, H., et al. (2019). "Implementation of an open-source galvanometer scan engine for LPBF." NIST AM-Bench.
  3. DIN EN ISO/ASTM 52900: Additive manufacturing — General principles — Fundamentals.

Kinematics Physics:
  - Finite galvanometer acceleration/deceleration: a_max (typical: 2.0e4 to 1.0e5 mm/s^2)
  - Trapezoidal & Triangular velocity profiles
  - Mark/Jump delay intervals: Laser-on, Laser-off, Mark delay, Jump delay (microseconds)
  - Localized linear energy density (LED): E_L(s) = P(s) / v(s) [J/mm]
"""

from __future__ import annotations
import math
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple


@dataclass
class ToolpathVector:
    x_start: float
    y_start: float
    x_end: float
    y_end: float
    vector_type: str  # 'hatch', 'contour', 'jump'
    nominal_power_W: float
    nominal_speed_mms: float
    layer_idx: int = 0


@dataclass
class KinematicSegment:
    x_start: float
    y_start: float
    x_end: float
    y_end: float
    distance_mm: float
    v_start_mms: float
    v_peak_mms: float
    v_end_mms: float
    t_acc_s: float
    t_cruise_s: float
    t_dec_s: float
    t_total_s: float
    laser_active: bool
    nominal_power_W: float
    effective_energy_J: float
    avg_speed_mms: float
    avg_linear_energy_density_J_mm: float
    vector_type: str


@dataclass
class ScannerProfile:
    accel_max_mms2: float = 40000.0        # Max galvo mirror acceleration (mm/s^2)
    jump_speed_mms: float = 3000.0         # Fast positioning mirror velocity (mm/s)
    laser_on_delay_us: float = 100.0       # Time from command to optical emission (µs)
    laser_off_delay_us: float = 120.0      # Time for laser power drop (µs)
    mark_delay_us: float = 200.0           # Settling delay at end of mark vector (µs)
    jump_delay_us: float = 350.0           # Settling delay after positioning move (µs)
    skywriting_enabled: bool = False       # True: Laser only on during steady-state velocity


class LPBFToolpathParser:
    """Parses standard G-Code and Common Layer Interface (.cli) into ToolpathVectors."""

    @staticmethod
    def parse_gcode(gcode_text: str, default_power_W: float = 250.0, default_speed_mms: float = 1000.0) -> List[ToolpathVector]:
        vectors: List[ToolpathVector] = []
        curr_x, curr_y = 0.0, 0.0
        laser_on = False
        current_power = default_power_W
        current_speed = default_speed_mms
        current_layer = 0

        for line in gcode_text.splitlines():
            line = line.strip()
            if not line or line.startswith(";") or line.startswith("("):
                if "LAYER:" in line.upper():
                    m = re.search(r"LAYER:\s*(\d+)", line, re.IGNORECASE)
                    if m:
                        current_layer = int(m.group(1))
                continue

            # Command extraction
            parts = line.split()
            cmd = parts[0].upper()

            # Laser state checks
            if cmd in ("M3", "M03"):
                laser_on = True
                # Parse power if provided (e.g. S250)
                for p in parts[1:]:
                    if p.upper().startswith("S"):
                        try:
                            current_power = float(p[1:])
                        except ValueError:
                            pass
                continue
            elif cmd in ("M5", "M05"):
                laser_on = False
                continue

            # Motion commands
            if cmd in ("G0", "G00", "G1", "G01"):
                new_x, new_y = curr_x, curr_y
                for p in parts[1:]:
                    p_up = p.upper()
                    if p_up.startswith("X"):
                        try: new_x = float(p[1:])
                        except ValueError: pass
                    elif p_up.startswith("Y"):
                        try: new_y = float(p[1:])
                        except ValueError: pass
                    elif p_up.startswith("F"):
                        try:
                            # Feedrate in mm/min, convert to mm/s
                            current_speed = float(p[1:]) / 60.0
                        except ValueError: pass
                    elif p_up.startswith("S"):
                        try: current_power = float(p[1:])
                        except ValueError: pass

                dist = math.hypot(new_x - curr_x, new_y - curr_y)
                if dist > 1e-6:
                    is_jump = (cmd in ("G0", "G00")) or (not laser_on)
                    v_type = "jump" if is_jump else "hatch"
                    vectors.append(ToolpathVector(
                        x_start=curr_x,
                        y_start=curr_y,
                        x_end=new_x,
                        y_end=new_y,
                        vector_type=v_type,
                        nominal_power_W=0.0 if is_jump else current_power,
                        nominal_speed_mms=current_speed if not is_jump else 3000.0,
                        layer_idx=current_layer
                    ))
                    curr_x, curr_y = new_x, new_y

        return vectors

    @staticmethod
    def parse_cli(cli_text: str, default_power_W: float = 250.0, default_speed_mms: float = 1000.0) -> List[ToolpathVector]:
        """Parses ASCII CLI (Common Layer Interface) format for LPBF."""
        vectors: List[ToolpathVector] = []
        current_layer = 0
        layer_scale = 1.0  # CLI units are often in 0.01 mm or 0.1 mm

        for line in cli_text.splitlines():
            line = line.strip()
            if not line:
                continue

            if line.startswith("$$UNITS/"):
                try:
                    layer_scale = float(line.split("/")[1].strip())
                except (IndexError, ValueError):
                    layer_scale = 1.0
            elif line.startswith("$$LAYER/"):
                try:
                    current_layer += 1
                except ValueError:
                    pass
            elif line.startswith("$$HATCHES/") or line.startswith("$$POLYLINE/"):
                # Format: $$HATCHES/id, n, x1, y1, x2, y2, ...
                prefix, data = line.split("/", 1)
                tokens = [t.strip() for t in data.split(",") if t.strip()]
                if len(tokens) >= 5:
                    is_hatch = "HATCHES" in prefix
                    # Skip id and count
                    coords = [float(c) * layer_scale for c in tokens[2:]]
                    for i in range(0, len(coords) - 3, 4):
                        x1, y1, x2, y2 = coords[i], coords[i+1], coords[i+2], coords[i+3]
                        if math.hypot(x2 - x1, y2 - y1) > 1e-6:
                            vectors.append(ToolpathVector(
                                x_start=x1, y_start=y1,
                                x_end=x2, y_end=y2,
                                vector_type="hatch" if is_hatch else "contour",
                                nominal_power_W=default_power_W,
                                nominal_speed_mms=default_speed_mms,
                                layer_idx=current_layer
                            ))
        return vectors


class GalvanometerKinematicsEngine:
    """Computes exact time, acceleration, velocity profiles, and thermal energy density."""

    def __init__(self, profile: Optional[ScannerProfile] = None):
        self.profile = profile or ScannerProfile()

    def simulate_vector(self, vec: ToolpathVector) -> KinematicSegment:
        p = self.profile
        dx = vec.x_end - vec.x_start
        dy = vec.y_end - vec.y_start
        dist = math.hypot(dx, dy)

        if dist < 1e-7:
            return KinematicSegment(
                x_start=vec.x_start, y_start=vec.y_start,
                x_end=vec.x_end, y_end=vec.y_end,
                distance_mm=0.0,
                v_start_mms=0.0, v_peak_mms=0.0, v_end_mms=0.0,
                t_acc_s=0.0, t_cruise_s=0.0, t_dec_s=0.0, t_total_s=0.0,
                laser_active=False, nominal_power_W=0.0, effective_energy_J=0.0,
                avg_speed_mms=0.0, avg_linear_energy_density_J_mm=0.0,
                vector_type=vec.vector_type
            )

        v_target = p.jump_speed_mms if vec.vector_type == "jump" else vec.nominal_speed_mms
        a_max = p.accel_max_mms2

        # Distance needed to reach target velocity from rest: d_acc = v^2 / (2 * a)
        d_acc = (v_target ** 2) / (2.0 * a_max)
        is_laser_on = (vec.vector_type != "jump") and (vec.nominal_power_W > 0)

        # Delays in seconds
        delays_s = 0.0
        if vec.vector_type == "jump":
            delays_s = p.jump_delay_us * 1e-6
        else:
            delays_s = (p.laser_on_delay_us + p.mark_delay_us) * 1e-6

        if 2.0 * d_acc <= dist:
            # Trapezoidal profile: acceleration -> cruise -> deceleration
            v_peak = v_target
            t_acc = v_peak / a_max
            t_dec = t_acc
            d_cruise = dist - 2.0 * d_acc
            t_cruise = d_cruise / v_peak
        else:
            # Triangular profile: vector too short to reach nominal speed
            v_peak = math.sqrt(dist * a_max)
            t_acc = v_peak / a_max
            t_dec = t_acc
            t_cruise = 0.0

        t_motion = t_acc + t_cruise + t_dec
        t_total = t_motion + delays_s

        # Energy calculation:
        # If skywriting is enabled, laser only fires during cruise.
        # Otherwise, laser fires through acc/dec causing localized energy spikes!
        power = vec.nominal_power_W if is_laser_on else 0.0
        if not is_laser_on or power <= 0:
            effective_energy_J = 0.0
            avg_led_J_mm = 0.0
        else:
            if p.skywriting_enabled:
                # Ideal skywriting: constant power at constant speed
                laser_time_s = t_cruise
            else:
                # Standard LPBF: laser active during ramp-up and ramp-down
                laser_time_s = t_motion + (p.laser_on_delay_us * 1e-6)
            effective_energy_J = power * laser_time_s
            avg_led_J_mm = effective_energy_J / dist if dist > 0 else 0.0

        avg_speed = dist / t_motion if t_motion > 0 else 0.0

        return KinematicSegment(
            x_start=vec.x_start, y_start=vec.y_start,
            x_end=vec.x_end, y_end=vec.y_end,
            distance_mm=dist,
            v_start_mms=0.0,
            v_peak_mms=v_peak,
            v_end_mms=0.0,
            t_acc_s=t_acc,
            t_cruise_s=t_cruise,
            t_dec_s=t_dec,
            t_total_s=t_total,
            laser_active=is_laser_on,
            nominal_power_W=power,
            effective_energy_J=effective_energy_J,
            avg_speed_mms=avg_speed,
            avg_linear_energy_density_J_mm=avg_led_J_mm,
            vector_type=vec.vector_type
        )

    def simulate_toolpath(self, vectors: List[ToolpathVector]) -> Dict[str, Any]:
        """Simulates an entire toolpath sequence and aggregates timing and thermal accumulation."""
        segments: List[KinematicSegment] = []
        total_time_s = 0.0
        total_laser_time_s = 0.0
        total_energy_J = 0.0
        total_mark_dist_mm = 0.0
        total_jump_dist_mm = 0.0

        for vec in vectors:
            seg = self.simulate_vector(vec)
            segments.append(seg)
            total_time_s += seg.t_total_s
            if seg.laser_active:
                # Count only the time the energy model actually charges, so the
                # duty cycle and the energy total describe the same exposure.
                if self.profile.skywriting_enabled:
                    total_laser_time_s += seg.t_cruise_s
                else:
                    total_laser_time_s += (seg.t_acc_s + seg.t_cruise_s + seg.t_dec_s
                                           + self.profile.laser_on_delay_us * 1e-6)
                total_energy_J += seg.effective_energy_J
                total_mark_dist_mm += seg.distance_mm
            else:
                total_jump_dist_mm += seg.distance_mm

        # Average-LED screen flags: segments whose average LED exceeds 1.25x nominal (no thermal field is solved)
        hotspots = []
        for i, s in enumerate(segments):
            if s.laser_active:
                nominal_led = (s.nominal_power_W / (vectors[i].nominal_speed_mms or 1.0))
                # If deceleration/acceleration causes LED to spike > 1.25x nominal
                if s.avg_linear_energy_density_J_mm > nominal_led * 1.25:
                    hotspots.append({
                        "segment_index": i,
                        "x": (s.x_start + s.x_end) / 2.0,
                        "y": (s.y_start + s.y_end) / 2.0,
                        "nominal_led_J_mm": round(nominal_led, 4),
                        "actual_led_J_mm": round(s.avg_linear_energy_density_J_mm, 4),
                        "overheating_ratio": round(s.avg_linear_energy_density_J_mm / max(nominal_led, 1e-4), 2),
                        "cause": "short_vector_acceleration_limit" if s.t_cruise_s == 0 else "turnaround_delay"
                    })

        duty_cycle_pct = (total_laser_time_s / total_time_s * 100.0) if total_time_s > 0 else 0.0

        # Segments where the vector is too short to reach cruise speed (cruise ~ 0).
        # Under skywriting the laser only fires during cruise, so these never fire:
        # zero energy / zero hotspots there means "laser never fires", NOT "mitigated".
        mark_segments = [s for s in segments if s.laser_active]
        no_cruise_count = sum(1 for s in mark_segments if s.t_cruise_s <= 1e-9)
        warnings: List[str] = []
        if mark_segments and no_cruise_count > 0:
            frac = no_cruise_count / len(mark_segments)
            if self.profile.skywriting_enabled:
                warnings.append(
                    f"{no_cruise_count} of {len(mark_segments)} marking vectors have no constant-velocity "
                    "cruise phase; with skywriting the laser never fires on them (0 J deposited). "
                    "Zero hotspots here means no exposure, not a mitigated exposure."
                )
            else:
                warnings.append(
                    f"{no_cruise_count} of {len(mark_segments)} marking vectors never reach their "
                    "commanded speed (triangular velocity profile); delivered LED differs from nominal."
                )
            if frac >= 0.999 and self.profile.skywriting_enabled:
                warnings.append("The laser never fires anywhere in this toolpath under skywriting.")

        return {
            "total_segments": len(segments),
            "total_build_time_s": round(total_time_s, 4),
            "total_laser_on_time_s": round(total_laser_time_s, 4),
            "duty_cycle_pct": round(duty_cycle_pct, 2),
            "total_energy_input_J": round(total_energy_J, 2),
            "total_mark_distance_mm": round(total_mark_dist_mm, 2),
            "total_jump_distance_mm": round(total_jump_dist_mm, 2),
            "hotspot_count": len(hotspots),
            "hotspots": hotspots[:50],  # Return top 50 critical hotspots
            "skywriting_mitigation_active": self.profile.skywriting_enabled,
            "no_cruise_segment_count": no_cruise_count,
            "marking_segment_count": len(mark_segments),
            "laser_never_fires": bool(mark_segments) and total_energy_J <= 0.0 and self.profile.skywriting_enabled,
            "warnings": warnings,
        }
