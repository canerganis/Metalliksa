/**
 * Differential comparison of the A/B-basis screening statistics between two code versions.
 *
 *   npx tsx tests/tools/differential-screening-k.ts <rev> [<rev2>]
 *
 * Extracts src/utils/{aerospaceScreening,qualificationScreening,toleranceFactors,toleranceFactorTable}.ts at <rev>
 * (whichever exist) into a temporary folder and compares computeAerospaceScreeningStats and
 * computeQualificationMmpdsStats against the working tree (or against <rev2>, extracted the same way) over the grid
 *   N = -5..2000 (2006 values) x CV {0, 0.5, 1, 2.8, 5, 8.5, 15, 40} x (yield, tensile) {930/1010, 275/310, 1100/1250, 100/120}
 * = 64192 combinations. Prints per screen how many combinations are identical (isDeepStrictEqual) and, per field,
 * how many differ and the largest absolute difference. Not a test (not matched by tests/*.test.ts).
 *
 * p8-formula-fixes lane: `04afb93 ceeed0a` -> aerospace identical in all 64192 combinations (k grouping fix kept the
 * aerospace numbers); `5f26277` vs the exact-table commit -> the intended k change (N <= 300 only).
 */
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { isDeepStrictEqual } from "node:util";

const rev = process.argv[2];
const rev2 = process.argv[3];
if (!rev) {
  console.error("usage: npx tsx tests/tools/differential-screening-k.ts <rev> [<rev2>]");
  process.exit(2);
}
const repo = resolve(import.meta.dirname, "..", "..");
const typesUrl = JSON.stringify(pathToFileURL(join(repo, "src", "types")).href);
const NAMES = ["aerospaceScreening", "qualificationScreening", "toleranceFactors", "toleranceFactorTable"];

function extract(r: string): string {
  const dir = mkdtempSync(join(tmpdir(), "diff-screening-"));
  for (const name of NAMES) {
    let src: string | undefined;
    try {
      src = execFileSync("git", ["-C", repo, "show", `${r}:src/utils/${name}.ts`], {
        encoding: "utf8",
        stdio: ["ignore", "pipe", "ignore"],
      });
    } catch {
      src = undefined; // file does not exist at this revision
    }
    if (src !== undefined) writeFileSync(join(dir, `${name}.ts`), src.split('"../types"').join(typesUrl));
  }
  return dir;
}

const dirs: string[] = [];
try {
  const oldDir = extract(rev);
  dirs.push(oldDir);
  const newDir = rev2 ? extract(rev2) : join(repo, "src", "utils");
  if (rev2) dirs.push(newDir);
  const load = (d: string, n: string) => import(pathToFileURL(join(d, `${n}.ts`)).href);
  const oldA = await load(oldDir, "aerospaceScreening");
  const oldQ = await load(oldDir, "qualificationScreening");
  const newA = await load(newDir, "aerospaceScreening");
  const newQ = await load(newDir, "qualificationScreening");

  const cvs = [0, 0.5, 1, 2.8, 5, 8.5, 15, 40];
  const pairs = [
    [930, 1010],
    [275, 310],
    [1100, 1250],
    [100, 120],
  ];
  type Tally = { combos: number; identical: number; fields: Record<string, { differ: number; maxAbs: number }> };
  const res: Record<"aerospace" | "qualification", Tally> = {
    aerospace: { combos: 0, identical: 0, fields: {} },
    qualification: { combos: 0, identical: 0, fields: {} },
  };
  const add = (t: Tally, a: Record<string, unknown>, b: Record<string, unknown>) => {
    t.combos++;
    if (isDeepStrictEqual(a, b)) {
      t.identical++;
      return;
    }
    for (const k of Object.keys(b)) {
      if (isDeepStrictEqual(a[k], b[k])) continue;
      const f = (t.fields[k] ??= { differ: 0, maxAbs: 0 });
      f.differ++;
      const x = a[k];
      const y = b[k];
      if (typeof x === "number" && typeof y === "number") f.maxAbs = Math.max(f.maxAbs, Math.abs(x - y));
    }
  };
  for (let N = -5; N <= 2000; N++)
    for (const cv of cvs)
      for (const [y, t] of pairs) {
        const ai = { meanYieldMpa: y, meanTensileMpa: t, sampleSizeN: N, scatterCvPct: cv };
        add(res.aerospace, oldA.computeAerospaceScreeningStats(ai), newA.computeAerospaceScreeningStats(ai));
        const qi = { meanYieldMpa: y, meanTensileMpa: t, fractureToughnessMpaM: 68, sampleSizeN: N, customScatterCv: cv };
        add(res.qualification, oldQ.computeQualificationMmpdsStats(qi), newQ.computeQualificationMmpdsStats(qi));
      }
  console.log(`rev ${rev} vs ${rev2 ?? "working tree"}`);
  console.log(JSON.stringify(res, null, 1));
} finally {
  for (const d of dirs) rmSync(d, { recursive: true, force: true });
}
