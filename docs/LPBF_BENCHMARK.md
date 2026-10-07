# LPBF open screening benchmark

Screening benchmark, not validation. Anyone can predict the melt-pool width and depth of the published
single tracks that the calibration scorecard uses, and have the predictions scored with the same protocol as the
scorecard. Nothing here changes an evidence label: every output stays `screening-only`, and
`experimentalValidation` is `false` in every record.

## What is published

`data/benchmark/leaderboard/` (written by `python -B python/lpbf_benchmark.py export_inputs`, verified by
`... export_inputs --check`):

| File | Content |
| --- | --- |
| `inputs-v1.csv` | The scorecard's trainable rows, inputs only: `row_id, source, material, P, v, beam, preheat, layer, hatch, regime_class_input`. There is no width or depth column. |
| `inputs-sentinels-v1.csv` | The 11 catalog sentinel rows (Guo 316L, NIST IN718), same columns. They were used while the physics was developed, so they are not blind; they are scored in a separate block. |
| `manifest-v1.json` | Pinned loader table sha256 per source, rows per source, the calibration config sha256, the input file hashes and the protocol text. |
| `submissions/` | Local submission score files (`<slug>.score.json`). Empty today. |

Units: `P` in W, `v` in mm/s, `beam` (beam diameter) in um, `preheat` in degrees C,
`layer` and `hatch` in um (empty when the source has none). `regime_class_input` is the input-only normalised
enthalpy class at the material default (conduction, transition, keyhole), never the published regime label.

The truth (width, depth in um) is never written next to the inputs. It is read at scoring time from the pinned
dataset loaders (`lpbf_calibration_fit.load_rows`); scoring refuses to run if the committed inputs or the manifest no
longer match those loaders or the calibration config.

## Submitting predictions

A submission is a CSV and a JSON file.

```
row_id,width_um,depth_um[,width_lo90,width_hi90,depth_lo90,depth_hi90]
```

* Every `row_id` must exist in `inputs-v1.csv` (or the sentinel file); duplicates, unknown ids, a non-numeric value, a
  non-finite value or a value that is not strictly positive are refused. Nothing is silently dropped.
* A row that is absent, or has a blank value, is **unresolved**. It is counted and reported (see below).
* Optional 90 % intervals are absolute values in um, `lo <= hi`; the two columns of a quantity come together.
* `meta.json`: `name`, `version`, `author` (non-empty strings), `description`, `url` (plain text, shown as text and
  never as a link) and `trainedOnSources` (a list of source names; `[]` for none). Unknown fields are refused.

```
python -B python/tools/lpbf_benchmark_score.py score --submission my.csv --meta my.json \
    --table-cache .runtime/cache/lpbf_benchmark_default_table.json
```

This writes `data/benchmark/leaderboard/submissions/<slug>.score.json`, which carries the submission file hashes, the
manifest and config hashes and the implementation fingerprint of the baseline.

## Protocol (identical to the calibration scorecard)

* **Held out per (material, source).** Every trainable source of a material is one block. Sources listed in
  `trainedOnSources` are excluded from that submission and the cell is marked `excluded-trained-on`; it is never
  dropped silently and never scored.
* **Clusters.** Rows are grouped into parameter sets with `lpbf_calibration_stats.set_key` (source, material, power,
  speed, beam); replicates and layer variants of one setting form one cluster.
* **Metrics per block and quantity.** MAPE on the resolved rows, mean `|ln(pred / meas)|`, bias, and
  `mapeUnresolvedAsFail` (an unresolved row counts as a 100 % error), plus the unresolved count.
* **Skill.** `1 - MAPE_A / MAPE_B` on the common resolved rows against the **frozen Rosenthal kernel at its default
  absorptivity** (the solver's default heat source), with a paired cluster bootstrap (B and seed from
  `CALIBRATION_CONFIG`, theta fixed). The Rosenthal built-in therefore scores 0 against itself.
* **Coverage.** When intervals are given: the share of resolved rows inside `[lo, hi]` with a Wilson 95 % interval
  (`lpbf_calibration_stats.wilson`). It is reported only for rows that carry an interval, and the rows without one are
  counted.
* **No cross-material rank.** Materials have different data, so the record and the page never combine blocks into one
  number or one rank. The page sorts rows within one (material, quantity) table only.

The statistics are the scorecard's own functions (`lpbf_calibration_stats`), reused read-only; the calibration
tool, config, stats, cells and the public dataset loaders are not modified.

## Built-in entries and the leaderboard record

```
python -B python/tools/lpbf_benchmark_score.py builtin --table-cache .runtime/cache/lpbf_benchmark_default_table.json --date 2026-10-07
python -B python/tools/lpbf_benchmark_score.py builtin --check
```

`builtin` scores the three frozen kernels (Rosenthal, Eagar-Tsai v2, Goldak v3) at the material default absorptivity
on the CPU flat-plate path and writes `docs/LPBF_LEADERBOARD_<date>.json` (schema `lpbf-leaderboard-1`), aggregating
them with every local submission score. A calibrated rung is only scored for cells the calibration gate has enabled.
**No cell is enabled today**, so there is no calibrated entry and the record says so (`calibratedRung.enabledCells = 0`);
if a cell ever becomes enabled, the tool refuses to write a record that would silently omit it until that path exists.

The kernel table is either the scorecard cache or a default-only table (about 1900 solver calls, roughly a minute with
`--jobs 8`) that the tool builds and writes to the given path. A cache built for another implementation fingerprint is
refused.

`--check` re-derives the newest committed record and fails on drift: changed inputs or manifest, a changed config,
a different implementation fingerprint, or an edited or stale submission score. When a kernel table is available
(`--table-cache`, or the default cache path) the built-in entries are recomputed and compared as well; without a table
the built-in numbers are taken from the record and are **not** re-verified, and the tool says so. No network is used by
any command.

## In the app

The Calibration Scorecard page ends with one section, "Open screening benchmark leaderboard", read from the newest
committed `docs/LPBF_LEADERBOARD_*.json` (`src/data/lpbfLeaderboard.ts`, `src/components/LpbfLeaderboardPanel.tsx`). Each
(material, quantity) has its own table with: entry, kind (built-in kernel or local submission), held-out source, rows and
sets, MAPE, skill with its CI95, 90 % coverage, unresolved count and the provenance sha256. Column headers are
buttons (keyboard operable, `aria-sort`). Without a committed record the section says so and shows no entries. There are
no demo or placeholder entries.

## What this does not show

* It is not experimental validation and no evidence label is derived from a score.
* The sources carry no per-row measurement uncertainty; a low MAPE on one source says nothing about another.
* The catalog sentinels are not blind (the physics was developed against them) and are shown apart.
* A submission's `trainedOnSources` is a declaration, not something the tool can verify. A submission that trains on a
  source and does not declare it is not held out on that source.
* Local submissions are scored on the submitter's machine; the record is a committed file, not a hosted service.
