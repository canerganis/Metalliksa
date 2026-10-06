#!/usr/bin/env python3
"""Process-map sweep (P x v) of the LPBF screening kernels.

SCREENING, NOT VALIDATION: for one material, beam diameter, layer, hatch and preheat, the Rosenthal, Eagar-Tsai
and Goldak screening kernels of ``calculate_meltpool_physics`` are evaluated on a power x speed grid. Every cell
carries the kernel's own ``extentStatus``; cells that are not ``computed`` are listed as heuristic zones and carry
no width/depth information. The regime label is the a-priori normalised-enthalpy index of
``lpbf_public_datasets.classify_regime`` (same function as the dataset-comparison tool, no thresholds duplicated);
regime boundaries are read off the labels, never fitted. Nothing here is validation.

Usage (from python/, locked interpreter, PYTHONDONTWRITEBYTECODE=1):
    python -B tools/lpbf_process_map.py --material "316L Stainless Steel" --beam-um 80 --layer-um 30 \
        --hatch-um 100 --preheat-C 20 --powers 50:500:25 --speeds 200:1600:100 \
        --kernels rosenthal,eagar-tsai,goldak --overlay-datasets --out ../docs/LPBF_PROCESS_MAP_316L_80um_2026-10-05.json
Ranges are start:stop:step (inclusive) or comma lists. --jobs N worker processes (default 6).
--allow-raytracer does NOT pin the flat-plate absorption path (default: pinned, like lpbf_dataset_comparison).
The companion .md is written next to the json. Nothing is written under python/golden.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import multiprocessing
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

PYTHON_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PYTHON_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lpbf_dataset_comparison as dc  # noqa: E402  (pin_flat_plate, probe, constants, fallback text)

SCHEMA = "lpbf-process-map-1"
KERNELS = dc.KERNELS
GENERATED_AT_DEFAULT = "2026-10-05"
OVERLAY_BEAM_TOL_UM_DEFAULT = 1.0
REGIME_LETTER = {"conduction": "C", "transition": "T", "keyhole": "K", "balling-flagged": "B"}
NON_COMPUTED_MARK = "*"
HONESTY_STATEMENT = ("screening kernels only; not experimental validation; estimated material laws; absorptivity "
                     "assumed (flat-plate, not measured); regime labels are an a-priori normalised-enthalpy index, "
                     "not the kernels' own result; non-computed cells carry no width/depth information")
HEADER_MD = ("**Process-map sweep of screening kernels; not experimental validation; estimated material laws; "
             "flat-plate absorptivity assumed; non-computed cells are marked, never filled.**")
DEFECT_KEYS = ("lackOfFusionStatus", "lackOfFusionRisk", "lackOfFusionOverlapIndex", "tangIndex_hW_tD",
               "hOverW", "tOverD", "keyholePorosityRisk", "ballingInstabilityRisk")
GEOMETRIC_SCREEN_KEYS = ("status", "lackOfFusion", "keyhole", "balling")


# ---------------------------------------------------------------------------------------------
# argument parsing
# ---------------------------------------------------------------------------------------------
def parse_range(text: str) -> List[float]:
    """'a:b:c' (inclusive, step c > 0) or 'x,y,z' -> ascending-as-given list of floats."""
    text = text.strip()
    if ":" in text:
        parts = text.split(":")
        if len(parts) != 3:
            raise ValueError(f"range {text!r} must be start:stop:step")
        a, b, c = (float(p) for p in parts)
        if c <= 0 or b < a:
            raise ValueError(f"range {text!r} needs step > 0 and stop >= start")
        n = int(math.floor((b - a) / c + 1e-9)) + 1
        return [round(a + i * c, 9) for i in range(n)]
    vals = [float(p) for p in text.split(",") if p.strip()]
    if not vals:
        raise ValueError("empty value list")
    return vals


def parse_kernels(text: str) -> List[str]:
    ks = [k.strip() for k in text.split(",") if k.strip()]
    bad = [k for k in ks if k not in KERNELS]
    if bad or not ks:
        raise ValueError(f"unknown kernels {bad}; choose from {list(KERNELS)}")
    return ks


# ---------------------------------------------------------------------------------------------
# solver calls
# ---------------------------------------------------------------------------------------------
def _cell_worker(task: Dict[str, Any]) -> Dict[str, Any]:
    """One (P, v, kernel) cell. Solver stdout is captured; flat-plate calls are counted and popped by the caller."""
    dc.pin_flat_plate(bool(task.get("allowRaytracer")))
    absorption_model = "powder-raytrace" if task.get("allowRaytracer") else "flat-plate"
    flat_plate = 0
    from lpbf_thermal_solver import calculate_meltpool_physics
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured):
            res = calculate_meltpool_physics(
                task["material"], task["power_W"], task["speed_mm_s"], task["beam_um"], task["preheat_C"],
                task["layer_um"], task["hatch_um"], heat_source=task["kernel"], absorption_model=absorption_model)
        flat_plate = int(res["processParameters"].get("absorptionModel") == "flat-plate")
        g = res["meltPoolGeometry"]
        dd = res.get("defectDiagnostics", {})
        gs = res.get("geometricDefectScreen", {})
        out = {"width_um": round(float(g["width_um"]), 3), "depth_um": round(float(g["depth_um"]), 3),
               "length_um": round(float(g["length_um"]), 3), "extentStatus": g.get("extentStatus"),
               "extentNote": g.get("extentNote"), "solverRegime": g.get("regime"),
               "keyholeVaporCavityDepth_um": g.get("keyholeVaporCavityDepth_um"),
               "solverNormalizedEnthalpy": res.get("processParameters", {}).get("normalizedEnthalpy"),
               "defectDiagnostics": {k: dd[k] for k in DEFECT_KEYS if k in dd},
               "geometricDefectScreen": {k: gs[k] for k in GEOMETRIC_SCREEN_KEYS if k in gs}}
    except Exception as exc:  # recorded as data, never silently dropped
        out = {"width_um": None, "depth_um": None, "length_um": None,
               "extentStatus": f"error: {type(exc).__name__}", "extentNote": str(exc)[:300], "solverRegime": None,
               "keyholeVaporCavityDepth_um": None, "solverNormalizedEnthalpy": None,
               "defectDiagnostics": {}, "geometricDefectScreen": {}}
    out["_flatPlateCalls"] = flat_plate
    return out


def _map(tasks: List[Dict[str, Any]], jobs: int) -> List[Dict[str, Any]]:
    if jobs <= 1 or len(tasks) <= 1:
        return [_cell_worker(t) for t in tasks]
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(min(jobs, len(tasks))) as pool:
        return pool.map(_cell_worker, tasks, chunksize=4)  # order preserved -> deterministic


# ---------------------------------------------------------------------------------------------
# derived blocks (pure functions of the cells)
# ---------------------------------------------------------------------------------------------
def regime_boundaries(cells: Sequence[Dict[str, Any]], powers: Sequence[float], speeds: Sequence[float],
                      kernels: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Per kernel: neighbouring grid cells (along power or along speed) whose regime labels differ.

    Derived from the labels only; each entry names the two cells and their labels. No interpolation, no fit.
    """
    out: Dict[str, List[Dict[str, Any]]] = {}
    for k in kernels:
        lab = {(c["power_W"], c["speed_mm_s"]): c["regime"] for c in cells if c["kernel"] == k}
        edges = []
        for v in speeds:
            for p0, p1 in zip(powers, powers[1:]):
                a, b = lab[(p0, v)], lab[(p1, v)]
                if a != b:
                    edges.append({"axis": "power", "speed_mm_s": v, "from": {"power_W": p0, "regime": a},
                                  "to": {"power_W": p1, "regime": b}})
        for p in powers:
            for v0, v1 in zip(speeds, speeds[1:]):
                a, b = lab[(p, v0)], lab[(p, v1)]
                if a != b:
                    edges.append({"axis": "speed", "power_W": p, "from": {"speed_mm_s": v0, "regime": a},
                                  "to": {"speed_mm_s": v1, "regime": b}})
        out[k] = edges
    return out


