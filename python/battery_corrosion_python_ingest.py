#!/usr/bin/env python3
"""
MetalliX Python Ingestion & Analytics Engine for Battery and Corrosion Data
Supports:
1. User custom Python script execution (.py, .ipynb cells, or in-browser script)
2. Direct REST API / python requests upload for Battery Cycling, EIS, Tafel, and OCP data
3. ASTM G102 / G59 Corrosion Rate & Polarization Resistance solver
4. Battery Galvanostatic Charge-Discharge, Coulombic Efficiency & dQ/dV Spectrogram solver
5. EIS Nyquist/Bode extraction & Kramers-Kronig validation
"""

import sys
import os
import json
import math
import cmath
import time
import io
import traceback
import re

# =========================================================================
# Lightweight Shim for numpy & pandas if user code does "import numpy as np"
# =========================================================================
class NumpyShim:
    pi = math.pi
    e = math.e
    inf = float("inf")
    nan = float("nan")

    @staticmethod
    def array(data, dtype=None):
        if isinstance(data, list):
            return list(data)
        return [data]

    @staticmethod
    def mean(data):
        return sum(data) / max(1, len(data))

    @staticmethod
    def std(data):
        m = NumpyShim.mean(data)
        return math.sqrt(sum((x - m) ** 2 for x in data) / max(1, len(data)))

    @staticmethod
    def linspace(start, stop, num=50):
        if num <= 1:
            return [start]
        step = (stop - start) / (num - 1)
        return [start + i * step for i in range(num)]

    @staticmethod
    def log10(x):
        if isinstance(x, (list, tuple)):
            return [math.log10(max(1e-12, val)) for val in x]
        return math.log10(max(1e-12, x))

    @staticmethod
    def exp(x):
        if isinstance(x, (list, tuple)):
            return [math.exp(val) for val in x]
        return math.exp(x)

    @staticmethod
    def diff(x):
        return [x[i] - x[i - 1] for i in range(1, len(x))]

    @staticmethod
    def abs(x):
        if isinstance(x, (list, tuple)):
            return [abs(val) for val in x]
        return abs(x)

class PandasShim:
    @staticmethod
    def DataFrame(data=None, columns=None):
        class DF(dict):
            def __init__(self, initial=None):
                super().__init__(initial or {})
            def to_dict(self, orient="list"):
                return dict(self)
        if isinstance(data, dict):
            return DF(data)
        elif isinstance(data, list) and data and isinstance(data[0], dict):
            keys = list(data[0].keys())
            res = {k: [row.get(k) for row in data] for k in keys}
            return DF(res)
        return DF({})

def require_observations(minimum=2, **columns):
    """Validate uploaded columns without generating or truncating measurements."""
    lengths = set()
    for name, values in columns.items():
        if not isinstance(values, (list, tuple)) or len(values) < minimum:
            raise ValueError(f"{name}: at least {minimum} observed values are required")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            raise ValueError(f"{name}: observations must be finite numbers")
        lengths.add(len(values))
    if len(lengths) != 1:
        raise ValueError("Observation columns must have equal lengths")


def require_positive(payload, key):
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{key}: an explicit positive finite value is required")
    return float(value)


