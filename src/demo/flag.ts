/**
 * Compile-time switch for the static GitHub Pages demo (docs/DEMO_STATIC_DESIGN.md section 2).
 * Vite replaces the env access with a literal, so in a normal build this is `false` and every
 * branch guarded by it, including the dynamic import of the demo module, is removed.
 * Do not import this file from tests: tsx has no import.meta.env. Tests import demoFetch.ts directly.
 */
export const IS_STATIC_DEMO: boolean = import.meta.env.VITE_STATIC_DEMO === '1';
