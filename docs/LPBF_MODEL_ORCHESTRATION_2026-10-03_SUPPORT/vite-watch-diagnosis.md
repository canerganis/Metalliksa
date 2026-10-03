# Vite watcher failure source diagnosis — 2026-10-03

Read-only source/log inspection only. No test was rerun; no source, docs, index, process, browser, or commit changes were made.

## Observed failure

`native-unit.log` reports **372 tests, 370 pass, 1 fail, 1 skip**, suite duration 54.174 s. There is exactly one failure: `tests/vite-watch.test.ts` at test line 9, assertion at line 38, after 8,252 ms. The assertion text is `application source watcher must become ready`. No other tests failed. Build was not run.

## Source and environment facts

- Test source: `tests/vite-watch.test.ts:10-18` calls `mkdtemp(path.join(tmpdir(), 'metalliksa-vite-watch-'))` and creates `src/probe.ts` plus generated files below that root.
- `tests/vite-watch.test.ts:24-31` loads `path.resolve('vite.config.ts')` while setting the Vite `root` to that fixture. In the native run the test/cwd path in the stack is inside `.runtime/v1-input-claims-native-20261003`, so the project config is selected from that snapshot.
- `tests/vite-watch.test.ts:33-38` polls `server.watcher.getWatched()` for the source directory for 5 seconds, then fails if the source is absent. It does not wait for or record Chokidar's `ready` event or dump the watched-path map.
- Native run's `TMP`/`TEMP` points to `.tmp-lpbf-input-claims-acceptance-20261003/native-temp` (provided run context). Node `os.tmpdir()` therefore places the test fixture under that `.tmp-lpbf-*` ancestor.
- `vite.config.ts` sets `server.watch.ignored` patterns including `**/.tmp-lpbf*/**` (along with graft, `.lpbf-*`, warp cache, and partial docs patterns). The test deletes `DISABLE_HMR` before creating Vite, so the config does not select `watch: null`; the per-test `hmr:false` option disables HMR transport, not the file watcher.
- Installed Vite is 6.4.3. Its bundled watcher option resolver at `node_modules/vite/dist/node/chunks/dep-Dm0c1Wj2.js:27537-27558` appends configured ignored patterns. The bundled `FSWatcher._isIgnored` at lines 24014-24028 applies `anymatch` to paths; `_addToNodeFs` at 22653-22658 returns without watching an ignored root. `disableGlobbing:true` is passed for watched input paths but does not disable matching of configured ignore globs.

## Diagnosis

**Strong, environment-dependent fixture/config interaction:** under the supplied native `TMP` parent, the fixture's absolute root path contains `.tmp-lpbf-input-claims-acceptance-20261003`. The project's `**/.tmp-lpbf*/**` ignore rule therefore matches the fixture root and its descendants. Vite can consequently have no watched `src/probe.ts` entry, which explains the exact readiness assertion. This does not establish a production watch failure when the application root is outside that ignored ancestor.

This is a source-based causal diagnosis, not a runtime-observed matched path: the failure log contains only the assertion and stack, not `getWatched()` contents or ignored-match traces. A separate 5-second readiness timeout could be sensitive to load in other environments, but CPU contention is not needed to explain this particular run if the supplied TMP path was inherited as reported. Extending the timeout alone would not correct an ignored fixture root.

## Graft coverage

The first Graft query identified the two relevant files but returned no inline source spans. `graft skeleton tests/vite-watch.test.ts` indexed only the nested `watchedSource` helper at lines 33-35; it omitted the top-level test body. `graft skeleton vite.config.ts` reported no indexed definitions. The generated native log and installed Vite dependency are not represented by those graph nodes, so I inspected the exact snapshot test/config and bundled watcher source directly. No graph refresh was reported.

## Confidence and next decision

High confidence that the test fixture location is incompatible with the current ignore glob under this run's TMP setting; not evidence of a general production watcher bug or random flake. A code owner can make the test independent of inherited TMP placement or scope the ignored-path verification so its own fixture root is not excluded. Do not infer the fix has passed until the focused watcher test is later rerun. No claim about CPU contention or browser acceptance is made.
