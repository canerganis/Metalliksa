import React, { useState, useMemo } from "react";
import {
  Flame,
  Layers,
  Activity,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Info,
  TrendingUp,
  Clock,
  Gauge,
  Sparkles,
  Zap,
  Sliders,
  ChevronRight,
} from "lucide-react";
import { CandidateAlloySolution, InverseDesignTargets } from "../utils/inverseAlloyOptimizer";

interface Props {
  candidate: CandidateAlloySolution;
  targets: InverseDesignTargets;
}

export type HeatTreatmentStage = "stress-relief" | "hip" | "solution" | "aging" | "full-cycle";

export const HeatTreatmentAgingSimulator: React.FC<Props> = ({ candidate, targets }) => {
  const [input, setInput] = useState({ candidate, fraction: "" });
  const text = input.candidate === candidate ? input.fraction : "";
  const fraction = text.trim() === "" ? null : Number(text);
  const valid = fraction !== null && Number.isFinite(fraction) && fraction >= 0 && fraction <= 0.35;
  return <div className="space-y-4">
    <div className="p-4 rounded-xl border border-amber-500/40 text-sm text-slate-300 space-y-2">
      <p>Illustrative heat-treatment sensitivity model. Fixed empirical coefficients, 0.95% initial porosity and 4 µm dendrite spacing are assumptions; outputs are not validated material predictions.</p>
      <label className="block">Precipitate volume fraction (0–0.35, scenario input)
        <input type="number" min="0" max="0.35" step="0.01" value={text}
          onChange={event => setInput({ candidate, fraction: event.target.value })}
          className="ml-3 w-24 bg-slate-900 border border-slate-600 rounded p-1" />
      </label>
      {!valid && <p role="status">Results unavailable. Supply a precipitate volume fraction; Scheil solid fraction is not a precipitate fraction.</p>}
    </div>
    {valid && <HeatTreatmentScenario key={candidate.id} candidate={candidate} targets={targets} precipitateFraction={fraction!} />}
  </div>;
};

