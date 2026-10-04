import React, { useState, useMemo, useRef, useEffect, useCallback } from "react";
import {
  Compass,
  Thermometer,
  Droplets,
  Layers,
  Activity,
  Sliders,
  RefreshCw,
  Download,
  Info,
  ShieldCheck,
  ShieldAlert,
  Zap,
  Atom,
  Flame,
  CheckCircle2,
  AlertTriangle,
  ZoomIn,
  ZoomOut,
  Maximize2,
  HelpCircle,
  Eye,
  Box,
  Binary,
  Target,
  FileSpreadsheet,
  Plus,
} from "lucide-react";
import {
  ALLOY_PRESETS,
  ELEMENT_THERMODYNAMICS,
  calculateWaterStabilityLines,
  evaluateMulticomponentAlloyAtPoint,
  evaluateElementThermodynamicsAtPoint,
  GAS_CONSTANT_R,
  FARADAY_CONSTANT_F,
} from "../utils/pourbaixThermodynamics";
import {
  AlloyPreset,
  StabilityCategory,
  WaterStabilityLines,
  ExperimentalEpHEntry,
  PythonPourbaixResult,
  ReferenceElectrode,
} from "../types/pourbaix";
import {
  EXPERIMENTAL_POURBAIX_PRESETS,
  REF_OFFSETS_VS_SHE,
} from "../utils/experimentalPourbaixOverlay";
import { pythonComputationService } from "../services/pythonComputationService";
import { useDebouncedLatestTask } from "../hooks/useDebouncedLatestTask";


