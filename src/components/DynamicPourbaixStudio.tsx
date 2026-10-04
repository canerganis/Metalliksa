import React, { useState, useMemo, useRef, useEffect, useCallback } from "react";
import {
  Compass,
  Thermometer,
  Droplets,
  Layers,
  RefreshCw,
  Download,
  Zap,
  Atom,
  Binary,
  Target,
  Sliders,
  Plus,
} from "lucide-react";
import {
  ALLOY_PRESETS,
  CATEGORY_DISPLAY,
  CATEGORY_STYLE,
  DEFAULT_ALLOY_ID,
  NERNST_SLOPE_25C,
  PASSIVATION_NOTE,
  POURBAIX_DATA,
  classifyPourbaixPoint,
  computeDomains,
  ION_ACTIVITY_OPTIONS,
  WITHHELD_REGION_NOTE,
  activityInRange,
  computeWithheldRegions,
  freePhWindows,
  pourbaixActivityRange,
  pourbaixUnavailableReason,
  withheldSpeciesAt,
  primaryElementOf,
  speciesCoefficients,
  waterLines25C,
} from "../utils/pourbaixThermodynamics";
import {
  AlloyPreset,
  StabilityCategory,
  ExperimentalEpHEntry,
  PythonPourbaixResult,
  ReferenceElectrode,
} from "../types/pourbaix";
import {
  EXPERIMENTAL_POURBAIX_PRESETS,
  CAPTURED_PROBE_NOTE,
  CAPTURED_PROBE_STAGE,
  PRESET_POINTS_NOTE,
  REF_OFFSETS_VS_SHE,
} from "../utils/experimentalPourbaixOverlay";
import { drawPourbaixScene } from "../utils/pourbaixCanvas";
import { pythonComputationService } from "../services/pythonComputationService";
import { useDebouncedLatestTask } from "../hooks/useDebouncedLatestTask";
import { buildPourbaixRequest, pourbaixRequestSignature } from "../utils/pourbaixRequest";

/** The engine data is 25 °C only (python/pourbaix_solver.py raises TEMPERATURE_UNSUPPORTED otherwise). */
const SUPPORTED_TEMPERATURE_C = POURBAIX_DATA.temperature_C;
const BOX = POURBAIX_DATA.box;
const PASSIVATION: StabilityCategory = "Passivation (thermodynamic)";

/** Accessible solver-failure line; shows the existing error text only. */
export function PourbaixSolveError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs font-mono text-red-300">
      {message}
    </p>
  );
}

