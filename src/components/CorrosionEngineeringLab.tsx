import React, { useState, useMemo } from "react";
import {
  ShieldAlert,
  Activity,
  AlertTriangle,
  CheckCircle2,
  Sliders,
  Zap,
  Compass,
} from "lucide-react";
import { DynamicPourbaixStudio } from "./DynamicPourbaixStudio";
import { CorrosionEISKineticsStudio } from "./CorrosionEISKineticsStudio";
import { TafelPolarizationLab } from "./TafelPolarizationLab";

export function CorrosionEngineeringLab() {
  const [activeTab, setActiveTab] = useState<"pren" | "polarization" | "pourbaix" | "corrosion-eis">("corrosion-eis");

  // PREN & Critical Pitting State
  const [cr, setCr] = useState<number>(22.0);
  const [mo, setMo] = useState<number>(3.2);
  const [w, setW] = useState<number>(0.0);
  const [n, setN] = useState<number>(0.18);

  // PREN Score
  const prenScore = useMemo(() => {
    return cr + 3.3 * (mo + 0.5 * w) + 16 * n;
  }, [cr, mo, w, n]);

  return (
    <div className="space-y-6">
      {/* Top Banner Header */}
      <div className="flex flex-col gap-4 bg-[#090e18] p-5 rounded-2xl border border-[#162032] shadow-sm">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 shadow-[0_0_16px_rgba(245,158,11,0.25)]">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-extrabold text-white font-mono tracking-wide uppercase">
                Corrosion & Degradation Engineering
              </h2>
              <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 text-[10px] font-mono border border-amber-500/40">
                PREN / Tafel / Kinetics
              </span>
            </div>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              PREN Pitting Index, Tafel / Stern-Geary Polarization, Pourbaix E-pH and Stern-Geary / Faraday kinetics
            </p>
          </div>
        </div>

        {/* Tab Navigation: its own row and wrapping, so every tab (Pourbaix included) and the active one stay visible. */}
        <div role="group" aria-label="Corrosion views" className="flex flex-wrap items-center gap-1.5 p-1 bg-[#050810] rounded-xl border border-[#162032]">
          <button
            type="button"
            onClick={() => {
              if (typeof navigator !== "undefined" && navigator.vibrate) navigator.vibrate(8);
              setActiveTab("pren");
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold transition whitespace-nowrap flex items-center gap-1.5 ${
              activeTab === "pren"
                ? "bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-[0_0_10px_rgba(245,158,11,0.3)]"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Pitting Resistance (PREN)</span>
          </button>

          <button
            type="button"
            onClick={() => {
              if (typeof navigator !== "undefined" && navigator.vibrate) navigator.vibrate(8);
              setActiveTab("polarization");
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold transition whitespace-nowrap flex items-center gap-1.5 ${
              activeTab === "polarization"
                ? "bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-[0_0_10px_rgba(245,158,11,0.3)]"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Tafel / Stern-Geary</span>
          </button>


          <button
            type="button"
            onClick={() => {
              if (typeof navigator !== "undefined" && navigator.vibrate) navigator.vibrate(8);
              setActiveTab("pourbaix");
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold transition whitespace-nowrap flex items-center gap-1.5 ${
              activeTab === "pourbaix"
                ? "bg-sky-500/20 text-sky-300 border border-sky-500/40 shadow-[0_0_10px_rgba(56,189,248,0.3)]"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Compass className="w-3.5 h-3.5 text-sky-400" />
            <span>Pourbaix E–pH (25 °C)</span>
          </button>

          <button
            type="button"
            onClick={() => {
              if (typeof navigator !== "undefined" && navigator.vibrate) navigator.vibrate(8);
              setActiveTab("corrosion-eis");
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold transition whitespace-nowrap flex items-center gap-1.5 ${
              activeTab === "corrosion-eis"
                ? "bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-[0_0_10px_rgba(245,158,11,0.3)]"
                : "text-amber-400 hover:text-amber-200 bg-amber-950/20 border border-amber-900/30"
            }`}
          >
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span>Corrosion Kinetics (R_p / Faraday)</span>
          </button>
        </div>
      </div>

      {/* ======================================================== */}
      {/* 2. PITTING RESISTANCE (PREN)                              */}
      {/* ======================================================== */}
      {activeTab === "pren" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-7 space-y-6">
            <div className="bg-[#090e18] p-5 rounded-xl border border-[#162032] space-y-5">
              <div className="flex items-center justify-between border-b border-[#162032] pb-3">
                <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-sky-400" />
                  <span>Pitting Resistance Equivalent Number (PREN)</span>
                </h3>
                <span className="text-[11px] text-slate-400 font-mono">Composition-based index only</span>
              </div>

              <p className="text-xs text-slate-400 leading-relaxed font-mono">
                Formula: <span className="text-sky-300 font-bold">PREN = %Cr + 3.3(%Mo + 0.5%W) + 16(%N)</span>. A composition-based ranking index only; it is not a measured pitting potential or critical pitting temperature.
              </p>

              {/* Elemental Composition Sliders & Inputs */}
              <div className="space-y-4">
                {/* Cr */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-300">Chromium (%Cr):</span>
                    <span className="text-sky-300 font-bold">{cr.toFixed(1)} wt%</span>
                  </div>
                  <input aria-label="Chromium (%Cr)"
                    type="range"
                    min="10.0"
                    max="32.0"
                    step="0.1"
                    value={cr}
                    onChange={(e) => setCr(parseFloat(e.target.value))}
                    className="w-full accent-sky-400 cursor-pointer"
                  />
                </div>

                {/* Mo */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-300">Molybdenum (%Mo):</span>
                    <span className="text-sky-300 font-bold">{mo.toFixed(1)} wt%</span>
                  </div>
                  <input aria-label="Molybdenum (%Mo)"
                    type="range"
                    min="0.0"
                    max="10.0"
                    step="0.1"
                    value={mo}
                    onChange={(e) => setMo(parseFloat(e.target.value))}
                    className="w-full accent-sky-400 cursor-pointer"
                  />
                </div>

                {/* W */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-300">Tungsten (%W):</span>
                    <span className="text-sky-300 font-bold">{w.toFixed(1)} wt%</span>
                  </div>
                  <input aria-label="Tungsten (%W)"
                    type="range"
                    min="0.0"
                    max="6.0"
                    step="0.1"
                    value={w}
                    onChange={(e) => setW(parseFloat(e.target.value))}
                    className="w-full accent-sky-400 cursor-pointer"
                  />
                </div>

                {/* N */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-300">Nitrogen (%N):</span>
                    <span className="text-sky-300 font-bold">{n.toFixed(2)} wt%</span>
                  </div>
                  <input aria-label="Nitrogen (%N)"
                    type="range"
                    min="0.0"
                    max="0.60"
                    step="0.01"
                    value={n}
                    onChange={(e) => setN(parseFloat(e.target.value))}
                    className="w-full accent-sky-400 cursor-pointer"
                  />
                </div>
              </div>

              {/* Standard Presets */}
              <div className="pt-2">
                <span className="text-[11px] text-slate-400 font-mono block mb-1.5">Industry Standard Alloy Presets:</span>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-[11px]">
                  <button
                    type="button"
                    onClick={() => { setCr(18.0); setMo(0.2); setW(0); setN(0.04); }}
                    className="p-2 rounded bg-[#050810] hover:bg-sky-500/20 text-slate-300 border border-[#162032]"
                  >
                    AISI 304 (18/8)
                  </button>
                  <button
                    type="button"
                    onClick={() => { setCr(17.5); setMo(2.5); setW(0); setN(0.06); }}
                    className="p-2 rounded bg-[#050810] hover:bg-sky-500/20 text-slate-300 border border-[#162032]"
                  >
                    AISI 316L
                  </button>
                  <button
                    type="button"
                    onClick={() => { setCr(22.0); setMo(3.1); setW(0); setN(0.18); }}
                    className="p-2 rounded bg-[#050810] hover:bg-sky-500/20 text-slate-300 border border-[#162032]"
                  >
                    Duplex 2205
                  </button>
                  <button
                    type="button"
                    onClick={() => { setCr(25.0); setMo(3.8); setW(0.6); setN(0.28); }}
                    className="p-2 rounded bg-[#050810] hover:bg-sky-500/20 text-slate-300 border border-[#162032]"
                  >
                    Super Duplex 2507
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Diagnostic Prediction Cards */}
          <div className="lg:col-span-5 space-y-6">
            <div className="bg-[#090e18] p-5 rounded-xl border border-[#162032] space-y-5">
              <div className="flex items-center justify-between border-b border-[#162032] pb-3">
                <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider flex items-center gap-2">
                  <Activity className="w-4 h-4 text-emerald-400" />
                  <span>Pitting Resistance Index</span>
                </h3>
              </div>

              {/* Big Score Card */}
              <div className="p-5 bg-[#050810] rounded-xl border border-[#162032] text-center space-y-2">
                <span className="text-xs text-slate-400 font-mono uppercase tracking-wider block">
                  Calculated PREN Index
                </span>
                <div className="text-4xl font-black font-mono text-sky-400 tracking-tight">
                  {prenScore.toFixed(1)}
                </div>

                <div className="pt-2">
                  {prenScore >= 40 ? (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-xs font-mono font-bold">
                      <CheckCircle2 className="w-4 h-4" />
                      PREN ≥ 40 (super duplex range)
                    </span>
                  ) : prenScore >= 32 ? (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-sky-500/20 text-sky-300 border border-sky-500/40 text-xs font-mono font-bold">
                      <CheckCircle2 className="w-4 h-4" />
                      PREN 32-40 (duplex range)
                    </span>
                  ) : prenScore >= 24 ? (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs font-mono font-bold">
                      <AlertTriangle className="w-4 h-4" />
                      PREN 24-32 (lower pitting resistance)
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-red-500/20 text-red-400 border border-red-500/40 text-xs font-mono font-bold">
                      <AlertTriangle className="w-4 h-4" />
                      PREN &lt; 24 (low pitting resistance)
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* 3. TAFEL POLARIZATION & STERN-GEARY KINETICS             */}
      {/* ======================================================== */}
      {activeTab === "polarization" && (
        <div className="pt-2">
          <TafelPolarizationLab />
        </div>
      )}

      {/* ======================================================== */}
      {/* 5. POURBAIX E-pH (25 °C, SINGLE ELEMENT) STUDIO          */}
      {/* ======================================================== */}
      {activeTab === "pourbaix" && (
        <div className="pt-2">
          <DynamicPourbaixStudio />
        </div>
      )}

      {/* ======================================================== */}
      {/* 6. CORROSION KINETICS (Rp / FARADAY) STUDIO              */}
      {/* ======================================================== */}
      {activeTab === "corrosion-eis" && (
        <div className="pt-2">
          <CorrosionEISKineticsStudio />
        </div>
      )}
    </div>
  );
}



