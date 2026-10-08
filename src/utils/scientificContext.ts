import type { ActiveSpecimenState } from '../store/useMaterialSpecimenStore';
import type { ModuleId } from '../data/workspaces';
import { formatDisplayNumber } from './numberFormat';
import { ruleOfMixturesDensity } from './compositionPropertyAvailability';

export interface ScientificContext {
  title: string;
  observation: string;
  mechanism: string;
  variables: string[];
  interpretation: string;
  limitation: string;
}

// Browser-locale formatting showed "1.200 mm/s" and "31,25 J/mm³" in a Turkish browser; same rounding, fixed locale.
const format = formatDisplayNumber;
// The shared specimen holds no composition-derived temperatures or strengths (COMPOSITION_PROPERTY_UNAVAILABLE_NOTE).
const COMPOSITION_PROPERTY_UNAVAILABLE_SHORT = 'unavailable (not computed from composition)';

// Display density is recomputed from the shown composition; the store's density_gcm3 keeps an internal 8.0 g/cm³
// per-element fallback for LPBF inputs and must not be shown as a number.
function densityContextLine(specimen: ActiveSpecimenState): string {
  const density = ruleOfMixturesDensity(specimen.composition, specimen.unit);
  return density.status === 'computed'
    ? `Density (inverse rule of mixtures, wt.%): ${format(density.density_gcm3, 3)} g/cm³`
    : `Density: unavailable (${density.note.replace(/^Unavailable: /, '')})`;
}

// Modules that have a module-specific context text above. Every other module would fall through to the generic
// default at the end of buildScientificContext, which prints the shared LPBF specimen numbers (composition, density,
// freezing range) that are unrelated to that module, so the panel is hidden there (see ScientificContextPanel).
const MODULES_WITH_CONTEXT: ReadonlySet<string> = new Set([
  '3d-distortion-lab', 'phase-diagram',
  'research-hub', 'experimental-data', 'traceability',
]);

export function hasScientificContext(moduleId: ModuleId): boolean {
  return MODULES_WITH_CONTEXT.has(moduleId);
}

export function buildScientificContext(moduleId: ModuleId, specimen: ActiveSpecimenState): ScientificContext {
  const { lpbf } = specimen;
  const ved = lpbf.laserPower_W / ((lpbf.scanSpeed_mms || 1) * (lpbf.hatch_um / 1000) * (lpbf.layer_um / 1000));
  const shared = `Active specimen ${specimen.name}; ${format(lpbf.laserPower_W)} W, ${format(lpbf.scanSpeed_mms)} mm/s, ${format(lpbf.hatch_um)} µm hatch, ${format(lpbf.layer_um)} µm layer.`;

  if (moduleId === '3d-distortion-lab') return {
    title: 'LPBF process physics',
    observation: `${shared} These inputs mainly control deposited energy and inter-layer heat transport.`,
    mechanism: 'The moving laser creates a melt pool that solidifies as thermal gradients, latent heat, and constrained contraction evolve. Too little energy raises lack-of-fusion risk; too much energy increases keyhole porosity, recoil, and residual stress tendency.',
    variables: [`Computed VED: ${format(ved, 2)} J/mm³`, 'Thermal conductivity is temperature-dependent; inspect the executed material table for values used.', `Preheat: ${format(lpbf.preheatTemp_C)} °C`, `Material family: ${specimen.baseMetal}, ${specimen.xrd.crystalSystem}`],
    interpretation: 'VED is a first-order signal only. A physically grounded readout should also include beam profile, absorption behavior, scan pattern, shielding quality, and heat accumulation trend.',
    limitation: 'This panel explains process physics only; it does not by itself prove density, strength, or certification readiness.',
  };

  // Only the phase-equilibrium and transformation-kinetics views get the microstructure text; a trailing
  // `|| moduleId` used to route every other module (corrosion, EIS, databases...) here as well.
  if (moduleId === 'phase-diagram') return {
    title: 'How thermal history changes microstructure',
    observation: `${shared} This module checks temperature-time path, phase equilibrium, or kinetic transformation behavior.`,
    mechanism: 'Phase stability follows Gibbs free-energy balance; transformation rates follow diffusion and nucleation kinetics. Fast cooling can shift behavior away from equilibrium; soak steps increase diffusion-controlled growth.',
    variables: [`Liquidus / solidus / solvus: ${COMPOSITION_PROPERTY_UNAVAILABLE_SHORT}`, `Nominal phase labels (rule-based, not computed): ${specimen.stablePhases.join(', ')}`, `Thermal conductivity: ${format(lpbf.thermalConductivity_k_WmK)} W/m·K`],
    interpretation: 'Equilibrium diagrams provide a near-equilibrium reference, while TTT/CCT maps kinetics for a specific composition and cooling trajectory. Neither replaces direct microstructural measurement.',
    limitation: 'Results depend on database quality, initial microstructure assumptions, and cooling-rate accuracy. This is not a substitute for experiment.',
  };

  if (moduleId === 'research-hub' || moduleId === 'experimental-data' || moduleId === 'traceability') return {
    title: 'Evidence chain for any claim',
    observation: `${shared} Here the goal is traceability: which data supports a claim, under which conditions, with what uncertainty.`,
    mechanism: 'Scientific confidence is built through claim → method → data → condition match → uncertainty characterization → independent validation. Solver convergence supports numerical robustness; external comparison supports real-world confidence.',
    variables: [`Freeze range and yield strength: ${COMPOSITION_PROPERTY_UNAVAILABLE_SHORT}`, `Specimen source: ${specimen.sourceTab}`, `Process seed: ${lpbf.processSeed}`],
    interpretation: 'Treat values as context, not a final conclusion. Evidence types should remain separated as measured data, literature estimate, simulation screening, or unresolved.',
    limitation: 'If the source is missing, conditions do not match, or synthetic data dominates, it must not be escalated into qualification evidence.',
  };

  return {
    title: 'Scientific interpretation for this module',
    observation: `${shared} The model output shown in this module reflects how input parameters and assumptions map to predicted behavior.`,
    mechanism: 'The model combines constitutive assumptions, material properties, and boundary conditions to generate a testable prediction.',
    variables: [`Composition: ${Object.entries(specimen.composition).map(([element, value]) => `${element} ${format(value)}%`).join(', ')}`, densityContextLine(specimen), `Solidification range: ${COMPOSITION_PROPERTY_UNAVAILABLE_SHORT}`],
    interpretation: 'Start by checking assumptions, then sensitive inputs, then the evidence type attached to each value.',
    limitation: 'Model output is not a measurement. Uncertainty, coverage, and validation status must always be carried with the result.',
  };
}

