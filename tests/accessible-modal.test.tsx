import React from "react";
import test from "node:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import {
  AccessibleModal,
  closeTopmostOverlay,
  escapeStackDepth,
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
