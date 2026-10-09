/**
 * Entry of the static GitHub Pages demo (docs/DEMO_STATIC_DESIGN.md). Production code reaches this module
 * only through a dynamic import behind IS_STATIC_DEMO, so a normal build never contains it.
 */
import { installDemoFetch as install } from './demoFetch.ts';

export { IS_STATIC_DEMO } from './flag.ts';
export { DEMO_MODULES, isDemoModule } from './demoModules.ts';

/** Installs the snapshot-backed fetch using the app's base path. */
export function installDemoFetch(): void {
  install(import.meta.env.BASE_URL);
}
