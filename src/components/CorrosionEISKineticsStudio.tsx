import React, { useState, useEffect } from "react";
import { useDebouncedLatestTask } from "../hooks/useDebouncedLatestTask";
import { isPythonValidationError, validationErrorFromResponse } from "../utils/pythonValidationError";
import { UNAVAILABLE_TEXT } from "../utils/tafelDisplay";
import {
  ShieldAlert,
  RefreshCw,
  Sliders
} from "lucide-react";


export function CorrosionEISKineticsStudio() {
  const [metalId, setMetalId] = useState<string>("steel-316l");
  const [betaA, setBetaA] = useState<number>(0.12);
  const [betaC, setBetaC] = useState<number>(0.10);
  const [i0Corr, setI0Corr] = useState<number>(0.15); // uA/cm2
  // Pitting margin inputs (EUQ-12): measured E_pit and E_corr on one reference electrode. No preset: the former
  // per-substrate "E0" presets were pure-metal SHE standard potentials, not a pitting reference.
  const [ePit, setEPit] = useState<number | null>(null); // V vs referenceElectrode
  const [eCorr, setECorr] = useState<number | null>(null); // V vs referenceElectrode
  const [referenceElectrode, setReferenceElectrode] = useState<string>("SCE");

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [simResult, setSimResult] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const runPythonSimulation = async (signal?: AbortSignal): Promise<boolean> => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const response = await fetch("/api/python/battery-corrosion-eis", {
        signal,
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "corrosion_kinetics",
          metalId,
          betaA,
          betaC,
          i0Corr_uA: i0Corr,
          ePit,
          eCorr,
          ePitReference: referenceElectrode,
          eCorrReference: referenceElectrode,
        }),
      });

      if (!response.ok) {
        // An unknown substrate id is refused by the engine (HTTP 422): show its message, never a guessed alloy.
        const validation = await validationErrorFromResponse(response, "Corrosion kinetics");
        if (validation) throw validation;
        throw new Error(`Python solver HTTP error: ${response.statusText}`);
      }

      const data = await response.json();
      if (data.error) {
        throw new Error(data.error);
      }
      if (signal?.aborted) return false;
      setSimResult(data);
      return true;
    } catch (err: any) {
      if (signal?.aborted) return false;
      console.error("Corrosion kinetics error:", err);
      if (isPythonValidationError(err)) setSimResult(null);
      setErrorMsg(err.message || "Failed to execute Python corrosion kinetics solver.");
      return false;
    } finally {
      if (!signal?.aborted) setIsLoading(false);
    }
  };

  // Debounced, visibility-gated and abortable. The signature only contains request inputs.
  const corrosionInputSignature = JSON.stringify([metalId, betaA, betaC, i0Corr, ePit, eCorr, referenceElectrode]);
  useEffect(() => {
    setSimResult(null);
  }, [corrosionInputSignature]);
  const { runNow: runPythonSimulationNow } = useDebouncedLatestTask(corrosionInputSignature, (_signature, signal) => runPythonSimulation(signal), 200);

  return (
    <div className="space-y-4">
      {/* Top Banner */}
      <div className="p-4 rounded-2xl bg-[#090e18] border border-[#162032] flex flex-col md:flex-row md:items-center justify-between gap-3 shadow-md">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono">
                Corrosion Kinetics: Stern-Geary R_p, Faraday Rate &amp; Pitting Margin
              </h3>
              <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 text-[10px] font-mono border border-amber-500/40">
                Stern-Geary / ASTM G102
              </span>
            </div>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              Calculates R_p polarization resistance, corrosion rate (mm/yr &amp; mpy) and the pitting-potential margin from the entered parameters
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => runPythonSimulationNow()}
            disabled={isLoading}
            className="px-3 py-1.5 rounded-xl bg-[#050810] border border-[#1e2d46] hover:border-amber-500 text-slate-200 text-xs font-mono flex items-center gap-1.5 transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin text-amber-400" : ""}`} />
            <span>Re-Solve</span>
          </button>
        </div>
      </div>

      {errorMsg && (
        <div role="alert" className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/40 text-rose-300 text-xs font-mono">
          {errorMsg}
        </div>
      )}

      {/* Grid: Controls & Output */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column Controls */}
        <div className="lg:col-span-4 space-y-4">
          <div className="p-4 rounded-xl bg-[#090e18] border border-[#162032] space-y-4">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block border-b border-[#162032] pb-2 flex items-center gap-1.5">
              <Sliders className="w-3.5 h-3.5 text-amber-400" />
              Alloy &amp; Electrochemical Parameters
            </span>

            {/* Metal Selection */}
            <div>
              <label className="text-[10px] text-slate-400 block mb-1">Substrate Alloy</label>
              <select aria-label="Substrate Alloy"
                value={metalId}
                onChange={(e) => {
                  const m = e.target.value;
                  setMetalId(m);
                  if (m === "steel-316l") { setI0Corr(0.12); }
                  else if (m === "al-7075") { setI0Corr(1.85); }
                  else if (m === "az31b") { setI0Corr(6.5); }
                  else if (m === "ti-6al-4v") { setI0Corr(0.01); }
                  else if (m === "steel-1018") { setI0Corr(4.2); }
                }}
                className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-amber-500"
              >
                <option value="steel-316l">Stainless Steel 316L (Cr-Ni-Mo)</option>
                <option value="al-7075">Aerospace Aluminum 7075-T6 (Al-Zn-Mg)</option>
                <option value="az31b">Magnesium AZ31B (Sacrificial/Active)</option>
                <option value="ti-6al-4v">Titanium Ti-6Al-4V (Self-Healing TiO₂)</option>
                <option value="steel-1018">Carbon Steel AISI 1018 (Uniform Rust)</option>
              </select>
            </div>

            {/* Tafel Slopes */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Anodic Slope β_a (V/dec)</label>
                <input aria-label="Anodic Slope β_a (V/dec)"
                  type="number"
                  step="0.01"
                  value={betaA}
                  onChange={(e) => setBetaA(parseFloat(e.target.value) || 0.1)}
                  className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Cathodic Slope β_c (V/dec)</label>
                <input aria-label="Cathodic Slope β_c (V/dec)"
                  type="number"
                  step="0.01"
                  value={betaC}
                  onChange={(e) => setBetaC(parseFloat(e.target.value) || 0.1)}
                  className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                />
              </div>
            </div>

            {/* Baseline i_corr */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">Corrosion Current i_corr</span>
                <span className="text-amber-400 font-bold font-mono">{i0Corr} µA/cm²</span>
              </div>
              <input aria-label="Corrosion Current i_corr (µA/cm²)"
                type="range"
                min={0.01}
                max={10.0}
                step={0.05}
                value={i0Corr}
                onChange={(e) => setI0Corr(parseFloat(e.target.value))}
                className="w-full accent-amber-500 h-1.5 bg-[#162032] rounded-lg cursor-pointer"
              />
            </div>

            {/* Pitting margin: measured potentials on one reference electrode (ASTM G61 compares E_pit with E_corr) */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Measured E_pit (V)</label>
                <input aria-label="Measured pitting potential E_pit (V)"
                  type="number"
                  step="0.01"
                  value={ePit ?? ""}
                  placeholder="not supplied"
                  onChange={(e) => setEPit(Number.isFinite(parseFloat(e.target.value)) ? parseFloat(e.target.value) : null)}
                  className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Measured E_corr (V)</label>
                <input aria-label="Measured corrosion potential E_corr (V)"
                  type="number"
                  step="0.01"
                  value={eCorr ?? ""}
                  placeholder="not supplied"
                  onChange={(e) => setECorr(Number.isFinite(parseFloat(e.target.value)) ? parseFloat(e.target.value) : null)}
                  className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                />
              </div>
            </div>
            <div>
              <label className="text-[10px] text-slate-400 block mb-1">Reference electrode (both potentials)</label>
              <select aria-label="Reference electrode for E_pit and E_corr"
                value={referenceElectrode}
                onChange={(e) => setReferenceElectrode(e.target.value)}
                className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-amber-500"
              >
                <option value="SCE">SCE (saturated calomel)</option>
                <option value="Ag/AgCl (sat. KCl)">Ag/AgCl (sat. KCl)</option>
                <option value="SHE">SHE</option>
              </select>
            </div>
          </div>

          {/* Quick Metrics Cards */}
          {simResult && (
            <div className="grid grid-cols-2 gap-2.5">
              <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032]">
                <span className="text-[9px] text-slate-400 block">Polarization Resistance (R_p)</span>
                <span className="text-base font-bold text-amber-400 font-mono">
                  {simResult.polarizationResistance_Rp_Ohm_cm2 == null
                    ? UNAVAILABLE_TEXT
                    : `${simResult.polarizationResistance_Rp_Ohm_cm2.toLocaleString()} Ω·cm²`}
                </span>
                <span className="text-[9px] text-slate-500 block">ASTM G59</span>
              </div>
              <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032]">
                <span className="text-[9px] text-slate-400 block">Penetration Rate (CR)</span>
                <span className="text-base font-bold text-rose-400 font-mono">
                  {simResult.corrosionRate_mm_yr == null ? UNAVAILABLE_TEXT : `${simResult.corrosionRate_mm_yr} mm/yr`}
                </span>
                <span className="text-[9px] text-slate-500 block">
                  ({simResult.corrosionRate_mpy == null ? UNAVAILABLE_TEXT : `${simResult.corrosionRate_mpy} mpy`})
                </span>
                {simResult.equivalentWeight_g_eq != null && (
                  <span className="text-[9px] text-slate-500 block" title={simResult.equivalentWeightNote}>
                    EW {simResult.equivalentWeight_g_eq} g/eq, ρ {simResult.density_g_cm3} g/cm³ ({simResult.alloyId})
                  </span>
                )}
              </div>
            </div>
          )}

          {simResult?.unavailableReason && (
            <div role="status" className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/40 text-amber-200 text-xs font-mono">
              {simResult.unavailableReason}
            </div>
          )}

          {/* Pitting Susceptibility Alert */}
          {simResult && (
            <div
              className={`p-3 rounded-xl border text-xs flex items-start gap-2.5 ${
                simResult.deltaE_pit_V == null
                  ? "bg-slate-500/10 border-slate-500/30 text-slate-300"
                  : simResult.deltaE_pit_V < 0.15
                  ? "bg-rose-500/10 border-rose-500/30 text-rose-300"
                  : "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
              }`}
            >
              <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <span className="font-bold block uppercase text-[10px]">
                  Pitting Margin: ΔE_pit = {simResult.deltaE_pit_V == null ? UNAVAILABLE_TEXT : `${simResult.deltaE_pit_V} V`}
                </span>
                <p className="text-[11px] opacity-90 mt-0.5">
                  Assessment: <strong>{simResult.pittingAssessment ?? UNAVAILABLE_TEXT}</strong>
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: solver inputs/outputs summary. The former coating Nyquist, water-uptake and pore-resistance
            charts came from fixed constants (no request input changed them) and were removed. */}
        <div className="lg:col-span-8 p-4 rounded-xl bg-[#090e18] border border-[#162032] space-y-3">
          <div className="flex items-center justify-between border-b border-[#162032] pb-2 flex-wrap gap-2">
            <span className="text-xs font-bold text-slate-300 font-mono uppercase tracking-wider">Solver Output</span>
            {simResult?.pythonDurationMs && (
              <span className="text-[10px] text-amber-400 font-mono">
                CPython solved in {simResult.pythonDurationMs} ms
              </span>
            )}
          </div>
          <div className="text-[11px] text-slate-400 font-mono space-y-1.5 leading-relaxed">
            <p>R_p = B / i_corr with the Stern-Geary constant B = (β_a·β_c) / (ln 10·(β_a + β_c)).</p>
            <p>Penetration rate (ASTM G102): CR = K1·i_corr·EW / ρ, with EW and ρ resolved from the substrate alloy composition.</p>
            <p>Pitting margin: ΔE_pit = E_pit − E_corr, both entered by you against the same reference electrode ({referenceElectrode}; E_pit = {ePit ?? "not supplied"} V, E_corr = {eCorr ?? "not supplied"} V), as ASTM G61 compares E_pit with E_corr. No potential is preset. The qualitative label uses fixed in-house thresholds (not a standard).</p>
            <p>Coating degradation (water uptake, pore resistance, coating EIS spectra) is not modelled here.</p>
            {simResult?.sternGeary_B_V != null && <p>Stern-Geary B = {simResult.sternGeary_B_V} V</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
