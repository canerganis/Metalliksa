import React from "react";
import test from "node:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import { MeltPoolExtentNotice } from "../src/components/MeltPoolExtentNotice";

test("amber notice shows the status and the note for non-computed extents", () => {
  const markup = renderToStaticMarkup(
    <MeltPoolExtentNotice geometry={{ extentStatus: "heuristic-width-fallback", extentNote: "not a computed isotherm" }} />,
  );
  assert.match(markup, /data-extent-status="heuristic-width-fallback"/);
  assert.match(markup, /border-amber-500\/40/);
  assert.match(markup, />heuristic-width-fallback</);
  assert.match(markup, /not a computed isotherm/);
});

test("each non-computed status renders; computed renders nothing", () => {
  for (const status of ["width-floor-applied", "search-box-limited"]) {
    assert.match(renderToStaticMarkup(<MeltPoolExtentNotice geometry={{ extentStatus: status, extentNote: null }} />), new RegExp(`data-extent-status="${status}"`));
  }
  assert.equal(renderToStaticMarkup(<MeltPoolExtentNotice geometry={{ extentStatus: "computed", extentNote: null }} />), "");
  assert.match(renderToStaticMarkup(<MeltPoolExtentNotice geometry={{}} />), /data-extent-status="not-reported"/);
});
