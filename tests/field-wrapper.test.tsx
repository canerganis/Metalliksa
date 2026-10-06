import React from "react";
import test from "node:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import { Field, buildFieldIds, describedByIds, mergeIdList } from "../src/components/Field";

test("id helpers are deterministic", () => {
  const ids = buildFieldIds("f1");
  assert.deepEqual(ids, { control: "f1", hint: "f1-hint", error: "f1-error" });
  assert.equal(describedByIds(ids, false), undefined);
  assert.equal(describedByIds(ids, true), "f1-hint");
});

test("render-prop field wires label, hint, error, required and unit", () => {
  const html = renderToStaticMarkup(
    <Field id="temp" label="Temperature" unit="K" hint="300-2000" error="Too low" required>
      {(p) => <input type="number" {...p} />}
    </Field>,
  );
  assert.match(html, /<label for="temp">Temperature/);
  assert.match(html, /id="temp"/);
  assert.match(html, /aria-describedby="temp-hint"/);
  assert.match(html, /aria-invalid="true"/);
  assert.match(html, /aria-required="true"/);
  assert.match(html, /id="temp-hint"/);
  assert.match(html, /<p id="temp-error" role="alert">Too low<\/p>/);
  assert.match(html, />K</);
});

test("children cloning works for select and textarea, no extras when plain", () => {
  const sel = renderToStaticMarkup(<Field id="s" label="Alloy"><select><option>A</option></select></Field>);
  assert.match(sel, /<select id="s">/);
  assert.doesNotMatch(sel, /aria-invalid|aria-describedby|aria-required/);
  const ta = renderToStaticMarkup(<Field id="n" label="Notes" hint="h"><textarea /></Field>);
  assert.match(ta, /<textarea id="n" aria-describedby="n-hint">/);
});

test("generated ids are unique and match label for", () => {
  const html = renderToStaticMarkup(
    <div>
      <Field label="A"><input /></Field>
      <Field label="B"><input /></Field>
    </div>,
  );
  const ids = [...html.matchAll(/<input id="([^"]+)"/g)].map((m) => m[1]);
  assert.equal(ids.length, 2);
  assert.notEqual(ids[0], ids[1]);
  for (const id of ids) assert.ok(html.includes(`for="${id}"`));
});

test("error is not referenced by aria-describedby (role=alert only)", () => {
  const html = renderToStaticMarkup(<Field id="e" label="E" error="bad"><input /></Field>);
  assert.doesNotMatch(html, /aria-describedby/);
  assert.match(html, /role="alert"/);
});

test("mergeIdList dedupes and keeps existing ids first", () => {
  assert.equal(mergeIdList(undefined, undefined), undefined);
  assert.equal(mergeIdList("a b", "b c"), "a b c");
  assert.equal(mergeIdList("  ", "x"), "x");
});

test("cloned child keeps its own id and describedby merged with hint", () => {
  const html = renderToStaticMarkup(
    <Field label="L" hint="h"><input id="mine" aria-describedby="ext" /></Field>,
  );
  assert.match(html, /<label for="mine">/);
  assert.match(html, /id="mine"/);
  assert.match(html, /aria-describedby="ext [^"]+-hint"/);
});
