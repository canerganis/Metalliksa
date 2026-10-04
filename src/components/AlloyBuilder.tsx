import React, { useState } from "react";
import {
  Boxes,
  Atom,
  Sliders,
  Sparkles,
  Plus,
  Trash2,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Flame,
  Activity,
  Layers,
  ArrowRight,
  BookmarkPlus,
  Info,
  ExternalLink,
  ShieldCheck,
  Cpu,
} from "lucide-react";
import { useMaterialStore, MATERIAL_PRESETS, BaseMetalType } from "../store/useMaterialStore";
import { useMaterialSpecimenStore } from "../store/useMaterialSpecimenStore";
import { MATERIAL_CATEGORIES, normalizeMaterialCategory } from "../utils/materialCategory";
import { InverseAlloyStudio } from "./InverseAlloyStudio";

interface AlloyBuilderProps {
  onNavigate?: (tabId: string) => void;
}

const COMMON_ALLOYING_ELEMENTS = [
  "Ni", "Fe", "Cr", "Co", "Mo", "W", "Ta", "Nb", "Ti", "Al",
  "V", "Mn", "Si", "Cu", "Mg", "Zr", "Hf", "Re", "Sc", "C", "B"
];
const MANUFACTURING_ROUTES = [
  "Unspecified", "LPBF (Laser Powder Bed Fusion)", "Forged & Rolled", "Investment Cast",
  "DED (Direct Energy Deposition)", "HIP (Hot Isostatic Pressed)",
];