def heuristic_zones(cells: Sequence[Dict[str, Any]], kernels: Sequence[str]) -> Dict[str, Any]:
    """Per kernel: count and list of cells whose extentStatus != 'computed' (their width/depth carry no information)."""
    out: Dict[str, Any] = {}
    for k in kernels:
        ks = [c for c in cells if c["kernel"] == k]
        bad = [{"power_W": c["power_W"], "speed_mm_s": c["speed_mm_s"], "extentStatus": c["extentStatus"],
                "regime": c["regime"]} for c in ks if c["extentStatus"] != "computed"]
        by_status: Dict[str, int] = {}
        for b in bad:
            by_status[str(b["extentStatus"])] = by_status.get(str(b["extentStatus"]), 0) + 1
        out[k] = {"cells": len(ks), "computed": len(ks) - len(bad), "nonComputed": len(bad),
                  "byExtentStatus": by_status, "list": bad}
    return out


def overlay_rows(material: str, beam_um: float, tol_um: float,
                 rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Dataset rows with the same material and beam diameter within tol_um; measured W/D and the regime label."""
    import lpbf_public_datasets as pd
    out = []
    for r in rows:
        if r["material"] != material or abs(r["beamDiameter_um"] - beam_um) > tol_um:
            continue
        reg = pd.classify_regime(r["material"], r["power_W"], r["speed_mm_s"], r["beamDiameter_um"],
                                 r["preheat_C"], r["balling"])
        out.append({"dataset": r["dataset"], "rowId": r["rowId"], "power_W": r["power_W"],
                    "speed_mm_s": r["speed_mm_s"], "beamDiameter_um": r["beamDiameter_um"],
                    "powderLayer_um": r["layer_um"], "width_um": r["width_um"], "depth_um": r["depth_um"],
                    "dOverW": round(r["depth_um"] / r["width_um"], 4), "balling": r["balling"],
                    "regime": reg["label"], "normalizedEnthalpy": reg["normalizedEnthalpy"]})
    return out


def load_overlay(material: str, beam_um: float, tol_um: float) -> List[Dict[str, Any]]:
    import lpbf_public_datasets as pd
    rows = pd.load_hofmann_316l()["rows"] + pd.load_totis_ti64()["rows"]
    return overlay_rows(material, beam_um, tol_um, rows)


def load_overlay_provenance(material: str, beam_um: float, tol_um: float) -> List[Dict[str, Any]]:
    """Return source records for datasets contributing at least one selected overlay row."""
    import lpbf_public_datasets as pd
    loaded = [pd.load_hofmann_316l(), pd.load_totis_ti64()]
    matched = {r["dataset"] for item in loaded
               for r in item["rows"]
               if r["material"] == material and abs(r["beamDiameter_um"] - beam_um) <= tol_um}
    records = []
    for item in loaded:
        p = item["provenance"]
        if p["id"] not in matched:
            continue
        records.append({"id": p["id"], "citation": p["citation"], "doi": p["doi"],
                        "license": p["license"], "url": p["url"], "file": p["file"],
                        "fileSha256": p["fileSha256"], "source": p["source"],
                        "caveats": list(p["caveats"])})
    return records


def _round(o: Any) -> Any:
    if isinstance(o, float):
        return None if not math.isfinite(o) else round(o, 4)
    if isinstance(o, dict):
        return {k: _round(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_round(v) for v in o]
    return o


def build_limits(absorption: Dict[str, Any], zones: Dict[str, Any], overlay: Optional[Sequence[Dict[str, Any]]]) -> List[str]:
    lim = [
        "Screening kernels (Rosenthal, Eagar-Tsai, Goldak) of calculate_meltpool_physics; nothing here is "
        "experimental validation.",
        f"Flat-plate absorptivity assumed ({absorption['path']}; "
        + ", ".join(f"{m} {a}" for m, a in absorption["absorptivity_by_material"].items())
        + "); the absorptivity acting in a physical track is unknown and the GPU powder ray tracer is "
        + ("not used." if absorption["pinned"] else "used where it is importable (path not pinned)."),
        "The kernels have no powder-layer dependence: width, depth and length are identical for any layer "
        "thickness; layer and hatch enter only the lack-of-fusion / defect screens carried per cell.",
        "Regime labels are an a-priori normalised-enthalpy index (lpbf_public_datasets.classify_regime, "
        "thresholds 15 and 30), identical for all kernels; they are not a kernel result and not the "
        "papers' regime definition. 'balling-flagged' cannot occur in the map (it needs a dataset flag).",
        "Regime boundaries are neighbouring-grid-cell label changes (resolution = grid step), not fitted or interpolated "
        "curves.",
        "Non-computed cells (extentStatus other than 'computed') carry no width/depth information: the values stored "
        "are the solver's heuristic fallback / floor and must not be read as a prediction. Counts per kernel: "
        + "; ".join(f"{k} {z['nonComputed']} of {z['cells']}" for k, z in zones.items()) + ".",
        "Lack-of-fusion, keyhole-porosity and balling entries are the solver's own screens carried as returned, "
        "including on non-computed cells; no criterion is added here.",
    ]
    if overlay is not None:
        lim.append(f"Overlay rows ({len(overlay)}) are published single-track measurements (powder layers as in the "
                   "dataset) matched by material and beam diameter only; they are not on the grid, carry no "
                   "uncertainty model, and are shown next to the map, not compared with it.")
    return lim


# ---------------------------------------------------------------------------------------------
# document assembly
# ---------------------------------------------------------------------------------------------
def build_document(material: str, beam_um: float, layer_um: float, hatch_um: float, preheat_C: float,
                   powers: Sequence[float], speeds: Sequence[float], kernels: Sequence[str], jobs: int = 6,
                   overlay: bool = False, overlay_beam_tol_um: float = OVERLAY_BEAM_TOL_UM_DEFAULT,
                   allow_raytracer: bool = False, generated_at: str = GENERATED_AT_DEFAULT,
                   probe_raytracer: bool = True) -> Dict[str, Any]:
    dc.pin_flat_plate(allow_raytracer)
    import lpbf_public_datasets as pd
    from lpbf_simulation import implementation_fingerprint
    from four_alloy_materials import thermal_props
    if thermal_props(material) is None:
        raise ValueError(f"Unsupported material {material!r}")

    tasks = [{"material": material, "power_W": p, "speed_mm_s": v, "beam_um": beam_um, "preheat_C": preheat_C,
              "layer_um": layer_um, "hatch_um": hatch_um, "kernel": k, "allowRaytracer": allow_raytracer}
             for k in kernels for p in powers for v in speeds]
    preds = _map(tasks, jobs)
    warn_by_kernel = {k: 0 for k in kernels}
    cells: List[Dict[str, Any]] = []
    for t, pr in zip(tasks, preds):
        warn_by_kernel[t["kernel"]] += int(pr.pop("_flatPlateCalls", 0) or 0)
        reg = pd.classify_regime(material, t["power_W"], t["speed_mm_s"], beam_um, preheat_C, None)
        status = pr["extentStatus"]
        cell = {"kernel": t["kernel"], "power_W": t["power_W"], "speed_mm_s": t["speed_mm_s"],
                "width_um": pr["width_um"], "depth_um": pr["depth_um"], "length_um": pr["length_um"],
                "extentStatus": status, "extentNote": pr["extentNote"], "computed": status == "computed",
                "normalizedEnthalpy": reg["normalizedEnthalpy"], "regime": reg["label"]}
        for key in ("solverRegime", "keyholeVaporCavityDepth_um", "solverNormalizedEnthalpy", "defectDiagnostics",
                    "geometricDefectScreen"):
            cell[key] = pr[key]
        cells.append(cell)

    zones = heuristic_zones(cells, kernels)
    absorption = {
        "path": "flat-plate" if not allow_raytracer else "powder-raytrace (explicit opt-in)",
        "pinned": not allow_raytracer,
        "howPinned": ("calculate_meltpool_physics(absorption_model='flat-plate'), the solver default on every machine "
                      "since the 2026-10-06 tier-2 bump; sys.modules['powder_bed_raytracer'] = None is also set in "
                      "the main process and in every worker so any ray-tracer import fails loudly" if not allow_raytracer
                      else "--allow-raytracer: calculate_meltpool_physics(absorption_model='powder-raytrace'); the "
                      "ray tracer's errors propagate (no silent fallback)"),
        "raytracerModulePresent": (PYTHON_DIR / f"{dc.RAYTRACER_MODULE}.py").is_file(),
        "raytracerImportable": dc.probe_raytracer_importable() if probe_raytracer else None,
        "absorptivity_by_material": {material.replace(" Stainless Steel", ""): thermal_props(material)["absorptivity_IR"]},
        "flatPlateCalls": sum(warn_by_kernel.values()),
        "flatPlateCallsByKernel": warn_by_kernel,
        "solverCalls": len(tasks),
        "note": ("flat-plate absorptivity_IR; the GPU powder ray tracer was not used. flatPlateCalls counts the solver "
                 "results that report processParameters.absorptionModel == 'flat-plate'; equal to solverCalls when "
                 "every call took the flat-plate path (failed calls report none)."
                 if not allow_raytracer else
                 "ray tracer requested explicitly (absorption_model='powder-raytrace'); flatPlateCalls is 0 when "
                 "every call used it."),
    }
    ov = load_overlay(material, beam_um, overlay_beam_tol_um) if overlay else None
    ov_provenance = load_overlay_provenance(material, beam_um, overlay_beam_tol_um) if overlay else []
    doc: Dict[str, Any] = {
        "schema": SCHEMA, "generatedAt": generated_at,
        "implementationHash": implementation_fingerprint(),
        "honesty": {"experimentalValidation": False, "statement": HONESTY_STATEMENT},
        "absorption": absorption,
        "inputs": {"material": material, "beamDiameter_um": beam_um, "layer_um": layer_um, "hatch_um": hatch_um,
                   "preheat_C": preheat_C, "kernels": list(kernels), "overlayDatasets": bool(overlay),
                   "overlayBeamTolerance_um": overlay_beam_tol_um if overlay else None},
        "regimeFilter": {"rule": pd.REGIME_RULE, "parameters": pd.REGIME_PARAMETERS,
                         "note": "the classifier is called with balling=None: the map has no balling flag"},
        "grid": {"powers_W": list(powers), "speeds_mm_s": list(speeds)},
        "cells": cells,
        "regimeBoundaries": regime_boundaries(cells, powers, speeds, kernels),
        "heuristicZones": zones,
        "overlay": ov if overlay else [],
        "overlayProvenance": ov_provenance,
        "limits": build_limits(absorption, zones, ov),
    }
    return _round(doc)


# ---------------------------------------------------------------------------------------------
# markdown
# ---------------------------------------------------------------------------------------------
def render_markdown(doc: Dict[str, Any]) -> str:
    inp, grid = doc["inputs"], doc["grid"]
    P, V = grid["powers_W"], grid["speeds_mm_s"]
    L = [f"# LPBF process map: {inp['material']}, beam {inp['beamDiameter_um']:g} um ({doc['generatedAt']})", "",
         HEADER_MD, "",
         f"Schema `{doc['schema']}`; implementation fingerprint `{doc['implementationHash']}`. "
         f"Honesty: {doc['honesty']['statement']}. `experimentalValidation` = false.", "",
         f"Inputs: layer {inp['layer_um']:g} um, hatch {inp['hatch_um']:g} um, preheat {inp['preheat_C']:g} C; "
         f"{len(P)} powers ({P[0]:g}-{P[-1]:g} W) x {len(V)} speeds ({V[0]:g}-{V[-1]:g} mm/s); "
         f"kernels {', '.join(inp['kernels'])}.", "",
         "## Regime rule", "", doc["regimeFilter"]["rule"], "",
         f"Table legend: **C** conduction, **T** transition, **K** keyhole (normalised-enthalpy index, same for all "
         f"kernels); a trailing `{NON_COMPUTED_MARK}` marks a cell whose kernel extentStatus is not `computed` "
         f"(no width/depth information). Rows are power, columns are scan speed (mm/s).", ""]
    for k in inp["kernels"]:
        by = {(c["power_W"], c["speed_mm_s"]): c for c in doc["cells"] if c["kernel"] == k}
        z = doc["heuristicZones"][k]
        L += [f"## Kernel {k}", "",
              "| P W \\ v mm/s | " + " | ".join(f"{v:g}" for v in V) + " |", "|---|" + "---|" * len(V)]
        for p in reversed(P):
            row = []
            for v in V:
                c = by[(p, v)]
                row.append(REGIME_LETTER.get(c["regime"], "?") + ("" if c["computed"] else NON_COMPUTED_MARK))
            L.append(f"| {p:g} | " + " | ".join(row) + " |")
        L += ["", f"Heuristic zone: {z['nonComputed']} of {z['cells']} cells not computed "
              f"({', '.join(f'{s}: {n}' for s, n in sorted(z['byExtentStatus'].items())) or 'none'}); "
              f"{z['computed']} computed. Regime-label changes between neighbouring cells: "
              f"{len(doc['regimeBoundaries'][k])}.", ""]
    L += ["## Heuristic-zone counts", "", "| kernel | cells | computed | not computed | by extentStatus |",
          "|---|---|---|---|---|"]
    for k in inp["kernels"]:
        z = doc["heuristicZones"][k]
        L.append(f"| {k} | {z['cells']} | {z['computed']} | {z['nonComputed']} | "
                 f"{', '.join(f'{s}: {n}' for s, n in sorted(z['byExtentStatus'].items())) or '-'} |")
    L += ["", "## Regime boundaries", "",
          "Neighbouring grid cells whose regime label differs (JSON `regimeBoundaries`; resolution = grid step; "
          "derived from labels, not fitted). Counts by unordered label pair:", "",
          "| kernel | changes | by pair |", "|---|---|---|"]
    for k in inp["kernels"]:
        pairs: Dict[str, int] = {}
        for e in doc["regimeBoundaries"][k]:
            key = "-".join(sorted((e["from"]["regime"], e["to"]["regime"])))
            pairs[key] = pairs.get(key, 0) + 1
        L.append(f"| {k} | {len(doc['regimeBoundaries'][k])} | "
                 + (", ".join(f"{a}: {n}" for a, n in sorted(pairs.items())) or "-") + " |")
    same = len({json.dumps(doc["regimeBoundaries"][k], sort_keys=True) for k in inp["kernels"]}) == 1
    L += ["", ("The boundary sets are identical for all kernels: the label is a kernel-independent index." if same
               else "The boundary sets differ between kernels."), ""]
    ov = doc["overlay"]
    if inp["overlayDatasets"]:
        L += ["## Dataset overlay", "",
              f"{len(ov)} published single-track rows with the same material and beam diameter within "
              f"{inp['overlayBeamTolerance_um']:g} um (measured, not predicted; no uncertainty model; not on the grid)."]
        if ov:
            counts: Dict[str, int] = {}
            for r in ov:
                counts[r["regime"]] = counts.get(r["regime"], 0) + 1
            L += ["", "Regime labels of the overlay rows: " + ", ".join(f"{k} {n}" for k, n in sorted(counts.items())) + ".",
                  "", "| regime | n | P range W | v range mm/s | median D/W | min D/W | max D/W |", "|---|---|---|---|---|---|---|"]
            for lab in sorted(counts):
                rr = [r for r in ov if r["regime"] == lab]
                dw = sorted(r["dOverW"] for r in rr)
                med = dw[len(dw) // 2] if len(dw) % 2 else 0.5 * (dw[len(dw) // 2 - 1] + dw[len(dw) // 2])
                L.append(f"| {lab} | {len(rr)} | {min(r['power_W'] for r in rr):g}-{max(r['power_W'] for r in rr):g} | "
                         f"{min(r['speed_mm_s'] for r in rr):g}-{max(r['speed_mm_s'] for r in rr):g} | "
                         f"{med:.2f} | {dw[0]:.2f} | {dw[-1]:.2f} |")
            nb = sum(1 for r in ov if r["balling"] == 1)
            L += ["", f"Rows flagged as balling in the dataset: {nb} (labelled `balling-flagged`, which the "
                  "grid cannot produce). Every row with its measured width/depth is in JSON `overlay[]`."]
        for source in doc.get("overlayProvenance", []):
            raw_hash = source.get("source", {}).get("raw_sha256") or source.get("source", {}).get("rawSha256")
            hash_text = f"; raw SHA-256 `{raw_hash}`" if raw_hash else ""
            L += ["", f"### Source: {source['id']}", "",
                  f"{source['citation']} DOI: [{source['doi']}](https://doi.org/{source['doi']}); "
                  f"licence: {source['license']}; source: [{source['url']}]({source['url']}); "
                  f"loaded table `{source['file']}` SHA-256 `{source['fileSha256']}`{hash_text}.",
                  "Caveats:"]
            L.extend(f"- {caveat}" for caveat in source["caveats"])
        L += [""]
    ab = doc["absorption"]
    L += ["## Absorption path", "",
          f"Path: **{ab['path']}** (pinned: {ab['pinned']}). {ab['howPinned']}. Absorptivity by material: "
          + ", ".join(f"{m} {a}" for m, a in ab["absorptivity_by_material"].items())
          + (f". Flat-plate calls: {ab['flatPlateCalls']} of {ab['solverCalls']} solver calls." if "flatPlateCalls" in ab
             else f". Fallback warnings captured: {ab['fallbackWarnings']} of {ab['solverCalls']} solver calls."), "",
          ab["note"], "", "## Limits", ""]
    for x in doc["limits"]:
        L.append(f"- {x}")
    return "\n".join(L).rstrip("\n") + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--material", required=True, help="material name as the material authority uses it, "
                    "e.g. '316L Stainless Steel', 'Ti-6Al-4V', 'Inconel 718'")
    ap.add_argument("--beam-um", type=float, required=True)
    ap.add_argument("--layer-um", type=float, default=30.0)
    ap.add_argument("--hatch-um", type=float, default=100.0)
    ap.add_argument("--preheat-C", type=float, default=20.0)
    ap.add_argument("--powers", required=True, help="start:stop:step (inclusive) or comma list, W")
    ap.add_argument("--speeds", required=True, help="start:stop:step (inclusive) or comma list, mm/s")
    ap.add_argument("--kernels", default=",".join(KERNELS))
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--out", required=True, help="output JSON path (the .md goes next to it)")
    ap.add_argument("--overlay-datasets", action="store_true")
    ap.add_argument("--overlay-beam-tol-um", type=float, default=OVERLAY_BEAM_TOL_UM_DEFAULT)
    ap.add_argument("--allow-raytracer", action="store_true",
                    help="do not pin the flat-plate absorption path (default: pinned)")
    ap.add_argument("--generated-at", default=GENERATED_AT_DEFAULT)
    a = ap.parse_args(argv)
    out = Path(a.out).resolve()
    if "golden" in out.parts:
        raise SystemExit("refusing to write under golden/")
    try:
        powers, speeds, kernels = parse_range(a.powers), parse_range(a.speeds), parse_kernels(a.kernels)
    except ValueError as exc:
        raise SystemExit(str(exc))
    t0 = time.perf_counter()
    doc = build_document(a.material, a.beam_um, a.layer_um, a.hatch_um, a.preheat_C, powers, speeds, kernels,
                         jobs=a.jobs, overlay=a.overlay_datasets, overlay_beam_tol_um=a.overlay_beam_tol_um,
                         allow_raytracer=a.allow_raytracer, generated_at=a.generated_at)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, sort_keys=True, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    out.with_suffix(".md").write_text(render_markdown(doc), encoding="utf-8", newline="\n")
    print(f"wrote {out} and .md in {time.perf_counter() - t0:.0f} s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
