import assert from "node:assert/strict";
import {test} from "node:test";
import {useMaterialStore} from "../src/store/useMaterialStore";
import {useMaterialSpecimenStore} from "../src/store/useMaterialSpecimenStore";

function withRestoredStore(run: (originalComposition: Record<string, number>) => void) {
  const materialInitial = useMaterialStore.getState();
  const sharedInitial = useMaterialSpecimenStore.getState();
  try {
    run(materialInitial.activeMaterialSpecimen.composition);
  } finally {
    useMaterialStore.setState(materialInitial, true);
    useMaterialSpecimenStore.setState(sharedInitial, true);
  }
}

test("setElement accepts 100 but rejects 101 without mutating the specimen", () => {
  withRestoredStore(() => {
    useMaterialStore.getState().setElement("Cr", 100);
    assert.equal(useMaterialStore.getState().activeMaterialSpecimen.composition.Cr, 100);

    const beforeInvalidEdit = {...useMaterialStore.getState().activeMaterialSpecimen.composition};
    useMaterialStore.getState().setElement("Cr", 101);
    assert.deepEqual(useMaterialStore.getState().activeMaterialSpecimen.composition, beforeInvalidEdit);
  });
});

test("setElement rejects non-finite values without storing NaN or Infinity", () => {
  for (const badValue of [Number.NaN, Number.POSITIVE_INFINITY]) {
    withRestoredStore((originalComposition) => {
      useMaterialStore.getState().setElement("Cr", badValue);
      assert.deepEqual(useMaterialStore.getState().activeMaterialSpecimen.composition, originalComposition);
    });
  }
});

test("negative element content is rejected without mutating the specimen", () => {
  withRestoredStore((originalComposition) => {
    useMaterialStore.getState().setElement("Cr", -0.1);
    assert.deepEqual(useMaterialStore.getState().activeMaterialSpecimen.composition, originalComposition);
  });
});

test("zero remains the explicit remove action", () => {
  withRestoredStore(() => {
    useMaterialStore.getState().setElement("Cr", 0);
    assert.equal("Cr" in useMaterialStore.getState().activeMaterialSpecimen.composition, false);
  });
});

test("updateComposition rejects malformed maps atomically before deriving properties", () => {
  withRestoredStore((originalComposition) => {
    const outcomes = [101, Number.NaN, Number.POSITIVE_INFINITY, -0.1].map((badValue) => {
      useMaterialStore.getState().updateComposition({...originalComposition, Cr: badValue});
      return useMaterialStore.getState().activeMaterialSpecimen.composition;
    });
    assert.deepEqual(outcomes, Array(4).fill(originalComposition));
  });
});

test("normalizeComposition does not turn a non-finite total into invalid entries", () => {
  withRestoredStore(() => {
    const original = useMaterialStore.getState().activeMaterialSpecimen;
    const invalidComposition = {Ni: Number.POSITIVE_INFINITY, Cr: 18};
    useMaterialStore.setState({
      activeMaterialSpecimen: {...original, composition: invalidComposition},
      activeSpecimen: {...original, composition: invalidComposition},
    });

    useMaterialStore.getState().normalizeComposition();
    assert.deepEqual(useMaterialStore.getState().activeMaterialSpecimen.composition, invalidComposition);
  });
});

test("invalid mutating updater cannot alter live aliases, properties or shared specimen", () => {
  withRestoredStore(() => {
    const before = useMaterialStore.getState();
    const sharedBefore = useMaterialSpecimenStore.getState().activeSpecimen;
    const specimenSnapshot = structuredClone(before.activeMaterialSpecimen);
    useMaterialStore.getState().updateComposition(comp => {
      comp.Ni = Number.NaN;
      return comp;
    });
    const after = useMaterialStore.getState();
    assert.strictEqual(after.activeMaterialSpecimen, before.activeMaterialSpecimen);
    assert.strictEqual(after.activeSpecimen, before.activeSpecimen);
    assert.deepEqual(after.activeMaterialSpecimen, specimenSnapshot);
    assert.strictEqual(useMaterialSpecimenStore.getState().activeSpecimen, sharedBefore);
  });
});

test("JSON import rejects exponent overflow before storing or deriving it", () => {
  withRestoredStore((originalComposition) => {
    const accepted = useMaterialStore.getState().importFromJSON('{"name":"Overflow specimen","composition":{"Ni":1e999}}');

    assert.equal(accepted, false);
    assert.deepEqual(useMaterialStore.getState().activeMaterialSpecimen.composition, originalComposition);
  });
});

test("specimen replacement rejects invalid or unknown composition maps atomically", () => {
  for (const method of ["setActiveMaterialSpecimen", "setSpecimen"] as const) {
    for (const badComposition of [
      {Ni: 101},
      {Ni: -1},
      {Ni: Number.POSITIVE_INFINITY},
      {Ni: Number.NaN},
      {Ni: "101"},
      [],
      null,
      {},
    ]) {
      withRestoredStore(() => {
        const before = useMaterialStore.getState();
        const snapshot = structuredClone(before.activeMaterialSpecimen);
        useMaterialStore.getState()[method]({
          name: "Invalid replacement",
          composition: badComposition,
        } as never);
        const after = useMaterialStore.getState();
        assert.strictEqual(after.activeMaterialSpecimen, before.activeMaterialSpecimen);
        assert.strictEqual(after.activeSpecimen, before.activeSpecimen);
        assert.deepEqual(after.activeMaterialSpecimen, snapshot);
      });
    }
  }
});

test("setSpecimen accepts valid per-element bounds and a total above 100", () => {
  withRestoredStore(() => {
    const replacement = {Ni: 0, Cr: 100, Fe: 75};
    useMaterialStore.getState().setSpecimen({composition: replacement});

    const after = useMaterialStore.getState();
    assert.deepEqual(after.activeMaterialSpecimen.composition, replacement);
    assert.strictEqual(after.activeSpecimen, after.activeMaterialSpecimen);
  });
});
