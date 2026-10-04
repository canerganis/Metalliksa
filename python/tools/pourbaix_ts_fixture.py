#!/usr/bin/env python3
"""Parity fixture for the TypeScript Pourbaix port (tests/pourbaix-equilibrium.test.ts).

The Python engine (``pourbaix_solver``: _coefficients/_argmin) classifies a 200 x 200 grid of cell
centres over the engine box (pH -2..16, E -3.0..2.5 V SHE) for every available element at two
dissolved activities. The result is written run-length encoded to
``tests/fixtures/pourbaix-grid-200x200.json``; the TypeScript port must reproduce every cell that is
not within 1 mV of a boundary.

Cells within 1 mV (E direction) or 1 mV / 59.16 mV per pH unit = 0.0169 pH (pH direction) of a
boundary of the winning species are written as '.' and are not compared. That margin is measured
with ``pourbaix_oracle`` (independent numbers), not with the engine.

Usage (from python/):
  python tools/pourbaix_ts_fixture.py --emit    write the fixture (LF)
  python tools/pourbaix_ts_fixture.py --check   exit 1 when the committed fixture differs from a fresh build
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import pourbaix_oracle as oracle  # noqa: E402
import pourbaix_solver as solver  # noqa: E402
import pourbaix_species_25c as table  # noqa: E402

SCHEMA = "pourbaix-ts-parity-fixture-v1"
FIXTURE = HERE.parent.parent / "tests" / "fixtures" / "pourbaix-grid-200x200.json"
N = 200
LOG_ACTIVITIES = (-6.0, -3.0)
MARGIN_E_V = 1e-3
MARGIN_PH = 1e-3 / 0.0591597


def cell_centres():
    box = table.BOX
    d_ph = (box["pH_max"] - box["pH_min"]) / N
    d_e = (box["E_max_V_SHE"] - box["E_min_V_SHE"]) / N
    return ([box["pH_min"] + (i + 0.5) * d_ph for i in range(N)],
            [box["E_min_V_SHE"] + (j + 0.5) * d_e for j in range(N)])


def near_boundary(c, ph, e):
    """True when the point is within MARGIN_E_V (E direction) or MARGIN_PH (pH direction) of a boundary;
    ``c`` = pourbaix_oracle.coeffs(element, log_a) (table order)."""
    g = {k: v[0] + v[1] * ph + v[2] * e for k, v in c.items()}
    best = None
    for k in g:  # first minimum in table order
        if best is None or g[k] < g[best]:
            best = k
    for k in c:
        if k == best:
            continue
        gap = g[k] - g[best]
        d_e = abs(c[k][2] - c[best][2])
        d_p = abs(c[k][1] - c[best][1])
        if (d_e > 1e-9 and gap / d_e < MARGIN_E_V) or (d_p > 1e-9 and gap / d_p < MARGIN_PH) \
                or (d_e <= 1e-9 and d_p <= 1e-9 and gap < 1e-9):
            return True
    return False


def encode_row(cells):
    runs = []
    for token in cells:
        if runs and runs[-1][0] == token:
            runs[-1][1] += 1
        else:
            runs.append([token, 1])
    return ",".join(f"{t}:{n}" for t, n in runs)


def build():
    phs, es = cell_centres()
    cases = []
    for element in table.available_elements():
        for log_a in LOG_ACTIVITIES:
            coeffs = solver._coefficients(element, log_a)
            index = {sp.id: i for i, sp in enumerate(coeffs)}
            oracle_c = oracle.coeffs(element, log_a)
            rows = []
            for e in es:
                cells = []
                for ph in phs:
                    if near_boundary(oracle_c, ph, e):
                        cells.append(".")
                    else:
                        cells.append(str(index[solver._argmin(coeffs, ph, e).id]))
                rows.append(encode_row(cells))
            cases.append({"element": element, "log10Activity": log_a,
                          "speciesIds": [sp.id for sp in coeffs], "rows": rows})
    return {
        "schema": SCHEMA,
        "generatedBy": "python/tools/pourbaix_ts_fixture.py",
        "engine": solver.ENGINE_ID,
        "n": N,
        "box": dict(table.BOX),
        "cell": "centre of the (i, j) cell; rows run from E_min upward, columns from pH_min upward",
        "encoding": "per row 'token:count' runs; token = index into speciesIds of the engine argmin, '.' = within 1 mV "
                    "(E) or 0.0169 pH of a boundary of the winning species (not compared)",
        "cases": cases,
    }


def emit_text():
    return json.dumps(build(), ensure_ascii=False, indent=1) + "\n"


def main(argv):
    if "--emit" in argv:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        with open(FIXTURE, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(emit_text())
        print(f"wrote {FIXTURE}")
        return 0
    if "--check" in argv:
        current = FIXTURE.read_text(encoding="utf-8").replace("\r\n", "\n") if FIXTURE.is_file() else None
        if current != emit_text():
            print("tests/fixtures/pourbaix-grid-200x200.json is stale: run python tools/pourbaix_ts_fixture.py --emit")
            return 1
        print("fixture is current")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