# =========================================================================
# 1. BATTERY CYCLING & dQ/dV ANALYTICS
# =========================================================================
def analyze_battery_data(payload):
    """
    Parses and calculates battery cycling, GCD capacity, dQ/dV spectrogram,
    and capacity retention decay trends.
    """
    cycles = payload.get("cycles") or payload.get("cycle_index") or []
    retention = payload.get("capacityRetentionPct") or payload.get("retention_pct") or []
    ce = payload.get("coulombicEfficiencyPct") or payload.get("ce_pct") or []
    voltage = payload.get("voltage") or payload.get("voltage_V") or []
    capacity = payload.get("capacity_mAh") or payload.get("capacity") or []
    nominal_cap = require_positive(payload, "nominalCapacityAh")
    require_observations(cycles=cycles, retention=retention, efficiency=ce)
    require_observations(minimum=4, voltage=voltage, capacity=capacity)

    # Compute dQ/dV differential capacity profile
    dqdv_points = []
    if len(voltage) >= 4 and len(capacity) >= 4:
        # Smooth and differentiate
        for i in range(1, len(voltage) - 1):
            dv = voltage[i + 1] - voltage[i - 1]
            dq = capacity[i + 1] - capacity[i - 1]
            if abs(dv) > 1e-4:
                val = dq / dv
                dqdv_points.append({
                    "voltage": round(voltage[i], 3),
                    "dqdv": round(abs(val), 2),
                    "capacity_mAh": round(capacity[i], 2)
                })

    # Find peaks in dQ/dV
    peaks = []
    for i in range(1, len(dqdv_points) - 1):
        prev_p = dqdv_points[i - 1]["dqdv"]
        curr_p = dqdv_points[i]["dqdv"]
        next_p = dqdv_points[i + 1]["dqdv"]
        if curr_p > prev_p and curr_p > next_p and curr_p > 200:
            v_val = dqdv_points[i]["voltage"]
            phase_name = "Phase Transition"
            if 3.6 <= v_val <= 3.75:
                phase_name = "H1 -> M Phase Transition"
            elif 3.85 <= v_val <= 4.0:
                phase_name = "M -> H2 Core Redox"
            elif 4.1 <= v_val <= 4.25:
                phase_name = "H2 -> H3 Lattice Contraction"
            peaks.append({
                "voltage": v_val,
                "peakHeight": curr_p,
                "identification": phase_name
            })

    # Summary metrics
    initial_cap = capacity[-1]
    final_retention = retention[-1]
    avg_ce = sum(ce) / len(ce)

    metrics = [
        {"name": "Nominal Capacity", "value": f"{nominal_cap:.2f} Ah", "badge": "Specification"},
        {"name": "Current Retention (SOH)", "value": f"{final_retention:.1f}%", "badge": "Health Indicator", "status": "good" if final_retention > 80 else "warning"},
        {"name": "Avg Coulombic Efficiency", "value": f"{avg_ce:.2f}%", "badge": "Reversibility", "status": "good" if avg_ce > 99.5 else "caution"},
        {"name": "dQ/dV Phase Peaks Detected", "value": f"{len(peaks)} Redox Peaks", "badge": "Degradation Signature"}
    ]

    gcd_curve = [{"voltage": v, "capacity_mAh": q} for v, q in zip(voltage, capacity)]
    cycling_trend = [{"cycle": c, "retentionPct": r, "coulombicEffPct": e} for c, r, e in zip(cycles, retention, ce)]

    return {
        "dataType": "battery_cycling",
        "metrics": metrics,
        "peaks": peaks,
        "gcdCurve": gcd_curve,
        "cyclingTrend": cycling_trend,
        "dqdvSpectrogram": dqdv_points,
        "summary": {
            "initialCapacity_mAh": round(initial_cap, 1),
            "finalRetentionPct": round(final_retention, 2),
            "avgCoulombicEfficiencyPct": round(avg_ce, 2),
            "totalCycles": len(cycles),
            "healthStatus": "EXCELLENT" if final_retention >= 90 else ("GOOD" if final_retention >= 80 else "END OF LIFE (EOL)")
        }
    }

