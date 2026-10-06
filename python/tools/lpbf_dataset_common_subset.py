#!/usr/bin/env python3
"""Common-subset W/D error between two LPBF dataset-comparison records (before/after a physics bump).

The pooled figures of tools/lpbf_dataset_comparison.py are computed on each record's own included
rows (extentStatus == "computed"), so two records with different inclusion are not like-for-like.
This tool keeps, per kernel, only the rows that are computed in BOTH records and reports width and
depth MAPE and mean bias before -> after on that common subset: pooled over the before record's
summary scope, over every dataset including wave 2, and per dataset. Comparison, not validation;
nothing is fitted.

Usage (from python/):
    python -B tools/lpbf_dataset_common_subset.py BEFORE.json AFTER.json --out OUT.json
(the companion OUT.md is written next to OUT.json)
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any, Dict, List, Tuple

KERNELS = ("rosenthal", "eagar-tsai", "goldak")
SCHEMA = "lpbf-dataset-common-subset-1"


def _rows(doc: Dict[str, Any]) -> Dict[Tuple[str, Any], Dict[str, Any]]:
    return {(r["dataset"], r["rowId"]): r for r in doc["rows"]}


def _stats(values: List[float]) -> Dict[str, float]:
    return {"mape_pct": round(100.0 * statistics.mean(abs(v - 1.0) for v in values), 1),
            "bias_pct": round(100.0 * statistics.mean(v - 1.0 for v in values), 1)}


def compare(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    scope = set(before["summaryScope"]["datasets"])
    rows_before, rows_after = _rows(before), _rows(after)
    kernels: Dict[str, Any] = {}
    for kernel in KERNELS:
        groups: Dict[str, List[Tuple[float, float, float, float]]] = {}
        computed = {"before": 0, "after": 0}
        for key, rb in sorted(rows_before.items(), key=lambda item: (item[0][0], str(item[0][1]))):
            ra = rows_after.get(key)
            if ra is None:
                continue
            pb, pa = rb["predictions"].get(kernel, {}), ra["predictions"].get(kernel, {})
            in_b, in_a = pb.get("extentStatus") == "computed", pa.get("extentStatus") == "computed"
            if rb["dataset"] in scope:
                computed["before"] += int(in_b)
                computed["after"] += int(in_a)
            measured = rb["measured"]
            if not (in_b and in_a and measured.get("width_um") and measured.get("depth_um")):
                continue
            ratios = (pb["width_um"] / measured["width_um"], pb["depth_um"] / measured["depth_um"],
                      pa["width_um"] / measured["width_um"], pa["depth_um"] / measured["depth_um"])
            names = [rb["dataset"], "all-datasets"] + (["pooled-summary-scope"] if rb["dataset"] in scope else [])
            for name in names:
                groups.setdefault(name, []).append(ratios)
        out = {}
        for name, values in sorted(groups.items()):
            out[name] = {"n": len(values),
                         "width": {"before": _stats([v[0] for v in values]), "after": _stats([v[2] for v in values])},
                         "depth": {"before": _stats([v[1] for v in values]), "after": _stats([v[3] for v in values])}}
        kernels[kernel] = {"computedRowsInSummaryScope": computed, "groups": out}
    return {
        "schema": SCHEMA,
        "before": {"implementationHash": before["implementationHash"], "generatedAt": before["generatedAt"]},
        "after": {"implementationHash": after["implementationHash"], "generatedAt": after["generatedAt"]},
        "summaryScopeDatasets": sorted(scope),
        "rule": "per kernel, rows with extentStatus == 'computed' in BOTH records; ratio = model / measured",
        "honesty": {"experimentalValidation": False,
                    "statement": "Comparison against published single-track measurements; not validation; nothing fitted."},
        "kernels": kernels,
    }


def render_markdown(doc: Dict[str, Any]) -> str:
    lines = [f"# LPBF dataset comparison: common subset {doc['before']['implementationHash'][:8]} -> "
             f"{doc['after']['implementationHash'][:8]}", "",
             f"Schema `{doc['schema']}`. Rule: {doc['rule']}. {doc['honesty']['statement']} "
             f"`experimentalValidation` = false.", "",
             "| kernel | group | n | W MAPE % | D MAPE % | W bias % | D bias % |",
             "| --- | --- | ---: | --- | --- | --- | --- |"]
    for kernel, entry in doc["kernels"].items():
        for name, g in entry["groups"].items():
            w, d = g["width"], g["depth"]
            lines.append(f"| {kernel} | {name} | {g['n']} | {w['before']['mape_pct']} -> {w['after']['mape_pct']} | "
                         f"{d['before']['mape_pct']} -> {d['after']['mape_pct']} | {w['before']['bias_pct']} -> "
                         f"{w['after']['bias_pct']} | {d['before']['bias_pct']} -> {d['after']['bias_pct']} |")
    lines += ["", "Computed rows in the summary scope (before -> after): " + ", ".join(
        f"{k} {e['computedRowsInSummaryScope']['before']} -> {e['computedRowsInSummaryScope']['after']}"
        for k, e in doc["kernels"].items()) + ".", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    doc = compare(json.loads(Path(args.before).read_text(encoding="utf-8")),
                  json.loads(Path(args.after).read_text(encoding="utf-8")))
    out = Path(args.out)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    out.with_suffix(".md").write_text(render_markdown(doc), encoding="utf-8", newline="\n")
    print(f"wrote {out} and {out.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
