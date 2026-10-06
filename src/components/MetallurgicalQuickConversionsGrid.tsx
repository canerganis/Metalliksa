import React, { useState, useMemo } from "react";
import {
  ArrowRightLeft,
  Search,
  X,
  Copy,
  Check,
  Sparkles,
  Thermometer,
  ShieldCheck,
  Activity,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Info,
} from "lucide-react";
import {
  convertStress,
  interpretStressMpa,
  interpretHardness,
  convertTemperature,
  StressUnit,
  TempUnit,
} from "../utils/metallurgicalConversions";
import {
  HARDNESS_CONVERSION_DISCLAIMER,
  HARDNESS_MATERIAL_CLASSES,
  HardnessMaterialClass,
  UNAVAILABLE_TEXT,
  convertHardness,
} from "../utils/hardnessConversion";
import { HARDNESS_PRESETS, HardnessPreset } from "../utils/hardnessPresets";
import { useMaterialStore } from "../store/useMaterialStore";
import { specimenStrengthsToLoad } from "../utils/compositionPropertyAvailability";
import { StandardInfoIcon } from "./StandardInfoIcon";

interface Props {
  onOpenFullSuite?: () => void;
}

export const MetallurgicalQuickConversionsGrid: React.FC<Props> = ({ onOpenFullSuite }) => {
  const { activeMaterialSpecimen } = useMaterialStore();
  // The shared specimen holds no composition-derived yield strength; null disables "Use Specimen Values".
  const specimenYield = specimenStrengthsToLoad(activeMaterialSpecimen).yieldMpa;

  // Search filter across the conversion grid
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = (val: string | number, id: string) => {
    navigator.clipboard.writeText(String(val));
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1800);
  };

  // --------------------------------------------------------------------------
  // 1. STRESS & STRENGTH CONVERSION (MPa / ksi)
  // --------------------------------------------------------------------------
  const [stressInputMode, setStressInputMode] = useState<"MPa" | "ksi">("MPa");
  const [stressValMpa, setStressValMpa] = useState<number>(850);
  const [stressValKsi, setStressValKsi] = useState<number>(123.3);

  const stressConversions = useMemo(() => {
    if (stressInputMode === "MPa") {
      return convertStress(stressValMpa, "MPa");
    } else {
      return convertStress(stressValKsi, "ksi");
    }
  }, [stressInputMode, stressValMpa, stressValKsi]);

  const stressInterpretation = useMemo(
    () => interpretStressMpa(stressConversions.MPa),
    [stressConversions.MPa]
  );

  const handleMpaChange = (val: number) => {
    setStressInputMode("MPa");
    setStressValMpa(val);
    setStressValKsi(Number((val * 0.1450377).toFixed(1)));
  };

  const handleKsiChange = (val: number) => {
    setStressInputMode("ksi");
    setStressValKsi(val);
    setStressValMpa(Number((val * 6.894757).toFixed(1)));
  };

  const stressPresets = [
    { name: "A36 Steel Yield", mpa: 250, ksi: 36.3, desc: "Structural mild steel" },
    { name: "Al 7075-T6 Yield", mpa: 503, ksi: 73.0, desc: "Aerospace wing spar" },
    { name: "Ti-6Al-4V UTS", mpa: 950, ksi: 137.8, desc: "Annealed grade 5" },
    { name: "4140 Q&T UTS", mpa: 1050, ksi: 152.3, desc: "Forged shafting" },
    { name: "Inconel 718 Aged", mpa: 1400, ksi: 203.1, desc: "Aero turbine disk" },
    { name: "AerMet 100 Ultra", mpa: 1965, ksi: 285.0, desc: "Landing gear steel" },
  ];

  // --------------------------------------------------------------------------
  // 2. HARDNESS CONVERSION (RC [HRC] / Vickers [HV])
  // --------------------------------------------------------------------------
  const [hardnessInputScale, setHardnessInputScale] = useState<"HRC" | "HV">("HRC");
  const [hardnessValHrc, setHardnessValHrc] = useState<number>(34);
  const [hardnessValHv, setHardnessValHv] = useState<number>(336);
  // Conversion tables exist only for non-austenitic steels; other classes keep the measured value only.
  const [hardnessClass, setHardnessClass] = useState<HardnessMaterialClass>("non-austenitic-steel");

  const hardnessConversions = useMemo(() => {
    if (hardnessInputScale === "HRC") {
      return convertHardness(hardnessValHrc, "HRC", hardnessClass);
    } else {
      return convertHardness(hardnessValHv, "HV", hardnessClass);
    }
  }, [hardnessInputScale, hardnessValHrc, hardnessValHv, hardnessClass]);

  const hardnessInterpretation = useMemo(
    () => (hardnessConversions.HV === null ? null : interpretHardness(hardnessConversions.HV, hardnessClass)),
    [hardnessConversions.HV, hardnessClass]
  );

  const handleHrcChange = (val: number, cls: HardnessMaterialClass = hardnessClass) => {
    setHardnessInputScale("HRC");
    setHardnessValHrc(val);
    const converted = convertHardness(val, "HRC", cls);
    if (converted.HV !== null) {
      setHardnessValHv(converted.HV);
    }
  };

  const handleHvChange = (val: number, cls: HardnessMaterialClass = hardnessClass) => {
    setHardnessInputScale("HV");
    setHardnessValHv(val);
    const converted = convertHardness(val, "HV", cls);
    if (converted.HRC !== null) {
      setHardnessValHrc(converted.HRC);
    }
  };

  // Shared example measured inputs; this card takes HRC or HV only.
  const hardnessPresets = HARDNESS_PRESETS.filter(
    (p): p is HardnessPreset & { scale: "HRC" | "HV" } => p.scale === "HRC" || p.scale === "HV"
  ).map((p) => ({ ...p, desc: p.note }));
  const applyHardnessPreset = (p: (typeof hardnessPresets)[number]) => {
    setHardnessClass(p.cls);
    if (p.scale === "HRC") handleHrcChange(p.value, p.cls);
    else handleHvChange(p.value, p.cls);
  };

  // --------------------------------------------------------------------------
  // 3. TEMPERATURE CONVERSION (Celsius / Kelvin / Rankine)
  // --------------------------------------------------------------------------
  const [tempInputScale, setTempInputScale] = useState<"C" | "K" | "R" | "F">("C");
  const [tempValC, setTempValC] = useState<number>(650);
  const [tempValK, setTempValK] = useState<number>(923.15);
  const [tempValR, setTempValR] = useState<number>(1661.67);
  const [tempValF, setTempValF] = useState<number>(1202);

  const tempConversions = useMemo(() => {
    let sourceVal = tempValC;
    let sourceUnit: TempUnit = "C";
    if (tempInputScale === "K") {
      sourceVal = tempValK;
      sourceUnit = "K";
    } else if (tempInputScale === "R") {
      sourceVal = tempValR;
      sourceUnit = "R";
    } else if (tempInputScale === "F") {
      sourceVal = tempValF;
      sourceUnit = "F";
    }
    return convertTemperature(sourceVal, sourceUnit);
  }, [tempInputScale, tempValC, tempValK, tempValR, tempValF]);

  const handleTempCChange = (val: number) => {
    setTempInputScale("C");
    setTempValC(val);
    const converted = convertTemperature(val, "C");
    setTempValK(converted.K);
    setTempValR(converted.R);
    setTempValF(converted.F);
  };

  const handleTempKChange = (val: number) => {
    setTempInputScale("K");
    setTempValK(val);
    const converted = convertTemperature(val, "K");
    setTempValC(converted.C);
    setTempValR(converted.R);
    setTempValF(converted.F);
  };

  const handleTempRChange = (val: number) => {
    setTempInputScale("R");
    setTempValR(val);
    const converted = convertTemperature(val, "R");
    setTempValC(converted.C);
    setTempValK(converted.K);
    setTempValF(converted.F);
  };

  const handleTempFChange = (val: number) => {
    setTempInputScale("F");
    setTempValF(val);
    const converted = convertTemperature(val, "F");
    setTempValC(converted.C);
    setTempValK(converted.K);
    setTempValR(converted.R);
  };

  const tempPresets = [
    { name: "Cryogenic LN2", c: -196, k: 77.15, r: 138.87, desc: "Sub-zero treatment" },
    { name: "Ambient Standard Lab", c: 20, k: 293.15, r: 527.67, desc: "ASTM standard test" },
    { name: "Stress Relief Temper", c: 250, k: 523.15, r: 941.67, desc: "Residual stress removal" },
    { name: "Aging / Nitriding", c: 540, k: 813.15, r: 1463.67, desc: "Secondary precipitation" },
    { name: "Steel Austenitizing Ac3", c: 850, k: 1123.15, r: 2021.67, desc: "FCC gamma transition" },
    { name: "Carburizing Atmosphere", c: 930, k: 1203.15, r: 2165.67, desc: "Carbon interstitial flux" },
    { name: "Pure Iron Liquidus", c: 1538, k: 1811.15, r: 3260.07, desc: "BCC delta melting pt" },
  ];

  // --------------------------------------------------------------------------
  // SYNC FROM ACTIVE UNIVERSAL SPECIMEN
  // --------------------------------------------------------------------------
  const handleLoadSpecimen = () => {
    if (!activeMaterialSpecimen || specimenYield === null) return;
    handleMpaChange(specimenYield);
    // Hardness is not loaded: the hardness card takes measured values, and the specimen record's HV is a
    // yield-strength estimate or unavailable (never measured).
    handleTempCChange(25);
  };

  // --------------------------------------------------------------------------
  // SEARCH FILTER LOGIC
  // --------------------------------------------------------------------------
  const query = searchQuery.trim().toLowerCase();

  const stressMatches =
    !query ||
    "stress strength mpa ksi n/mm2 yield tensile psi gpa bar"
      .toLowerCase()
      .includes(query) ||
    stressPresets.some(
      (p) =>
        p.name.toLowerCase().includes(query) ||
        p.desc.toLowerCase().includes(query)
    );

  const hardnessMatches =
    !query ||
    "hardness rockwell rc hrc vickers hv brinell hbw knoop hk leeb tensile rm"
      .toLowerCase()
      .includes(query) ||
    hardnessPresets.some(
      (p) =>
        p.name.toLowerCase().includes(query) ||
        p.desc.toLowerCase().includes(query)
    );

  const tempMatches =
    !query ||
    "temperature celsius kelvin rankine fahrenheit thermal heat cryogenic austenitizing"
      .toLowerCase()
      .includes(query) ||
    tempPresets.some(
      (p) =>
        p.name.toLowerCase().includes(query) ||
        p.desc.toLowerCase().includes(query)
    );

  const visibleCardsCount = [stressMatches, hardnessMatches, tempMatches].filter(
    Boolean
  ).length;

  return (
    <section
      id="metallurgical-unit-conversions-section"
      className="bg-[#090e18] rounded-xl border border-sky-500/30 shadow-lg overflow-hidden transition-all"
    >
      {/* Header Bar */}
      <div className="p-4 bg-gradient-to-r from-sky-950/40 via-slate-900 to-indigo-950/40 border-b border-[#162032] flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-sky-500/20 text-sky-400 border border-sky-400/40 shadow-[0_0_12px_rgba(56,189,248,0.2)]">
            <ArrowRightLeft className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white tracking-tight">
                Metallurgical Unit Conversions
              </h2>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-sky-500/20 text-sky-300 border border-sky-400/40">
                ASTM E140 / E8 / ISO
              </span>
              <StandardInfoIcon category="hardness" align="left" />
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Instant bidirectional conversion grid for <strong>MPa ⇄ ksi</strong>,{" "}
              <strong>RC (HRC) ⇄ HV</strong>, and{" "}
              <strong>Celsius ⇄ Kelvin ⇄ Rankine</strong> with searchable fields &amp; live outputs.
            </p>
          </div>
        </div>

        {/* Right side utilities */}
        <div className="flex items-center gap-2 self-start md:self-auto flex-wrap">
          <button
            id="btn-sync-specimen-units-grid"
            onClick={handleLoadSpecimen}
            disabled={specimenYield === null}
            className="px-2.5 py-1.5 bg-sky-600/20 hover:bg-sky-600/30 text-sky-300 border border-sky-500/40 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
            title={specimenYield === null
              ? `${activeMaterialSpecimen.name}: yield strength unavailable (not computed from composition), nothing to load`
              : `Load ${activeMaterialSpecimen.name} yield strength (hardness is not loaded: the specimen record holds no measured hardness)`}
          >
            <Sparkles className="w-3.5 h-3.5 text-sky-400" />
            <span className="hidden sm:inline">Use Specimen Values</span>
            <span className="sm:hidden">Specimen</span>
          </button>

          {onOpenFullSuite && (
            <button
              onClick={onOpenFullSuite}
              className="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all"
              title="Open the complete suite with Fracture Toughness, Grain Size &amp; Corrosion"
            >
              <span>Full Suite</span>
              <ExternalLink className="w-3.5 h-3.5 text-slate-400" />
            </button>
          )}

          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-1.5 text-slate-400 hover:text-white bg-slate-800/60 hover:bg-slate-800 border border-slate-700 rounded-lg transition"
            title={isCollapsed ? "Expand section" : "Collapse section"}
            aria-label="Toggle section collapse"
          >
            {isCollapsed ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {!isCollapsed && (
        <div className="p-4 space-y-4">
          {/* Search Bar with live indicator */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#0c1322] p-2.5 rounded-xl border border-[#1e2d46]">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input aria-label="Search conversions"
                id="search-metallurgical-units"
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search conversions (e.g., 'MPa', 'ksi', 'RC', 'HV', 'Rankine', 'Celsius', 'Ti-6Al-4V', 'bearing')..."
                className="w-full pl-9 pr-8 py-1.5 bg-[#090e18] border border-[#162032] focus:border-sky-400 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none font-medium"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                  title="Clear search"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            <div className="flex items-center gap-2 text-xs text-slate-400 font-mono shrink-0">
              <span>Showing:</span>
              <span className="px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 border border-sky-500/30 font-bold">
                {visibleCardsCount} of 3 Modules
              </span>
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="text-sky-400 underline hover:text-sky-300 text-[11px]"
                >
                  Reset Filter
                </button>
              )}
            </div>
          </div>

          {/* 3-Column Dedicated Grid Layout */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {/* =============================================================
                CARD 1: STRESS & STRENGTH (MPa / ksi)
               ============================================================= */}
            {stressMatches && (
              <div
                id="converter-card-stress-mpa-ksi"
                className="p-4 bg-[#0c1322] rounded-xl border border-[#1e2d46] hover:border-sky-500/50 transition flex flex-col justify-between space-y-3.5"
              >
                {/* Header */}
                <div>
                  <div className="flex items-center justify-between pb-2 border-b border-[#162032]">
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 rounded bg-sky-500/20 text-sky-400 border border-sky-500/30">
                        <Activity className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="flex items-center gap-1.5">
                          <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                            Stress &amp; Strength
                          </h3>
                          <StandardInfoIcon category="stress" align="left" />
                        </div>
                        <span className="text-[10px] font-mono text-sky-400 font-semibold">
                          MPa ⇄ ksi (ASTM E8 / E21)
                        </span>
                      </div>
                    </div>

                    <div className="text-right">
                      <span className={`text-[10px] font-mono font-bold ${stressInterpretation.color}`}>
                        ● {stressInterpretation.category}
                      </span>
                    </div>
                  </div>

                  {/* Dual Searchable Interactive Input Fields */}
                  <div className="grid grid-cols-2 gap-2 mt-3">
                    {/* MPa Input */}
                    <div className="space-y-1">
                      <label
                        htmlFor="input-stress-mpa"
                        className="text-[11px] font-mono text-slate-300 flex justify-between items-center"
                      >
                        <span className="font-bold text-sky-300">Megapascals (MPa)</span>
                        <span className="text-[9px] text-slate-500">N/mm²</span>
                      </label>
                      <div className="relative">
                        <input
                          id="input-stress-mpa"
                          type="number"
                          inputMode="decimal"
                          value={stressConversions.MPa}
                          onChange={(e) => handleMpaChange(parseFloat(e.target.value) || 0)}
                          className="w-full px-2.5 py-1.5 bg-[#090e18] border border-[#1e2d46] rounded-lg font-mono font-bold text-sm text-sky-400 focus:outline-none focus:border-sky-400"
                        />
                        <button
                          onClick={() => handleCopy(stressConversions.MPa, "quick-mpa")}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-sky-300"
                          title="Copy MPa"
                        >
                          {copiedId === "quick-mpa" ? (
                            <Check className="w-3.5 h-3.5 text-emerald-400" />
                          ) : (
                            <Copy className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </div>
                    </div>

                    {/* ksi Input */}
                    <div className="space-y-1">
                      <label
                        htmlFor="input-stress-ksi"
                        className="text-[11px] font-mono text-slate-300 flex justify-between items-center"
                      >
                        <span className="font-bold text-emerald-400">Kilopounds (ksi)</span>
                        <span className="text-[9px] text-slate-500">1000 psi</span>
                      </label>
                      <div className="relative">
                        <input
                          id="input-stress-ksi"
                          type="number"
                          inputMode="decimal"
                          value={stressConversions.ksi}
                          onChange={(e) => handleKsiChange(parseFloat(e.target.value) || 0)}
                          className="w-full px-2.5 py-1.5 bg-[#090e18] border border-[#1e2d46] rounded-lg font-mono font-bold text-sm text-emerald-400 focus:outline-none focus:border-emerald-400"
                        />
                        <button
                          onClick={() => handleCopy(stressConversions.ksi, "quick-ksi")}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-emerald-300"
                          title="Copy ksi"
                        >
                          {copiedId === "quick-ksi" ? (
                            <Check className="w-3.5 h-3.5 text-emerald-400" />
                          ) : (
                            <Copy className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Immediate Slider */}
                  <div className="mt-2.5">
                    <input aria-label="Megapascals (MPa) slider"
                      type="range"
                      min={20}
                      max={2200}
                      step={10}
                      value={stressConversions.MPa}
                      onChange={(e) => handleMpaChange(parseFloat(e.target.value) || 0)}
                      className="w-full accent-sky-400 bg-[#090e18] h-1.5 rounded cursor-pointer"
                    />
                  </div>

                  {/* Immediate Output Auxiliary Units */}
                  <div className="grid grid-cols-3 gap-1.5 mt-2.5 p-2 bg-[#090e18] rounded-lg border border-[#162032] text-center font-mono">
                    <div>
                      <div className="text-[9px] text-slate-500">GPa (Modulus)</div>
                      <div className="text-xs font-bold text-slate-200">{stressConversions.GPa}</div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500">Pounds/sq.in</div>
                      <div className="text-xs font-bold text-slate-200">
                        {stressConversions.psi.toLocaleString()}
                      </div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500">Hydrostatic Bar</div>
                      <div className="text-xs font-bold text-slate-200">{stressConversions.bar}</div>
                    </div>
                  </div>
                </div>

                {/* Filterable Alloy Presets */}
                <div className="pt-2 border-t border-[#162032]">
                  <span className="text-[9px] font-mono text-slate-400 uppercase tracking-wider block mb-1">
                    Quick Alloy Presets:
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {stressPresets
                      .filter(
                        (p) =>
                          !query ||
                          p.name.toLowerCase().includes(query) ||
                          p.desc.toLowerCase().includes(query)
                      )
                      .map((p, idx) => (
                        <button
                          key={idx}
                          onClick={() => handleMpaChange(p.mpa)}
                          className={`px-2 py-1 rounded text-[10px] font-mono border transition ${
                            stressConversions.MPa === p.mpa
                              ? "bg-sky-500/20 text-sky-300 border-sky-400/60"
                              : "bg-[#090e18] hover:bg-slate-800 text-slate-400 hover:text-slate-200 border-[#162032]"
                          }`}
                          title={`${p.name}: ${p.mpa} MPa (${p.ksi} ksi) - ${p.desc}`}
                        >
                          {p.name.split(" ")[0]} ({p.mpa} MPa)
                        </button>
                      ))}
                  </div>
                </div>
              </div>
            )}

            {/* =============================================================
                CARD 2: HARDNESS SCALES (Rockwell C [RC] / Vickers [HV])
               ============================================================= */}
            {hardnessMatches && (
              <div
                id="converter-card-hardness-rc-hv"
                className="p-4 bg-[#0c1322] rounded-xl border border-[#1e2d46] hover:border-emerald-500/50 transition flex flex-col justify-between space-y-3.5"
              >
                {/* Header */}
                <div>
                  <div className="flex items-center justify-between pb-2 border-b border-[#162032]">
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                        <ShieldCheck className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="flex items-center gap-1.5">
                          <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                            Hardness &amp; Tensile $R_m$
                          </h3>
                          <StandardInfoIcon category="hardness" align="center" />
                        </div>
                        <span className="text-[10px] font-mono text-emerald-400 font-semibold">
                          RC (HRC) ⇄ HV (ASTM E140)
                        </span>
                      </div>
                    </div>

                    <div className="text-right">
                      <span className="text-[10px] font-mono font-bold text-emerald-400">
                        {hardnessConversions.tensileRm_MPa === null
                          ? `Rm: ${UNAVAILABLE_TEXT}`
                          : `Rm ≈ ${hardnessConversions.tensileRm_MPa} MPa`}
                      </span>
                    </div>
                  </div>

                  {/* Alloy class: only non-austenitic steels are converted */}
                  <div className="flex justify-between items-center gap-2 mt-3 text-[11px] font-mono text-slate-300">
                    <span>Alloy class</span>
                    <select
                      aria-label="Alloy class"
                      value={hardnessClass}
                      onChange={(e) => setHardnessClass(e.target.value as HardnessMaterialClass)}
                      className="px-2 py-1 bg-[#090e18] border border-[#1e2d46] rounded-lg text-[10px] text-emerald-300 focus:outline-none focus:border-emerald-400"
                    >
                      {HARDNESS_MATERIAL_CLASSES.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Dual Searchable Interactive Input Fields */}
                  <div className="grid grid-cols-2 gap-2 mt-3">
                    {/* HRC Input */}
                    <div className="space-y-1">
                      <label
                        htmlFor="input-hardness-hrc"
                        className="text-[11px] font-mono text-slate-300 flex justify-between items-center"
                      >
                        <span className="font-bold text-emerald-400">Rockwell C (RC)</span>
                        <span className="text-[9px] text-slate-500">Brale Cone</span>
                      </label>
                      <div className="relative">
                        <input
                          id="input-hardness-hrc"
                          type="number"
                          inputMode="decimal"
                          min={20}
                          max={68}
                          value={hardnessInputScale === "HRC" ? hardnessValHrc : hardnessConversions.HRC ?? ""}
                          placeholder={hardnessConversions.HRC === null ? UNAVAILABLE_TEXT : ""}
                          onChange={(e) => handleHrcChange(parseFloat(e.target.value) || 0)}
                          className="w-full px-2.5 py-1.5 bg-[#090e18] border border-[#1e2d46] rounded-lg font-mono font-bold text-sm text-emerald-400 focus:outline-none focus:border-emerald-400"
                        />
                        <button
                          onClick={() => handleCopy(hardnessConversions.HRC ?? UNAVAILABLE_TEXT, "quick-hrc")}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-emerald-300"
                          title="Copy HRC"
                        >
                          {copiedId === "quick-hrc" ? (
                            <Check className="w-3.5 h-3.5 text-emerald-400" />
                          ) : (
                            <Copy className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </div>
                    </div>

                    {/* HV Input */}
                    <div className="space-y-1">
                      <label
                        htmlFor="input-hardness-hv"
                        className="text-[11px] font-mono text-slate-300 flex justify-between items-center"
                      >
                        <span className="font-bold text-cyan-400">Vickers (HV)</span>
                        <span className="text-[9px] text-slate-500">Diamond DPH</span>
                      </label>
                      <div className="relative">
                        <input
                          id="input-hardness-hv"
                          type="number"
                          inputMode="decimal"
                          min={80}
                          max={940}
                          value={hardnessInputScale === "HV" ? hardnessValHv : hardnessConversions.HV ?? ""}
                          placeholder={hardnessConversions.HV === null ? UNAVAILABLE_TEXT : ""}
                          onChange={(e) => handleHvChange(parseFloat(e.target.value) || 0)}
                          className="w-full px-2.5 py-1.5 bg-[#090e18] border border-[#1e2d46] rounded-lg font-mono font-bold text-sm text-cyan-400 focus:outline-none focus:border-cyan-400"
                        />
                        <button
                          onClick={() => handleCopy(hardnessConversions.HV ?? UNAVAILABLE_TEXT, "quick-hv")}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-cyan-300"
                          title="Copy HV"
                        >
                          {copiedId === "quick-hv" ? (
                            <Check className="w-3.5 h-3.5 text-emerald-400" />
                          ) : (
                            <Copy className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Immediate Slider */}
                  <div className="mt-2.5">
                    <input aria-label="Vickers (HV) slider"
                      type="range"
                      min={80}
                      max={940}
                      step={5}
                      value={hardnessConversions.HV ?? hardnessValHv}
                      onChange={(e) => handleHvChange(parseFloat(e.target.value) || 0)}
                      className="w-full accent-emerald-400 bg-[#090e18] h-1.5 rounded cursor-pointer"
                    />
                  </div>

                  {/* Immediate Auxiliary Conversions: Brinell, HRB, Estimated Rm */}
                  <div className="grid grid-cols-3 gap-1.5 mt-2.5 p-2 bg-[#090e18] rounded-lg border border-[#162032] text-center font-mono">
                    <div>
                      <div className="text-[9px] text-slate-500">Brinell HBW</div>
                      <div className="text-xs font-bold text-slate-200">{hardnessConversions.HBW ?? UNAVAILABLE_TEXT}</div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500">Rockwell B</div>
                      <div className="text-xs font-bold text-slate-200">
                        {hardnessConversions.HRB ?? UNAVAILABLE_TEXT}
                      </div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500">Tensile Rm</div>
                      <div className="text-xs font-bold text-emerald-300">
                        {hardnessConversions.tensileRm_ksi === null ? UNAVAILABLE_TEXT : `≈ ${hardnessConversions.tensileRm_ksi} ksi`}
                      </div>
                    </div>
                  </div>
                  <p className="text-[9px] text-slate-500 mt-1.5 leading-snug">
                    {hardnessClass === "non-austenitic-steel" ? HARDNESS_CONVERSION_DISCLAIMER : hardnessConversions.validRangeNote}
                  </p>
                </div>

                {/* Filterable Alloy Hardness Presets */}
                <div className="pt-2 border-t border-[#162032]">
                  <span className="text-[9px] font-mono text-slate-400 uppercase tracking-wider block mb-1">
                    Quick Heat-Treat Presets:
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {hardnessPresets
                      .filter(
                        (p) =>
                          !query ||
                          p.name.toLowerCase().includes(query) ||
                          p.desc.toLowerCase().includes(query)
                      )
                      .map((p, idx) => (
                        <button
                          key={idx}
                          onClick={() => applyHardnessPreset(p)}
                          className={`px-2 py-1 rounded text-[10px] font-mono border transition ${
                            hardnessInputScale === p.scale &&
                            (p.scale === "HRC" ? hardnessValHrc : hardnessValHv) === p.value &&
                            hardnessClass === p.cls
                              ? "bg-emerald-500/20 text-emerald-300 border-emerald-400/60"
                              : "bg-[#090e18] hover:bg-slate-800 text-slate-400 hover:text-slate-200 border-[#162032]"
                          }`}
                          title={`${p.name}: ${p.value} ${p.scale} (measured) - ${p.desc}`}
                        >
                          {p.name.split(" ")[0]} ({p.value} {p.scale})
                        </button>
                      ))}
                  </div>
                </div>
              </div>
            )}

            {/* =============================================================
                CARD 3: TEMPERATURE SCALES (Celsius / Kelvin / Rankine)
               ============================================================= */}
            {tempMatches && (
              <div
                id="converter-card-temp-c-k-r"
                className="p-4 bg-[#0c1322] rounded-xl border border-[#1e2d46] hover:border-amber-500/50 transition flex flex-col justify-between space-y-3.5"
              >
                {/* Header */}
                <div>
                  <div className="flex items-center justify-between pb-2 border-b border-[#162032]">
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30">
                        <Thermometer className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="flex items-center gap-1.5">
                          <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                            Temperature Scales
                          </h3>
                          <StandardInfoIcon category="temperature" align="right" />
                        </div>
                        <span className="text-[10px] font-mono text-amber-400 font-semibold">
                          Celsius ⇄ Kelvin ⇄ Rankine
                        </span>
                      </div>
                    </div>

                    <div className="text-right">
                      <span className="text-[10px] font-mono text-slate-400">
                        {tempConversions.C < 0
                          ? "Cryogenic"
                          : tempConversions.C <= 100
                          ? "Ambient"
                          : tempConversions.C <= 600
                          ? "Tempering/Aging"
                          : "Austenitizing/Melt"}
                      </span>
                    </div>
                  </div>

                  {/* 3 Synchronized Interactive Inputs: °C, K, °R */}
                  <div className="grid grid-cols-3 gap-2 mt-3">
                    {/* Celsius */}
                    <div className="space-y-1">
                      <label
                        htmlFor="input-temp-celsius"
                        className="text-[10px] font-mono text-slate-300 flex justify-between items-center"
                      >
                        <span className="font-bold text-amber-400">Celsius (°C)</span>
                      </label>
                      <div className="relative">
                        <input
                          id="input-temp-celsius"
                          type="number"
                          inputMode="decimal"
                          value={tempConversions.C}
                          onChange={(e) => handleTempCChange(parseFloat(e.target.value) || 0)}
                          className="w-full px-2 py-1.5 bg-[#090e18] border border-[#1e2d46] rounded-lg font-mono font-bold text-xs text-amber-400 focus:outline-none focus:border-amber-400"
                        />
                        <button
                          onClick={() => handleCopy(tempConversions.C, "quick-temp-c")}
                          className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-amber-300"
                          title="Copy °C"
                        >
                          {copiedId === "quick-temp-c" ? (
                            <Check className="w-3 h-3 text-emerald-400" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                        </button>
                      </div>
                    </div>

                    {/* Kelvin */}
                    <div className="space-y-1">
                      <label
                        htmlFor="input-temp-kelvin"
                        className="text-[10px] font-mono text-slate-300 flex justify-between items-center"
                      >
                        <span className="font-bold text-sky-400">Kelvin (K)</span>
                      </label>
                      <div className="relative">
                        <input
                          id="input-temp-kelvin"
                          type="number"
                          inputMode="decimal"
                          min={0}
                          value={tempConversions.K}
                          onChange={(e) => handleTempKChange(parseFloat(e.target.value) || 0)}
                          className="w-full px-2 py-1.5 bg-[#090e18] border border-[#1e2d46] rounded-lg font-mono font-bold text-xs text-sky-400 focus:outline-none focus:border-sky-400"
                        />
                        <button
                          onClick={() => handleCopy(tempConversions.K, "quick-temp-k")}
                          className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-sky-300"
                          title="Copy Kelvin"
                        >
                          {copiedId === "quick-temp-k" ? (
                            <Check className="w-3 h-3 text-emerald-400" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                        </button>
                      </div>
                    </div>

                    {/* Rankine */}
                    <div className="space-y-1">
                      <label
                        htmlFor="input-temp-rankine"
                        className="text-[10px] font-mono text-slate-300 flex justify-between items-center"
                      >
                        <span className="font-bold text-rose-400">Rankine (°R)</span>
                      </label>
                      <div className="relative">
                        <input
                          id="input-temp-rankine"
                          type="number"
                          inputMode="decimal"
                          min={0}
                          value={tempConversions.R}
                          onChange={(e) => handleTempRChange(parseFloat(e.target.value) || 0)}
                          className="w-full px-2 py-1.5 bg-[#090e18] border border-[#1e2d46] rounded-lg font-mono font-bold text-xs text-rose-400 focus:outline-none focus:border-rose-400"
                        />
                        <button
                          onClick={() => handleCopy(tempConversions.R, "quick-temp-r")}
                          className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-rose-300"
                          title="Copy Rankine"
                        >
                          {copiedId === "quick-temp-r" ? (
                            <Check className="w-3 h-3 text-emerald-400" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Immediate Slider */}
                  <div className="mt-2.5">
                    <input aria-label="Celsius (°C) slider"
                      type="range"
                      min={-200}
                      max={1600}
                      step={5}
                      value={tempConversions.C}
                      onChange={(e) => handleTempCChange(parseFloat(e.target.value) || 0)}
                      className="w-full accent-amber-400 bg-[#090e18] h-1.5 rounded cursor-pointer"
                    />
                  </div>

                  {/* Immediate Auxiliary Output: Fahrenheit & Reference Equation */}
                  <div className="grid grid-cols-2 gap-2 mt-2.5 p-2 bg-[#090e18] rounded-lg border border-[#162032] items-center text-xs font-mono">
                    <div>
                      <span className="text-[9px] text-slate-500 block">Fahrenheit (°F)</span>
                      <span className="font-bold text-slate-200">{tempConversions.F} °F</span>
                    </div>
                    <div className="text-right text-[10px] text-slate-400">
                      <span>°R = 1.8 × K</span>
                      <span className="block text-[9px] text-slate-500">K = °C + 273.15</span>
                    </div>
                  </div>
                </div>

                {/* Filterable Thermal Presets */}
                <div className="pt-2 border-t border-[#162032]">
                  <span className="text-[9px] font-mono text-slate-400 uppercase tracking-wider block mb-1">
                    Thermal Process Presets:
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {tempPresets
                      .filter(
                        (p) =>
                          !query ||
                          p.name.toLowerCase().includes(query) ||
                          p.desc.toLowerCase().includes(query)
                      )
                      .map((p, idx) => (
                        <button
                          key={idx}
                          onClick={() => handleTempCChange(p.c)}
                          className={`px-2 py-1 rounded text-[10px] font-mono border transition ${
                            tempConversions.C === p.c
                              ? "bg-amber-500/20 text-amber-300 border-amber-400/60"
                              : "bg-[#090e18] hover:bg-slate-800 text-slate-400 hover:text-slate-200 border-[#162032]"
                          }`}
                          title={`${p.name}: ${p.c}°C = ${p.k} K = ${p.r}°R (${p.desc})`}
                        >
                          {p.name.split(" ")[0]} ({p.c}°C)
                        </button>
                      ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
};