/** `initialSolveError` and `initialAlloyId` are render-test seams only (the solver effect resets the error before every dispatch). */
export function DynamicPourbaixStudio({ initialSolveError = null, initialAlloyId = DEFAULT_ALLOY_ID }: { initialSolveError?: string | null; initialAlloyId?: string } = {}) {
  // The loaded experimental preset names the element its points belong to; the default alloy (pure Fe) agrees with it.
  const initialPreset = EXPERIMENTAL_POURBAIX_PRESETS[0];
  const [selectedAlloyId, setSelectedAlloyId] = useState<string>(initialAlloyId);
  const initialElementForError =
    initialAlloyId === DEFAULT_ALLOY_ID
      ? initialPreset.element
      : (() => { const a = ALLOY_PRESETS.find((p) => p.id === initialAlloyId); return a ? primaryElementOf(a.composition) : initialPreset.element; })();
  const [selectedElement, setSelectedElement] = useState<string>(initialElementForError);

  // Environmental Parameters (temperature is fixed: 25 °C data only)
  const temperature_C = SUPPORTED_TEMPERATURE_C;
  const [chlorideActivity, setChlorideActivity] = useState<number>(0.54); // 0.54 M ~ 3.5% NaCl seawater (echoed to the solver; not part of the equilibrium)
  const [ionActivity, setIonActivity] = useState<number>(1e-6); // 1e-6 M corrosion convention
  const [refElectrode, setRefElectrode] = useState<ReferenceElectrode>("SHE");

  // Tab selection
  const [activeTab, setActiveTab] = useState<"diagram" | "experimental-overlay" | "reactions" | "alloy-formulator">("diagram");

  // Experimental Test Points Overlay State
  const [experimentalPoints, setExperimentalPoints] = useState<ExperimentalEpHEntry[]>(() => [
    ...EXPERIMENTAL_POURBAIX_PRESETS[0].points,
  ]);
  const [selectedPointId, setSelectedPointId] = useState<string | null>(() =>
    EXPERIMENTAL_POURBAIX_PRESETS[0].points.length > 0
      ? EXPERIMENTAL_POURBAIX_PRESETS[0].points[0].id
      : null
  );

  // Overlay visual options
  const [showExperimentalOverlay, setShowExperimentalOverlay] = useState<boolean>(true);
  const [showTrajectoryPath, setShowTrajectoryPath] = useState<boolean>(true);
  const [showPointLabels, setShowPointLabels] = useState<boolean>(true);

  // Python Backend Computation State (boundary table and point diagnostics; the map itself is the TS port of the same engine)
  const [pythonPourbaixData, setPythonPourbaixData] = useState<PythonPourbaixResult | null>(null);
  const [isPythonSolving, setIsPythonSolving] = useState<boolean>(false);
  // The error belongs to the element it was raised for: after an element switch it is not shown next to another map.
  const [solveErrorState, setSolveErrorState] = useState<{ message: string; element: string } | null>(
    initialSolveError === null ? null : { message: initialSolveError, element: initialElementForError }
  );
  const setPythonSolveError = (message: string | null, element: string = primaryElement) =>
    setSolveErrorState(message === null ? null : { message, element });
  const pythonSolveError = solveErrorState && solveErrorState.element === selectedElement ? solveErrorState.message : null;

  // Interactive Crosshair Probe
  const [probePH, setProbePH] = useState<number>(7.0);
  const [probePotential_SHE, setProbePotential_SHE] = useState<number>(0.2);

  // View bounds: the engine box (pH -2..16, E -3.0..2.5 V SHE)
  const FULL_VIEW = { minPH: BOX.pH_min, maxPH: BOX.pH_max, minE: BOX.E_min_V_SHE, maxE: BOX.E_max_V_SHE };
  const [viewBounds, setViewBounds] = useState<{ minPH: number; maxPH: number; minE: number; maxE: number }>(FULL_VIEW);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const currentAlloy = useMemo<AlloyPreset>(
    () => ALLOY_PRESETS.find((a) => a.id === selectedAlloyId) || ALLOY_PRESETS.find((a) => a.id === DEFAULT_ALLOY_ID)!,
    [selectedAlloyId]
  );
  const activeComposition = currentAlloy.composition;

  // The single element whose M-H2O map is shown and sent to the Python solver
  const primaryElement = selectedElement;
  const unavailableReason = pourbaixUnavailableReason(selectedElement);
  // Each element has its own dissolved-activity range (Cr up to 1e-2, Mo up to 1e-4: polynuclear species); a
  // chosen activity outside it falls back to 1e-6 for this element, and the request carries that value.
  const [activityLo, activityHi] = pourbaixActivityRange(selectedElement);
  const activityOutsideRange = !activityInRange(selectedElement, Math.log10(ionActivity));
  const effectiveIonActivity = activityOutsideRange ? 1e-6 : ionActivity;
  const log10Activity = Math.log10(effectiveIonActivity);
  const elementEntry = POURBAIX_DATA.elements[selectedElement];
  const candidateSets = elementEntry && "candidateSets" in elementEntry ? elementEntry.candidateSets : [];
  const unsourcedSpecies = elementEntry && "unsourcedSpecies" in elementEntry ? elementEntry.unsourcedSpecies : [];

  // Water stability lines (25 °C) and Nernst slope
  const waterLines = useMemo(() => waterLines25C(), []);
  const nernstSlope = NERNST_SLOPE_25C;

  // Reference electrode offset
  const refOffset = REF_OFFSETS_VS_SHE[refElectrode] || 0.0;

  // Species coefficients and exact domains of the selected element
  const coeffs = useMemo(
    () => (unavailableReason === null ? speciesCoefficients(selectedElement, log10Activity) : null),
    [selectedElement, log10Activity, unavailableReason]
  );
  const domains = useMemo(() => (coeffs ? computeDomains(coeffs) : []), [coeffs]);
  // Regions where a withheld (contradictory or excluded) species would be stable: the map is not valid there
  const withheldRegions = useMemo(
    () => (coeffs ? computeWithheldRegions(selectedElement, log10Activity) : []),
    [coeffs, selectedElement, log10Activity]
  );
  const freeWindows = useMemo(() => freePhWindows(withheldRegions), [withheldRegions]);

  // Probed Thermodynamic State
  const probedState = useMemo(
    () => (coeffs ? classifyPourbaixPoint(coeffs, probePH, probePotential_SHE) : null),
    [coeffs, probePH, probePotential_SHE]
  );
  const probeWithheld = useMemo(
    () => (coeffs ? withheldSpeciesAt(selectedElement, log10Activity, probePH, probePotential_SHE) : []),
    [coeffs, selectedElement, log10Activity, probePH, probePotential_SHE]
  );

  // Every test point classified in the CURRENT map by the same port (never by a solver echo, so it cannot be
  // stale and cannot describe another element's map).
  const pointStates = useMemo(
    () =>
      experimentalPoints.map((pt) => {
        const she = pt.potential_V + (REF_OFFSETS_VS_SHE[pt.refElectrode] ?? 0);
        return {
          pt,
          she,
          state: coeffs ? classifyPourbaixPoint(coeffs, pt.pH, she) : null,
          withheld: coeffs ? withheldSpeciesAt(selectedElement, log10Activity, pt.pH, she).length > 0 : false,
        };
      }),
    [experimentalPoints, coeffs, selectedElement, log10Activity]
  );

  // Each constituent element evaluated alone at the probe point (no alloy equilibrium, no composite verdict)
  const elementStates = useMemo(() => {
    const states: { [el: string]: ReturnType<typeof classifyPourbaixPoint> | null } = {};
    for (const el of Object.keys(activeComposition)) {
      states[el] = pourbaixUnavailableReason(el) === null && activityInRange(el, log10Activity)
        ? classifyPourbaixPoint(speciesCoefficients(el, log10Activity), probePH, probePotential_SHE)
        : null;
    }
    return states;
  }, [activeComposition, log10Activity, probePH, probePotential_SHE]);

  // The Python result is shown only while it belongs to the current element and activity.
  const pythonFresh =
    pythonPourbaixData !== null &&
    pythonPourbaixData.element === selectedElement &&
    pythonPourbaixData.parameters.ionActivity_log10 === log10Activity;

  // -------------------------------------------------------------
  // ASYNC PYTHON POURBAIX EQUILIBRIUM SOLVER DISPATCH
  // -------------------------------------------------------------
  // Debounced, visibility-gated and abortable; an unchanged input is not re-solved when the module is shown again.
  const pourbaixInputSignature = pourbaixRequestSignature({ primaryElement, temperature_C, ionActivity: effectiveIonActivity, chlorideActivity, experimentalPoints });
  useDebouncedLatestTask(pourbaixInputSignature, async (_signature, signal): Promise<boolean> => {
    async function dispatchPythonSolver(): Promise<boolean> {
      // No verified data: the panel already states the engine's reason; a request would only repeat it as an alert.
      if (pourbaixUnavailableReason(primaryElement) !== null) {
        setPythonPourbaixData(null);
        setPythonSolveError(null);
        setIsPythonSolving(false);
        return true;
      }
      try {
        setIsPythonSolving(true);
        setPythonSolveError(null);

        const result = await pythonComputationService.solvePourbaixDiagram(
          buildPourbaixRequest({ primaryElement, temperature_C, ionActivity: effectiveIonActivity, chlorideActivity, experimentalPoints }), signal);

        if (!signal.aborted && result.success) {
          // The result is shown only for the element and activity it was solved for (pythonFresh). Solver
          // diagnostics are NEVER merged back into the user's points: echoed text would change the request
          // signature and trigger another solve (an endless request loop), and a result of another element
          // would label the points of the current map. Point states come from the port (pointStates).
          setPythonPourbaixData(result);
          return true;
        }
        return false;
      } catch (err: any) {
        if (!signal.aborted) {
          setPythonPourbaixData(null);
          setPythonSolveError(err.message || "Failed to reach Python Pourbaix solver.", primaryElement);
        }
        return false;
      } finally {
        if (!signal.aborted) {
          setIsPythonSolving(false);
        }
      }
    }

    return dispatchPythonSolver();
  }, 150);

  // -------------------------------------------------------------
  // CANVAS RENDERING ENGINE WITH EXPERIMENTAL OVERLAY
  // -------------------------------------------------------------
  const renderPourbaixCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    drawPourbaixScene(ctx, {
      width: canvas.width,
      height: canvas.height,
      viewBounds,
      refOffset,
      refLabel: refElectrode,
      domains,
      coeffs,
      waterLines,
      nernstSlope,
      temperature_C,
      log10Activity,
      probePH,
      probePotential_SHE,
      probedState,
      showExperimentalOverlay,
      showTrajectoryPath,
      showPointLabels,
      selectedPointId,
      points: pointStates.map(({ pt, she, state }) => ({
        id: pt.id, name: pt.name, stageName: pt.stageName, pH: pt.pH, she, category: state ? state.category : null,
      })),
      withheldRegions,
      probeInWithheldRegion: probeWithheld.length > 0,
    });
  }, [
    viewBounds,
    refOffset,
    refElectrode,
    log10Activity,
    domains,
    coeffs,
    waterLines,
    nernstSlope,
    temperature_C,
    probePH,
    probePotential_SHE,
    probedState,
    showExperimentalOverlay,
    pointStates,
    selectedPointId,
    showTrajectoryPath,
    showPointLabels,
    withheldRegions,
    probeWithheld,
  ]);

  // Redraw on dependency changes AND whenever the canvas is (re)mounted: it is unmounted with the diagram tab
  // and with an element that has no verified data, and a fresh canvas is blank until drawn.
  const canvasMounted = activeTab === "diagram" && unavailableReason === null;
  useEffect(() => {
    if (canvasMounted) renderPourbaixCanvas();
  }, [renderPourbaixCanvas, canvasMounted]);

  // Handle canvas mouse move / click
  const handleCanvasInteraction = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * canvas.width;
    const y = ((e.clientY - rect.top) / rect.height) * canvas.height;

    const { minPH, maxPH, minE, maxE } = viewBounds;
    const ph = minPH + (x / canvas.width) * (maxPH - minPH);
    const e_disp = minE + ((canvas.height - y) / canvas.height) * (maxE - minE);
    const e_she = e_disp + refOffset;

    // Check if user clicked close to an experimental point
    if (showExperimentalOverlay && experimentalPoints.length > 0) {
      const phToX = (p: number) => ((p - minPH) / (maxPH - minPH)) * canvas.width;
      const eToY = (es: number) => {
        const ed = es - refOffset;
        return canvas.height - ((ed - minE) / (maxE - minE)) * canvas.height;
      };

      for (const { pt, she } of pointStates) {
        const px = phToX(pt.pH);
        const py = eToY(she);
        const dist = Math.hypot(x - px, y - py);
        if (dist <= 18) {
          setSelectedPointId(pt.id);
          setProbePH(pt.pH);
          setProbePotential_SHE(she);
          return;
        }
      }
    }

    setProbePH(parseFloat(Math.max(BOX.pH_min, Math.min(BOX.pH_max, ph)).toFixed(2)));
    setProbePotential_SHE(parseFloat(Math.max(BOX.E_min_V_SHE, Math.min(BOX.E_max_V_SHE, e_she)).toFixed(3)));
  };

  const handleAddProbedCoordinateAsPoint = () => {
    const newEntry: ExperimentalEpHEntry = {
      id: `pt_probed_${Date.now()}`,
      name: `Computed probe coordinate (pH ${probePH.toFixed(2)}, ${(probePotential_SHE - refOffset).toFixed(3)} V ${refElectrode})`,
      pH: probePH,
      potential_V: probePotential_SHE - refOffset,
      refElectrode: refElectrode,
      stageName: CAPTURED_PROBE_STAGE,
      notes: `${CAPTURED_PROBE_NOTE} Captured at T=${temperature_C}°C (25 °C data only), a(M)=10^${log10Activity}. Dominant in the computed map: ${probedState ? probedState.formula : "no verified data"}`,
    };
    const updated = [...experimentalPoints, newEntry];
    setExperimentalPoints(updated);
    setSelectedPointId(newEntry.id);
  };

  const selectElement = (element: string) => {
    setSelectedElement(element);
    setActiveTab("diagram");
  };

  const selectedPointState = pointStates.find(({ pt }) => pt.id === selectedPointId) ?? null;
  // Preset points belong to the preset's element; in another element's map they are only reclassified.
  const presetPointIds = useMemo(() => new Set(initialPreset.points.map((p) => p.id)), [initialPreset]);
  const reclassifiedPresetPoints =
    unavailableReason === null &&
    selectedElement !== initialPreset.element &&
    experimentalPoints.some((p) => presetPointIds.has(p.id));

  return (
    <div className="space-y-6 animate-fadeIn pb-12 font-sans">
      {/* =========================================================================
          FLAGSHIP HEADER BANNER
         ========================================================================= */}
      <div className="relative rounded-2xl bg-gradient-to-br from-[#0c1524] via-[#09111e] to-[#050912] p-6 lg:p-8 border border-sky-500/20 shadow-2xl overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-sky-500/5 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20"></div>
        <div className="absolute bottom-0 left-1/3 w-80 h-80 bg-teal-500/5 rounded-full blur-3xl pointer-events-none"></div>

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2 max-w-3xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky-500/10 border border-sky-500/30 text-sky-300 text-xs font-mono font-semibold">
              <Compass className="w-3.5 h-3.5 text-sky-400" />
              <span>THEORETICAL POURBAIX STABILITY BOUNDARIES &amp; EXPERIMENTAL OVERLAY</span>
            </div>
            <h1 className="text-2xl lg:text-3xl font-extrabold text-white tracking-tight font-mono">
              Pourbaix E–pH Studio (25 °C)
            </h1>
            <p className="text-slate-300 text-sm leading-relaxed">
              Single-element M–H₂O equilibrium by minimum Gibbs energy (25 °C, dissolved activity 10ⁿ, γ = 1); overlays
              illustrative preset E–pH points (not measured data) and points you add.
            </p>
          </div>

          {/* Quick Metrics Badge */}
          <div className="flex flex-wrap lg:flex-col gap-2.5 shrink-0 font-mono text-xs">
            <div className="px-3.5 py-2 rounded-xl bg-[#09101c] border border-sky-500/30 flex items-center justify-between gap-4">
              <span className="text-slate-400">Nernst Slope (2.303RT/F):</span>
              <span className="text-sky-300 font-bold">{(nernstSlope * 1000).toFixed(1)} mV/pH</span>
            </div>
            <div className="px-3.5 py-2 rounded-xl bg-[#09101c] border border-emerald-500/30 flex items-center justify-between gap-4">
              <span className="text-slate-400">Water Window (ΔE):</span>
              <span className="text-emerald-300 font-bold">
                {(waterLines.oerLine.e_at_ph0 - waterLines.herLine.e_at_ph0).toFixed(3)} V
              </span>
            </div>
            <div className="px-3.5 py-2 rounded-xl bg-[#09101c] border border-amber-500/30 flex items-center justify-between gap-4">
              <span className="text-slate-400">Test points:</span>
              <span className="text-amber-300 font-bold">{experimentalPoints.length} Loaded</span>
            </div>
          </div>
        </div>

        {/* Sub-Navigation Tabs */}
        <div className="mt-6 pt-4 border-t border-[#1a263c] flex flex-wrap items-center gap-2">
          {[
            { id: "diagram", label: "2D Pourbaix E-pH Diagram", icon: Compass },
            {
              id: "experimental-overlay",
              label: `Test points (${experimentalPoints.length})`,
              icon: Target,
            },
            { id: "reactions", label: "Equilibrium boundaries (25 °C)", icon: Binary },
            { id: "alloy-formulator", label: "Element selector (no alloy equilibrium)", icon: Sliders },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-mono font-bold transition-all ${
                  isActive
                    ? "bg-gradient-to-r from-sky-500/20 to-teal-500/20 text-sky-300 border border-sky-400/50 shadow-[0_0_12px_rgba(56,189,248,0.3)]"
                    : "text-slate-400 hover:text-slate-200 hover:bg-[#0c1424]"
                }`}
              >
                <Icon className="w-4 h-4 text-sky-400" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* =========================================================================
          VIEW 1: PRIMARY 2D POURBAIX DIAGRAM & INTERACTIVE CONTROLS
         ========================================================================= */}
      {activeTab === "diagram" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Control Column: Environmental & Alloy Controls */}
          <div className="lg:col-span-4 space-y-4">
            {/* Alloy Selection Card */}
            <div className="bg-[#090e18] rounded-2xl border border-[#162032] p-4 space-y-4">
              <div className="flex items-center justify-between border-b border-[#162032] pb-2">
                <span className="text-xs font-bold text-white font-mono flex items-center gap-2">
                  <Atom className="w-4 h-4 text-sky-400" />
                  Alloy &amp; Metal System
                </span>
                <span className="text-[10px] font-mono text-slate-400 px-2 py-0.5 rounded bg-[#060b13] border border-[#1a263c]">
                  {currentAlloy.category}
                </span>
              </div>

              <div>
                <label className="text-[10px] text-slate-400 font-mono block mb-1">Standard Preset:</label>
                <select aria-label="Standard Preset"
                  value={selectedAlloyId}
                  onChange={(e) => {
                    const preset = ALLOY_PRESETS.find((a) => a.id === e.target.value);
                    setSelectedAlloyId(e.target.value);
                    if (preset) setSelectedElement(primaryElementOf(preset.composition));
                  }}
                  className="w-full bg-[#060b13] border border-[#1a263c] rounded px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500"
                >
                  {ALLOY_PRESETS.map((preset) => (
                    <option key={preset.id} value={preset.id}>
                      {preset.name} ({preset.category})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-[10px] text-slate-400 font-mono block mb-1">Element (M–H₂O system):</label>
                <select aria-label="Element (M–H₂O system)"
                  value={selectedElement}
                  onChange={(e) => setSelectedElement(e.target.value)}
                  className="w-full bg-[#060b13] border border-[#1a263c] rounded px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500"
                >
                  {Object.entries(activeComposition).map(([el, wt]) => (
                    <option key={el} value={el}>
                      {el} ({wt}% wt){pourbaixUnavailableReason(el) === null ? "" : " - no verified data"}
                    </option>
                  ))}
                </select>
              </div>

              <div className="text-xs text-slate-400 font-mono leading-relaxed bg-[#060b13] p-2.5 rounded-lg border border-[#162032]">
                <strong className="text-slate-300 block mb-1">{currentAlloy.name}</strong>
                {currentAlloy.description}
              </div>
            </div>

            {/* Solution State */}
            <div className="bg-[#090e18] rounded-2xl border border-[#162032] p-4 space-y-4">
              <div className="flex items-center justify-between border-b border-[#162032] pb-2">
                <span className="text-xs font-bold text-white font-mono flex items-center gap-2">
                  <Thermometer className="w-4 h-4 text-amber-400" />
                  Solution State (25 °C data only)
                </span>
                <span className="text-[10px] font-mono text-amber-400">
                  T = {temperature_C}°C ({Math.round(temperature_C + 273.15)} K)
                </span>
              </div>

              {/* Temperature: fixed */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-slate-400">Temperature:</span>
                  <span className="text-amber-300 font-bold">{temperature_C} °C — 25 °C data only</span>
                </div>
                <input aria-label="Temperature (25 °C data only)"
                  type="range"
                  min={temperature_C}
                  max={temperature_C}
                  step="1"
                  value={temperature_C}
                  disabled
                  readOnly
                  className="w-full h-1.5 bg-[#162032] rounded-lg appearance-none cursor-not-allowed accent-amber-400 opacity-60"
                />
                <p className="text-[10px] text-slate-500 font-mono">
                  The species table has no consistent entropies or heat capacities; the engine refuses other temperatures.
                </p>
              </div>

              {/* Chloride Ion Activity Slider */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-slate-400 flex items-center gap-1.5">
                    <Droplets className="w-3.5 h-3.5 text-teal-400" />
                    Chloride Activity a(Cl⁻):
                  </span>
                  <span className="text-teal-300 font-bold">
                    {chlorideActivity} M ({Math.round(chlorideActivity * 35453)} ppm)
                  </span>
                </div>
                <input aria-label="Chloride Activity a(Cl⁻)"
                  type="range"
                  min="0.0001"
                  max="4.0"
                  step="0.01"
                  value={chlorideActivity}
                  onChange={(e) => setChlorideActivity(parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-[#162032] rounded-lg appearance-none cursor-pointer accent-teal-400"
                />
                <p className="text-[10px] text-slate-500 font-mono">
                  Echoed to the solver only: the equilibrium has no chloride species and no sourced pitting potential.
                </p>
              </div>

              {/* Reference Electrode Selector */}
              <div className="grid grid-cols-2 gap-2 pt-1">
                <div>
                  <label className="text-[10px] text-slate-400 font-mono block mb-1">Reference Scale:</label>
                  <select aria-label="Reference Scale"
                    value={refElectrode}
                    onChange={(e) => setRefElectrode(e.target.value as ReferenceElectrode)}
                    className="w-full bg-[#060b13] border border-[#1a263c] rounded px-2 py-1.5 text-xs text-slate-200 font-mono"
                  >
                    <option value="SHE">SHE (Standard Hydrogen)</option>
                    <option value="SCE">SCE (+0.241V)</option>
                    <option value="Ag/AgCl (3M KCl)">Ag/AgCl (+0.207V)</option>
                    <option value="CSE">CSE (+0.316V)</option>
                    <option value="MMS">MMS (+0.640V)</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 font-mono block mb-1">Metal Ion Activity a(M):</label>
                  <select aria-label="Metal Ion Activity a(M)"
                    value={effectiveIonActivity}
                    onChange={(e) => setIonActivity(parseFloat(e.target.value))}
                    className="w-full bg-[#060b13] border border-[#1a263c] rounded px-2 py-1.5 text-xs text-slate-200 font-mono"
                  >
                    {ION_ACTIVITY_OPTIONS.filter((o) => activityInRange(selectedElement, Math.log10(o.value))).map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                  <p className="text-[10px] text-slate-500 font-mono mt-1">
                    Mononuclear hydrolysis species (MOH⁺, M(OH)₂(aq)) are not in the species table for any element, so
                    10⁻⁶ M is the lowest activity offered; the engine refuses lower values. At 10⁻⁶ M they change at most
                    about 0.6 % of the cells for Fe, Ni, Cu, Mg and Al; Zn is constant-dependent (with the wateq4f / Baes &amp;
                    Mesmer Zn(OH)₂(aq) constant the whole ZnO domain would vanish, with IUPAC 2013 it stays). Cr is limited to
                    10⁻² M and Mo to 10⁻⁴ M (polynuclear Cr₂O₇²⁻ and heptamolybdates are not in the table).
                    {activityOutsideRange
                      ? ` The chosen activity is outside the ${selectedElement} range (10^${activityLo} to 10^${activityHi}); 10⁻⁶ M is used.`
                      : ""}
                  </p>
                </div>
              </div>
            </div>

            {/* Probed State Summary Card with Quick Add to Experimental Data */}
            <div className="p-4 rounded-2xl bg-[#090e18] border border-[#162032] space-y-3 font-mono text-xs">
              <div className="flex items-center justify-between border-b border-[#162032] pb-2">
                <span className="font-bold text-white flex items-center gap-1.5">
                  <Zap className="w-3.5 h-3.5 text-purple-400" />
                  Live Probe Coordinates
                </span>
                <span
                  className="px-2 py-0.5 rounded text-[10px] font-bold"
                  style={{
                    backgroundColor: `${probedState ? CATEGORY_STYLE[probedState.category].color : "#94a3b8"}20`,
                    color: probedState ? CATEGORY_STYLE[probedState.category].color : "#94a3b8",
                    borderColor: `${probedState ? CATEGORY_STYLE[probedState.category].color : "#94a3b8"}50`,
                    borderWidth: 1,
                  }}
                >
                  {probedState ? probedState.category : "No verified data"}
                </span>
              </div>

              <div className="space-y-1.5 text-[11px]">
                <div className="flex justify-between">
                  <span className="text-slate-400">Solution pH:</span>
                  <span className="text-emerald-300 font-bold">{probePH.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Potential E ({refElectrode}):</span>
                  <span className="text-sky-300 font-bold">
                    {(probePotential_SHE - refOffset > 0 ? "+" : "") +
                      (probePotential_SHE - refOffset).toFixed(3)}{" "}
                    V
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Potential E (vs SHE):</span>
                  <span className="text-slate-300 font-bold">
                    {(probePotential_SHE > 0 ? "+" : "") + probePotential_SHE.toFixed(3)} V
                  </span>
                </div>
                <div className="flex justify-between border-t border-[#162032] pt-1 mt-1">
                  <span className="text-slate-400">Predominant Form:</span>
                  <span className="text-white font-bold">{probedState ? probedState.formula : "no verified data"}</span>
                </div>
                {probedState?.category === PASSIVATION && (
                  <p className="text-[10px] text-emerald-300/80 leading-snug">Passivation here means a {PASSIVATION_NOTE}.</p>
                )}
                {probeWithheld.length > 0 && (
                  <p role="status" className="text-[10px] text-amber-300 leading-snug">
                    {`Not valid here: ${WITHHELD_REGION_NOTE} (${[...new Set(probeWithheld.map((h) => h.formula))].join(", ")}).`}
                  </p>
                )}
                <div className="flex justify-between">
                  <span className="text-slate-400">Water Stability:</span>
                  {probedState ? (
                    <span
                      className={
                        probedState.isInsideWaterStability ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"
                      }
                    >
                      {probedState.isInsideWaterStability
                        ? "Thermodynamically Stable in H₂O"
                        : "Electrolysis / Gas Evolution (outside water stability, metastable)"}
                    </span>
                  ) : (
                    <span className="text-slate-500">n/a</span>
                  )}
                </div>
              </div>

              <button
                type="button"
                onClick={handleAddProbedCoordinateAsPoint}
                className="w-full mt-2 py-1.5 rounded-lg bg-sky-500/10 border border-sky-500/30 text-sky-300 hover:bg-sky-500/20 text-xs font-bold transition flex items-center justify-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                Capture probe as test point
              </button>
            </div>
          </div>

          {/* Right Column: 2D Interactive Canvas Pourbaix Diagram */}
          <div className="lg:col-span-8 space-y-4">
            <div className="bg-[#090e18] rounded-2xl border border-[#162032] p-5 flex flex-col justify-between space-y-4">
              {/* Diagram Top Bar */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#162032] pb-3 font-mono">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    {selectedElement}–H₂O ({currentAlloy.name}) • E-pH Pourbaix Diagram
                    {unavailableReason === null && experimentalPoints.length > 0 && showExperimentalOverlay && (
                      <span className="px-2 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/40">
                        {experimentalPoints.length} Test Points Overlaid
                      </span>
                    )}
                  </h3>
                  <span className="text-[11px] text-slate-400">
                    T = {temperature_C}°C (25 °C data only) | a(M) = 10^{log10Activity} | Nernst Slope ={" "}
                    {(nernstSlope * 1000).toFixed(1)} mV/pH
                    {isPythonSolving ? " | engine solving…" : ""}
                  </span>
                  <p className="text-[10px] text-slate-500 mt-1">
                    Passivation = {PASSIVATION_NOTE}. The map gives no corrosion rate and no film protectiveness.
                  </p>
                </div>

                {/* Legend Chips */}
                <div className="flex flex-wrap items-center gap-1.5 text-[10px]">
                  {(Object.keys(CATEGORY_STYLE) as StabilityCategory[]).map((cat) => (
                    <span
                      key={cat}
                      className="px-2 py-0.5 rounded font-semibold"
                      style={{
                        backgroundColor: `${CATEGORY_STYLE[cat].color}1a`,
                        border: `1px solid ${CATEGORY_STYLE[cat].color}4d`,
                        color: CATEGORY_STYLE[cat].color,
                      }}
                    >
                      ■ {cat === PASSIVATION ? "Passivation (thermodynamic)" : cat}
                    </span>
                  ))}
                </div>
              </div>

              <PourbaixSolveError message={pythonSolveError} />

              {/* Overlay Toggle Toolbar */}
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-mono bg-[#060b13] p-2.5 rounded-xl border border-[#162032]">
                <div className="flex flex-wrap items-center gap-3">
                  <label className="flex items-center gap-1.5 text-slate-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={showExperimentalOverlay}
                      onChange={(e) => setShowExperimentalOverlay(e.target.checked)}
                      className="rounded bg-[#0c1424] border-slate-700 text-sky-500 focus:ring-0"
                    />
                    <span>Show Test Data Overlay</span>
                  </label>

                  {showExperimentalOverlay && (
                    <>
                      <label className="flex items-center gap-1.5 text-slate-400 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={showTrajectoryPath}
                          onChange={(e) => setShowTrajectoryPath(e.target.checked)}
                          className="rounded bg-[#0c1424] border-slate-700 text-sky-500 focus:ring-0"
                        />
                        <span>Trajectory Arrows</span>
                      </label>
                      <label className="flex items-center gap-1.5 text-slate-400 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={showPointLabels}
                          onChange={(e) => setShowPointLabels(e.target.checked)}
                          className="rounded bg-[#0c1424] border-slate-700 text-sky-500 focus:ring-0"
                        />
                        <span>Stage Labels</span>
                      </label>
                    </>
                  )}
                </div>

                <button
                  type="button"
                  onClick={() => setActiveTab("experimental-overlay")}
                  className="text-sky-400 hover:text-sky-300 font-bold flex items-center gap-1"
                >
                  <Target className="w-3.5 h-3.5" />
                  Open test-point table →
                </button>
              </div>

              {/* Canvas Container, or the engine's reason when the element has no verified data */}
              {unavailableReason === null ? (
                <div className="relative w-full aspect-[16/10] bg-[#050b14] rounded-xl overflow-hidden border border-[#162032] cursor-crosshair">
                  <canvas
                    ref={canvasRef}
                    role="img"
                    aria-label={`${selectedElement}–H₂O E–pH map at 25 °C, dissolved activity 10^${log10Activity}; probe at pH ${probePH.toFixed(2)}, ${(probePotential_SHE - refOffset).toFixed(3)} V ${refElectrode}${probedState ? `: ${probedState.formula}, ${probedState.category}` : ""}${probeWithheld.length > 0 ? "; withheld-data region, map not valid here" : ""}`}
                    width={960}
                    height={600}
                    className="w-full h-full object-contain"
                    onMouseMove={handleCanvasInteraction}
                    onClick={handleCanvasInteraction}
                  />
                </div>
              ) : (
                <div role="status" className="w-full rounded-xl border border-amber-500/40 bg-amber-500/10 p-5 font-mono text-xs space-y-2">
                  <p className="font-bold text-amber-300">No verified {selectedElement}–H₂O data: no map is drawn.</p>
                  <p className="text-slate-300 leading-relaxed">{unavailableReason}</p>
                  <p className="text-[10px] text-slate-500">Engine code POURBAIX_DATA_UNAVAILABLE. Pick another element of this composition (element selector).</p>
                </div>
              )}

              {unavailableReason === null && selectedPointState?.state && (
                <p className="text-[11px] font-mono text-slate-300">
                  <span className="text-slate-500">Selected test point:</span> {selectedPointState.pt.stageName || selectedPointState.pt.name}
                  {` — ${selectedPointState.state.category}${selectedPointState.state.isInsideWaterStability ? "" : " — outside water stability (metastable)"}`}
                  {` (${selectedPointState.state.formula})`}
                  {` — ${CATEGORY_DISPLAY[selectedPointState.state.category]}`}
                </p>
              )}
              {unavailableReason === null && candidateSets.length > 0 && (
                <div role="note" aria-label="Data validity" className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 font-mono text-[10px] text-slate-300 space-y-1">
                  <p className="font-bold text-amber-300">
                    Data validity ({selectedElement}, dissolved activity 10^{activityLo} to 10^{activityHi} M): hatched = {WITHHELD_REGION_NOTE}.
                  </p>
                  <p>
                    Inside the water window the map is free of withheld-data regions for{" "}
                    {freeWindows.length > 0
                      ? freeWindows.map(([a, b]) => `pH ${a.toFixed(2)} to ${b.toFixed(2)}`).join(", ")
                      : "no pH"}{" "}
                    at a(M) = 10^{log10Activity}.
                  </p>
                  <p>Withheld candidate sets: {candidateSets.map((c) => c.label).join("; ")}.</p>
                  {unsourcedSpecies.length > 0 && (
                    <p>Not represented (no sourced value): {unsourcedSpecies.map((u) => u.formula).join(", ")}.</p>
                  )}
                </div>
              )}
              {unavailableReason === null && experimentalPoints.length > 0 && showExperimentalOverlay && (
                <p className="text-[10px] font-mono text-slate-500">
                  {PRESET_POINTS_NOTE}
                  {reclassifiedPresetPoints
                    ? ` The points of the preset "${initialPreset.name}" belong to ${initialPreset.element}; they are only reclassified here in the ${selectedElement}–H₂O map.`
                    : ""}
                </p>
              )}

              {/* Canvas Footer Controls */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-xs font-mono text-slate-400 pt-1">
                <div className="flex items-center gap-3">
                  <span>
                    💡 <em>Click anywhere on the phase diagram or on experimental markers to probe coordinates.</em>
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setViewBounds(FULL_VIEW);
                      setProbePH(7.0);
                      setProbePotential_SHE(0.2);
                    }}
                    className="px-3 py-1 rounded bg-[#0c1424] border border-[#1e2d46] hover:text-white text-slate-300 transition flex items-center gap-1.5"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    Reset View
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      const canvas = canvasRef.current;
                      if (!canvas) return;
                      const link = document.createElement("a");
                      link.download = `pourbaix_${currentAlloy.id}_${selectedElement}_overlay_${temperature_C}C.png`;
                      link.href = canvas.toDataURL("image/png");
                      link.click();
                    }}
                    className="px-3 py-1 rounded bg-sky-500/20 border border-sky-500/40 text-sky-300 hover:bg-sky-500/30 transition flex items-center gap-1.5"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Export Annotated PNG
                  </button>
                </div>
              </div>
            </div>

            {/* Constituent elements, each evaluated alone */}
            <div className="bg-[#090e18] rounded-2xl border border-[#162032] p-4 space-y-3 font-mono">
              <span className="text-xs font-bold text-white flex items-center gap-2">
                <Layers className="w-4 h-4 text-purple-400" />
                Constituent elements, each evaluated alone (no alloy equilibrium) at (pH {probePH.toFixed(1)}, E{" "}
                {probePotential_SHE.toFixed(2)}V vs SHE):
              </span>

              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
                {Object.keys(activeComposition).map((elem) => {
                  const state = elementStates[elem];
                  const wt = activeComposition[elem];
                  const color = state ? CATEGORY_STYLE[state.category].color : "#94a3b8";
                  return (
                    <div key={elem} className="p-2.5 rounded-xl bg-[#060b13] border border-[#162032] space-y-1">
                      <div className="flex justify-between items-center">
                        <span className="text-xs font-bold text-white">{elem}</span>
                        <span className="text-[10px] text-slate-500">{wt}% wt</span>
                      </div>
                      <div className="text-[11px] font-semibold text-slate-300 truncate">
                        {state
                          ? state.formula
                          : pourbaixUnavailableReason(elem) === null
                            ? `activity outside ${elem} range`
                            : "no verified data"}
                      </div>
                      <div
                        className="text-[9px] font-bold px-1.5 py-0.5 rounded text-center truncate"
                        style={{ backgroundColor: `${color}15`, color }}
                      >
                        {state ? state.category : "unavailable"}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          VIEW 2: TEST POINTS classified in the current map (illustrative presets and points you added)
         ========================================================================= */}
      {activeTab === "experimental-overlay" && (
        <div className="bg-[#090e18] rounded-2xl border border-[#162032] p-6 space-y-4 font-mono">
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <Target className="w-5 h-5 text-amber-400" />
            Test points in the {selectedElement}–H₂O map (25 °C, a(M) = 10^{log10Activity})
          </h3>
          <p className="text-xs text-slate-400">{PRESET_POINTS_NOTE} Classification is the thermodynamic domain of the point; it says nothing about rates.</p>
          {unavailableReason !== null ? (
            <p role="status" className="text-xs text-amber-300">No verified {selectedElement}–H₂O data: {unavailableReason}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="text-slate-500">
                  <tr><th className="py-1 pr-3">#</th><th className="pr-3">Point</th><th className="pr-3">pH</th><th className="pr-3">E ({refElectrode})</th><th className="pr-3">E (vs SHE)</th><th className="pr-3">Species</th><th className="pr-3">Category</th><th>Data validity</th></tr>
                </thead>
                <tbody className="text-slate-300">
                  {pointStates.map(({ pt, she, state, withheld }, idx) => (
                    <tr key={pt.id} className="border-t border-[#162032]">
                      <td className="py-1 pr-3">{idx + 1}</td>
                      <td className="pr-3">{pt.stageName || pt.name}</td>
                      <td className="pr-3">{pt.pH.toFixed(2)}</td>
                      <td className="pr-3">{(she - refOffset).toFixed(3)} V</td>
                      <td className="pr-3">{she.toFixed(3)} V</td>
                      <td className="pr-3">{state ? state.formula : "n/a"}</td>
                      <td className="pr-3">{state ? `${state.category}${state.isInsideWaterStability ? "" : " — outside water stability (metastable)"}` : "n/a"}</td>
                      <td>{state ? (withheld ? "withheld-data region (map not valid)" : "valid") : "n/a"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}


      {/* =========================================================================
          VIEW 3: EXACT EQUILIBRIUM BOUNDARIES (from the Python engine)
         ========================================================================= */}
      {activeTab === "reactions" && (
        <div className="bg-[#090e18] rounded-2xl border border-[#162032] p-6 space-y-6 font-mono">
          <div className="flex items-center justify-between border-b border-[#162032] pb-3">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Binary className="w-5 h-5 text-sky-400" />
                {selectedElement}–H₂O equilibrium boundaries (T = 25 °C, a(M) = 10^{log10Activity})
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Each boundary is the exact line g(A) = g(B) of the species table, computed by the Python engine; nothing is entered by hand.
              </p>
            </div>
            <span className="text-xs text-sky-300 font-bold px-3 py-1 rounded-lg bg-sky-500/10 border border-sky-500/30">
              Nernst slope: {(nernstSlope * 1000).toFixed(1)} mV/pH
            </span>
          </div>

          <PourbaixSolveError message={pythonSolveError} />

          {unavailableReason !== null ? (
            <p role="status" className="text-xs text-amber-300">No verified {selectedElement}–H₂O data: {unavailableReason}</p>
          ) : !pythonFresh ? (
            <p role="status" className="text-xs text-slate-400">
              {pythonSolveError ? "The Python engine did not return boundaries for this input." : "Waiting for the Python engine…"}
            </p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {pythonPourbaixData!.analyticalBoundaries.map((b) => {
                const [p0, p1] = b.points;
                const line = b.line;
                const lineText = !line
                  ? ""
                  : line.type === "vertical"
                    ? `pH = ${line.pH.toFixed(3)}`
                    : Math.abs(line.slope_V_per_pH) < 5e-5
                      ? `E = ${line.E_V_SHE_at_pH0.toFixed(4)} V (SHE), independent of pH`
                      : `E = ${line.E_V_SHE_at_pH0.toFixed(4)} ${line.slope_V_per_pH < 0 ? "−" : "+"} ${Math.abs(line.slope_V_per_pH).toFixed(4)}·pH V (SHE)`;
                return (
                  <div key={b.id} className="p-3 rounded-lg bg-[#0c1424] border border-[#1a263c] space-y-1.5 text-xs">
                    <div className="text-slate-200 font-bold text-[13px]">{b.name}</div>
                    <div className="text-[11px] text-slate-400">{b.equation}</div>
                    <div className="flex justify-between text-[11px] text-slate-400">
                      <span>Line:</span>
                      <span className="text-amber-300 font-bold">{lineText}</span>
                    </div>
                    {p0 && p1 && (
                      <div className="text-[10px] text-slate-500">
                        Segment: (pH {p0.pH.toFixed(2)}, {p0.E_V_SHE.toFixed(3)} V) to (pH {p1.pH.toFixed(2)}, {p1.E_V_SHE.toFixed(3)} V)
                      </div>
                    )}
                    <div className="text-[10px] text-slate-500">{b.boundaryType}</div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* =========================================================================
          VIEW 4: ELEMENT SELECTOR (no alloy equilibrium)
         ========================================================================= */}
      {activeTab === "alloy-formulator" && (
        <div className="bg-[#090e18] rounded-2xl border border-[#162032] p-6 space-y-6 font-mono">
          <div className="border-b border-[#162032] pb-3">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Sliders className="w-5 h-5 text-purple-400" />
              Element selector (no alloy equilibrium)
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              The engine solves one element in water at a time. It computes no alloy equilibrium, alloy passivity or
              composite verdict: choose which constituent element of {currentAlloy.name} to map.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(activeComposition).map(([elem, wt]) => {
              const reason = pourbaixUnavailableReason(elem);
              const isSelected = elem === selectedElement;
              return (
                <div
                  key={elem}
                  className={`p-4 rounded-xl bg-[#060b13] border space-y-2 ${isSelected ? "border-sky-500/60" : "border-[#162032]"}`}
                >
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-bold text-white">{elem}</span>
                    <span className="text-xs font-bold text-purple-300">{wt}% wt</span>
                  </div>
                  <div className="text-[11px] text-slate-400 leading-relaxed">
                    {reason === null ? (
                      <span className="text-emerald-300">
                        Verified {elem}–H₂O data available.
                        {(() => {
                          const e = POURBAIX_DATA.elements[elem];
                          return e && "candidateSets" in e && e.candidateSets.length > 0
                            ? " Contradictory or excluded species are withheld; their regions are hatched on the map."
                            : "";
                        })()}
                      </span>
                    ) : (
                      <>
                        <span className="text-amber-300">No verified {elem}–H₂O data.</span> {reason}
                      </>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => selectElement(elem)}
                    className="px-3 py-1.5 rounded-lg bg-purple-500/20 border border-purple-500/40 text-purple-300 hover:bg-purple-500/30 text-xs font-bold transition flex items-center gap-1.5"
                  >
                    <Compass className="w-3.5 h-3.5" />
                    {reason === null ? `Show ${elem}–H₂O map` : `Show ${elem} data status`}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