export function DynamicPourbaixStudio() {
  // Selected Alloy Preset & Custom Elements
  const [selectedAlloyId, setSelectedAlloyId] = useState<string>("carbon-steel");
  const [isCustomMode, setIsCustomMode] = useState<boolean>(false);
  const [customComposition, setCustomComposition] = useState<{ [elem: string]: number }>({
    Fe: 98.5,
    Cr: 0.5,
    Mn: 0.8,
    C: 0.2,
  });

  // Environmental Parameters
  const [temperature_C, setTemperature_C] = useState<number>(25); // 0 to 300 °C
  const [chlorideActivity, setChlorideActivity] = useState<number>(0.54); // 0.54 M ~ 3.5% NaCl seawater
  const [ionActivity, setIonActivity] = useState<number>(1e-6); // 1e-6 M standard
  const [refElectrode, setRefElectrode] = useState<ReferenceElectrode>("SHE");

  // Multi-element overlay display & Tab selection
  const [activeTab, setActiveTab] = useState<
    "diagram" | "experimental-overlay" | "reactions" | "alloy-formulator" | "temperature-slice"
  >("diagram");

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
  const [showPittingBoundary, setShowPittingBoundary] = useState<boolean>(true);

  // Python Backend Computation State
  const [pythonPourbaixData, setPythonPourbaixData] = useState<PythonPourbaixResult | null>(null);
  const [isPythonSolving, setIsPythonSolving] = useState<boolean>(false);
  const [pythonSolveError, setPythonSolveError] = useState<string | null>(null);

  // Interactive Crosshair Probe
  const [probePH, setProbePH] = useState<number>(7.0);
  const [probePotential_SHE, setProbePotential_SHE] = useState<number>(0.2);

  // Zoom and Pan View Bounds
  const [viewBounds, setViewBounds] = useState<{ minPH: number; maxPH: number; minE: number; maxE: number }>({
    minPH: -2,
    maxPH: 16,
    minE: -2.2,
    maxE: 2.2,
  });

  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Selected Preset
  const currentAlloy = useMemo<AlloyPreset>(() => {
    if (isCustomMode) {
      return {
        id: "custom-alloy",
        name: "Custom Formulated Alloy",
        category: "High-Entropy Alloy (HEA)",
        description: "User-synthesized multicomponent alloy formulation with customized thermodynamic passivity.",
        composition: customComposition,
        dominantPassiveOxides: ["Cr₂O₃", "TiO₂", "NiO", "Al₂O₃"],
        pittingResistanceIndex: (customComposition.Cr || 0) + 3.3 * (customComposition.Mo || 0),
        recommendedApplication: "Experimental laboratory alloy formulation.",
      };
    }
    return ALLOY_PRESETS.find((a) => a.id === selectedAlloyId) || ALLOY_PRESETS[0];
  }, [selectedAlloyId, isCustomMode, customComposition]);

  const activeComposition = useMemo(() => {
    return isCustomMode ? customComposition : currentAlloy.composition;
  }, [isCustomMode, customComposition, currentAlloy]);

  // Primary Base Element for Python Solver
  const primaryElement = useMemo(() => {
    let maxElem = "Fe";
    let maxVal = -1;
    for (const [elem, val] of Object.entries(activeComposition)) {
      const numVal = typeof val === "number" ? val : parseFloat(String(val)) || 0;
      if (numVal > maxVal) {
        maxVal = numVal;
        maxElem = elem;
      }
    }
    return maxElem;
  }, [activeComposition]);

  // Water stability lines
  const waterLines = useMemo<WaterStabilityLines>(() => {
    return calculateWaterStabilityLines(temperature_C);
  }, [temperature_C]);

  // Nernst slope at current temperature
  const nernstSlope = useMemo(() => {
    const T_K = temperature_C + 273.15;
    return (2.30258509 * GAS_CONSTANT_R * T_K) / FARADAY_CONSTANT_F;
  }, [temperature_C]);

  // Reference electrode offset
  const refOffset = REF_OFFSETS_VS_SHE[refElectrode] || 0.0;

  // Probed Thermodynamic State
  const probedState = useMemo(() => {
    return evaluateMulticomponentAlloyAtPoint(
      {
        temperature_C,
        chlorideActivity,
        ionActivity,
        activeElements: activeComposition,
        selectedAlloy: currentAlloy,
      },
      probePH,
      probePotential_SHE
    );
  }, [temperature_C, chlorideActivity, ionActivity, activeComposition, currentAlloy, probePH, probePotential_SHE]);

  // -------------------------------------------------------------
  // ASYNC PYTHON POURBAIX EQUILIBRIUM SOLVER DISPATCH
  // -------------------------------------------------------------
  // Debounced, visibility-gated and abortable; an unchanged input is not re-solved when the module is shown again.
  const pourbaixInputSignature = JSON.stringify([primaryElement, temperature_C, ionActivity, chlorideActivity, experimentalPoints.length]);
  useDebouncedLatestTask(pourbaixInputSignature, async (_signature, signal): Promise<boolean> => {
    const chloride_ppm = Math.round(chlorideActivity * 35453); // Convert Molar to ppm Cl-

    async function dispatchPythonSolver(): Promise<boolean> {
      try {
        setIsPythonSolving(true);
        setPythonSolveError(null);

        const result = await pythonComputationService.solvePourbaixDiagram({
          element: primaryElement,
          temperature_C,
          ionActivity_log10: Math.log10(ionActivity),
          chloride_ppm,
          experimentalPoints: experimentalPoints.length > 0 ? experimentalPoints : undefined,
        }, signal);

        if (!signal.aborted && result.success) {
          setPythonPourbaixData(result);

          // Update experimental points with enriched mechanism identification from Python
          if (result.experimentalOverlay?.points && result.experimentalOverlay.points.length > 0) {
            setExperimentalPoints((prev) => {
              const resultMap = new Map(result.experimentalOverlay!.points.map((p) => [p.id, p]));
              return prev.map((p) => {
                const analyzed = resultMap.get(p.id);
                if (analyzed) {
                  return { ...p, ...analyzed };
                }
                return p;
              });
            });
          }
          return true;
        }
        return false;
      } catch (err: any) {
        if (!signal.aborted) {
          setPythonSolveError(err.message || "Failed to reach Python Pourbaix solver.");
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

    const width = canvas.width;
    const height = canvas.height;

    // Coordinate transforms
    const { minPH, maxPH, minE, maxE } = viewBounds;
    const phToX = (ph: number) => ((ph - minPH) / (maxPH - minPH)) * width;
    const eToY = (e_she: number) => {
      const e_disp = e_she - refOffset;
      return height - ((e_disp - minE) / (maxE - minE)) * height;
    };
    const xToPH = (x: number) => minPH + (x / width) * (maxPH - minPH);
    const yToE = (y: number) => {
      const e_disp = minE + ((height - y) / height) * (maxE - minE);
      return e_disp + refOffset;
    };

    // 1. Clear background
    ctx.fillStyle = "#050b14";
    ctx.fillRect(0, 0, width, height);

    // 2. Render 2D Phase Stability Color Field (Subsampled mesh for smooth 60fps)
    const stepX = 4;
    const stepY = 4;
    for (let x = 0; x < width; x += stepX) {
      const ph = xToPH(x + stepX / 2);
      for (let y = 0; y < height; y += stepY) {
        const e_she = yToE(y + stepY / 2);
        const state = evaluateMulticomponentAlloyAtPoint(
          {
            temperature_C,
            chlorideActivity,
            ionActivity,
            activeElements: activeComposition,
            selectedAlloy: currentAlloy,
          },
          ph,
          e_she
        );

        // Alpha shading
        let alpha = 0.22;
        if (state.category === "Passive Oxide / Hydroxide") alpha = 0.32;
        if (state.category === "Immunity") alpha = 0.25;
        if (state.category === "Chloro-Complex Dissolution") alpha = 0.28;
        if (state.category === "Transpassive / Oxyanion") alpha = 0.30;

        ctx.fillStyle = state.color;
        ctx.globalAlpha = alpha;
        ctx.fillRect(x, y, stepX, stepY);
      }
    }
    ctx.globalAlpha = 1.0;

    // 3. Grid Lines & Axis
    ctx.strokeStyle = "#162235";
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);

    for (let ph = Math.ceil(minPH); ph <= maxPH; ph += 2) {
      const x = phToX(ph);
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();

      // Label
      ctx.fillStyle = "#64748b";
      ctx.font = "10px monospace";
      ctx.fillText(`pH ${ph}`, x + 4, height - 8);
    }

    for (let e = Math.ceil(minE * 2) / 2; e <= maxE; e += 0.5) {
      const y = height - ((e - minE) / (maxE - minE)) * height;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();

      // Label
      ctx.fillStyle = "#64748b";
      ctx.font = "10px monospace";
      ctx.fillText(`${e > 0 ? "+" : ""}${e.toFixed(1)}V`, 8, y - 4);
    }
    ctx.setLineDash([]);

    // 4. Water Stability Lines (Dashed Red Line a: HER, Line b: OER)
    // Line a: HER
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 2.0;
    ctx.setLineDash([6, 4]);
    ctx.beginPath();
    for (let ph = minPH; ph <= maxPH; ph += 0.5) {
      const e_her_she = waterLines.herLine.e_at_ph0 + waterLines.herLine.slope * ph;
      const x = phToX(ph);
      const y = eToY(e_her_she);
      if (ph === minPH) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Line b: OER
    ctx.strokeStyle = "#f43f5e";
    ctx.lineWidth = 2.0;
    ctx.beginPath();
    for (let ph = minPH; ph <= maxPH; ph += 0.5) {
      const e_oer_she = waterLines.oerLine.e_at_ph0 + waterLines.oerLine.slope * ph;
      const x = phToX(ph);
      const y = eToY(e_oer_she);
      if (ph === minPH) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    // Water stability line annotations
    ctx.fillStyle = "#38bdf8";
    ctx.font = "bold 11px monospace";
    const x_a = phToX(2);
    const y_a = eToY(waterLines.herLine.e_at_ph0 + waterLines.herLine.slope * 2);
    ctx.fillText(`(a) H₂/H⁺: E = -${nernstSlope.toFixed(3)}·pH`, x_a + 6, y_a - 6);

    ctx.fillStyle = "#f43f5e";
    const x_b = phToX(2);
    const y_b = eToY(waterLines.oerLine.e_at_ph0 + waterLines.oerLine.slope * 2);
    ctx.fillText(
      `(b) O₂/H₂O: E = ${waterLines.oerLine.e_at_ph0.toFixed(2)} - ${nernstSlope.toFixed(3)}·pH`,
      x_b + 6,
      y_b - 6
    );

    // 5. Pitting Breakdown Potential Boundary Line (if chloride > 0)
    if (showPittingBoundary && chlorideActivity > 0.001) {
      const epit_nominal = 0.55 - 0.088 * Math.log10(chlorideActivity) - 0.001 * (temperature_C - 25);
      const y_pit = eToY(epit_nominal);

      ctx.strokeStyle = "rgba(225, 29, 72, 0.85)";
      ctx.lineWidth = 2.0;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(phToX(4.5), y_pit);
      ctx.lineTo(phToX(13.5), y_pit);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = "rgba(225, 29, 72, 0.95)";
      ctx.font = "bold 10px monospace";
      ctx.fillText(
        `⚡ Epit [Cl⁻ Pitting Breakdown]: ${(epit_nominal - refOffset).toFixed(2)}V (${Math.round(
          chlorideActivity * 35453
        )} ppm Cl⁻)`,
        phToX(5.0),
        y_pit - 6
      );
    }

    // 6. Phase Zone Text Labels in Diagram
    ctx.font = "bold 12px monospace";
    ctx.fillStyle = "rgba(16, 185, 129, 0.9)";
    ctx.fillText(`PASSIVITY [${currentAlloy.dominantPassiveOxides[0] || "Cr₂O₃"}]`, phToX(7), eToY(0.4));

    ctx.fillStyle = "rgba(56, 189, 248, 0.9)";
    ctx.fillText("IMMUNITY [M°(s)]", phToX(6), eToY(-1.2));

    ctx.fillStyle = "rgba(248, 113, 113, 0.9)";
    ctx.fillText("ACTIVE CORROSION", phToX(0.5), eToY(-0.2));

    // -------------------------------------------------------------
    // 7. EXPERIMENTAL TEST DATA OVERLAY & TRAJECTORY SPLINE
    // -------------------------------------------------------------
    if (showExperimentalOverlay && experimentalPoints.length > 0) {
      const coords = experimentalPoints.map((pt) => {
        const she =
          pt.potential_V_SHE ??
          pt.potential_V + (REF_OFFSETS_VS_SHE[pt.refElectrode] || 0);
        return {
          id: pt.id,
          name: pt.name,
          stageName: pt.stageName,
          riskLevel: pt.riskLevel,
          mechanismTitle: pt.mechanismTitle,
          x: phToX(pt.pH),
          y: eToY(she),
          pH: pt.pH,
          she,
          inputPot: pt.potential_V,
          ref: pt.refElectrode,
        };
      });

      // Draw Trajectory Connecting Path with Direction Arrows
      if (showTrajectoryPath && coords.length > 1) {
        ctx.strokeStyle = "rgba(255, 255, 255, 0.65)";
        ctx.lineWidth = 2.5;
        ctx.setLineDash([6, 3]);
        ctx.beginPath();
        ctx.moveTo(coords[0].x, coords[0].y);
        for (let i = 1; i < coords.length; i++) {
          ctx.lineTo(coords[i].x, coords[i].y);
        }
        ctx.stroke();
        ctx.setLineDash([]);

        // Arrowheads along trajectory
        for (let i = 0; i < coords.length - 1; i++) {
          const from = coords[i];
          const to = coords[i + 1];
          const midX = (from.x + to.x) / 2;
          const midY = (from.y + to.y) / 2;
          const angle = Math.atan2(to.y - from.y, to.x - from.x);

          ctx.save();
          ctx.translate(midX, midY);
          ctx.rotate(angle);
          ctx.fillStyle = "#38bdf8";
          ctx.beginPath();
          ctx.moveTo(6, 0);
          ctx.lineTo(-4, -4);
          ctx.lineTo(-4, 4);
          ctx.closePath();
          ctx.fill();
          ctx.restore();
        }
      }

      // Draw Individual Measured Point Scatter Bubbles
      coords.forEach((pt, idx) => {
        const isSelected = pt.id === selectedPointId;

        let markerColor = "#38bdf8";
        if (pt.riskLevel === "Stable Passivity") markerColor = "#10b981";
        else if (pt.riskLevel === "Pitting Hazard") markerColor = "#e11d48";
        else if (pt.riskLevel === "Severe Corrosion") markerColor = "#f87171";
        else if (pt.riskLevel === "Caution") markerColor = "#f59e0b";
        else if (pt.riskLevel === "High Risk") markerColor = "#c084fc";

        // Outer glow halo if selected
        if (isSelected) {
          ctx.beginPath();
          ctx.arc(pt.x, pt.y, 16, 0, Math.PI * 2);
          ctx.fillStyle = `${markerColor}30`;
          ctx.fill();

          ctx.beginPath();
          ctx.arc(pt.x, pt.y, 22, 0, Math.PI * 2);
          ctx.strokeStyle = markerColor;
          ctx.lineWidth = 1.5;
          ctx.setLineDash([3, 3]);
          ctx.stroke();
          ctx.setLineDash([]);
        }

        // Main Bubble
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, isSelected ? 10 : 8, 0, Math.PI * 2);
        ctx.fillStyle = markerColor;
        ctx.fill();
        ctx.lineWidth = isSelected ? 3 : 2;
        ctx.strokeStyle = "#ffffff";
        ctx.stroke();

        // Point Index Number inside circle
        ctx.fillStyle = "#0f172a";
        ctx.font = "bold 9px monospace";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(`${idx + 1}`, pt.x, pt.y);
        ctx.textAlign = "start";
        ctx.textBaseline = "alphabetic";

        // Point Labels
        if (showPointLabels) {
          ctx.fillStyle = "#ffffff";
          ctx.font = isSelected ? "bold 11px monospace" : "10px monospace";
          const labelText = pt.stageName || pt.name || `Pt #${idx + 1}`;
          const lx = pt.x + 12;
          const ly = pt.y - 8;

          // Text pill background
          const textWidth = ctx.measureText(labelText).width;
          ctx.fillStyle = "rgba(10, 16, 28, 0.85)";
          ctx.strokeStyle = markerColor;
          ctx.lineWidth = 1;
          ctx.fillRect(lx - 4, ly - 11, textWidth + 8, 15);
          ctx.strokeRect(lx - 4, ly - 11, textWidth + 8, 15);

          ctx.fillStyle = "#f8fafc";
          ctx.fillText(labelText, lx, ly);
        }
      });
    }

    // 8. Crosshair Probe Marker
    const probeX = phToX(probePH);
    const probeY = eToY(probePotential_SHE);

    // Crosshair lines
    ctx.strokeStyle = "rgba(255, 255, 255, 0.4)";
    ctx.lineWidth = 1;
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 2]);
    ctx.beginPath();
    ctx.moveTo(probeX, 0);
    ctx.lineTo(probeX, height);
    ctx.moveTo(0, probeY);
    ctx.lineTo(width, probeY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Glowing Probe Circle
    ctx.beginPath();
    ctx.arc(probeX, probeY, 7, 0, Math.PI * 2);
    ctx.fillStyle = probedState.color;
    ctx.fill();
    ctx.lineWidth = 2.5;
    ctx.strokeStyle = "#ffffff";
    ctx.stroke();

    // Probe readout box near point
    ctx.fillStyle = "#0c1524";
    ctx.strokeStyle = probedState.color;
    ctx.lineWidth = 1.5;
    const boxX = Math.min(width - 170, Math.max(10, probeX + 12));
    const boxY = Math.min(height - 60, Math.max(20, probeY - 45));
    ctx.fillRect(boxX, boxY, 160, 50);
    ctx.strokeRect(boxX, boxY, 160, 50);

    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 10px monospace";
    ctx.fillText(
      `pH: ${probePH.toFixed(2)} | E: ${(probePotential_SHE - refOffset).toFixed(3)}V`,
      boxX + 6,
      boxY + 16
    );
    ctx.fillStyle = probedState.color;
    ctx.fillText(`${probedState.category}`, boxX + 6, boxY + 30);
    ctx.fillStyle = "#94a3b8";
    ctx.font = "9px monospace";
    ctx.fillText(`T: ${temperature_C}°C | [Cl⁻]: ${chlorideActivity}M`, boxX + 6, boxY + 42);
  }, [
    viewBounds,
    refOffset,
    temperature_C,
    chlorideActivity,
    ionActivity,
    activeComposition,
    currentAlloy,
    waterLines,
    nernstSlope,
    probePH,
    probePotential_SHE,
    probedState,
    showExperimentalOverlay,
    experimentalPoints,
    selectedPointId,
    showTrajectoryPath,
    showPointLabels,
    showPittingBoundary,
  ]);

  // Redraw canvas on dependencies change
  useEffect(() => {
    renderPourbaixCanvas();
  }, [renderPourbaixCanvas]);

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

      for (const pt of experimentalPoints) {
        const she =
          pt.potential_V_SHE ??
          pt.potential_V + (REF_OFFSETS_VS_SHE[pt.refElectrode] || 0);
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

    setProbePH(parseFloat(Math.max(-2, Math.min(16, ph)).toFixed(2)));
    setProbePotential_SHE(parseFloat(Math.max(-2.5, Math.min(2.5, e_she)).toFixed(3)));
  };

  const handleAddProbedCoordinateAsPoint = () => {
    const newEntry: ExperimentalEpHEntry = {
      id: `pt_probed_${Date.now()}`,
      name: `Probed Sample (${probePH.toFixed(2)}, ${(probePotential_SHE - refOffset).toFixed(3)}V)`,
      pH: probePH,
      potential_V: probePotential_SHE - refOffset,
      refElectrode: refElectrode,
      stageName: "Probed Test Point",
      notes: `Captured at T=${temperature_C}°C, [Cl⁻]=${chlorideActivity}M. Dominant: ${probedState.dominantSpeciesFormula}`,
    };
    const updated = [...experimentalPoints, newEntry];
    setExperimentalPoints(updated);
    setSelectedPointId(newEntry.id);
  };

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
              Dynamic Pourbaix (E-pH-T-Salinity) Stability Studio
            </h1>
            <p className="text-slate-300 text-sm leading-relaxed">
              Calculates multicomponent Nernst equilibria and overlays theoretical Pourbaix stability boundaries
              onto measured experimental E-pH test data to identify active corrosion pathways, pitting thresholds,
              and cathodic protection criteria.
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
              <span className="text-slate-400">Experimental Points:</span>
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
              label: `Experimental E-pH Overlay & Mechanisms (${experimentalPoints.length})`,
              icon: Target,
            },
            { id: "reactions", label: "Equilibrium Reactions & ΔG°(T)", icon: Binary },
            { id: "alloy-formulator", label: "Multicomponent Alloy Formulator", icon: Sliders },
            { id: "temperature-slice", label: "Temperature & Salinity Envelopes", icon: Thermometer },
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
                <select
                  value={selectedAlloyId}
                  onChange={(e) => {
                    setIsCustomMode(false);
                    setSelectedAlloyId(e.target.value);
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

              <div className="text-xs text-slate-400 font-mono leading-relaxed bg-[#060b13] p-2.5 rounded-lg border border-[#162032]">
                <strong className="text-slate-300 block mb-1">{currentAlloy.name}</strong>
                {currentAlloy.description}
              </div>
            </div>

            {/* Hydrothermal & Salinity Controls */}
            <div className="bg-[#090e18] rounded-2xl border border-[#162032] p-4 space-y-4">
              <div className="flex items-center justify-between border-b border-[#162032] pb-2">
                <span className="text-xs font-bold text-white font-mono flex items-center gap-2">
                  <Thermometer className="w-4 h-4 text-amber-400" />
                  Hydrothermal &amp; Salinity State
                </span>
                <span className="text-[10px] font-mono text-amber-400">
                  T = {temperature_C}°C ({temperature_C + 273} K)
                </span>
              </div>

              {/* Temperature Slider */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-slate-400">Temperature (0°C to 300°C):</span>
                  <span className="text-amber-300 font-bold">{temperature_C} °C</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="300"
                  step="5"
                  value={temperature_C}
                  onChange={(e) => setTemperature_C(parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-[#162032] rounded-lg appearance-none cursor-pointer accent-amber-400"
                />
                <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                  <span>0°C (Ice/Cold)</span>
                  <span>25°C (NTP)</span>
                  <span>100°C (Boiling)</span>
                  <span>300°C (Autoclave)</span>
                </div>
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
                <input
                  type="range"
                  min="0.0001"
                  max="4.0"
                  step="0.01"
                  value={chlorideActivity}
                  onChange={(e) => setChlorideActivity(parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-[#162032] rounded-lg appearance-none cursor-pointer accent-teal-400"
                />
                <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                  <span>10⁻⁴ M (DI Water)</span>
                  <span>0.54 M (Seawater)</span>
                  <span>4.0 M (Brine)</span>
                </div>
              </div>

              {/* Reference Electrode Selector */}
              <div className="grid grid-cols-2 gap-2 pt-1">
                <div>
                  <label className="text-[10px] text-slate-400 font-mono block mb-1">Reference Scale:</label>
                  <select
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
                  <select
                    value={ionActivity}
                    onChange={(e) => setIonActivity(parseFloat(e.target.value))}
                    className="w-full bg-[#060b13] border border-[#1a263c] rounded px-2 py-1.5 text-xs text-slate-200 font-mono"
                  >
                    <option value={1e-8}>10⁻⁸ M (Traces)</option>
                    <option value={1e-6}>10⁻⁶ M (ASTM Standard)</option>
                    <option value={1e-3}>10⁻³ M (Millimolar)</option>
                    <option value={1.0}>1.0 M (Concentrated)</option>
                  </select>
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
                    backgroundColor: `${probedState.color}20`,
                    color: probedState.color,
                    borderColor: `${probedState.color}50`,
                    borderWidth: 1,
                  }}
                >
                  {probedState.category}
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
                  <span className="text-white font-bold">{probedState.dominantSpeciesFormula}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Water Stability:</span>
                  <span
                    className={
                      probedState.isInsideWaterStability ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"
                    }
                  >
                    {probedState.isInsideWaterStability
                      ? "Thermodynamically Stable in H₂O"
                      : "Electrolysis / Gas Evolution"}
                  </span>
                </div>
              </div>

              <button
                type="button"
                onClick={handleAddProbedCoordinateAsPoint}
                className="w-full mt-2 py-1.5 rounded-lg bg-sky-500/10 border border-sky-500/30 text-sky-300 hover:bg-sky-500/20 text-xs font-bold transition flex items-center justify-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                Capture as Experimental Test Point
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
                    {currentAlloy.name} • E-pH Pourbaix Diagram
                    {experimentalPoints.length > 0 && showExperimentalOverlay && (
                      <span className="px-2 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/40">
                        {experimentalPoints.length} Test Points Overlaid
                      </span>
                    )}
                  </h3>
                  <span className="text-[11px] text-slate-400">
                    T = {temperature_C}°C | [Cl⁻] = {chlorideActivity} M | Nernst Slope ={" "}
                    {(nernstSlope * 1000).toFixed(1)} mV/pH
                  </span>
                </div>

                {/* Legend Chips */}
                <div className="flex flex-wrap items-center gap-1.5 text-[10px]">
                  <span className="px-2 py-0.5 rounded bg-[#38bdf8]/10 border border-[#38bdf8]/30 text-[#38bdf8] font-semibold">
                    ■ Immunity
                  </span>
                  <span className="px-2 py-0.5 rounded bg-[#10b981]/10 border border-[#10b981]/30 text-[#10b981] font-semibold">
                    ■ Passivity
                  </span>
                  <span className="px-2 py-0.5 rounded bg-[#f87171]/10 border border-[#f87171]/30 text-[#f87171] font-semibold">
                    ■ Corrosion
                  </span>
                  <span className="px-2 py-0.5 rounded bg-[#fb923c]/10 border border-[#fb923c]/30 text-[#fb923c] font-semibold">
                    ■ Chloro-Complex
                  </span>
                  <span className="px-2 py-0.5 rounded bg-[#e11d48]/10 border border-[#e11d48]/30 text-[#e11d48] font-semibold">
                    ■ Pitting Breakdown
                  </span>
                </div>
              </div>

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
                      <label className="flex items-center gap-1.5 text-slate-400 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={showPittingBoundary}
                          onChange={(e) => setShowPittingBoundary(e.target.checked)}
                          className="rounded bg-[#0c1424] border-slate-700 text-sky-500 focus:ring-0"
                        />
                        <span>E_pit Boundary</span>
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
                  Open Mechanism Matrix →
                </button>
              </div>

              {/* Canvas Container */}
              <div className="relative w-full aspect-[16/10] bg-[#050b14] rounded-xl overflow-hidden border border-[#162032] cursor-crosshair">
                <canvas
                  ref={canvasRef}
                  width={960}
                  height={600}
                  className="w-full h-full object-contain"
                  onMouseMove={handleCanvasInteraction}
                  onClick={handleCanvasInteraction}
                />
              </div>

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
                      setViewBounds({ minPH: -2, maxPH: 16, minE: -2.2, maxE: 2.2 });
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
                      link.download = `pourbaix_${currentAlloy.id}_overlay_${temperature_C}C.png`;
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

            {/* Constituent Element Passivity Matrix */}
            <div className="bg-[#090e18] rounded-2xl border border-[#162032] p-4 space-y-3 font-mono">
              <span className="text-xs font-bold text-white flex items-center gap-2">
                <Layers className="w-4 h-4 text-purple-400" />
                Constituent Element Multi-Phase Status at (pH {probePH.toFixed(1)}, E{" "}
                {probePotential_SHE.toFixed(2)}V vs SHE):
              </span>

              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
                {Object.keys(activeComposition).map((elem) => {
                  const state = probedState.elementStates?.[elem];
                  const wt = activeComposition[elem];
                  return (
                    <div key={elem} className="p-2.5 rounded-xl bg-[#060b13] border border-[#162032] space-y-1">
                      <div className="flex justify-between items-center">
                        <span className="text-xs font-bold text-white">{elem}</span>
                        <span className="text-[10px] text-slate-500">{wt}% wt</span>
                      </div>
                      <div className="text-[11px] font-semibold text-slate-300 truncate">
                        {state?.species || "M°(s)"}
                      </div>
                      <div
                        className="text-[9px] font-bold px-1.5 py-0.5 rounded text-center truncate"
                        style={{
                          backgroundColor: `${state?.color || "#38bdf8"}15`,
                          color: state?.color || "#38bdf8",
                        }}
                      >
                        {state?.category || "Immunity"}
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
          VIEW 2: DEDICATED EXPERIMENTAL E-pH OVERLAY & CORROSION MECHANISMS
         ========================================================================= */}
      

      {/* =========================================================================
          VIEW 3: EQUILIBRIUM REACTIONS & THERMODYNAMIC ΔG°(T) BREAKDOWN
         ========================================================================= */}
      {activeTab === "reactions" && (
        <div className="bg-[#090e18] rounded-2xl border border-[#162032] p-6 space-y-6 font-mono">
          <div className="flex items-center justify-between border-b border-[#162032] pb-3">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Binary className="w-5 h-5 text-sky-400" />
                Half-Cell Redox &amp; Chemical Precipitation Reactions (T = {temperature_C}°C)
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Nernst equation potential equilibria and standard Gibbs free energy of reaction ΔG°_T
              </p>
            </div>
            <span className="text-xs text-sky-300 font-bold px-3 py-1 rounded-lg bg-sky-500/10 border border-sky-500/30">
              Nernst: E = E° - (2.303RT / nF) · m · pH
            </span>
          </div>

          <div className="space-y-4">
            {Object.keys(activeComposition).map((elem) => {
              const elemSys = ELEMENT_THERMODYNAMICS[elem];
              if (!elemSys) return null;
              return (
                <div key={elem} className="p-4 rounded-xl bg-[#060b13] border border-[#162032] space-y-3">
                  <div className="flex items-center justify-between border-b border-[#162032] pb-2">
                    <span className="text-sm font-bold text-sky-300 flex items-center gap-2">
                      <Atom className="w-4 h-4" />
                      {elemSys.name} ({elem}) System Reactions • E° = {elemSys.standardPotential_V} V vs SHE
                    </span>
                    <span className="text-xs text-slate-400">{elemSys.species.length} Active Species</span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {elemSys.reactions.map((rxn) => {
                      const slope_T = -(rxn.mProtons / Math.max(1, rxn.nElectrons)) * nernstSlope;
                      const deltaG_kJ = (-rxn.nElectrons * FARADAY_CONSTANT_F * rxn.calcE0_298_V) / 1000;
                      return (
                        <div
                          key={rxn.id}
                          className="p-3 rounded-lg bg-[#0c1424] border border-[#1a263c] space-y-1.5 text-xs"
                        >
                          <div className="text-slate-200 font-bold text-[13px]">{rxn.description}</div>
                          <div className="flex justify-between text-[11px] text-slate-400">
                            <span>Standard Potential (25°C):</span>
                            <span className="text-amber-300 font-bold">
                              {rxn.calcE0_298_V > 0 ? "+" : ""}
                              {rxn.calcE0_298_V} V vs SHE
                            </span>
                          </div>
                          <div className="flex justify-between text-[11px] text-slate-400">
                            <span>pH Equilibrium Slope (dE/dpH):</span>
                            <span className="text-emerald-300 font-bold">{(slope_T * 1000).toFixed(1)} mV/pH</span>
                          </div>
                          <div className="text-[10px] text-slate-500">
                            Electrons: {rxn.nElectrons} e⁻ | Protons: {rxn.mProtons} H⁺ | ΔG°_298 ={" "}
                            {deltaG_kJ.toFixed(1)} kJ/mol
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* =========================================================================
          VIEW 4: MULTICOMPONENT ALLOY FORMULATOR
         ========================================================================= */}
      {activeTab === "alloy-formulator" && (
        <div className="bg-[#090e18] rounded-2xl border border-[#162032] p-6 space-y-6 font-mono">
          <div className="flex items-center justify-between border-b border-[#162032] pb-3">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Sliders className="w-5 h-5 text-purple-400" />
                Custom Alloy Composition &amp; Cocktail Passivation Formulator
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Formulate arbitrary High-Entropy Alloys (HEAs), superalloys, or duplex alloys and analyze spontaneous
                passivity.
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                setIsCustomMode(true);
                setActiveTab("diagram");
              }}
              className="px-4 py-2 rounded-xl bg-purple-500/20 border border-purple-500/40 text-purple-300 hover:bg-purple-500/30 text-xs font-bold transition flex items-center gap-1.5"
            >
              <Compass className="w-4 h-4" />
              Apply &amp; Render Diagram
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {["Ni", "Cr", "Fe", "Ti", "Al", "Mo", "Cu"].map((elem) => {
              const currentVal = customComposition[elem] || 0;
              return (
                <div key={elem} className="p-4 rounded-xl bg-[#060b13] border border-[#162032] space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-bold text-white">{elem} (wt%)</span>
                    <span className="text-xs font-bold text-purple-300">{currentVal.toFixed(1)}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="0.5"
                    value={currentVal}
                    onChange={(e) => {
                      setIsCustomMode(true);
                      setCustomComposition((prev) => ({
                        ...prev,
                        [elem]: parseFloat(e.target.value),
                      }));
                    }}
                    className="w-full h-1.5 bg-[#162032] rounded-lg appearance-none cursor-pointer accent-purple-400"
                  />
                  <div className="text-[10px] text-slate-500">
                    Oxide Film:{" "}
                    {ELEMENT_THERMODYNAMICS[elem]?.species.find((s) => s.isPassiveFilm)?.formula || "Oxide"}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Composition Summary */}
          <div className="p-4 rounded-xl bg-[#0c1424] border border-[#1a263c] flex flex-wrap items-center justify-between gap-4 text-xs">
            <div>
              <span className="text-slate-400 block">Total Weight Fraction:</span>
              <span className="text-white font-bold text-sm">
                {(Object.values(customComposition) as number[])
                  .reduce((a: number, b: number) => a + b, 0)
                  .toFixed(1)}
                %
              </span>
            </div>
            <div>
              <span className="text-slate-400 block">Pitting Resistance (PREN):</span>
              <span className="text-emerald-300 font-bold text-sm">
                {((customComposition.Cr || 0) + 3.3 * (customComposition.Mo || 0)).toFixed(1)}
              </span>
            </div>
            <button
              type="button"
              onClick={() => {
                const total =
                  (Object.values(customComposition) as number[]).reduce((a: number, b: number) => a + b, 0) || 1;
                const normalized: { [elem: string]: number } = {};
                for (const k of Object.keys(customComposition)) {
                  normalized[k] = parseFloat((((customComposition[k] || 0) / total) * 100).toFixed(1));
                }
                setCustomComposition(normalized);
              }}
              className="px-3 py-1.5 rounded-lg bg-[#060b13] border border-[#1e2d46] text-slate-300 hover:text-white transition"
            >
              Normalize to 100 wt%
            </button>
          </div>
        </div>
      )}

      {/* =========================================================================
          VIEW 5: TEMPERATURE & SALINITY CROSS-SECTIONS
         ========================================================================= */}
      {activeTab === "temperature-slice" && (
        <div className="bg-[#090e18] rounded-2xl border border-[#162032] p-6 space-y-6 font-mono">
          <div className="border-b border-[#162032] pb-3">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Thermometer className="w-5 h-5 text-amber-400" />
              Hydrothermal &amp; Salinity Stability Envelopes (0°C to 300°C)
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Effect of extreme autoclave temperatures and chloride activity on pitting breakdown (E_pit) and water
              window.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-xl bg-[#060b13] border border-[#162032] space-y-2">
              <span className="text-xs text-slate-400 block">Water Dissociation Constant Kw(T):</span>
              <span className="text-xl font-bold text-sky-400">{waterLines.kw.toExponential(2)}</span>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                At 300°C, neutral pH shifts from 7.00 down to ~5.7 due to massive auto-ionization of high-temperature
                pressurized water.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-[#060b13] border border-[#162032] space-y-2">
              <span className="text-xs text-slate-400 block">Saturated Steam Pressure P_sat:</span>
              <span className="text-xl font-bold text-amber-400">{waterLines.vaporPressure_bar.toFixed(2)} bar</span>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                Autoclave pressure required to maintain liquid phase contact above 100°C.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-[#060b13] border border-[#162032] space-y-2">
              <span className="text-xs text-slate-400 block">Nernst Potential Sensitivity:</span>
              <span className="text-xl font-bold text-emerald-400">{(nernstSlope * 1000).toFixed(1)} mV/pH</span>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                Increases from 59.16 mV/pH at 25°C to 113.7 mV/pH at 300°C, expanding phase boundary slopes.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