export const AlloyBuilder: React.FC<AlloyBuilderProps> = ({ onNavigate }) => {
  // Global shared store (replaces local useState for material specimen)
  const {
    activeMaterialSpecimen,
    updateComposition,
    setElement,
    removeElement,
    normalizeComposition,
    updateName,
    updateMetadata,
    loadPreset,
    resetToDefault,
    saveCurrentSpecimen,
  } = useMaterialStore();
  const currentProcess = useMaterialSpecimenStore((state) => state.activeSpecimen.lpbf);
  const category = normalizeMaterialCategory(activeMaterialSpecimen.metadata?.category, activeMaterialSpecimen.metadata?.baseMetal);
  const categoryOptions: string[] = Object.values(MATERIAL_CATEGORIES);
  if (!categoryOptions.includes(category)) categoryOptions.push(category);
  const manufacturingRoute = activeMaterialSpecimen.metadata?.manufacturingRoute || "Unspecified";
  const routeOptions = MANUFACTURING_ROUTES.includes(manufacturingRoute)
    ? MANUFACTURING_ROUTES : [...MANUFACTURING_ROUTES, manufacturingRoute];

  // Local UI state for tab switching & element selection dropdown only
  const [activeSubView, setActiveSubView] = useState<"specimen-studio" | "inverse-pareto">("specimen-studio");
  const [selectedElementToAdd, setSelectedElementToAdd] = useState<string>("Re");
  const [isSavedToast, setIsSavedToast] = useState<boolean>(false);

  // Derive total elemental weight sum
  const composition = activeMaterialSpecimen.composition || {};
  const totalWeight = Object.values(composition).reduce((acc, val) => acc + (typeof val === "number" ? val : 0), 0);
  const isBalanced = Math.abs(totalWeight - 100.0) < 0.05;

  const handleSaveSnapshot = () => {
    saveCurrentSpecimen(`Saved from AlloyBuilder at ${new Date().toLocaleTimeString()}`);
    setIsSavedToast(true);
    setTimeout(() => setIsSavedToast(false), 2500);
  };

  const handleAddElementClick = () => {
    if (selectedElementToAdd && composition[selectedElementToAdd] === undefined) {
      setElement(selectedElementToAdd, 1.0);
    }
  };

  return (
    <div id="alloy-builder-root" className="space-y-6 text-slate-100 font-sans">
      {/* Top Banner & Universal Specimen Header */}
      <div className="bg-slate-900/90 border border-emerald-500/30 rounded-2xl p-6 shadow-2xl relative overflow-hidden backdrop-blur-md">
        <div className="absolute -top-24 -right-24 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="p-2.5 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl shadow-lg shadow-emerald-500/20 text-white">
                <Atom className="w-6 h-6 animate-pulse" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-xl font-black tracking-tight text-white">
                    MetalliX Universal Alloy Builder &amp; Specimen Studio
                  </h1>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wider uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
                    Live Shared Store
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Single source of truth for chemical composition, provenance metadata, and multi-physics propagation.
                </p>
              </div>
            </div>
          </div>

          {/* Sub-View Navigation Tabs */}
          <div className="flex items-center gap-2 bg-slate-950/80 p-1.5 rounded-xl border border-slate-800">
            <button
              id="tab-specimen-studio"
              onClick={() => setActiveSubView("specimen-studio")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                activeSubView === "specimen-studio"
                  ? "bg-emerald-500 text-slate-950 shadow-md font-bold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Sliders className="w-3.5 h-3.5" />
              <span>Specimen Formulator</span>
            </button>
            <button
              id="tab-inverse-pareto"
              onClick={() => setActiveSubView("inverse-pareto")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                activeSubView === "inverse-pareto"
                  ? "bg-emerald-500 text-slate-950 shadow-md font-bold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Inverse Pareto AI</span>
            </button>
          </div>
        </div>

        {/* Global Live Thread Status Strip */}
        <div className="mt-4 pt-4 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-slate-400 font-medium">Broadcasting to:</span>
            <span className="px-2 py-0.5 rounded bg-slate-800/90 text-slate-300 font-mono text-[11px] border border-slate-700">
              CALPHAD Thermodynamics
            </span>
            <span className="px-2 py-0.5 rounded bg-slate-800/90 text-slate-300 font-mono text-[11px] border border-slate-700">
              LPBF Melt Pool
            </span>
            <span className="px-2 py-0.5 rounded bg-slate-800/90 text-slate-300 font-mono text-[11px] border border-slate-700">
              Rapid XRD Lab
            </span>
            <span className="px-2 py-0.5 rounded bg-slate-800/90 text-slate-300 font-mono text-[11px] border border-slate-700">
              Digital Twin Hub
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              id="btn-save-specimen-snapshot"
              onClick={handleSaveSnapshot}
              className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium border border-slate-700 flex items-center gap-1.5 transition-colors"
            >
              <BookmarkPlus className="w-3.5 h-3.5 text-emerald-400" />
              <span>{isSavedToast ? "Snapshot Saved!" : "Save Snapshot"}</span>
            </button>
            <button
              id="btn-reset-specimen-default"
              onClick={resetToDefault}
              className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium border border-slate-700 flex items-center gap-1.5 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5 text-rose-400" />
              <span>Reset</span>
            </button>
          </div>
        </div>
      </div>

      {activeSubView === "specimen-studio" && (
        <>
          {/* Specimen Identity & Metadata Configurator */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-800 pb-3">
              <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <Boxes className="w-4 h-4 text-emerald-400" />
                <span>Active Specimen Identity &amp; Metadata</span>
              </h2>
              <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-md border border-emerald-500/20">
                Formula: {activeMaterialSpecimen.chemicalFormula}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
              {/* Specimen Name */}
              <div className="space-y-1.5">
                <label className="text-slate-400 font-semibold block">Specimen Name</label>
                <input aria-label="Specimen Name"
                  id="input-specimen-name"
                  type="text"
                  value={activeMaterialSpecimen.name}
                  onChange={(e) => updateName(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 font-medium focus:outline-none focus:border-emerald-500 transition-colors"
                  placeholder="e.g. Inconel 718 High-T Blade"
                />
              </div>

              {/* Material Category */}
              <div className="space-y-1.5">
                <label className="text-slate-400 font-semibold block">Material Category</label>
                <select aria-label="Material Category"
                  id="select-specimen-category"
                  value={category}
                  onChange={(e) => updateMetadata({ category: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 font-medium focus:outline-none focus:border-emerald-500 transition-colors"
                >
                  {categoryOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                </select>
              </div>

              {/* Standard Designation */}
              <div className="space-y-1.5">
                <label className="text-slate-400 font-semibold block">Standard Designation / Ref</label>
                <input aria-label="Standard Designation / Ref"
                  id="input-specimen-standard"
                  type="text"
                  value={activeMaterialSpecimen.metadata?.standardDesignation || ""}
                  onChange={(e) => updateMetadata({ standardDesignation: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 font-medium focus:outline-none focus:border-emerald-500 transition-colors"
                  placeholder="e.g. UNS N07718 / AMS 5662"
                />
              </div>

              {/* Manufacturing Route */}
              <div className="space-y-1.5">
                <label className="text-slate-400 font-semibold block">Manufacturing Route</label>
                <select aria-label="Manufacturing Route"
                  id="select-specimen-route"
                  value={manufacturingRoute}
                  onChange={(e) => updateMetadata({ manufacturingRoute: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 font-medium focus:outline-none focus:border-emerald-500 transition-colors"
                >
                  {routeOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                </select>
              </div>
            </div>

            {/* Quick Presets Carousel */}
            <div className="pt-2">
              <span className="text-[11px] uppercase tracking-wider text-slate-400 font-bold block mb-2">
                Quick Standard Alloy Presets:
              </span>
              <div className="flex flex-wrap gap-2">
                {Object.entries(MATERIAL_PRESETS).map(([key, preset]) => (
                  <button
                    key={key}
                    id={`btn-preset-${key}`}
                    onClick={() => loadPreset(key)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-all ${
                      activeMaterialSpecimen.name.includes(preset.name.split(" ")[0])
                        ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/50 shadow-sm"
                        : "bg-slate-950/60 hover:bg-slate-800 text-slate-300 border-slate-800"
                    }`}
                  >
                    {preset.name}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Chemical Composition Matrix Editor */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Atom className="w-4 h-4 text-cyan-400" />
                <h3 className="text-sm font-bold text-slate-100">
                  Chemical Composition Matrix ({activeMaterialSpecimen.unit === "at_pct" ? "at.%" : "wt.%"})
                </h3>
                <span
                  className={`px-2 py-0.5 rounded text-xs font-mono font-bold border ${
                    isBalanced
                      ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                      : "bg-amber-500/20 text-amber-400 border-amber-500/30"
                  }`}
                >
                  Total: {totalWeight.toFixed(2)}%
                </span>
              </div>

              <div className="flex items-center gap-2">
                {!isBalanced && (
                  <button
                    id="btn-normalize-comp"
                    onClick={normalizeComposition}
                    className="px-3 py-1 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 rounded-lg text-xs font-bold border border-amber-500/40 flex items-center gap-1 transition-colors"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Auto-Normalize to 100%</span>
                  </button>
                )}
                <div className="flex items-center gap-1.5">
                  <select aria-label="Add element"
                    id="select-add-element"
                    value={selectedElementToAdd}
                    onChange={(e) => setSelectedElementToAdd(e.target.value)}
                    className="px-2 py-1 bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
                  >
                    {COMMON_ALLOYING_ELEMENTS.filter((el) => composition[el] === undefined).map((el) => (
                      <option key={el} value={el}>
                        + {el}
                      </option>
                    ))}
                  </select>
                  <button
                    id="btn-add-element"
                    onClick={handleAddElementClick}
                    className="p-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-700 transition-colors"
                    title="Add Element"
                  >
                    <Plus className="w-4 h-4 text-emerald-400" />
                  </button>
                </div>
              </div>
            </div>

            {/* Element Input Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {Object.entries(composition).map(([element, pct]) => (
                <div
                  key={element}
                  className="bg-slate-950/70 border border-slate-800 rounded-xl p-3 space-y-2 relative group hover:border-slate-700 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <span className="w-7 h-7 rounded-lg bg-slate-900 border border-slate-700 flex items-center justify-center font-bold font-mono text-sm text-sky-400 shadow-inner">
                        {element}
                      </span>
                      <span className="text-xs text-slate-400 font-medium">Element</span>
                    </div>

                    <div className="flex items-center gap-1">
                      <input aria-label={`${element} content`}
                        type="number"
                        step="0.1"
                        min="0"
                        max="100"
                        value={pct}
                        onChange={(e) => setElement(element, parseFloat(e.target.value) || 0)}
                        className="w-16 px-1.5 py-0.5 bg-slate-900 border border-slate-700 rounded text-right font-mono text-xs text-slate-100 focus:outline-none focus:border-emerald-500"
                      />
                      <span className="text-xs text-slate-400">%</span>
                      <button
                        onClick={() => removeElement(element)}
                        className="p-1 text-slate-500 hover:text-rose-400 transition-colors opacity-60 group-hover:opacity-100"
                        title={`Remove ${element}`}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Slider Control */}
                  <input aria-label={`${element} content slider`}
                    type="range"
                    min="0"
                    max={element === activeMaterialSpecimen.metadata?.baseMetal ? 100 : 35}
                    step="0.1"
                    value={pct}
                    onChange={(e) => setElement(element, parseFloat(e.target.value))}
                    className="w-full accent-emerald-400 h-1.5 bg-slate-800 rounded-lg cursor-pointer"
                  />
                </div>
              ))}
            </div>
          </div>

          {/* Real-time Multi-Physics Derived KPI Dashboard */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {/* Density */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-lg space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 flex items-center gap-1">
                <Layers className="w-3.5 h-3.5 text-sky-400" />
                <span>Alloy Density (Rule of Mixtures)</span>
              </span>
              <div className="flex items-baseline gap-1.5">
                <span className="text-xl font-black font-mono text-sky-300">
                  {activeMaterialSpecimen.metadata?.density_gcm3?.toFixed(3) || "8.190"}
                </span>
                <span className="text-xs text-slate-400 font-mono">g/cm³</span>
              </div>
            </div>

            {/* Solidification Freezing Range */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-lg space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 flex items-center gap-1">
                <Flame className="w-3.5 h-3.5 text-amber-400" />
                <span>Liquidus / Solidus Range</span>
              </span>
              <div className="flex items-baseline gap-1.5">
                <span className="text-xl font-black font-mono text-amber-300">
                  {activeMaterialSpecimen.freezingRange_C}
                </span>
                <span className="text-xs text-slate-400 font-mono">°C ΔT ({activeMaterialSpecimen.liquidus_C}° / {activeMaterialSpecimen.solidus_C}°)</span>
              </div>
            </div>

            {/* Yield Strength & UTS */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-lg space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 flex items-center gap-1">
                <Activity className="w-3.5 h-3.5 text-emerald-400" />
                <span>Yield Strength (25°C)</span>
              </span>
              <div className="flex items-baseline gap-1.5">
                <span className="text-xl font-black font-mono text-emerald-300">
                  {activeMaterialSpecimen.yieldStrength_25C_MPa}
                </span>
                <span className="text-xs text-slate-400 font-mono">MPa (UTS: {activeMaterialSpecimen.uts_25C_MPa} MPa)</span>
              </div>
            </div>

            {/* LPBF Additive Laser Power */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-lg space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 flex items-center gap-1">
                <Cpu className="w-3.5 h-3.5 text-violet-400" />
                <span>LPBF Starting Estimate (Screening)</span>
              </span>
              <div className="flex items-baseline gap-1.5">
                <span className="text-xl font-black font-mono text-violet-300">
                  {activeMaterialSpecimen.lpbf?.recommendedLaserPower_W}
                </span>
                <span className="text-xs text-slate-400 font-mono">W @ {activeMaterialSpecimen.lpbf?.recommendedScanSpeed_mms} mm/s</span>
              </div>
              <p className="text-xs text-slate-300" data-testid="alloy-current-process">
                Current shared process: {currentProcess.laserPower_W} W @ {currentProcess.scanSpeed_mms} mm/s
              </p>
              <p className="text-[11px] text-slate-400">Composition-based estimate; unvalidated. Current process settings are retained.</p>
            </div>
          </div>
        </>
      )}

      {/* Sub-View: Inverse Pareto Multi-Objective Optimization Studio */}
      {activeSubView === "inverse-pareto" && (
        <InverseAlloyStudio onNavigate={onNavigate} />
      )}
    </div>
  );
};
