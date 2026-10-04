import React from "react";
import test from "node:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import {
  AccessibleModal,
  acquireScrollLock,
  closeTopmostOverlay,
  escapeStackDepth,
  insertByOpenOrder,
  isTabbableCandidate,
  nextOpenSeq,
  releaseScrollLock,
  nextTrapIndex,
  registerEscapeEntry,
} from "../src/components/AccessibleModal";

test("open modal renders dialog semantics and accessible name", () => {
  const html = renderToStaticMarkup(
    <AccessibleModal open onClose={() => {}} labelledBy="t1">
      <h2 id="t1">Title</h2>
    </AccessibleModal>,
  );
  assert.match(html, /role="dialog"/);
  assert.match(html, /aria-modal="true"/);
  assert.match(html, /aria-labelledby="t1"/);
  assert.doesNotMatch(html, /aria-label=/);
  assert.match(html, /fixed inset-0 z-50/);
});

test("label prop becomes aria-label and closed modal renders nothing", () => {
  const open = renderToStaticMarkup(<AccessibleModal open onClose={() => {}} label="Library" />);
  assert.match(open, /aria-label="Library"/);
  assert.equal(renderToStaticMarkup(<AccessibleModal open={false} onClose={() => {}} label="x" />), "");
});

test("escape stack closes only the topmost entry", () => {
  const calls: string[] = [];
  const base = escapeStackDepth();
  const offA = registerEscapeEntry({ current: () => calls.push("a") });
  const offB = registerEscapeEntry({ current: () => calls.push("b") });
  assert.equal(escapeStackDepth(), base + 2);
  assert.equal(closeTopmostOverlay(), true);
  assert.deepEqual(calls, ["b"]);
  offB();
  closeTopmostOverlay();
  assert.deepEqual(calls, ["b", "a"]);
  offA();
  assert.equal(escapeStackDepth(), base);
  assert.equal(closeTopmostOverlay(), false);
});

test("focus trap wraps at both ends", () => {
  assert.equal(nextTrapIndex(3, 2, false), 0);
  assert.equal(nextTrapIndex(3, 0, true), 2);
  assert.equal(nextTrapIndex(3, 1, false), null);
  assert.equal(nextTrapIndex(3, 1, true), null);
  assert.equal(nextTrapIndex(3, -1, false), 0);
  assert.equal(nextTrapIndex(0, -1, false), null);
});

test("escape stack orders by open sequence even when child registers first", () => {
  const calls: string[] = [];
  const parentSeq = nextOpenSeq();
  const childSeq = nextOpenSeq();
  const offChild = registerEscapeEntry({ current: () => calls.push("child"), seq: childSeq });
  const offParent = registerEscapeEntry({ current: () => calls.push("parent"), seq: parentSeq });
  closeTopmostOverlay();
  assert.deepEqual(calls, ["child"]);
  offChild();
  closeTopmostOverlay();
  assert.deepEqual(calls, ["child", "parent"]);
  offParent();
});

test("insertByOpenOrder is a pure sorted insert", () => {
  const stack = [{ current: () => {}, seq: 1 }, { current: () => {}, seq: 5 }];
  insertByOpenOrder(stack, { current: () => {}, seq: 3 });
  assert.deepEqual(stack.map((e) => e.seq), [1, 3, 5]);
});

test("ref-counted scroll lock restores original only at last release", () => {
  const state = { count: 0, original: "" };
  acquireScrollLock(state, "auto");
  acquireScrollLock(state, "hidden");
  assert.equal(releaseScrollLock(state), null);
  assert.equal(releaseScrollLock(state), "auto");
  assert.equal(releaseScrollLock(state), null);
});

test("tabbable predicate filters disabled, hidden, inert, tabindex -1 and unrendered", () => {
  assert.equal(isTabbableCandidate({ tabIndex: 0 }), true);
  assert.equal(isTabbableCandidate({}), true);
  assert.equal(isTabbableCandidate({ disabled: true }), false);
  assert.equal(isTabbableCandidate({ hidden: true }), false);
  assert.equal(isTabbableCandidate({ inert: true }), false);
  assert.equal(isTabbableCandidate({ hasInertAncestor: true }), false);
  assert.equal(isTabbableCandidate({ tabIndex: -1 }), false);
  assert.equal(isTabbableCandidate({ notRendered: true }), false);
});