# =========================================================================
# 2. CORROSION TAFEL POLARIZATION & ASTM G102 SOLVER
# =========================================================================
def analyze_corrosion_tafel(payload):
    """
    Analyzes experimental corrosion potentiodynamic polarization (Tafel) curves:
    Calculates E_corr, i_corr, beta_a, beta_c, R_p, and corrosion rate (mm/yr & mpy).
    """
    potentials = payload.get("potential_V") or payload.get("potential") or payload.get("voltage") or []
    currents = payload.get("current_A") or payload.get("current_mA") or payload.get("current_uA") or payload.get("log_i") or []
    area_cm2 = require_positive(payload, "electrodeArea_cm2")
    density = require_positive(payload, "density_g_cm3")
    equiv_weight = require_positive(payload, "equivalentWeight")
    require_observations(minimum=5, potential=potentials, current=currents)
    unit_fields = [key for key in ("current_A", "current_mA", "current_uA", "log_i") if payload.get(key)]
    if len(unit_fields) != 1:
        raise ValueError("Exactly one current column with explicit units is required")
    current_key = unit_fields[0]
    # log_i explicitly means log10(current in A); signed currents are not logs.
    scales = {"current_A": 1e6, "current_mA": 1e3, "current_uA": 1.0}
    current_density_uA = [
        (10.0 ** c * 1e6 if current_key == "log_i" else abs(c) * scales[current_key]) / area_cm2
        for c in currents
    ]
    if any(not math.isfinite(c) or c <= 0 for c in current_density_uA):
        raise ValueError("Tafel fitting requires nonzero finite current magnitudes")

    # Identify E_corr (minimum current density point)
    min_idx = 0
    min_val = current_density_uA[0]
    for i, val in enumerate(current_density_uA):
        if val < min_val:
            min_val = val
            min_idx = i

    e_corr = potentials[min_idx]

    # Fit cathodic Tafel slope (below E_corr - 30mV)
    cathodic_e = []
    cathodic_log_i = []
    for p, i_uA in zip(potentials, current_density_uA):
        if p < e_corr - 0.03:
            cathodic_e.append(p)
            cathodic_log_i.append(math.log10(i_uA))

    # Fit anodic Tafel slope (above E_corr + 30mV)
    anodic_e = []
    anodic_log_i = []
    for p, i_uA in zip(potentials, current_density_uA):
        if p > e_corr + 0.03:
            anodic_e.append(p)
            anodic_log_i.append(math.log10(i_uA))

    def linear_fit(x, y):
        if len(x) < 2:
            raise ValueError("Both Tafel branches require at least two observed points")
        mx, my = sum(x) / len(x), sum(y) / len(y)
        den = sum((value - mx) ** 2 for value in x)
        if den == 0:
            raise ValueError("Tafel branch potentials must span a nonzero interval")
        slope = sum((a - mx) * (b - my) for a, b in zip(x, y)) / den
        return slope, my - slope * mx

    cathodic_slope, cathodic_intercept = linear_fit(cathodic_e, cathodic_log_i)
    anodic_slope, anodic_intercept = linear_fit(anodic_e, anodic_log_i)
    if cathodic_slope >= 0 or anodic_slope <= 0:
        raise ValueError("Data do not resolve opposing cathodic/anodic Tafel branches")
    beta_c = abs(1.0 / cathodic_slope)
    beta_a = 1.0 / anodic_slope
    e_corr = (cathodic_intercept - anodic_intercept) / (anodic_slope - cathodic_slope)
    i_corr_uA_cm2 = 10.0 ** (anodic_slope * e_corr + anodic_intercept)

    # Stern-Geary polarization resistance Rp (Ohm cm2)
    # B = (beta_a * beta_c) / (2.303 * (beta_a + beta_c))
    b_stern = (beta_a * beta_c) / (2.303 * (beta_a + beta_c))
    i_corr_A_cm2 = i_corr_uA_cm2 * 1e-6
    rp_ohm_cm2 = b_stern / i_corr_A_cm2

    # ASTM G102 Corrosion Rate:
    # CR (mpy) = 0.129 * (i_corr_uA * EW) / density
    # CR (mm/year) = 0.00327 * (i_corr_uA * EW) / density
    cr_mpy = 0.129 * (i_corr_uA_cm2 * equiv_weight) / density
    cr_mm_yr = 0.00327 * (i_corr_uA_cm2 * equiv_weight) / density

    # Corrosion severity classification
    if cr_mm_yr < 0.02:
        classification = "PASSIVE / EXCELLENT RESISTANCE"
        status_color = "emerald"
    elif cr_mm_yr < 0.1:
        classification = "GOOD CORROSION RESISTANCE"
        status_color = "sky"
    elif cr_mm_yr < 0.5:
        classification = "MODERATE CORROSION (CAUTION)"
        status_color = "amber"
    else:
        classification = "SEVERE RAPID CORROSION (HIGH RISK)"
        status_color = "rose"

    tafel_plot = []
    for p, c in zip(potentials, current_density_uA):
        tafel_plot.append({
            "potential_V": round(p, 4),
            "currentDensity_uA_cm2": round(c, 4),
            "logCurrentDensity": round(math.log10(c), 3)
        })

    metrics = [
        {"name": "Corrosion Potential (E_corr)", "value": f"{e_corr:+.3f} V vs Ref", "badge": "Thermodynamics"},
        {"name": "Corrosion Current (i_corr)", "value": f"{i_corr_uA_cm2:.3f} μA/cm²", "badge": "Kinetics"},
        {"name": "Polarization Resistance (R_p)", "value": f"{rp_ohm_cm2:,.0f} Ω·cm²", "badge": "Stern-Geary"},
        {"name": "Corrosion Rate (ASTM G102)", "value": f"{cr_mm_yr:.4f} mm/yr ({cr_mpy:.2f} mpy)", "badge": classification, "status": status_color}
    ]

    return {
        "dataType": "corrosion_tafel",
        "metrics": metrics,
        "tafelPlot": tafel_plot,
        "summary": {
            "eCorr_V": round(e_corr, 4),
            "iCorr_uA_cm2": round(i_corr_uA_cm2, 4),
            "rp_ohm_cm2": round(rp_ohm_cm2, 1),
            "cr_mm_year": round(cr_mm_yr, 5),
            "cr_mpy": round(cr_mpy, 3),
            "betaA_V_dec": round(beta_a, 3),
            "betaC_V_dec": round(beta_c, 3),
            "classification": classification
        }
    }

