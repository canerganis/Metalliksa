import type { ModuleId } from './workspaces';

// Sub-views that live inside a module's own tabs, so a search for them finds the module (review S5).
export const SUBVIEW_KEYWORDS: Partial<Record<ModuleId, string>> = {
  'electrochem-suite': 'pourbaix e-ph eh-ph tafel polarization pren pitting galvanic eis impedance coating delamination',
  'micrograph': 'metallography grain size astm e112 segmentation porosity image',
  'phase-diagram': 'calphad gibbs tdb equilibrium liquidus solidus',
};
