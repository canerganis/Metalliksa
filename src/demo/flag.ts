/**
 * Compile-time switch for the static GitHub Pages demo (docs/DEMO_STATIC_DESIGN.md section 2).
 * vite.config.ts defines __STATIC_DEMO__ as a literal (true only for `vite build --mode demo` or VITE_STATIC_DEMO=1),
 * so in a normal build this is `false` and every branch guarded by it, including the dynamic import of the demo
 * module, is removed. Under tsx (unit tests) nothing defines it and the typeof guard yields false.
 */
declare const __STATIC_DEMO__: boolean | undefined;
export const IS_STATIC_DEMO: boolean = typeof __STATIC_DEMO__ !== 'undefined' && __STATIC_DEMO__ === true;