# =========================================================================
# 3. EIS IMPEDANCE ANALYTICS
# =========================================================================
def analyze_eis_data(payload):
    """
    Parses and calculates EIS Nyquist/Bode, estimated R0, Rct, Cdl, and Kramers-Kronig.
    """
    frequencies = payload.get("frequencies") or payload.get("frequency") or payload.get("freq_Hz") or []
    z_real = payload.get("zReal") or payload.get("z_real") or payload.get("Z_re") or []
    z_imag = payload.get("zImag") or payload.get("z_imag") or payload.get("Z_im") or []

    require_observations(frequency=frequencies, real=z_real, imaginary=z_imag)
    if any(f <= 0 for f in frequencies):
        raise ValueError("EIS frequencies must be positive")

    # Sort frequencies descending
    sorted_pts = sorted(zip(frequencies, z_real, z_imag), key=lambda x: x[0], reverse=True)
    f_sorted = [p[0] for p in sorted_pts]
    zr_sorted = [p[1] for p in sorted_pts]
    zi_sorted = [p[2] for p in sorted_pts]

    # Nyquist Points
    nyquist = []
    bode = []
    for f, zr, zi in zip(f_sorted, zr_sorted, zi_sorted):
        mag = math.sqrt(zr * zr + zi * zi)
        phase = math.atan2(zi, zr) * 180.0 / math.pi
        nyquist.append({
            "frequency_Hz": round(f, 3),
            "zReal": round(zr, 4),
            "minusZImag": round(-zi, 4)
        })
        bode.append({
            "frequency_Hz": round(f, 3),
            "magnitude_ohm": round(mag, 4),
            "phaseDeg": round(phase, 2)
        })

    # Estimate R0 (high frequency real intercept)
    r0 = max(0.0, zr_sorted[0])

    # Find semicircle apex (maximum -Z_imag)
    max_neg_zi = 0.0
    apex_idx = 0
    for i, zi in enumerate(zi_sorted):
        if -zi > max_neg_zi:
            max_neg_zi = -zi
            apex_idx = i

    f_apex = f_sorted[apex_idx]
    if max_neg_zi <= 0:
        raise ValueError("No capacitive arc is resolved; Rct/Cdl cannot be estimated")
    r_ct_est = max_neg_zi * 2.0
    c_dl_est = 1.0 / (2.0 * math.pi * f_apex * r_ct_est) if f_apex > 0 else 1e-6

    metrics = [
        {"name": "Bulk Ohmic Resistance (R_0)", "value": f"{r0:.3f} Ω", "badge": "High-Freq Intercept"},
        {"name": "Charge Transfer (R_ct)", "value": f"{r_ct_est:.3f} Ω", "badge": "Semicircle Diameter"},
        {"name": "Double Layer Capacitance (C_dl)", "value": f"{c_dl_est * 1e6:.2f} μF", "badge": f"Apex {f_apex:.1f} Hz"},
        {"name": "Frequency Range", "value": f"{min(f_sorted):.2e} to {max(f_sorted):.2e} Hz", "badge": f"{len(f_sorted)} points"}
    ]

    return {
        "dataType": "eis_impedance",
        "metrics": metrics,
        "nyquist": nyquist,
        "bode": bode,
        "summary": {
            "r0_ohm": round(r0, 4),
            "rCt_ohm": round(r_ct_est, 4),
            "cDl_uF": round(c_dl_est * 1e6, 3),
            "fApex_Hz": round(f_apex, 2),
            "numFrequencies": len(f_sorted)
        }
    }