const HeatTreatmentScenario: React.FC<Props & { precipitateFraction: number }> = ({ candidate, targets, precipitateFraction }) => {
  const [activeStage, setActiveStage] = useState<HeatTreatmentStage>("full-cycle");

  // Material thermal base parameters
  const matrix = targets.baseMatrix;
  const liquidus_C = candidate.liquidus_C;
  const solidus_C = candidate.solidus_C;

  // Recommended default temperatures based on matrix
  const defaults = useMemo(() => {
    switch (matrix) {
      case "Aluminum":
        return {
          srTemp_C: 280,
          srTime_h: 2,
          hipTemp_C: 500,
          hipPressure_MPa: 100,
          hipTime_h: 3,
          solTemp_C: 535,
          solTime_h: 4,
          ageTemp_C: 175,
          ageTime_h: 12,
          precipitatePhase: "Al3(Sc,Zr) / β'' (Mg2Si) / θ' (Al2Cu)",
          activationEnergy_kJ: 130,
        };
      case "Titanium":
        return {
          srTemp_C: 600,
          srTime_h: 2,
          hipTemp_C: 920,
          hipPressure_MPa: 100,
          hipTime_h: 2,
          solTemp_C: 950,
          solTime_h: 1.5,
          ageTemp_C: 540,
          ageTime_h: 6,
          precipitatePhase: "α-lamellae in β / Ti3Al (α2)",
          activationEnergy_kJ: 220,
        };
      case "Nickel":
        return {
          srTemp_C: 850,
          srTime_h: 3,
          hipTemp_C: 1180,
          hipPressure_MPa: 150,
          hipTime_h: 4,
          solTemp_C: 1220,
          solTime_h: 4,
          ageTemp_C: 760,
          ageTime_h: 16,
          precipitatePhase: "γ' Ni3(Al,Ti,Ta) + Carbides MC/M23C6",
          activationEnergy_kJ: 280,
        };
      case "Steel":
        return {
          srTemp_C: 550,
          srTime_h: 2,
          hipTemp_C: 1150,
          hipPressure_MPa: 120,
          hipTime_h: 3,
          solTemp_C: 1050,
          solTime_h: 2,
          ageTemp_C: 480,
          ageTime_h: 8,
          precipitatePhase: "Ni3Ti / Cu-rich Clusters / M2C Carbides",
          activationEnergy_kJ: 260,
        };
      default:
        return {
          srTemp_C: 700,
          srTime_h: 2,
          hipTemp_C: 1100,
          hipPressure_MPa: 120,
          hipTime_h: 3,
          solTemp_C: 1150,
          solTime_h: 3,
          ageTemp_C: 650,
          ageTime_h: 10,
          precipitatePhase: "Intermetallic Dispersoids / Nanoprecipitates",
          activationEnergy_kJ: 240,
        };
    }
  }, [matrix]);

  // Interactive controls
  const [hipTemp, setHipTemp] = useState<number>(defaults.hipTemp_C);
  const [hipPressure, setHipPressure] = useState<number>(defaults.hipPressure_MPa);
  const [hipTime, setHipTime] = useState<number>(defaults.hipTime_h);

  const [solTemp, setSolTemp] = useState<number>(defaults.solTemp_C);
  const [solTime, setSolTime] = useState<number>(defaults.solTime_h);

  const [ageTemp, setAgeTemp] = useState<number>(defaults.ageTemp_C);
  const [ageTime, setAgeTime] = useState<number>(defaults.ageTime_h);

  // KINETICS MODEL CALCULATIONS
  const kinetics = useMemo(() => {
    // 1. Stress Relief Relaxation: sigma_res / sigma_0 = exp(-A * t * exp(-Q/RT))
    const T_sr_K = defaults.srTemp_C + 273.15;
    const residualStressReliefPct = Math.min(
      96,
      Math.round(85 + ((defaults.srTemp_C / (solidus_C * 0.6)) * 10) + defaults.srTime_h * 2)
    );

    // 2. HIP Densification & Pore Closure (Ashby-Arzt-Frost model)
    // Homologous temperature T_hom = T_hip / T_solidus
    const T_hom_hip = (hipTemp + 273.15) / (solidus_C + 273.15);
    const initialPorosityPct = 0.95; // %0.95 typical as-built LPBF porosity
    
    // Diffusion + Power-law Creep pore closure rate
    const densificationDrive = (hipPressure / 100) * Math.pow(T_hom_hip / 0.8, 4) * Math.sqrt(hipTime / 2);
    const postHipPorosityPct = Math.max(0.005, parseFloat((initialPorosityPct * Math.exp(-densificationDrive * 3.5)).toFixed(3)));
    const postHipRelativeDensity = parseFloat((100 - postHipPorosityPct).toFixed(2));
    const fatigueLifeImprovementFactor = parseFloat((1 + (initialPorosityPct - postHipPorosityPct) * 1.8 + 0.35).toFixed(2));

    // 3. Solution Treatment & Homogenization Kinetics (Fick's 2nd Law)
    // Diffusion coefficient D = D0 * exp(-Q / RT)
    const R_const = 8.314; // J/(mol*K)
    const T_sol_K = solTemp + 273.15;
    const Q_hom = defaults.activationEnergy_kJ * 1000;
    const D0 = 1e-4; // m^2/s typical
    const D_sol = D0 * Math.exp(-Q_hom / (R_const * T_sol_K)); // m^2/s
    const dendriteSpacing_m = 4e-6; // ~4 um LPBF dendrite spacing

    // Homogenization parameter theta = (pi^2 * D * t) / L^2
    const theta_hom = (Math.pow(Math.PI, 2) * D_sol * (solTime * 3600)) / Math.pow(dendriteSpacing_m, 2);
    const segregationDissolutionPct = Math.min(99.8, parseFloat((100 * (1 - Math.exp(-theta_hom * 1.5))).toFixed(1)));

    // Incipient Melting Warning
    const incipientMeltingRisk = solTemp >= solidus_C - 15;

    // 4. Precipitation Hardening & Aging Kinetics (LSW Ostwald Ripening & JMAK)
    // Particle growth: r(t) = (r0^3 + K_lsw * t)^(1/3)
    const T_age_K = ageTemp + 273.15;
    const Q_precip = defaults.activationEnergy_kJ * 0.85 * 1000;
    const K_lsw = 1.2e-28 * Math.exp(-Q_precip / (R_const * T_age_K)); // m^3/s
    
    // Precipitate radius in nm
    const r0_nm = 1.2;
    const current_r_nm = parseFloat(
      (Math.pow(Math.pow(r0_nm * 1e-9, 3) + K_lsw * (ageTime * 3600), 1 / 3) * 1e9).toFixed(2)
    );

    // Optimal radius for peak strength (Cutting to Orowan transition)
    const r_optimal_nm = matrix === "Aluminum" ? 4.5 : matrix === "Nickel" ? 18.0 : matrix === "Titanium" ? 8.0 : 6.0;

    // Precipitate volume fraction f_vol
    const f_vol = precipitateFraction;

    // Shearing / Cutting strength contribution (Under-aged): delta_sigma_cut = C1 * sqrt(f * r)
    const delta_cut = 140 * Math.sqrt(f_vol * Math.max(0.5, current_r_nm));

    // Orowan Bypass strength contribution (Over-aged): delta_sigma_orowan = C2 * sqrt(f) / r * ln(r)
    const delta_orowan = (520 * Math.sqrt(f_vol)) / Math.max(1.0, current_r_nm) * Math.log(Math.max(2, current_r_nm));

    // Combined effective precipitation hardening
    const deltaYieldPrecip = Math.round(Math.min(delta_cut, delta_orowan) * 2.8);

    // Aging status: Under-aged, Peak-aged, or Over-aged
    let agingRegime: "Under-Aged (Shearing / Cutting)" | "Peak-Aged (T6 Peak Strength)" | "Over-Aged (T7 Orowan Bypass)";
    let agingBadgeColor = "text-sky-400 border-sky-500/40 bg-sky-500/10";
    if (Math.abs(current_r_nm - r_optimal_nm) < 1.2) {
      agingRegime = "Peak-Aged (T6 Peak Strength)";
      agingBadgeColor = "text-emerald-400 border-emerald-500/40 bg-emerald-500/10";
    } else if (current_r_nm < r_optimal_nm) {
      agingRegime = "Under-Aged (Shearing / Cutting)";
      agingBadgeColor = "text-sky-400 border-sky-500/40 bg-sky-500/10";
    } else {
      agingRegime = "Over-Aged (T7 Orowan Bypass)";
      agingBadgeColor = "text-amber-400 border-amber-500/40 bg-amber-500/10";
    }

    // Time-series curve points for interactive Aging Hardness Plot
    const timePoints = [0.5, 1, 2, 4, 8, 12, 16, 24, 36, 48, 72];
    const agingCurveData = timePoints.map((t_h) => {
      const r_nm = Math.pow(Math.pow(r0_nm * 1e-9, 3) + K_lsw * (t_h * 3600), 1 / 3) * 1e9;
      const cut = 140 * Math.sqrt(f_vol * Math.max(0.5, r_nm));
      const oro = (520 * Math.sqrt(f_vol)) / Math.max(1.0, r_nm) * Math.log(Math.max(2, r_nm));
      const strength = Math.round(Math.min(cut, oro) * 2.8);
      return { t_h, r_nm: parseFloat(r_nm.toFixed(1)), strength };
    });

    // 5. MECHANICAL PROPERTY STATE PROGRESSION
    const asBuiltYield = candidate.yieldStrength_25C_MPa;
    const asBuiltUTS = candidate.uts_25C_MPa;
    const asBuiltElong = candidate.elongation_pct;
    const asBuiltK1c = candidate.fractureToughness_K1c;

    // Post Stress-Relief
    const srYield = Math.round(asBuiltYield * 0.94);
    const srUTS = Math.round(asBuiltUTS * 0.96);
    const srElong = parseFloat((asBuiltElong * 1.15).toFixed(1));
    const srK1c = parseFloat((asBuiltK1c * 1.08).toFixed(1));

    // Post HIP
    const hipYield = Math.round(asBuiltYield * 0.90);
    const hipUTS = Math.round(asBuiltUTS * 0.95);
    const hipElong = parseFloat((asBuiltElong * 1.45).toFixed(1));
    const hipK1c = parseFloat((asBuiltK1c * 1.35).toFixed(1));

    // Post Solution + Peak Aging (Full Heat Treated)
    const finalYield = Math.round(hipYield + deltaYieldPrecip);
    const finalUTS = Math.round(finalYield * 1.18);
    const finalElong = parseFloat((Math.max(6.0, hipElong * 0.72)).toFixed(1));
    const finalK1c = parseFloat((Math.max(40, hipK1c * 0.92)).toFixed(1));

    return {
      residualStressReliefPct,
      postHipPorosityPct,
      postHipRelativeDensity,
      fatigueLifeImprovementFactor,
      segregationDissolutionPct,
      incipientMeltingRisk,
      current_r_nm,
      r_optimal_nm,
      deltaYieldPrecip,
      agingRegime,
      agingBadgeColor,
      agingCurveData,
      asBuiltYield,
      asBuiltUTS,
      asBuiltElong,
      asBuiltK1c,
      srYield,
      srUTS,
      srElong,
      srK1c,
      hipYield,
      hipUTS,
      hipElong,
      hipK1c,
      finalYield,
      finalUTS,
      finalElong,
      finalK1c,
    };
  }, [
    defaults,
    hipTemp,
    hipPressure,
    hipTime,
    solTemp,
    solTime,
    ageTemp,
    ageTime,
    solidus_C,
    candidate,
    matrix,
    precipitateFraction,
  ]);

  return (
    <div className="space-y-4">
      {/* HEADER: POST-PROCESSING & HEAT TREATMENT SUITE */}
      <div className="p-4 rounded-xl bg-[#0b1322] border border-[#1d2a44] space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <Flame className="w-5 h-5 text-amber-400" />
              <h3 className="text-sm font-bold text-white font-mono">
                Heat Treatment, HIP &amp; Aging Kinetics Simulator (Post-Processing Physics)
              </h3>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              LPBF residual stress relief, Ashby-Arzt HIP pore diffusion model, Fickian homogenization, and LSW Ostwald ripening precipitation hardening.
            </p>
          </div>

          <div
            className={`px-3 py-1.5 rounded-lg border font-mono text-xs font-bold flex items-center gap-1.5 self-start sm:self-auto ${kinetics.agingBadgeColor}`}
          >
            <Sparkles className="w-4 h-4" />
            <span>{kinetics.agingRegime}</span>
          </div>
        </div>

        {/* 4 STAGE KPI CARDS */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 font-mono">
          <div className="p-2.5 rounded-lg bg-[#070c16] border border-[#162032]">
            <span className="text-[10px] text-slate-400 block">Residual Stress Relief:</span>
            <div className="text-base font-bold text-sky-400 mt-0.5">
              %{kinetics.residualStressReliefPct}{" "}
              <span className="text-xs font-normal text-slate-400">relieved</span>
            </div>
            <span className="text-[9px] text-slate-500">{defaults.srTemp_C}°C / {defaults.srTime_h} h</span>
          </div>

          <div className="p-2.5 rounded-lg bg-[#070c16] border border-[#162032]">
            <span className="text-[10px] text-slate-400 block">Post-HIP Relative Density:</span>
            <div className="text-base font-bold text-emerald-400 mt-0.5">
              %{kinetics.postHipRelativeDensity}{" "}
              <span className="text-xs font-normal text-slate-400">(Porosity: %{kinetics.postHipPorosityPct})</span>
            </div>
            <span className="text-[9px] text-slate-500">Fatigue Life Increase: {kinetics.fatigueLifeImprovementFactor}x</span>
          </div>

          <div className="p-2.5 rounded-lg bg-[#070c16] border border-[#162032]">
            <span className="text-[10px] text-slate-400 block">Homogenization Dissolution:</span>
            <div className="text-base font-bold text-purple-400 mt-0.5">
              %{kinetics.segregationDissolutionPct}{" "}
              <span className="text-xs font-normal text-slate-400">segregation cleared</span>
            </div>
            <span className="text-[9px] text-slate-500">Fickian Diffusion ({solTemp}°C)</span>
          </div>

          <div className="p-2.5 rounded-lg bg-[#070c16] border border-[#162032]">
            <span className="text-[10px] text-slate-400 block">Precipitation Hardening Gain:</span>
            <div className="text-base font-bold text-amber-400 mt-0.5">
              +{kinetics.deltaYieldPrecip}{" "}
              <span className="text-xs font-normal text-slate-400">MPa Yield</span>
            </div>
            <span className="text-[9px] text-slate-500">
              Nanoparticle Radius: {kinetics.current_r_nm} nm (Opt: {kinetics.r_optimal_nm} nm)
            </span>
          </div>
        </div>
      </div>

      {/* 2-COLUMN MAIN BODY: PROCESS CONTROLS & AGING CURVE */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* LEFT 5 COLS: INTERACTIVE HEAT TREATMENT SLIDERS */}
        <div className="lg:col-span-5 p-4 rounded-xl bg-[#0c1322] border border-[#1a263c] space-y-4">
          <div className="flex items-center justify-between border-b border-[#162032] pb-2.5">
            <span className="text-xs font-bold text-white font-mono flex items-center gap-1.5">
              <Sliders className="w-4 h-4 text-amber-400" />
              Heat Treatment &amp; HIP Parameters
            </span>
            <span className="text-[10px] font-mono text-slate-400">
              Solidus: {solidus_C}°C
            </span>
          </div>

          {/* HIP CONTROLS */}
          <div className="space-y-2 p-2.5 rounded-lg bg-[#070c16] border border-[#162032]">
            <div className="flex items-center justify-between text-xs font-mono font-bold text-slate-200">
              <span className="flex items-center gap-1 text-emerald-400">
                <Gauge className="w-3.5 h-3.5" /> 1. HIP (Hot Isostatic Pressing)
              </span>
              <span className="text-[10px] text-slate-400">{hipPressure} MPa / {hipTime}h</span>
            </div>

            <div className="space-y-1">
              <div className="flex justify-between text-[11px] font-mono">
                <span className="text-slate-400">HIP Temperature (T_HIP)</span>
                <strong className="text-emerald-300">{hipTemp} °C</strong>
              </div>
              <input aria-label="HIP Temperature (T_HIP) (°C)"
                type="range"
                min={Math.round(solidus_C * 0.55)}
                max={Math.round(solidus_C * 0.92)}
                step="10"
                value={hipTemp}
                onChange={(e) => setHipTemp(parseInt(e.target.value))}
                className="w-full h-1.5 bg-[#162032] rounded-lg appearance-none cursor-pointer accent-emerald-400"
              />
            </div>

            <div className="grid grid-cols-2 gap-2 text-[11px] font-mono pt-1">
              <div>
                <span className="text-slate-400 text-[10px] block">Isostatic Pressure (P)</span>
                <select aria-label="Isostatic Pressure (P)"
                  value={hipPressure}
                  onChange={(e) => setHipPressure(parseInt(e.target.value))}
                  className="w-full mt-0.5 px-2 py-1 rounded bg-[#0b1322] border border-[#1e2a44] text-xs text-white"
                >
                  <option value={100}>100 MPa (Standard)</option>
                  <option value={120}>120 MPa (Medium)</option>
                  <option value={150}>150 MPa (High / Turbine)</option>
                  <option value={200}>200 MPa (Ultra HIP)</option>
                </select>
              </div>
              <div>
                <span className="text-slate-400 text-[10px] block">Dwell Time (t)</span>
                <select aria-label="Dwell Time (t)"
                  value={hipTime}
                  onChange={(e) => setHipTime(parseFloat(e.target.value))}
                  className="w-full mt-0.5 px-2 py-1 rounded bg-[#0b1322] border border-[#1e2a44] text-xs text-white"
                >
                  <option value={2}>2 Hours</option>
                  <option value={3}>3 Hours</option>
                  <option value={4}>4 Hours</option>
                  <option value={6}>6 Hours</option>
                </select>
              </div>
            </div>
          </div>

          {/* SOLUTION TREATMENT CONTROLS */}
          <div className="space-y-2 p-2.5 rounded-lg bg-[#070c16] border border-[#162032]">
            <div className="flex items-center justify-between text-xs font-mono font-bold text-slate-200">
              <span className="flex items-center gap-1 text-purple-400">
                <Flame className="w-3.5 h-3.5" /> 2. Solution Treatment (Solutionize)
              </span>
              <span className="text-[10px] text-slate-400">{solTime}h</span>
            </div>

            <div className="space-y-1">
              <div className="flex justify-between text-[11px] font-mono">
                <span className="text-slate-400">Solution Temperature (T_sol)</span>
                <strong className={`font-bold ${kinetics.incipientMeltingRisk ? "text-rose-400" : "text-purple-300"}`}>
                  {solTemp} °C {kinetics.incipientMeltingRisk && "⚠️ (Melting Risk!)"}
                </strong>
              </div>
              <input aria-label="Solution Temperature (T_sol) (°C)"
                type="range"
                min={Math.round(solidus_C * 0.7)}
                max={Math.min(liquidus_C, Math.round(solidus_C + 20))}
                step="5"
                value={solTemp}
                onChange={(e) => setSolTemp(parseInt(e.target.value))}
                className="w-full h-1.5 bg-[#162032] rounded-lg appearance-none cursor-pointer accent-purple-400"
              />
            </div>
          </div>

          {/* PRECIPITATION AGING CONTROLS */}
          <div className="space-y-2 p-2.5 rounded-lg bg-[#070c16] border border-[#162032]">
            <div className="flex items-center justify-between text-xs font-mono font-bold text-slate-200">
              <span className="flex items-center gap-1 text-amber-400">
                <Sparkles className="w-3.5 h-3.5" /> 3. Aging &amp; Precipitation
              </span>
              <span className="text-[10px] text-slate-400">{ageTime}h</span>
            </div>

            <div className="space-y-1">
              <div className="flex justify-between text-[11px] font-mono">
                <span className="text-slate-400">Aging Temperature (T_age)</span>
                <strong className="text-amber-300">{ageTemp} °C</strong>
              </div>
              <input aria-label="Aging Temperature (T_age) (°C)"
                type="range"
                min={Math.round(defaults.ageTemp_C * 0.7)}
                max={Math.round(defaults.ageTemp_C * 1.35)}
                step="5"
                value={ageTemp}
                onChange={(e) => setAgeTemp(parseInt(e.target.value))}
                className="w-full h-1.5 bg-[#162032] rounded-lg appearance-none cursor-pointer accent-amber-400"
              />
            </div>

            <div className="space-y-1 pt-1">
              <div className="flex justify-between text-[11px] font-mono">
                <span className="text-slate-400">Aging Duration (t_age)</span>
                <strong className="text-sky-300">{ageTime} Hours</strong>
              </div>
              <input aria-label="Aging Duration (t_age) (Hours)"
                type="range"
                min={1}
                max={48}
                step={1}
                value={ageTime}
                onChange={(e) => setAgeTime(parseInt(e.target.value))}
                className="w-full h-1.5 bg-[#162032] rounded-lg appearance-none cursor-pointer accent-sky-400"
              />
            </div>
          </div>
        </div>

        {/* RIGHT 7 COLS: AGING KINETICS CURVE & INTERACTIVE LSW PLOT */}
        <div className="lg:col-span-7 p-4 rounded-xl bg-[#0c1322] border border-[#1a263c] flex flex-col justify-between space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-white font-mono flex items-center gap-1.5">
              <Activity className="w-4 h-4 text-amber-400" />
              Precipitation Hardening Kinetics (Hardness vs. Aging Time Curve)
            </span>
            <span className="text-[10px] font-mono text-slate-400">
              Precipitating Phase: <strong className="text-sky-300">{defaults.precipitatePhase}</strong>
            </span>
          </div>

          {/* SVG Plot for Hardness / Yield Strength vs Time */}
          <div className="w-full bg-[#070c16] rounded-xl border border-[#162032] p-3 flex flex-col items-center justify-center relative overflow-hidden">
            <svg viewBox="0 0 440 180" className="w-full h-auto max-h-[200px]">
              {/* Grid Lines */}
              <line x1="50" y1="20" x2="420" y2="20" stroke="#162032" strokeWidth="1" />
              <line x1="50" y1="60" x2="420" y2="60" stroke="#162032" strokeWidth="1" />
              <line x1="50" y1="100" x2="420" y2="100" stroke="#162032" strokeWidth="1" />
              <line x1="50" y1="140" x2="420" y2="140" stroke="#334155" strokeWidth="1.5" />
              <line x1="50" y1="20" x2="50" y2="140" stroke="#334155" strokeWidth="1.5" />

              {/* Axis Labels */}
              <text x="25" y="25" fill="#64748b" fontSize="8" fontFamily="monospace">Δσ (MPa)</text>
              <text x="25" y="80" fill="#64748b" fontSize="8" fontFamily="monospace">+200</text>
              <text x="25" y="140" fill="#64748b" fontSize="8" fontFamily="monospace">0</text>
              <text x="420" y="155" fill="#64748b" fontSize="8" fontFamily="monospace" textAnchor="end">Time (Hours, log)</text>

              {/* Aging Curve Path */}
              {(() => {
                const maxStrength = Math.max(...kinetics.agingCurveData.map((d) => d.strength), 100);
                const points = kinetics.agingCurveData.map((d, i) => {
                  const x = 50 + (i / (kinetics.agingCurveData.length - 1)) * 360;
                  const y = 140 - (d.strength / (maxStrength * 1.2)) * 110;
                  return `${x},${y}`;
                });
                const pathD = `M ${points.join(" L ")}`;

                // Current operating point
                const currentIdx = Math.min(
                  kinetics.agingCurveData.length - 1,
                  Math.max(
                    0,
                    kinetics.agingCurveData.findIndex((d) => d.t_h >= ageTime)
                  )
                );
                const currentPoint = kinetics.agingCurveData[currentIdx] || kinetics.agingCurveData[4];
                const cx = 50 + (currentIdx / (kinetics.agingCurveData.length - 1)) * 360;
                const cy = 140 - (kinetics.deltaYieldPrecip / (maxStrength * 1.2)) * 110;

                return (
                  <g>
                    {/* Shaded Area */}
                    <path
                      d={`${pathD} L 410,140 L 50,140 Z`}
                      fill="url(#agingGradient)"
                      opacity="0.25"
                    />
                    <defs>
                      <linearGradient id="agingGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.8" />
                        <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.0" />
                      </linearGradient>
                    </defs>

                    {/* Main Line */}
                    <path d={pathD} fill="none" stroke="#f59e0b" strokeWidth="2.5" />

                    {/* Cutting Regime Indicator */}
                    <text x="90" y="130" fill="#38bdf8" fontSize="8" fontFamily="monospace">
                      Kesme (Under-aged)
                    </text>

                    {/* Orowan Looping Indicator */}
                    <text x="310" y="130" fill="#fb923c" fontSize="8" fontFamily="monospace">
                      Orowan Bypass (Over-aged)
                    </text>

                    {/* Current Operating Point Circle */}
                    <circle cx={cx} cy={cy} r="5" fill="#38bdf8" stroke="#ffffff" strokeWidth="2" />
                    <text
                      x={cx}
                      y={cy - 10}
                      fill="#38bdf8"
                      fontSize="9"
                      fontFamily="monospace"
                      fontWeight="bold"
                      textAnchor="middle"
                    >
                      +{kinetics.deltaYieldPrecip} MPa ({ageTime}h)
                    </text>
                  </g>
                );
              })()}
            </svg>
          </div>

          {/* Microstructural Explanation */}
          <div className="p-2.5 rounded-lg bg-[#070c16] border border-[#162032] text-xs font-mono text-slate-300 flex items-start gap-2">
            <Info className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <span>
              {kinetics.agingRegime === "Peak-Aged (T6 Peak Strength)"
                ? `At the optimum particle size (${kinetics.current_r_nm} nm), dislocation cutting resistance intersects with Orowan looping resistance at the peak. Maximum hardness and yield strength are achieved.`
                : kinetics.agingRegime === "Under-Aged (Shearing / Cutting)"
                ? `Precipitate particles are still fine (${kinetics.current_r_nm} nm). Dislocations easily shear through them; prolonging duration increases strength.`
                : `Particles have coarsened (${kinetics.current_r_nm} nm > ${kinetics.r_optimal_nm} nm). Dislocations bypass particles via Orowan looping; yield strength decreases while toughness and stress corrosion cracking (SCC) resistance increase.`}
            </span>
          </div>
        </div>
      </div>

      {/* SECTION 3: STEP-BY-STEP MECHANICAL PROPERTY TRANSFORMATION TABLE */}
      <div className="p-4 rounded-xl bg-[#0c1322] border border-[#1a263c] space-y-3 font-mono">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-white flex items-center gap-1.5">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            Heat Treatment Stages Mechanical Property Evolution (State Progression)
          </span>
          <span className="text-[10px] text-slate-400">
            As-Built → Stress Relief → HIP → Solution &amp; Aging
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-[#1a263c] text-slate-400 bg-[#070c16]">
                <th className="p-2 font-medium">State / Stage</th>
                <th className="p-2 font-medium">Yield Strength (Rp0.2)</th>
                <th className="p-2 font-medium">Tensile Strength (Rm)</th>
                <th className="p-2 font-medium">Elongation (A%)</th>
                <th className="p-2 font-medium">Fracture Toughness (K1c)</th>
                <th className="p-2 font-medium">Microstructural State</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#162032] text-slate-200">
              {/* As-Built */}
              <tr className="hover:bg-[#162032]/40 transition">
                <td className="p-2 font-bold text-slate-400 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-slate-500"></span>
                  1. As-Built (LPBF Print)
                </td>
                <td className="p-2 text-slate-300">{kinetics.asBuiltYield} MPa</td>
                <td className="p-2 text-slate-300">{kinetics.asBuiltUTS} MPa</td>
                <td className="p-2 text-slate-400">%{kinetics.asBuiltElong}</td>
                <td className="p-2 text-slate-400">{kinetics.asBuiltK1c} MPa√m</td>
                <td className="p-2 text-[11px] text-slate-500">High residual stress, anisotropic cellular grains</td>
              </tr>

              {/* Stress Relieved */}
              <tr className="hover:bg-[#162032]/40 transition">
                <td className="p-2 font-bold text-sky-400 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-sky-500"></span>
                  2. Stress Relief (SR)
                </td>
                <td className="p-2 text-slate-300">{kinetics.srYield} MPa</td>
                <td className="p-2 text-slate-300">{kinetics.srUTS} MPa</td>
                <td className="p-2 text-sky-300">%{kinetics.srElong}</td>
                <td className="p-2 text-sky-300">{kinetics.srK1c} MPa√m</td>
                <td className="p-2 text-[11px] text-slate-400">%{kinetics.residualStressReliefPct} residual stress relief</td>
              </tr>

              {/* Post HIP */}
              <tr className="hover:bg-[#162032]/40 transition">
                <td className="p-2 font-bold text-emerald-400 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                  3. Hot Isostatic Pressing (HIP)
                </td>
                <td className="p-2 text-slate-300">{kinetics.hipYield} MPa</td>
                <td className="p-2 text-slate-300">{kinetics.hipUTS} MPa</td>
                <td className="p-2 text-emerald-300 font-bold">%{kinetics.hipElong}</td>
                <td className="p-2 text-emerald-300 font-bold">{kinetics.hipK1c} MPa√m</td>
                <td className="p-2 text-[11px] text-emerald-400/90">
                  Pore closure (%{kinetics.postHipRelativeDensity} density, {kinetics.fatigueLifeImprovementFactor}x fatigue life)
                </td>
              </tr>

              {/* Full Solution + Age */}
              <tr className="hover:bg-[#162032]/40 bg-amber-500/5 transition font-bold">
                <td className="p-2 text-amber-300 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span>
                  4. Final Heat Treatment (Sol + Age)
                </td>
                <td className="p-2 text-amber-400">{kinetics.finalYield} MPa</td>
                <td className="p-2 text-amber-400">{kinetics.finalUTS} MPa</td>
                <td className="p-2 text-amber-300">%{kinetics.finalElong}</td>
                <td className="p-2 text-amber-300">{kinetics.finalK1c} MPa√m</td>
                <td className="p-2 text-[11px] text-amber-300/90">
                  Homogeneous matrix + {defaults.precipitatePhase} nanoparticle reinforcement
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
