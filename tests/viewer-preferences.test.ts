import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { test } from "node:test";
import { readChoice, writeChoice } from "../src/utils/viewerPreference";
import { LPBF_BACKEND_PREFERENCE_KEY, LPBF_ENGINEERING_JOB_STORAGE_KEY, startEngineeringJobPersistence, useLpbfEngineeringStore } from "../src/store/useLpbfEngineeringStore";

// D5 (Phase 2 record): the thermal backend select fell back to "Automatic" on reload.
function memoryStorage(seed: Record<string, string> = {}) {
  const values = new Map(Object.entries(seed));
  return { values, getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => { values.set(key, value); } };
}
const throwing = { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } };

test("readChoice accepts only allowed values and survives blocked storage; writeChoice never throws", () => {
  const storage = memoryStorage({ k: "warp", bad: "rm -rf" });
  assert.equal(readChoice("k", ["torch", "warp"] as const, "torch", storage), "warp");
  assert.equal(readChoice("bad", ["torch", "warp"] as const, "torch", storage), "torch");
  assert.equal(readChoice("missing", ["torch", "warp"] as const, "torch", storage), "torch");
  assert.equal(readChoice("k", ["torch", "warp"] as const, "torch", throwing), "torch");
  writeChoice("k", "torch", storage);
  assert.equal(storage.values.get("k"), "torch");
  assert.doesNotThrow(() => writeChoice("k", "warp", throwing));
});

test("thermal backend choice is restored at startup and written when it changes", () => {
  const initial = useLpbfEngineeringStore.getState();
  const storage = memoryStorage({ [LPBF_BACKEND_PREFERENCE_KEY]: "reference" });
  let stop = () => {};
  try {
    useLpbfEngineeringStore.setState({ job: undefined, busy: false, settings: { ...initial.settings, backend: "auto" } });
    stop = startEngineeringJobPersistence(storage);
    assert.equal(useLpbfEngineeringStore.getState().settings.backend, "reference", "restored before any view renders");
    useLpbfEngineeringStore.setState(s => ({ settings: { ...s.settings, backend: "openfoam-thermal" } }));
    assert.equal(storage.values.get(LPBF_BACKEND_PREFERENCE_KEY), "openfoam-thermal");
    // Only the select value is stored: no job, result or evidence state under the preference key.
    assert.equal(storage.values.has(LPBF_ENGINEERING_JOB_STORAGE_KEY), false);
    assert.deepEqual([...storage.values.keys()], [LPBF_BACKEND_PREFERENCE_KEY]);
  } finally { stop(); useLpbfEngineeringStore.setState(initial); }
});

test("unknown, missing or blocked backend values leave the current choice untouched", () => {
  const initial = useLpbfEngineeringStore.getState();
  let stop = () => {};
  try {
    for (const storage of [memoryStorage({ [LPBF_BACKEND_PREFERENCE_KEY]: "warp-cluster" }), memoryStorage(), throwing]) {
      useLpbfEngineeringStore.setState({ job: undefined, busy: false, settings: { ...initial.settings, backend: "reference" } });
      stop = startEngineeringJobPersistence(storage);
      assert.equal(useLpbfEngineeringStore.getState().settings.backend, "reference");
      assert.doesNotThrow(() => useLpbfEngineeringStore.setState(s => ({ settings: { ...s.settings, backend: "auto" } })));
      stop();
    }
  } finally { stop(); useLpbfEngineeringStore.setState(initial); }
});

test("the GPU pilot engine select is remembered through the same guarded helper", () => {
  const view = readFileSync(resolve(process.cwd(), "src/components/3d-distortion-lab/LpbfEngineeringSimulation.tsx"), "utf8");
  assert.match(view, /useState<'torch' \| 'warp'>\(\(\) => readChoice\(GPU_PILOT_ENGINE_PREFERENCE_KEY, GPU_PILOT_ENGINES, 'torch'\)\)/);
  assert.match(view, /setEngine\(next\); writeChoice\(GPU_PILOT_ENGINE_PREFERENCE_KEY, next\);/);
  assert.match(view, /const GPU_PILOT_ENGINES = \["torch", "warp"\] as const;/);
});