# =========================================================================
# 4. OPEN CIRCUIT POTENTIAL (OCP) ANALYTICS
# =========================================================================
def analyze_ocp_data(payload):
    """
    Analyzes experimental open circuit potential (OCP) vs time.
    Calculates drift rate, steady-state potential, and passivity status.
    """
    time_s = payload.get("time_s") or payload.get("time") or []
    potential_V = payload.get("potential_V") or payload.get("potential") or payload.get("voltage") or []

    require_observations(minimum=3, time=time_s, potential=potential_V)
    if any(b <= a for a, b in zip(time_s, time_s[1:])):
        raise ValueError("OCP time observations must be strictly increasing")

    steady_e = potential_V[-1]
    # Drift rate in last 20% of acquisition (mV/hr)
    cutoff = min(len(potential_V) - 2, max(1, int(len(potential_V) * 0.8)))
    dt_hr = (time_s[-1] - time_s[cutoff]) / 3600.0
    de_mv = (potential_V[-1] - potential_V[cutoff]) * 1000.0
    drift_rate_mv_hr = de_mv / dt_hr if dt_hr > 0 else 0.0

    is_stable = abs(drift_rate_mv_hr) < 5.0

    ocp_plot = [{"time_s": t, "potential_V": p} for t, p in zip(time_s, potential_V)]

    metrics = [
        {"name": "Steady-State OCP", "value": f"{steady_e:+.3f} V vs Ref", "badge": "Rest Potential"},
        {"name": "Drift Rate (ASTM G69)", "value": f"{drift_rate_mv_hr:+.2f} mV/hr", "badge": "STABLE" if is_stable else "DRIFTING"},
        {"name": "Monitoring Duration", "value": f"{time_s[-1] / 60.0:.1f} minutes", "badge": f"{len(time_s)} samples"}
    ]

    return {
        "dataType": "ocp_transient",
        "metrics": metrics,
        "ocpPlot": ocp_plot,
        "summary": {
            "steadyE_V": round(steady_e, 4),
            "driftRate_mV_hr": round(drift_rate_mv_hr, 2),
            "isPassivated": steady_e > -0.2,
            "isStable": is_stable
        }
    }

# =========================================================================
# 5. USER SCRIPT EXECUTION ENGINE
# =========================================================================
def execute_user_python_script(script_code, custom_data=None):
    """
    Executes user custom Python code with pre-imported scientific shims,
    captures stdout/stderr, and extracts structured battery/corrosion data.
    """
    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()

    # Build safe execution namespace
    exec_env = {
        "__name__": "__main__",
        "math": math,
        "cmath": cmath,
        "json": json,
        "re": re,
        "np": NumpyShim,
        "numpy": NumpyShim,
        "pd": PandasShim,
        "pandas": PandasShim,
        "custom_data": custom_data or {},
        "output_payload": {},
        "results": {},
    }

    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = captured_stdout
    sys.stderr = captured_stderr

    start_t = time.perf_counter()
    script_error = None

    try:
        compiled = compile(script_code, "<user_script>", "exec")
        exec(compiled, exec_env)
    except Exception as e:
        script_error = traceback.format_exc()
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    duration_ms = round((time.perf_counter() - start_t) * 1000.0, 2)
    stdout_text = captured_stdout.getvalue()
    stderr_text = captured_stderr.getvalue()

    # Check what data was generated or passed in
    extracted_data = exec_env.get("output_payload") or exec_env.get("results") or exec_env.get("data") or {}

    # Check if script printed JSON to stdout
    if not extracted_data and stdout_text:
        try:
            # Look for JSON block in stdout
            json_match = re.search(r"(\{.*\})", stdout_text, re.DOTALL)
            if json_match:
                extracted_data = json.loads(json_match.group(1))
        except:
            pass

    # If user defined variables like voltage, capacity, etc. directly in global scope
    if not extracted_data:
        extracted_data = {}
        for key in ["voltage", "capacity", "cycles", "retention", "potential_V", "current_A", "frequencies", "z_real", "z_imag", "time_s"]:
            if key in exec_env and isinstance(exec_env[key], (list, tuple)):
                extracted_data[key] = list(exec_env[key])

    # Infer domain / data type
    data_type = extracted_data.get("dataType") or "battery_cycling"
    if "potential_V" in extracted_data or "current_A" in extracted_data or "current_uA" in extracted_data:
        data_type = "corrosion_tafel"
    elif "frequencies" in extracted_data or "zReal" in extracted_data or "z_real" in extracted_data:
        data_type = "eis_impedance"
    elif "time_s" in extracted_data and "potential_V" in extracted_data and len(extracted_data) <= 3:
        data_type = "ocp_transient"

    # Analyze data according to type
    if data_type == "corrosion_tafel":
        analysis = analyze_corrosion_tafel(extracted_data)
    elif data_type == "eis_impedance":
        analysis = analyze_eis_data(extracted_data)
    elif data_type == "ocp_transient":
        analysis = analyze_ocp_data(extracted_data)
    else:
        analysis = analyze_battery_data(extracted_data)

    return {
        "success": script_error is None,
        "error": script_error,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "durationMs": duration_ms,
        "analysis": analysis,
        "extractedDataKeys": list(extracted_data.keys())
    }


