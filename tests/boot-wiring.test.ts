import assert from "node:assert/strict";
import { test } from "node:test";
import { BOOT_SKIP_STORAGE_KEY, createBootController } from "../src/utils/bootSequence";
import { bootOptions, getBootController, prefersReducedMotion, readSkipFlag, type BootStepDeps } from "../src/services/bootSteps";

// Wiring between the browser environment (sessionStorage flag, prefers-reduced-motion) and the
// controller: the flag and reduced motion may only switch the animation off, never skip a check.

const g = globalThis as Record<string, unknown>;

function fakeStorage(initial: Record<string, string> = {}) {
  const map = new Map(Object.entries(initial));
  return {
    map,
    getItem: (k: string) => map.get(k) ?? null,
    setItem: (k: string, v: string) => void map.set(k, String(v)),
    removeItem: (k: string) => void map.delete(k),
  };
}

function withEnv<T>(env: { storage?: ReturnType<typeof fakeStorage>; reduced?: boolean }, run: () => T): T {
  const prev = { sessionStorage: g.sessionStorage, window: g.window, hadStorage: "sessionStorage" in g, hadWindow: "window" in g };
  g.sessionStorage = env.storage;
  g.window = { matchMedia: (q: string) => ({ matches: env.reduced === true && q.includes("reduce") }) };
  const restore = () => {
    if (prev.hadStorage) g.sessionStorage = prev.sessionStorage;
    else delete g.sessionStorage;
    if (prev.hadWindow) g.window = prev.window;
    else delete g.window;
  };
  try {
    const out = run();
    if (out instanceof Promise) return out.finally(restore) as T;
    restore();
    return out;
  } catch (error) {
    restore();
    throw error;
  }
}

function countingDeps() {
  const calls = { loadConfig: 0, probe: 0, engineStatus: 0, moduleCount: 0 };
  const deps: BootStepDeps = {
    loadConfig: async () => (calls.loadConfig++, { airgapped: false, blockedServices: [], allowedLocal: [] }),
    probe: () => (calls.probe++, { loaded: true, accessRequired: false, failure: null }),
    engineStatus: async () => (calls.engineStatus++, { online: true, status: "online", pythonVersion: "3.12.10" }),
    moduleCount: () => (calls.moduleCount++, 37),
  };
  return { calls, deps };
}

const allCalled = (calls: Record<string, number>) => Object.entries(calls).filter(([, n]) => n === 0).map(([k]) => k);

test("the page singleton with the sessionStorage flag set: static checklist, but every check still runs", async () => {
  const storage = fakeStorage({ [BOOT_SKIP_STORAGE_KEY]: "1" });
  const { calls, deps } = countingDeps();
  const controller = withEnv({ storage }, () => {
    assert.equal(readSkipFlag(), true);
    return getBootController(() => deps);
  });
  const snap = controller.getSnapshot();
  assert.equal(snap.animate, false, "flag turns animation off");
  assert.equal(snap.dismissed, false, "the checklist is still shown");
  assert.equal(snap.total, 5, "all five checks are scheduled");
  await controller.start();
  assert.deepEqual(allCalled(calls), [], "every injected source was called");
  assert.deepEqual(controller.getSnapshot().rows.map((r) => r.state), ["ok", "ok", "ok", "ok", "ok"]);
  assert.equal(getBootController(() => countingDeps().deps), controller, "one controller per page");
});

test("reduced motion: static checklist, every check still runs", async () => {
  const { calls, deps } = countingDeps();
  const opts = withEnv({ storage: fakeStorage(), reduced: true }, () => {
    assert.equal(prefersReducedMotion(), true);
    return bootOptions(deps);
  });
  assert.equal(opts.reducedMotion, true);
  assert.equal(opts.skipAnimation, false);
  const c = createBootController(opts);
  assert.equal(c.getSnapshot().animate, false);
  await c.start();
  assert.deepEqual(allCalled(calls), []);
});

test("the flag is written when the boot finishes (after the 300 ms exit), not before", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const storage = fakeStorage();
  await withEnv({ storage }, async () => {
    const c = createBootController(bootOptions(countingDeps().deps));
    assert.equal(c.getSnapshot().animate, true, "first load in the tab animates");
    void c.start();
    for (let i = 0; i < 10; i += 1) await new Promise<void>((r) => setImmediate(r));
    assert.equal(c.getSnapshot().phase, "complete");
    assert.equal(storage.map.get(BOOT_SKIP_STORAGE_KEY), undefined);
    t.mock.timers.tick(300);
    assert.equal(c.getSnapshot().phase, "done");
    assert.equal(storage.map.get(BOOT_SKIP_STORAGE_KEY), "1");
  });
});

test("Esc/backdrop/button (skip) hide the overlay, write the flag, and checks continue", async () => {
  const storage = fakeStorage();
  const { calls, deps } = countingDeps();
  let releaseEngine!: () => void;
  const slowDeps: BootStepDeps = {
    ...deps,
    engineStatus: () => new Promise((r) => (releaseEngine = () => r(deps.engineStatus()))),
  };
  await withEnv({ storage }, async () => {
    const c = createBootController(bootOptions(slowDeps));
    const run = c.start();
    for (let i = 0; i < 10; i += 1) await new Promise<void>((r) => setImmediate(r));
    assert.equal(c.getSnapshot().rows[3].state, "running");
    c.skip();
    assert.equal(c.getSnapshot().dismissed, true);
    assert.equal(storage.map.get(BOOT_SKIP_STORAGE_KEY), "1");
    releaseEngine();
    await run;
    assert.deepEqual(allCalled(calls), []);
    assert.equal(c.getSnapshot().finished, 5, "checks finished after the overlay was hidden");
  });
});
