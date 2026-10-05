import React from "react";
import { Compass, RefreshCw, Table, ShieldCheck, AlertTriangle, Layers, Activity } from "lucide-react";
import { PythonDFTOutcome, isDftUnavailable } from "../services/pythonComputationService";
import {
  UNAVAILABLE_TEXT,
  computeTimeText,
  directionLabel,
  formatOrUnavailable,
  formatZener,
  provenanceLine,
} from "../utils/elasticityDisplay";

/**
 * Result panel of the continuum-elasticity engine (python/dft_property_calculator.py): 6x6 C_ij homogenisation,
 * Born stability, per-atom Debye temperature. Not a DFT calculation; every number the engine could not
 * compute is shown as "Unavailable" with its reason.
 */
export function ElasticityResultPanel({ outcome, computing }: { outcome: PythonDFTOutcome | null; computing: boolean }) {
  const dftUnavailable = outcome && isDftUnavailable(outcome) ? outcome : null;
  const dftResult = outcome && !isDftUnavailable(outcome) ? outcome : null;
  const pythonDftResult = outcome;
  const isDftComputing = computing;

  return (
      <div className="space-y-4 font-mono text-xs">
        {/* Engine Telemetry & Header */}
        <div className="p-3 bg-[#050810] rounded-xl border border-emerald-500/30 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 motion-safe:animate-ping" />
            <span className="text-emerald-300 font-bold">
              {pythonDftResult?.engine || "MetalliX Continuum Elasticity Engine"}
            </span>
            {computeTimeText(pythonDftResult) !== null && (
              <>
                <span className="text-slate-500">•</span>
                <span className="text-slate-400" data-testid="elasticity-compute-time">
                  Compute Time: <strong className="text-white">{computeTimeText(pythonDftResult)}</strong>
                </span>
              </>
            )}
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
            6x6 Stiffness Inversion & Anisotropy
          </span>
        </div>

        {isDftComputing ? (
          <div className="py-12 text-center text-slate-400 space-y-2">
            <RefreshCw className="w-6 h-6 motion-safe:animate-spin mx-auto text-emerald-400" />
            <p className="text-xs">Homogenising the 6x6 stiffness tensor & Debye temperature via Python...</p>
          </div>
        ) : dftUnavailable ? (
          <div className="p-4 bg-[#050810] rounded-xl border border-amber-500/30 space-y-1" data-testid="elasticity-unavailable">
            <span className="text-amber-300 font-bold text-xs block">{UNAVAILABLE_TEXT}</span>
            <p className="text-[11px] text-slate-400 leading-relaxed">{dftUnavailable.reason}</p>
          </div>
        ) : dftResult ? (
          <div className="space-y-4">
            <p className="text-[10px] text-slate-500 leading-relaxed" data-testid="elasticity-provenance">
              {provenanceLine(dftResult)}
            </p>

            {/* Born Mechanical Stability */}
            {dftResult.bornStability && (
              <div className={`p-4 rounded-xl border space-y-3 ${
                dftResult.bornStability.isMechanicallyStable
                  ? "bg-emerald-950/20 border-emerald-500/30"
                  : "bg-rose-950/20 border-rose-500/30"
              }`}>
                <div className="flex items-center justify-between">
                  <span className={`font-bold flex items-center gap-1.5 text-xs ${
                    dftResult.bornStability.isMechanicallyStable ? "text-emerald-400" : "text-rose-400"
                  }`}>
                    {dftResult.bornStability.isMechanicallyStable ? (
                      <ShieldCheck className="w-4 h-4" />
                    ) : (
                      <AlertTriangle className="w-4 h-4" />
                    )}
                    <span>Born Mechanical Stability</span>
                  </span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                    dftResult.bornStability.isMechanicallyStable
                      ? "bg-emerald-500/20 text-emerald-300"
                      : "bg-rose-500/20 text-rose-300"
                  }`}>
                    {dftResult.bornStability.verdict}
                  </span>
                </div>
                <div className="text-[11px] text-slate-400">
                  Minimum Eigenvalue: <strong className="text-white">{dftResult.bornStability.minimumEigenvalueGPa.toFixed(2)} GPa</strong>
                  <p className="mt-1 text-[10px] text-slate-500">Note: Mechanical stability (Born criteria) concerns elastic restoring forces against infinitesimal strain, distinct from thermodynamic phase stability (convex hull).</p>
                </div>
              </div>
            )}

            {/* Voigt-Reuss-Hill Moduli & Indices */}
            <div className="p-4 bg-[#050810] rounded-xl border border-[#162032] space-y-4">
              <div className="flex items-center gap-1.5 text-white font-bold text-xs">
                <Layers className="w-3.5 h-3.5 text-sky-400" />
                <span>Voigt-Reuss-Hill (VRH) Moduli</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 bg-[#090e18] rounded-lg border border-[#1e2d46]">
                  <span className="text-[10px] text-slate-400 block uppercase">Bulk Modulus K</span>
                  <span className="text-sm font-bold text-sky-400">{dftResult.voigtReussHillModuli.bulkModulus_K_VRH_GPa.toFixed(1)} GPa</span>
                </div>
                <div className="p-3 bg-[#090e18] rounded-lg border border-[#1e2d46]">
                  <span className="text-[10px] text-slate-400 block uppercase">Shear Modulus G</span>
                  <span className="text-sm font-bold text-emerald-400">{dftResult.voigtReussHillModuli.shearModulus_G_VRH_GPa.toFixed(1)} GPa</span>
                </div>
                <div className="p-3 bg-[#090e18] rounded-lg border border-[#1e2d46]">
                  <span className="text-[10px] text-slate-400 block uppercase">Young's Modulus E</span>
                  <span className="text-sm font-bold text-amber-400">{dftResult.voigtReussHillModuli.youngsModulus_E_VRH_GPa.toFixed(1)} GPa</span>
                </div>
                <div className="p-3 bg-[#090e18] rounded-lg border border-[#1e2d46]">
                  <span className="text-[10px] text-slate-400 block uppercase">Poisson's Ratio ν</span>
                  <span className="text-sm font-bold text-white">{dftResult.voigtReussHillModuli.poissonsRatio_nu.toFixed(3)}</span>
                </div>
              </div>

              <div className="pt-2 border-t border-[#1e2d46] grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="flex items-center justify-between p-2 bg-[#090e18] rounded border border-[#1e2d46]">
                  <span className="text-[10px] text-slate-400 flex items-center gap-1.5"><Activity className="w-3 h-3 text-purple-400"/> Pugh's Ratio (B/G)</span>
                  <div className="text-right">
                    <span className="text-xs font-bold text-white">{dftResult.mechanicalIntegrityIndices.pughRatio_B_over_G.toFixed(2)}</span>
                    <span className="text-[9px] text-slate-500 block">{dftResult.mechanicalIntegrityIndices.ductilityVerdict} (Qualitative)</span>
                  </div>
                </div>
                <div className="flex items-center justify-between p-2 bg-[#090e18] rounded border border-[#1e2d46]">
                  <span className="text-[10px] text-slate-400">Universal Anisotropy (A^U)</span>
                  <span className="text-xs font-bold text-white">{dftResult.mechanicalIntegrityIndices.universalAnisotropyIndex_AU.toFixed(3)}</span>
                </div>
              </div>
            </div>

            {/* 6x6 Elastic Stiffness Tensor C_ij (GPa) */}
            <div className="p-4 bg-[#050810] rounded-xl border border-[#162032] space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-white font-bold flex items-center gap-1.5 text-xs">
                  <Table className="w-3.5 h-3.5 text-emerald-400" />
                  <span>6x6 Elastic Stiffness Tensor C_ij (GPa)</span>
                </span>
                <span className="text-[10px] text-slate-400">Voigt Notation (i, j ∈ [1..6])</span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-center border-collapse">
                  <thead>
                    <tr className="border-b border-[#1e2d46] text-slate-400 text-[10px]">
                      <th className="p-1 text-left">GPa</th>
                      <th className="p-1">C_1j</th>
                      <th className="p-1">C_2j</th>
                      <th className="p-1">C_3j</th>
                      <th className="p-1">C_4j</th>
                      <th className="p-1">C_5j</th>
                      <th className="p-1">C_6j</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dftResult.elasticStiffnessMatrix_Cij_GPa.map((row, rIdx) => (
                      <tr key={rIdx} className="border-b border-[#162032] hover:bg-[#0c1322]/50">
                        <td className="p-1.5 text-left font-bold text-slate-400 text-[10px]">C_{rIdx + 1}k</td>
                        {row.map((val, cIdx) => (
                          <td
                            key={cIdx}
                            className={`p-1.5 text-[11px] font-bold ${
                              val === 0
                                ? "text-slate-600"
                                : rIdx === cIdx
                                ? "text-sky-300 bg-sky-950/20"
                                : "text-emerald-400"
                            }`}
                          >
                            {val}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Acoustic Wave Velocities & Thermal Properties */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 bg-[#050810] rounded-xl border border-[#162032]">
                <span className="text-[10px] text-slate-400 block uppercase">Debye Temp ($\Theta_D$)</span>
                <span
                  className="text-sm font-bold text-purple-300"
                  title={dftResult.acousticAndThermalProperties.reason ?? undefined}
                >
                  {formatOrUnavailable(dftResult.acousticAndThermalProperties.debyeTemperature_K, "K")}
                </span>
              </div>
              <div className="p-3 bg-[#050810] rounded-xl border border-[#162032]">
                <span className="text-[10px] text-slate-400 block uppercase">Longitudinal $v_l$</span>
                <span className="text-sm font-bold text-sky-300">
                  {formatOrUnavailable(dftResult.acousticAndThermalProperties.longitudinalSoundVelocity_m_s, "m/s")}
                </span>
              </div>
              <div className="p-3 bg-[#050810] rounded-xl border border-[#162032]">
                <span className="text-[10px] text-slate-400 block uppercase">Transverse $v_t$</span>
                <span className="text-sm font-bold text-emerald-300">
                  {formatOrUnavailable(dftResult.acousticAndThermalProperties.transverseSoundVelocity_m_s, "m/s")}
                </span>
              </div>
              <div className="p-3 bg-[#050810] rounded-xl border border-[#162032]">
                <span className="text-[10px] text-slate-400 block uppercase">Cauchy Pressure</span>
                <span className={`text-sm font-bold ${
                  dftResult.mechanicalIntegrityIndices.cauchyPressure_C12_minus_C44_GPa > 0
                    ? "text-emerald-400"
                    : "text-rose-400"
                }`}>
                  {dftResult.mechanicalIntegrityIndices.cauchyPressure_C12_minus_C44_GPa} GPa
                </span>
              </div>
            </div>

            {/* Directional Young's Modulus E(hkl) */}
            <div className="p-4 bg-[#050810] rounded-xl border border-[#162032] space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-white font-bold flex items-center gap-1.5 text-xs">
                  <Compass className="w-3.5 h-3.5 text-sky-400" />
                  <span>Directional Young's Modulus $E(n)$</span>
                </span>
                <span className="text-[10px] text-slate-400">
                  Zener Factor $A_Z$: <strong className="text-white">{formatZener(dftResult.mechanicalIntegrityIndices.zenerAnisotropyFactor_AZ)}</strong>
                </span>
              </div>

              {dftResult.directionalYoungsModuli ? (
                <div className="grid grid-cols-3 gap-2">
                  {dftResult.directionalYoungsModuli.map((dir) => (
                    <div key={dir.direction} className="p-2.5 rounded-lg bg-[#090e18] border border-[#1e2d46] text-center">
                      <div className="text-[10px] text-slate-400">{directionLabel(dir)}</div>
                      <div className="text-sm font-bold text-sky-300">{formatOrUnavailable(dir.youngsModulusGPa, "GPa")}</div>
                      <div className="text-[9px] text-slate-500 mt-0.5">
                        {dir.ratioToAverage === null ? UNAVAILABLE_TEXT : `${dir.ratioToAverage}x of E_VRH`}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-[11px] text-slate-400" data-testid="elasticity-directional-unavailable">
                  {UNAVAILABLE_TEXT}: {dftResult.directionalYoungsModuliReason ?? "no directional modulus"}
                </p>
              )}
            </div>
          </div>
        ) : null}
      </div>
  );
}