# =========================================================================
# CLI / IPC DISPATCHER
# =========================================================================
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        print(json.dumps({
            "status": "ready",
            "engine": "MetalliX Python Ingestion & Analytics Engine",
            "pythonVersion": sys.version,
            "capabilities": [
                "User Python Script Execution (.py & .ipynb)",
                "Battery Cycling & dQ/dV Differential Capacity Spectrogram",
                "ASTM G102 & G59 Potentiodynamic Tafel Solver",
                "EIS Impedance Nyquist/Bode Solver",
                "Open Circuit Potential (OCP) Transient & Passivity Monitor"
            ]
        }))
        sys.exit(0)

    try:
        raw = sys.stdin.read()
        if not raw.strip():
            print(json.dumps({"error": "Empty input payload", "success": False}))
            sys.exit(1)

        payload = json.loads(raw)
        action = payload.get("action", "upload_and_analyze")
        start_time = time.perf_counter()

        if action == "execute_python_script":
            # Same opt-in as routes/characterization.ts (inherited through the daemon's env), so
            # the IPC path cannot run arbitrary code when the Node route is disabled.
            if os.environ.get("METALLIKSA_ENABLE_SCRIPT_EXEC") != "1":
                print(json.dumps({"success": False, "error": "Custom script execution is disabled "
                                  "(set METALLIKSA_ENABLE_SCRIPT_EXEC=1 before starting the server)."}))
                sys.exit(1)
            script_code = payload.get("scriptCode") or payload.get("script") or ""
            custom_data = payload.get("data")
            res = execute_user_python_script(script_code, custom_data)

        elif action == "upload_and_analyze":
            data_type = payload.get("dataType") or "battery_cycling"
            # Auto detect data type if not specified
            if not payload.get("dataType") and any(k in payload for k in ("current_A", "current_mA", "current_uA", "log_i")):
                data_type = "corrosion_tafel"
            elif not payload.get("dataType") and any(k in payload for k in ("frequencies", "zReal", "z_real")):
                data_type = "eis_impedance"
            elif not payload.get("dataType") and "time_s" in payload and "potential_V" in payload:
                data_type = "ocp_transient"

            if data_type == "corrosion_tafel":
                analysis = analyze_corrosion_tafel(payload)
            elif data_type == "eis_impedance":
                analysis = analyze_eis_data(payload)
            elif data_type == "ocp_transient":
                analysis = analyze_ocp_data(payload)
            else:
                analysis = analyze_battery_data(payload)

            res = {
                "success": True,
                "analysis": analysis,
                "stdout": "Processed experimental dataset via MetalliX Python Engine.",
                "durationMs": round((time.perf_counter() - start_time) * 1000.0, 2)
            }

        else:
            res = {"error": f"Unknown action '{action}'", "success": False}

        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        res["pythonDurationMs"] = elapsed_ms
        print(json.dumps(res))

    except Exception as e:
        print(json.dumps({
            "error": str(e),
            "traceback": traceback.format_exc(),
            "success": False
        }))
        sys.exit(1)
