import type { SimulationResult } from "../../services/lpbfSimulationService";

const format = (value: number | null) => value === null ? "Unresolved" : value.toLocaleString("en-US", { maximumSignificantDigits: 5 });

export function LpbfPhysicsDiagnostics({ result }: { result: SimulationResult }) {
  const diagnostics = result.numericalDiagnostics;
  const screen = result.geometricDefectScreen;
  const sourceIntegration = diagnostics?.sourceIntegration;
  const sourceIntegrationLabel = sourceIntegration === "cell-integrated-gaussian-adaptive-gl-v2"
    ? "Adaptive Gauss-Legendre source integration"
    : sourceIntegration === "cell-integrated-gaussian-gl2-v1"
      ? "Two-point Gauss-Legendre source integration"
      : sourceIntegration
        ? `Source integration method unavailable · recorded identifier: ${sourceIntegration}`
        : "Source integration method unavailable";
  if (!diagnostics && !screen && !result.fieldOverlapDiagnostics) return null;
  return <section aria-label="Physics resolution and overlap" className="rounded-xl border border-slate-700 bg-slate-900/50 p-5 space-y-5">
    <h4 className="font-medium text-slate-100">Physics resolution and overlap</h4>
    {diagnostics && <div className="space-y-3">
      <p className="text-sm text-slate-200">{sourceIntegrationLabel}</p>
      <dl className="grid gap-4 text-sm sm:grid-cols-2 xl:grid-cols-3">
        {([
          ["Minimum captured source", `${format(diagnostics.minimumCapturedSourceFraction * 100)}%`],
          ["Maximum power renormalization", `${format(diagnostics.maximumSourceRenormalization)}×`],
          ["Maximum layer surface offset", `${format(diagnostics.maximumSurfaceOffset_um)} µm`],
          ["Maximum accepted timestep", `${format(diagnostics.maximumTimestep_s * 1e6)} µs`],
          ["Maximum sensible-equivalent increment", `${format(diagnostics.maximumEnthalpyIncrement_K)} K`],
          ["Source timestep retries", format(diagnostics.sourceTimestepRetries)],
        ] as const).map(([label, value]) => <div key={label}><dt className="text-slate-400">{label}</dt><dd className="mt-1 tabular-nums text-slate-100">{value}</dd></div>)}
      </dl>
      {diagnostics.acceptedTimestepDistribution && <details className="text-xs text-slate-300">
        <summary className="cursor-pointer py-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-300">Accepted timestep distribution</summary>
        <dl className="grid gap-3 py-2 sm:grid-cols-2 xl:grid-cols-3">
          <div><dt className="text-slate-400">Accepted steps</dt><dd className="mt-1 tabular-nums">{diagnostics.acceptedTimestepDistribution.count.toLocaleString("en-US")}</dd></div>
          <div><dt className="text-slate-400">Median / 90th percentile</dt><dd className="mt-1 tabular-nums">{format(diagnostics.acceptedTimestepDistribution.p50_s * 1e9)} / {format(diagnostics.acceptedTimestepDistribution.p90_s * 1e9)} ns</dd></div>
          <div><dt className="text-slate-400">Euler weighted timestep</dt><dd className="mt-1 tabular-nums">{format(diagnostics.acceptedTimestepDistribution.eulerFirstOrderWeightedDt_s * 1e9)} ns</dd></div>
          <div><dt className="text-slate-400">Steps at requested max dt</dt><dd className="mt-1 tabular-nums">{format(diagnostics.acceptedTimestepDistribution.requestedMaxDtHitFraction * 100)}%</dd></div>
          <div><dt className="text-slate-400">Source-limited steps</dt><dd className="mt-1 tabular-nums">{diagnostics.acceptedTimestepDistribution.sourceLimitedStepCount.toLocaleString("en-US")}</dd></div>
        </dl>
        <p className="leading-5 text-amber-200">The Euler weighted timestep summarizes the realized step sequence. It is diagnostic evidence, not a convergence pass criterion.</p>
      </details>}
      <p className="text-xs leading-5 text-amber-200">Thermal evolution remains first-order in time. Active layers use whole cells. Source integration and conservation do not establish mesh convergence or experimental accuracy.</p>
    </div>}
    {screen && <div className="space-y-3 border-t border-slate-700 pt-4">
      <h5 className="text-sm font-medium">Elliptical inter-track overlap · {screen.lackOfFusion.status.replaceAll("-", " ")}</h5>
      <p className="text-xs text-slate-400">Idealized criterion: (h/W)² + (t/D)² ≤ 1. {screen.lackOfFusion.reason}</p>
      <dl className="grid gap-4 text-sm sm:grid-cols-3">
        <div><dt className="text-slate-400">Overlap index</dt><dd className="mt-1 tabular-nums">{format(screen.lackOfFusion.ellipseIndex)}</dd></div>
        <div><dt className="text-slate-400">Overlap depth</dt><dd className="mt-1 tabular-nums">{format(screen.lackOfFusion.overlapDepth_um)}{screen.lackOfFusion.overlapDepth_um !== null && " µm"}</dd></div>
        <div><dt className="text-slate-400">Geometric hatch limit</dt><dd className="mt-1 tabular-nums">{format(screen.lackOfFusion.maximumHatch_um)}{screen.lackOfFusion.maximumHatch_um !== null && " µm"}</dd></div>
      </dl>
      <p className="text-xs leading-5 text-amber-200">Keyhole pores, balling, gas pores and porosity remain unresolved. A geometric hatch limit is not a recommended process setting.</p>
      <details className="text-xs text-slate-300"><summary className="cursor-pointer py-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-300">Model assumptions and source</summary>
        <ul className="list-disc space-y-2 pl-5 py-2">{screen.limitations.map(item => <li key={item}>{item}</li>)}</ul>
        <a className="underline" href="https://link.springer.com/article/10.1007/s00170-023-11163-0" target="_blank" rel="noreferrer">Harkin et al. (2023), Equation 5</a>
      </details>
    </div>}
    {result.fieldOverlapDiagnostics && <div className="space-y-3 border-t border-slate-700 pt-4">
      <h5 className="text-sm font-medium text-slate-100">
        Field-resolved inter-track overlap · {result.fieldOverlapDiagnostics.status.replaceAll("-", " ")}
      </h5>
      <p className="text-xs text-slate-400">{result.fieldOverlapDiagnostics.note}</p>
      <dl className="grid gap-4 text-sm sm:grid-cols-2 xl:grid-cols-3">
        <div><dt className="text-slate-400">Inter-track overlap</dt><dd className="mt-1 tabular-nums text-slate-100">{result.fieldOverlapDiagnostics.trackOverlapRatio !== null ? `${format(result.fieldOverlapDiagnostics.trackOverlapRatio * 100)}%` : "N/A (single track)"}</dd></div>
        <div><dt className="text-slate-400">Inter-track gap volume</dt><dd className="mt-1 tabular-nums text-slate-100">{format(result.fieldOverlapDiagnostics.interTrackGapVolume_um3)} µm³</dd></div>
        <div><dt className="text-slate-400">Global remelting ratio</dt><dd className="mt-1 tabular-nums text-slate-100">{format(result.fieldOverlapDiagnostics.globalRemeltRatio * 100)}%</dd></div>
        <div><dt className="text-slate-400">Substrate penetration depth</dt><dd className="mt-1 tabular-nums text-slate-100">{format(result.fieldOverlapDiagnostics.interLayerPenetrationDepth_um ?? 0)} µm</dd></div>
        <div><dt className="text-slate-400">Total molten volume</dt><dd className="mt-1 tabular-nums text-slate-100">{format(result.fieldOverlapDiagnostics.totalMeltVolume_um3)} µm³</dd></div>
        <div><dt className="text-slate-400">Total remelt volume</dt><dd className="mt-1 tabular-nums text-slate-100">{format(result.fieldOverlapDiagnostics.totalRemeltVolume_um3)} µm³</dd></div>
      </dl>
      <p className="text-xs leading-5 text-amber-200">Field-based overlap measures contiguous molten voxel envelopes across adjacent scan vectors. It does not replace full free-surface CFD or tomography qualification.</p>
    </div>}
  </section>;
}
