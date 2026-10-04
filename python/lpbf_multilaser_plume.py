"""
LPBF Multi-Laser Synchronization & Plume Attenuation Physics Engine
Phase 16 - Metalliksa Engineering Suite

Models the fluid-optic coupling between multi-beam LPBF galvo scanners and
the inert shield gas cross-flow. Grounded in peer-reviewed literature:
- Bidare et al. (2018) "Fluid and particle dynamics in laser powder bed fusion"
- Ladewig et al. (2016) "Influence of the shielding gas flow on the removal of process by-products in SLM"
- Ly et al. (2017) "Metal vapor flux and spatter dynamics in LPBF"

Key Physics:
1. Shield Gas Advection: Laminar flow u_gas sweeps vapor plumes downstream.
2. Beer-Lambert Optical Extinction: Trailing laser beams crossing a plume suffer
   intensity attenuation: I(z) = I_0 * exp(-tau), reducing delivered energy density.
3. Proximity & Beam Intersection Hazards: Direct beam clash (keyhole blowout) and
   excessive plume shadowing (lack-of-fusion pore formation).
4. Synchronous Scheduling / De-confliction: Plume-aware delay insertion and spatial
   sequencing (downwind-first rule).
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
import math


@dataclass
class ShieldGasFlow:
    """Inert chamber shielding gas cross-flow parameters."""
    gas_type: str = "Argon"            # Argon or Nitrogen
    velocity_m_s: float = 2.0          # Cross-flow speed (m/s), typ 1.5 - 3.5 m/s
    angle_deg: float = 0.0             # Flow direction in XY plane (0 deg = +X, 90 deg = +Y)
    ambient_pressure_mbar: float = 1013.0

    @property
    def velocity_mm_s(self) -> float:
        return self.velocity_m_s * 1000.0

    @property
    def unit_vector(self) -> Tuple[float, float]:
        rad = math.radians(self.angle_deg)
        return (math.cos(rad), math.sin(rad))


@dataclass
class PlumeParameters:
    """Aerosol / vapor plume physics parameters based on Bidare & Ladewig."""
    sigma_plume_mm: float = 2.5        # Lateral Gaussian standard deviation (mm)
    decay_length_mm: float = 25.0      # Downwind exponential decay length (mm)
    base_extinction_coeff: float = 0.35 # Peak optical thickness at nominal 300W
    min_collision_dist_mm: float = 1.0 # Minimum safe physical separation between beams
    attenuation_hazard_threshold: float = 0.10 # 10% attenuation triggers hazard


@dataclass
class LaserState:
    """Instantaneous state of a laser at time t."""
    laser_id: int
    x_mm: float
    y_mm: float
    power_W: float
    is_active: bool = True


@dataclass
class TimeStepSample:
    """Computed multi-laser interaction state at a specific simulation epoch."""
    time_s: float
    lasers: List[Dict[str, Any]]
    hazard_collision: bool
    hazard_plume_attenuation: bool
    max_attenuation_pct: float
    inter_laser_distance_mm: float


class MultiLaserPlumeEngine:
    """
    Simulates multi-laser optical extinction and spatiotemporal interaction.
    """

    def __init__(
        self,
        gas_flow: Optional[ShieldGasFlow] = None,
        plume_params: Optional[PlumeParameters] = None
    ):
        self.gas_flow = gas_flow or ShieldGasFlow()
        self.plume_params = plume_params or PlumeParameters()

    def calculate_plume_extinction(
        self,
        eval_x: float,
        eval_y: float,
        source_x: float,
        source_y: float,
        source_power_W: float,
        nominal_power_W: float = 300.0
    ) -> float:
        """
        Calculates optical thickness tau at (eval_x, eval_y) caused by active
        laser at (source_x, source_y).

        Mathematical formulation:
          Let delta = eval - source
          Downwind projection xi = delta . u_gas
          Transverse normal distance d_perp = |delta x u_gas|
          tau = alpha_0 * (P / P_nom) * exp(-d_perp^2 / (2*sigma^2)) * exp(-xi / L_decay)  (for xi >= 0)
        """
        if source_power_W <= 1e-3:
            return 0.0

        dx = eval_x - source_x
        dy = eval_y - source_y
        dist = math.hypot(dx, dy)
        if dist < 1e-6:
            return 0.0

        ux, uy = self.gas_flow.unit_vector
        # Downwind distance along gas streamline
        xi = dx * ux + dy * uy
        # Perpendicular cross-stream distance
        d_perp = abs(dx * uy - dy * ux)

        # Scale optical thickness linearly with vapor mass flow rate (power above threshold)
        power_ratio = max(0.0, source_power_W / max(1.0, nominal_power_W))
        alpha_0 = self.plume_params.base_extinction_coeff * power_ratio

        sigma = self.plume_params.sigma_plume_mm
        decay_l = self.plume_params.decay_length_mm

        if xi >= 0.0:
            # Downwind plume dispersion
            tau = alpha_0 * math.exp(-(d_perp ** 2) / (2.0 * (sigma ** 2))) * math.exp(-xi / decay_l)
        else:
            # Upwind region: very limited upstream diffusion within ~1 sigma
            tau = alpha_0 * math.exp(-(dist ** 2) / (2.0 * (sigma ** 2)))

        return tau

    def evaluate_time_step(
        self,
        time_s: float,
        active_states: List[LaserState]
    ) -> TimeStepSample:
        """
        Evaluates concurrent laser positions at a given time step.
        Computes mutual plume shadowing, Beer-Lambert transmission, and hazard alerts.
        """
        n = len(active_states)
        laser_results = []
        hazard_collision = False
        hazard_plume = False
        max_attenuation = 0.0
        min_inter_dist = float("inf")

        # 1. Proximity collision check
        for i in range(n):
            for j in range(i + 1, n):
                if active_states[i].is_active and active_states[j].is_active:
                    d = math.hypot(
                        active_states[i].x_mm - active_states[j].x_mm,
                        active_states[i].y_mm - active_states[j].y_mm
                    )
                    if d < min_inter_dist:
                        min_inter_dist = d
                    if d < self.plume_params.min_collision_dist_mm:
                        hazard_collision = True

        if min_inter_dist == float("inf"):
            min_inter_dist = 999.0

        # 2. Beer-Lambert attenuation per laser
        for i, target in enumerate(active_states):
            if not target.is_active:
                laser_results.append({
                    "laser_id": target.laser_id,
                    "x_mm": target.x_mm,
                    "y_mm": target.y_mm,
                    "nominal_power_W": target.power_W,
                    "effective_power_W": 0.0,
                    "transmission": 1.0,
                    "attenuation_pct": 0.0,
                    "optical_thickness_tau": 0.0,
                    "plume_shadowed": False
                })
                continue

            tau_total = 0.0
            for j, source in enumerate(active_states):
                if i != j and source.is_active:
                    tau_total += self.calculate_plume_extinction(
                        eval_x=target.x_mm,
                        eval_y=target.y_mm,
                        source_x=source.x_mm,
                        source_y=source.y_mm,
                        source_power_W=source.power_W
                    )

            transmission = math.exp(-tau_total)
            attenuation_pct = (1.0 - transmission) * 100.0
            effective_power = target.power_W * transmission

            if attenuation_pct > max_attenuation:
                max_attenuation = attenuation_pct

            is_shadowed = (1.0 - transmission) >= self.plume_params.attenuation_hazard_threshold
            if is_shadowed:
                hazard_plume = True

            laser_results.append({
                "laser_id": target.laser_id,
                "x_mm": round(target.x_mm, 4),
                "y_mm": round(target.y_mm, 4),
                "nominal_power_W": round(target.power_W, 2),
                "effective_power_W": round(effective_power, 2),
                "transmission": round(transmission, 4),
                "attenuation_pct": round(attenuation_pct, 2),
                "optical_thickness_tau": round(tau_total, 4),
                "plume_shadowed": is_shadowed
            })

        return TimeStepSample(
            time_s=round(time_s, 6),
            lasers=laser_results,
            hazard_collision=hazard_collision,
            hazard_plume_attenuation=hazard_plume,
            max_attenuation_pct=round(max_attenuation, 2),
            inter_laser_distance_mm=round(min_inter_dist, 4)
        )

    def simulate_multitrack_scenarios(
        self,
        laser1_vectors: List[Tuple[float, float, float, float, float, float]], # (x0, y0, x1, y1, power, speed)
        laser2_vectors: List[Tuple[float, float, float, float, float, float]],
        dt_s: float = 0.001
    ) -> Dict[str, Any]:
        """
        Simulates two synchronized laser toolpaths over time, generating time series
        data of beam positions, mutual attenuation, and hazard diagnostics.
        """
        samples: List[TimeStepSample] = []
        total_time_l1 = sum(math.hypot(v[2] - v[0], v[3] - v[1]) / max(1.0, v[5]) for v in laser1_vectors)
        total_time_l2 = sum(math.hypot(v[2] - v[0], v[3] - v[1]) / max(1.0, v[5]) for v in laser2_vectors)
        max_duration = max(total_time_l1, total_time_l2, 0.001)

        def interpolate_pos(vectors, t_curr):
            cum_t = 0.0
            for (x0, y0, x1, y1, p, s) in vectors:
                seg_d = math.hypot(x1 - x0, y1 - y0)
                seg_dur = seg_d / max(1.0, s)
                if cum_t <= t_curr <= cum_t + seg_dur:
                    alpha = (t_curr - cum_t) / max(1e-9, seg_dur)
                    return True, x0 + alpha * (x1 - x0), y0 + alpha * (y1 - y0), p
                cum_t += seg_dur
            return False, 0.0, 0.0, 0.0

        # Sample synchronously
        t = 0.0
        collision_count = 0
        plume_hazard_count = 0
        total_energy_lost_J = 0.0

        # Limit total samples to 200 for clean visualization
        step = max(dt_s, max_duration / 200.0)

        while t <= max_duration:
            act1, x1, y1, p1 = interpolate_pos(laser1_vectors, t)
            act2, x2, y2, p2 = interpolate_pos(laser2_vectors, t)

            states = [
                LaserState(laser_id=1, x_mm=x1, y_mm=y1, power_W=p1, is_active=act1),
                LaserState(laser_id=2, x_mm=x2, y_mm=y2, power_W=p2, is_active=act2)
            ]
            sample = self.evaluate_time_step(t, states)
            samples.append(sample)

            if sample.hazard_collision:
                collision_count += 1
            if sample.hazard_plume_attenuation:
                plume_hazard_count += 1

            for l_res in sample.lasers:
                p_loss = l_res["nominal_power_W"] - l_res["effective_power_W"]
                total_energy_lost_J += p_loss * step

            t += step

        # Plume 2D Spatial Density Grid for UI heatmaps
        grid_res = 30
        grid_data = self.compute_spatial_plume_snapshot(
            active_lasers=[s for s in samples[len(samples)//2].lasers if s["nominal_power_W"] > 0],
            grid_size_mm=60.0,
            resolution=grid_res
        )

        return {
            "duration_s": round(max_duration, 4),
            "sample_count": len(samples),
            "collision_hazard_count": collision_count,
            "plume_hazard_count": plume_hazard_count,
            "total_energy_lost_Joules": round(total_energy_lost_J, 3),
            "max_attenuation_pct": round(max(s.max_attenuation_pct for s in samples) if samples else 0.0, 2),
            "gas_flow": {
                "velocity_m_s": self.gas_flow.velocity_m_s,
                "angle_deg": self.gas_flow.angle_deg,
                "gas_type": self.gas_flow.gas_type
            },
            "time_series": [
                {
                    "time_s": s.time_s,
                    "l1_x": s.lasers[0]["x_mm"],
                    "l1_y": s.lasers[0]["y_mm"],
                    "l1_p_eff": s.lasers[0]["effective_power_W"],
                    "l1_atten_pct": s.lasers[0]["attenuation_pct"],
                    "l2_x": s.lasers[1]["x_mm"],
                    "l2_y": s.lasers[1]["y_mm"],
                    "l2_p_eff": s.lasers[1]["effective_power_W"],
                    "l2_atten_pct": s.lasers[1]["attenuation_pct"],
                    "inter_dist_mm": s.inter_laser_distance_mm,
                    "hazard_collision": s.hazard_collision,
                    "hazard_plume": s.hazard_plume_attenuation
                }
                for s in samples
            ],
            "spatial_snapshot": grid_data
        }

    def compute_spatial_plume_snapshot(
        self,
        active_lasers: List[Dict[str, Any]],
        grid_size_mm: float = 60.0,
        resolution: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Computes a 2D scalar field of total optical thickness across the chamber
        for UI heatmap rendering.
        """
        cells = []
        half = grid_size_mm / 2.0
        step = grid_size_mm / resolution

        for r in range(resolution):
            y = -half + (r + 0.5) * step
            for c in range(resolution):
                x = -half + (c + 0.5) * step
                tau_sum = 0.0
                for l in active_lasers:
                    tau_sum += self.calculate_plume_extinction(
                        eval_x=x,
                        eval_y=y,
                        source_x=l.get("x_mm", 0.0),
                        source_y=l.get("y_mm", 0.0),
                        source_power_W=l.get("nominal_power_W", 300.0)
                    )
                cells.append({
                    "x": round(x, 2),
                    "y": round(y, 2),
                    "optical_thickness": round(tau_sum, 4),
                    "transmission": round(math.exp(-tau_sum), 4)
                })
        return cells

    def optimize_deconfliction_schedule(
        self,
        laser1_vectors: List[Tuple[float, float, float, float, float, float]],
        laser2_vectors: List[Tuple[float, float, float, float, float, float]]
    ) -> Dict[str, Any]:
        """
        Computes de-confliction: Applies downwind-first vector sequencing or an
        inertial delay to eliminate plume crossings and collision hazards.
        """
        ux, uy = self.gas_flow.unit_vector

        # Calculate projection of each vector centroid onto gas flow direction
        def centroid_proj(v):
            cx = (v[0] + v[2]) / 2.0
            cy = (v[1] + v[3]) / 2.0
            return cx * ux + cy * uy

        # Unmitigated simulation
        unmitigated = self.simulate_multitrack_scenarios(laser1_vectors, laser2_vectors)

        # De-confliction strategy:
        # Sort vectors in downwind-first order (highest projection on gas flow first)
        # so downstream regions solidify before upstream plumes pass over them
        mitigated_l1 = sorted(laser1_vectors, key=centroid_proj, reverse=True)
        mitigated_l2 = sorted(laser2_vectors, key=centroid_proj, reverse=True)

        # Calculate time required for plume to decay downstream
        tau_clearance_s = (self.plume_params.decay_length_mm / self.gas_flow.velocity_mm_s) * 1.5

        # Also apply a staggered start delay of tau_clearance if initial beams start too close
        d_initial = math.hypot(mitigated_l1[0][0] - mitigated_l2[0][0], mitigated_l1[0][1] - mitigated_l2[0][1])
        stagger_delay_s = tau_clearance_s if d_initial < 15.0 else 0.0

        # Run mitigated simulation (staggered by prepending a zero-power jump)
        if stagger_delay_s > 0:
            # Prepend stationary dwell or zero-power jump for Laser 2
            delayed_l2 = [(mitigated_l2[0][0], mitigated_l2[0][1], mitigated_l2[0][0], mitigated_l2[0][1], 0.0, 1000.0)] + mitigated_l2
        else:
            delayed_l2 = mitigated_l2

        mitigated = self.simulate_multitrack_scenarios(mitigated_l1, delayed_l2)

        energy_saved_J = max(0.0, unmitigated["total_energy_lost_Joules"] - mitigated["total_energy_lost_Joules"])
        hazard_reduced = max(0, unmitigated["plume_hazard_count"] - mitigated["plume_hazard_count"])

        return {
            "unmitigated": unmitigated,
            "mitigated": mitigated,
            "stagger_delay_applied_ms": round(stagger_delay_s * 1000.0, 2),
            "energy_loss_reduction_J": round(energy_saved_J, 3),
            "plume_hazard_reduction_count": hazard_reduced,
            "attenuation_drop_pct": round(max(0.0, unmitigated["max_attenuation_pct"] - mitigated["max_attenuation_pct"]), 2),
            "downwind_first_reordered": True
        }
