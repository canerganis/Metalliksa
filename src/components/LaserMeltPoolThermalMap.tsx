import React, { useState, useMemo, useRef, useEffect, useCallback } from "react";
import {
  Flame,
  Activity,
  Layers,
  Thermometer,
  Zap,
  Maximize2,
  Minimize2,
  Info,
  Sparkles,
  Gauge,
  Sliders,
  Play,
  Pause,
  RotateCcw,
  Compass,
  AlertTriangle,
  CheckCircle2,
  ShieldAlert,
  Download,
  Crosshair,
  Grid,
  TrendingDown,
  Cpu,
  RefreshCw,
  Box,
} from "lucide-react";
import { useVisibleInterval } from "../hooks/useVisibleInterval";
import { CandidateAlloySolution,InverseDesignTargets } from "../utils/inverseAlloyOptimizer";
import { pythonComputationService, PythonLPBFResult } from "../services/pythonComputationService";
import { useDebouncedLatestTask } from "../hooks/useDebouncedLatestTask";

interface Props {
  candidate: CandidateAlloySolution;
  targets: InverseDesignTargets;
  laserPower_W: number;
  scanSpeed_mms: number;
  beamDiameter_um: number;
  preheatTemp_C: number;
  layerThickness_um?: number;
  hatchSpacing_um?: number;
  onParametersChange?: (params: {
    laserPower_W: number;
    scanSpeed_mms: number;
    beamDiameter_um: number;
    preheatTemp_C: number;
    layerThickness_um: number;
    hatchSpacing_um: number;
  }) => void;
}

export type ThermalMapMode = "temperature" | "cooling-rate" | "solidification-front" | "thermal-gradient";
export type ViewAngle = "top-down" | "longitudinal-side" | "transverse-front";

export const LaserMeltPoolThermalMap: React.FC<Props> = ({
  candidate,
  targets,
  laserPower_W: initialLaserPower,
  scanSpeed_mms: initialScanSpeed,
  beamDiameter_um: initialBeamDiameter,
  preheatTemp_C: initialPreheatTemp,
  layerThickness_um: initialLayerThickness = 40,
  hatchSpacing_um: initialHatchSpacing = 100,
  onParametersChange,
}) => {
  // Process Parameters State
  const [laserPower_W, setLaserPower_W] = useState<number>(initialLaserPower);
  const [scanSpeed_mms, setScanSpeed_mms] = useState<number>(initialScanSpeed);
  const [beamDiameter_um, setBeamDiameter_um] = useState<number>(initialBeamDiameter);
  const [preheatTemp_C, setPreheatTemp_C] = useState<number>(initialPreheatTemp);
  const [layerThickness_um, setLayerThickness_um] = useState<number>(initialLayerThickness);
  const [hatchSpacing_um, setHatchSpacing_um] = useState<number>(initialHatchSpacing);
  const [laserWavelength, setLaserWavelength] = useState<"IR_1064nm" | "Green_515nm" | "Blue_450nm">("IR_1064nm");
  const [selectedMaterial, setSelectedMaterial] = useState<string>(() => {
    const mat = targets.baseMatrix;
    if (mat === "Nickel") return "Inconel 718";
    if (mat === "Titanium") return "Ti-6Al-4V";
    if (mat === "Steel") return "316L Stainless Steel";
    if (mat === "Aluminum") return "AlSi10Mg";
    return "Inconel 718";
  });

  // Visualization View & Rendering State
  const [mapMode, setMapMode] = useState<ThermalMapMode>("temperature");
  const [viewAngle, setViewAngle] = useState<ViewAngle>("top-down");
  const [isSimulating, setIsSimulating] = useState<boolean>(true);
  const [timeStep, setTimeStep] = useState<number>(0);
  const [probePos, setProbePos] = useState<{ x_px: number; y_px: number; x_um: number; y_um: number; z_um: number } | null>(null);
  const [showOverlays, setShowOverlays] = useState<boolean>(true);
  const [showMeshVectors, setShowMeshVectors] = useState<boolean>(true);

  // Python Solver Results & Status State
  const [pyResult, setPyResult] = useState<PythonLPBFResult | null>(null);
  const [isSolving, setIsSolving] = useState<boolean>(false);
  const [solverError, setSolverError] = useState<string | null>(null);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Synchronize state if props update
  useEffect(() => {
    setLaserPower_W(initialLaserPower);
  }, [initialLaserPower]);
  useEffect(() => {
    setScanSpeed_mms(initialScanSpeed);
  }, [initialScanSpeed]);
  useEffect(() => {
    setBeamDiameter_um(initialBeamDiameter);
  }, [initialBeamDiameter]);
  useEffect(() => {
    setPreheatTemp_C(initialPreheatTemp);
  }, [initialPreheatTemp]);
  useEffect(() => {
    setLayerThickness_um(initialLayerThickness);
  }, [initialLayerThickness]);
  useEffect(() => {
    setHatchSpacing_um(initialHatchSpacing);
  }, [initialHatchSpacing]);
  useEffect(() => {
    setLayerThickness_um(initialLayerThickness);
  }, [initialLayerThickness]);
  useEffect(() => {
    setHatchSpacing_um(initialHatchSpacing);
  }, [initialHatchSpacing]);

  // Execute Python LPBF Solver
  const onParametersChangeRef = useRef(onParametersChange);
  onParametersChangeRef.current = onParametersChange;
  const runPythonSolver = useCallback(async (signal?: AbortSignal): Promise<boolean> => {
    setIsSolving(true);
    setSolverError(null);
    try {
      const res = await pythonComputationService.solveLPBFThermalPhysics({
        material: selectedMaterial,
        laserPower_W,
        scanSpeed_mm_s: scanSpeed_mms,
        beamDiameter_um,
        preheatTemp_C,
        layerThickness_um,
        hatchSpacing_um,
        laserWavelength,
      }, signal);
      if (signal?.aborted) return false;
      setPyResult(res);
      const notifyParametersChange = onParametersChangeRef.current;
      if (notifyParametersChange) {
        notifyParametersChange({
          laserPower_W,
          scanSpeed_mms,
          beamDiameter_um,
          preheatTemp_C,
          layerThickness_um,
          hatchSpacing_um,
        });
      }
      return true;
    } catch (err: any) {
      if (signal?.aborted) return false;
      console.warn("Python LPBF solver error:", err);
      setSolverError(err.message || "Failed to solve LPBF thermal fields.");
      return false;
    } finally {
      if (!signal?.aborted) setIsSolving(false);
    }
  }, [
    selectedMaterial,
    laserPower_W,
    scanSpeed_mms,
    beamDiameter_um,
    preheatTemp_C,
    layerThickness_um,
    hatchSpacing_um,
    laserWavelength,
  ]);

  // Run on mount or when key parameters change with debounce. The parent callback is read through a ref so
  // its (inline, per-render) identity cannot retrigger the solver; superseded/hidden requests are aborted.
  const thermalInputSignature = JSON.stringify([selectedMaterial, laserPower_W, scanSpeed_mms, beamDiameter_um, preheatTemp_C, layerThickness_um, hatchSpacing_um, laserWavelength]);
  useEffect(() => {
    setPyResult(null);
    setSolverError(null);
  }, [thermalInputSignature]);
  const { runNow: runPythonSolverNow } = useDebouncedLatestTask(thermalInputSignature, (_signature, signal) => runPythonSolver(signal), 180);

  // Animation Loop for Laser Motion
  useVisibleInterval(() => {
    setTimeStep((prev) => (prev + 1) % 120);
  }, isSimulating ? 40 : null);

  // Fallback / Live Rosenthal temperature helper for client pixel sampling
  const calculateRosenthalPoint = useCallback(
    (x_um: number, y_um: number, z_um: number) => {
      const geom = pyResult?.meltPoolGeometry;
      const hydro = pyResult?.hydrodynamicsAndRecoil;
      const T0 = preheatTemp_C;
      const Tpeak = hydro?.peakTemperature_C || 2800;
      const Tm = 1350; // liquidus approximation
      const Ts = 1260; // solidus approximation
      const af = geom?.goldakParameters?.semiAxis_af_front_um || (beamDiameter_um * 0.9);
      const ar = geom?.goldakParameters?.semiAxis_ar_rear_um || (beamDiameter_um * 2.8);
      const b = geom?.goldakParameters?.semiAxis_b_halfwidth_um || (beamDiameter_um * 0.7);
      const c = geom?.goldakParameters?.semiAxis_c_depth_um || (layerThickness_um * 1.8);

      // Goldak normalized radius in 3D
      const x_axis = x_um >= 0 ? af : ar;
      const goldak_r2 = Math.pow(x_um / Math.max(1, x_axis), 2) + Math.pow(y_um / Math.max(1, b), 2) + Math.pow(z_um / Math.max(1, c), 2);

      let temp = T0;
      if (goldak_r2 <= 1.0) {
        // Inside melt pool
        temp = Tm + (Tpeak - Tm) * Math.exp(-2.2 * goldak_r2);
      } else {
        // Trailing & surrounding heat affected zone
        const decayDist = Math.sqrt(goldak_r2) - 1.0;
        temp = T0 + (Tm - T0) * Math.exp(-1.4 * decayDist);
      }

      // Cooling rate approximation
      const v_m_s = scanSpeed_mms * 1e-3;
      const coolingRate = temp > Ts && x_um < 0 ? (temp - T0) * (v_m_s / Math.max(1e-6, Math.abs(x_um) * 1e-6)) * 4.0 : 100;
      const gradient = (temp - T0) / Math.max(1e-6, Math.sqrt(x_um * x_um + y_um * y_um + z_um * z_um) * 1e-6);

      return {
        temp: Math.min(3800, temp),
        coolingRate: Math.min(1e8, Math.max(0, coolingRate)),
        gradient: Math.min(5e8, Math.max(0, gradient)),
        isLiquid: temp >= Tm,
        isMushy: temp >= Ts && temp < Tm,
        isSolid: temp < Ts,
        isVapor: temp >= 2850,
      };
    },
    [pyResult, preheatTemp_C, beamDiameter_um, layerThickness_um, scanSpeed_mms]
  );

  // Canvas High-DPI Rendering
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Background
    ctx.fillStyle = "#060913";
    ctx.fillRect(0, 0, width, height);

    // Pixel domain origin and scaling
    const umPerPixel = 0.85; // High resolution (1 px = 0.85 um)
    let laserPixelX = width * 0.62;
    let laserPixelY = height * 0.5;

    if (viewAngle === "longitudinal-side") {
      laserPixelX = width * 0.65;
      laserPixelY = height * 0.28; // Surface at y=28%
    } else if (viewAngle === "transverse-front") {
      laserPixelX = width * 0.5;
      laserPixelY = height * 0.32; // Surface at y=32%
    }

    const imgData = ctx.createImageData(width, height);
    const data = imgData.data;

    // Melt pool geometry boundaries from Python
    const geom = pyResult?.meltPoolGeometry;
    const Tm = 1350;
    const Ts = 1260;
    const T0 = preheatTemp_C;

    // Fast 2x2 grid rasterizer
    for (let py = 0; py < height; py += 2) {
      for (let px = 0; px < width; px += 2) {
        let x_um = 0;
        let y_um = 0;
        let z_um = 0;

        if (viewAngle === "top-down") {
          x_um = (px - laserPixelX) * umPerPixel;
          y_um = (py - laserPixelY) * umPerPixel;
          z_um = 0;
        } else if (viewAngle === "longitudinal-side") {
          x_um = (px - laserPixelX) * umPerPixel;
          y_um = 0;
          z_um = Math.max(0, (py - laserPixelY) * umPerPixel);
        } else {
          // Transverse Y-Z
          x_um = 0;
          y_um = (px - laserPixelX) * umPerPixel;
          z_um = Math.max(0, (py - laserPixelY) * umPerPixel);
        }

        const pt = calculateRosenthalPoint(x_um, y_um, z_um);
        const temp = pt.temp;
        const coolingRate = pt.coolingRate;
        const gradient = pt.gradient;

        let r = 8, g = 12, b = 24;

        if (mapMode === "temperature") {
          if (temp < T0 + 60) {
            r = 10; g = 18; b = 34;
          } else if (temp < Ts) {
            // Solid heating (Dark Navy -> Electric Indigo -> Violet -> Magenta)
            const tNorm = (temp - T0) / (Ts - T0);
            r = Math.floor(15 + tNorm * 170);
            g = Math.floor(25 + tNorm * 50);
            b = Math.floor(60 + (1 - tNorm) * 140);
          } else if (temp <= Tm) {
            // Mushy Zone (Solidus -> Liquidus) -> Bright Neon Amber
            r = 251; g = 146; b = 60;
          } else if (temp < 2700) {
            // Liquid Melt Pool -> Radiant Gold / Hot Red-Orange
            const tNorm = Math.min(1, (temp - Tm) / (2700 - Tm));
            r = 255;
            g = Math.floor(170 + tNorm * 75);
            b = Math.floor(tNorm * 180);
          } else {
            // Keyhole Vapor Plume -> Intense Solar Cyan-White
            r = 240; g = 250; b = 255;
          }
        } else if (mapMode === "cooling-rate") {
          if (temp < Ts || x_um > 0) {
            r = 10; g = 18; b = 34;
          } else {
            const logCR = Math.log10(Math.max(1e3, coolingRate));
            const norm = Math.min(1, Math.max(0, (logCR - 3.5) / 3.5)); // 10^3.5 to 10^7 K/s
            r = Math.floor(norm * 240);
            g = Math.floor((1 - Math.abs(norm - 0.5) * 2) * 220);
            b = Math.floor((1 - norm) * 255);
          }
        } else if (mapMode === "solidification-front") {
          if (temp > Tm) {
            r = 24; g = 32; b = 48; // Liquid dark core
          } else if (temp >= Ts && temp <= Tm) {
            r = 255; g = 105; b = 0; // Glowing Orange Mushy Zone
          } else if (temp >= Ts - 150 && temp < Ts) {
            r = 16; g = 185; b = 129; // Freshly Solidified Emerald Band
          } else {
            r = 10; g = 18; b = 34;
          }
        } else {
          // Thermal Gradient G
          const logG = Math.log10(Math.max(1e4, gradient));
          const norm = Math.min(1, Math.max(0, (logG - 4.5) / 3.0));
          r = Math.floor(norm * 245);
          g = Math.floor(norm * 110);
          b = Math.floor((1 - norm) * 230);
        }

        // Fill 2x2 quad
        for (let dy = 0; dy < 2; dy++) {
          for (let dx = 0; dx < 2; dx++) {
            const idx = ((py + dy) * width + (px + dx)) * 4;
            data[idx] = r;
            data[idx + 1] = g;
            data[idx + 2] = b;
            data[idx + 3] = 255;
          }
        }
      }
    }

    ctx.putImageData(imgData, 0, 0);

    // Dynamic Visual Overlays & Vector Annotations
    ctx.save();

    // 1. Grid & Centerlines
    ctx.strokeStyle = "rgba(148, 163, 184, 0.12)";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(0, laserPixelY);
    ctx.lineTo(width, laserPixelY);
    ctx.moveTo(laserPixelX, 0);
    ctx.lineTo(laserPixelX, height);
    ctx.stroke();
    ctx.setLineDash([]);

    // 2. View Specific Overlays
    if (viewAngle === "top-down") {
      // Draw Python Calculated 3D Teardrop Contour
      if (pyResult?.geometricContours?.topDownXY && showOverlays) {
        ctx.beginPath();
        const contour = pyResult.geometricContours.topDownXY;
        contour.forEach((pt, idx) => {
          const px = laserPixelX + pt.x_um / umPerPixel;
          const py = laserPixelY + pt.y_um / umPerPixel;
          if (idx === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        });
        ctx.closePath();
        ctx.strokeStyle = "#38bdf8";
        ctx.lineWidth = 2.0;
        ctx.stroke();

        // Solidification Chevron Lag Lines
        if (showMeshVectors) {
          ctx.strokeStyle = "rgba(56, 189, 248, 0.4)";
          ctx.lineWidth = 1.2;
          const ar = geom?.goldakParameters?.semiAxis_ar_rear_um || 120;
          const b = geom?.goldakParameters?.semiAxis_b_halfwidth_um || 50;
          for (let frac = 0.2; frac <= 0.85; frac += 0.2) {
            const tailX = laserPixelX - (ar * frac) / umPerPixel;
            const spanY = (b * (1 - frac * 0.7)) / umPerPixel;
            ctx.beginPath();
            ctx.moveTo(tailX, laserPixelY - spanY);
            ctx.lineTo(laserPixelX - (ar * (frac - 0.12)) / umPerPixel, laserPixelY);
            ctx.lineTo(tailX, laserPixelY + spanY);
            ctx.stroke();
          }
        }
      }

      // Marangoni Recirculation Vortices (Outward Convective Surface Flow)
      if (showMeshVectors) {
        ctx.strokeStyle = "#f59e0b";
        ctx.fillStyle = "#f59e0b";
        ctx.lineWidth = 1.5;
        const b_px = ((geom?.width_um ?? 0) / 2.0) / (umPerPixel * 1.6);
        // Top vortex
        ctx.beginPath();
        ctx.arc(laserPixelX - 10, laserPixelY - b_px * 0.55, b_px * 0.35, Math.PI * 0.2, Math.PI * 1.3);
        ctx.stroke();
        // Bottom vortex
        ctx.beginPath();
        ctx.arc(laserPixelX - 10, laserPixelY + b_px * 0.55, b_px * 0.35, Math.PI * 0.7, Math.PI * 1.8);
        ctx.stroke();
      }

      // Laser Beam Spot & Wave Ring
      const r_beam_px = (beamDiameter_um / 2.0) / umPerPixel;
      ctx.beginPath();
      ctx.arc(laserPixelX, laserPixelY, r_beam_px, 0, Math.PI * 2);
      ctx.strokeStyle = "#f43f5e";
      ctx.lineWidth = 2.2;
      ctx.stroke();

      // Scan Speed Vector Arrow
      const arrowLen = 65;
      ctx.beginPath();
      ctx.moveTo(laserPixelX + r_beam_px + 10, laserPixelY);
      ctx.lineTo(laserPixelX + r_beam_px + 10 + arrowLen, laserPixelY);
      ctx.strokeStyle = "#10b981";
      ctx.lineWidth = 2.5;
      ctx.stroke();
      // Arrowhead
      ctx.beginPath();
      ctx.moveTo(laserPixelX + r_beam_px + 10 + arrowLen, laserPixelY);
      ctx.lineTo(laserPixelX + r_beam_px + arrowLen, laserPixelY - 5);
      ctx.lineTo(laserPixelX + r_beam_px + arrowLen, laserPixelY + 5);
      ctx.fillStyle = "#10b981";
      ctx.fill();

      ctx.font = "11px ui-monospace, monospace";
      ctx.fillStyle = "#10b981";
      ctx.fillText(`v = ${scanSpeed_mms} mm/s`, laserPixelX + r_beam_px + 15, laserPixelY - 8);
    } else if (viewAngle === "longitudinal-side") {
      // Surface Line
      ctx.strokeStyle = "#e2e8f0";
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      ctx.moveTo(0, laserPixelY);
      ctx.lineTo(width, laserPixelY);
      ctx.stroke();

      // Layer Thickness Powder Boundary (z = t_layer)
      const layerPx = layerThickness_um / umPerPixel;
      ctx.strokeStyle = "#fbbf24";
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(0, laserPixelY + layerPx);
      ctx.lineTo(width, laserPixelY + layerPx);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "#fbbf24";
      ctx.font = "10px ui-monospace, monospace";
      ctx.fillText(`Layer Thickness: t = ${layerThickness_um} μm`, 20, laserPixelY + layerPx - 6);

      // Melt Pool Longitudinal Contour
      if (pyResult?.geometricContours?.longitudinalXZ && showOverlays) {
        ctx.beginPath();
        const pts = pyResult.geometricContours.longitudinalXZ;
        pts.forEach((pt, idx) => {
          const px = laserPixelX + pt.x_um / umPerPixel;
          const py = laserPixelY + pt.z_depth_um / umPerPixel;
          if (idx === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        });
        ctx.strokeStyle = "#38bdf8";
        ctx.lineWidth = 2.2;
        ctx.stroke();

        // Keyhole Vapor Cavity if present
        const d_kh = pyResult.meltPoolGeometry.keyholeVaporCavityDepth_um;
        if (d_kh > 5) {
          ctx.beginPath();
          const khWidthPx = (beamDiameter_um * 0.45) / umPerPixel;
          const khDepthPx = d_kh / umPerPixel;
          ctx.moveTo(laserPixelX - khWidthPx, laserPixelY);
          ctx.quadraticCurveTo(laserPixelX, laserPixelY + khDepthPx, laserPixelX + khWidthPx, laserPixelY);
          ctx.strokeStyle = "#f43f5e";
          ctx.lineWidth = 2.0;
          ctx.fillStyle = "rgba(244, 63, 94, 0.25)";
          ctx.fill();
          ctx.stroke();

          ctx.fillStyle = "#f43f5e";
          ctx.fillText(`Keyhole Vapor Cavity: ${d_kh.toFixed(0)} μm`, laserPixelX + khWidthPx + 8, laserPixelY + khDepthPx * 0.7);
        }
      }
    } else {
      // Transverse Y-Z Cross Section with Multi-Track Overlap
      ctx.strokeStyle = "#e2e8f0";
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      ctx.moveTo(0, laserPixelY);
      ctx.lineTo(width, laserPixelY);
      ctx.stroke();

      const layerPx = layerThickness_um / umPerPixel;
      ctx.strokeStyle = "#fbbf24";
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(0, laserPixelY + layerPx);
      ctx.lineTo(width, laserPixelY + layerPx);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "#fbbf24";
      ctx.font = "10px ui-monospace, monospace";
      ctx.fillText(`t_layer = ${layerThickness_um} μm`, 20, laserPixelY + layerPx - 6);

      // Draw Left, Center, Right Overlapping Hatches
      if (pyResult?.geometricContours?.multiTrackHatchOverlap && showOverlays) {
        pyResult.geometricContours.multiTrackHatchOverlap.forEach((track) => {
          ctx.beginPath();
          const isCenter = track.y_center_um === 0;
          track.contour.forEach((pt, idx) => {
            const px = laserPixelX + pt.y_um / umPerPixel;
            const py = laserPixelY + pt.z_depth_um / umPerPixel;
            if (idx === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
          });
          ctx.strokeStyle = isCenter ? "#38bdf8" : "rgba(56, 189, 248, 0.45)";
          ctx.lineWidth = isCenter ? 2.2 : 1.4;
          ctx.stroke();
        });

        // Hatch Spacing Indicators
        const hatchPx = hatchSpacing_um / umPerPixel;
        ctx.strokeStyle = "#a855f7";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([2, 2]);
        ctx.beginPath();
        ctx.moveTo(laserPixelX - hatchPx, laserPixelY - 25);
        ctx.lineTo(laserPixelX - hatchPx, laserPixelY + 50);
        ctx.moveTo(laserPixelX, laserPixelY - 25);
        ctx.lineTo(laserPixelX, laserPixelY + 50);
        ctx.moveTo(laserPixelX + hatchPx, laserPixelY - 25);
        ctx.lineTo(laserPixelX + hatchPx, laserPixelY + 50);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = "#a855f7";
        ctx.fillText(`Hatch = ${hatchSpacing_um} μm`, laserPixelX - hatchPx / 2 - 35, laserPixelY - 12);
      }
    }

    // 3. Interactive Probe Point Rendering
    if (probePos) {
      ctx.beginPath();
      ctx.arc(probePos.x_px, probePos.y_px, 5, 0, Math.PI * 2);
      ctx.fillStyle = "#ffffff";
      ctx.fill();
      ctx.strokeStyle = "#0284c7";
      ctx.lineWidth = 2;
      ctx.stroke();

      // Probe Crosshairs
      ctx.strokeStyle = "rgba(255, 255, 255, 0.35)";
      ctx.setLineDash([2, 2]);
      ctx.beginPath();
      ctx.moveTo(probePos.x_px - 15, probePos.y_px);
      ctx.lineTo(probePos.x_px + 15, probePos.y_px);
      ctx.moveTo(probePos.x_px, probePos.y_px - 15);
      ctx.lineTo(probePos.x_px, probePos.y_px + 15);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // 4. Legend & Scale Bar (100 um)
    const scaleBarUm = 100;
    const scaleBarPx = scaleBarUm / umPerPixel;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(20, height - 25, scaleBarPx, 3);
    ctx.font = "10px ui-monospace, monospace";
    ctx.fillText(`${scaleBarUm} μm`, 20, height - 32);

    ctx.restore();
  }, [
    mapMode,
    viewAngle,
    timeStep,
    probePos,
    showOverlays,
    showMeshVectors,
    pyResult,
    calculateRosenthalPoint,
    laserPower_W,
    scanSpeed_mms,
    beamDiameter_um,
    preheatTemp_C,
    layerThickness_um,
    hatchSpacing_um,
  ]);

  // Handle Canvas Mouse Move for Live Coordinate & Temperature Probe
  const handleCanvasMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const x_px = (e.clientX - rect.left) * scaleX;
    const y_px = (e.clientY - rect.top) * scaleY;

    const umPerPixel = 0.85;
    let laserPixelX = canvas.width * 0.62;
    let laserPixelY = canvas.height * 0.5;

    if (viewAngle === "longitudinal-side") {
      laserPixelX = canvas.width * 0.65;
      laserPixelY = canvas.height * 0.28;
    } else if (viewAngle === "transverse-front") {
      laserPixelX = canvas.width * 0.5;
      laserPixelY = canvas.height * 0.32;
    }

    let x_um = 0;
    let y_um = 0;
    let z_um = 0;

    if (viewAngle === "top-down") {
      x_um = (x_px - laserPixelX) * umPerPixel;
      y_um = (y_px - laserPixelY) * umPerPixel;
      z_um = 0;
    } else if (viewAngle === "longitudinal-side") {
      x_um = (x_px - laserPixelX) * umPerPixel;
      y_um = 0;
      z_um = Math.max(0, (y_px - laserPixelY) * umPerPixel);
    } else {
      x_um = 0;
      y_um = (x_px - laserPixelX) * umPerPixel;
      z_um = Math.max(0, (y_px - laserPixelY) * umPerPixel);
    }

    setProbePos({
      x_px,
      y_px,
      x_um: Math.round(x_um),
      y_um: Math.round(y_um),
      z_um: Math.round(z_um),
    });
  };

  // Active Probe Data
  const probeData = useMemo(() => {
    if (!probePos) {
      // Default to laser peak
      return {
        x_um: 0,
        y_um: 0,
        z_um: 0,
        ...calculateRosenthalPoint(0, 0, 0),
      };
    }
    return {
      x_um: probePos.x_um,
      y_um: probePos.y_um,
      z_um: probePos.z_um,
      ...calculateRosenthalPoint(probePos.x_um, probePos.y_um, probePos.z_um),
    };
  }, [probePos, calculateRosenthalPoint]);

  // Export Goldak FEA Card
  const exportGoldakCard = () => {
    if (!pyResult) return;
    const geom = pyResult.meltPoolGeometry;
    const params = pyResult.processParameters;
    const goldak = geom.goldakParameters;

    const feaCard = `** -------------------------------------------------------------
** METALLIX LPBF GOLDAK HEAT SOURCE CAE EXPORT CARD
** Material: ${pyResult.material} (Base: ${pyResult.baseMetal})
** Laser Power: ${params.laserPower_W} W | Scan Speed: ${params.scanSpeed_mm_s} mm/s
** Beam Diameter: ${params.beamDiameter_um} um | Wavelength: ${pyResult.laserWavelength}
** Volumetric Energy Density (VED): ${params.volumetricEnergyDensity_J_mm3} J/mm3
** -------------------------------------------------------------
*DFLUX, USER
*GOLDAK_DOUBLE_ELLIPSOID
** Parameters in meters (SI Units):
** a_front (m), a_rear (m), b_halfwidth (m), c_depth (m), Q_Goldak=Q_total/2 (W), eta_eff
 ${(goldak.semiAxis_af_front_um * 1e-6).toExponential(4)}, ${(goldak.semiAxis_ar_rear_um * 1e-6).toExponential(4)}, ${(goldak.semiAxis_b_halfwidth_um * 1e-6).toExponential(4)}, ${(goldak.semiAxis_c_depth_um * 1e-6).toExponential(4)}, ${params.laserPower_W / 2}, ${params.effectiveAbsorptivity}
** Solidification Kinetics:
** G_avg: ${pyResult.solidificationKinetics.thermalGradient_G_K_m} K/m
** R_solid: ${pyResult.solidificationKinetics.solidificationRate_R_m_s} m/s
** Cooling Rate: ${pyResult.solidificationKinetics.coolingRate_K_s} K/s
** Primary Spacing (PDAS): ${pyResult.solidificationKinetics.primaryDendriteArmSpacing_PDAS_um} um
** -------------------------------------------------------------`;

    const blob = new Blob([feaCard], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Goldak_LPBF_${pyResult.material.replace(/\s+/g, "_")}_${params.laserPower_W}W.inp`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      {/* HEADER BAR */}
      <div className="p-4 rounded-xl bg-[#0b1322] border border-[#1d2a44] space-y-3">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="p-1.5 rounded-lg bg-rose-500/20 text-rose-400 border border-rose-500/30">
                <Flame className="w-5 h-5 animate-pulse" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-white font-mono tracking-wide">
                    LPBF 3D Melt Pool Geometry &amp; Multi-Defect Physics Studio
                  </h3>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                    <Cpu className="w-3 h-3 text-emerald-400" />
                    Python HPC v4.0
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  High-fidelity Goldak double-ellipsoid thermal fields, Knudsen recoil keyholing, Marangoni convection, and lack-of-fusion overlap dynamics.
                </p>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => runPythonSolverNow()}
              disabled={isSolving}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-mono font-bold transition shadow-sm disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isSolving ? "animate-spin" : ""}`} />
              <span>{isSolving ? "Computing..." : "Solve Physics (Python)"}</span>
            </button>

            <button
              type="button"
              onClick={exportGoldakCard}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-mono transition"
              title="Export Goldak heat source parameter card for Abaqus / Ansys"
            >
              <Download className="w-3.5 h-3.5 text-sky-400" />
              <span>Goldak CAE (.inp)</span>
            </button>
          </div>
        </div>

        {/* Process Sliders & Material Controls */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-2.5 pt-2 border-t border-slate-800/80 text-xs">
          {/* Material */}
          <div className="space-y-1">
            <label className="text-[11px] font-mono text-slate-400">Alloy Material</label>
            <select aria-label="Alloy Material"
              value={selectedMaterial}
              onChange={(e) => setSelectedMaterial(e.target.value)}
              className="w-full bg-[#080d1a] text-slate-200 border border-slate-700 rounded-lg px-2 py-1 text-xs font-mono focus:border-sky-500 outline-none"
            >
              <option value="Inconel 718">Inconel 718 (Ni-Cr-Fe)</option>
              <option value="Ti-6Al-4V">Ti-6Al-4V Grade 5</option>
              <option value="316L Stainless Steel">316L Stainless Steel</option>
              <option value="AlSi10Mg">AlSi10Mg (Al-Si)</option>
              <option value="CoCrMo">CoCrMo (Bio/Aero)</option>
              <option value="Scalmalloy (Al-Mg-Sc-Zr)">Scalmalloy (Sc-Zr)</option>
              <option value="Hastelloy X">Hastelloy X (Ni-Cr)</option>
              <option value="Pure Copper (Cu-OF)">Pure Copper (Cu-OF)</option>
            </select>
          </div>

          {/* Laser Power */}
          <div className="space-y-1">
            <div className="flex justify-between text-[11px] font-mono">
              <span className="text-slate-400">Power (P)</span>
              <span className="text-rose-400 font-bold">{laserPower_W} W</span>
            </div>
            <input aria-label="Power (P)"
              type="range"
              min={60}
              max={600}
              step={10}
              value={laserPower_W}
              onChange={(e) => setLaserPower_W(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-rose-500"
            />
          </div>

          {/* Scan Speed */}
          <div className="space-y-1">
            <div className="flex justify-between text-[11px] font-mono">
              <span className="text-slate-400">Speed (v)</span>
              <span className="text-emerald-400 font-bold">{scanSpeed_mms} mm/s</span>
            </div>
            <input aria-label="Speed (v)"
              type="range"
              min={200}
              max={2500}
              step={25}
              value={scanSpeed_mms}
              onChange={(e) => setScanSpeed_mms(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-emerald-500"
            />
          </div>

          {/* Beam Diameter */}
          <div className="space-y-1">
            <div className="flex justify-between text-[11px] font-mono">
              <span className="text-slate-400">Beam Dia. (d)</span>
              <span className="text-sky-400 font-bold">{beamDiameter_um} μm</span>
            </div>
            <input aria-label="Beam Dia. (d)"
              type="range"
              min={40}
              max={150}
              step={5}
              value={beamDiameter_um}
              onChange={(e) => setBeamDiameter_um(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-sky-500"
            />
          </div>

          {/* Layer Thickness */}
          <div className="space-y-1">
            <div className="flex justify-between text-[11px] font-mono">
              <span className="text-slate-400">Layer (t)</span>
              <span className="text-amber-400 font-bold">{layerThickness_um} μm</span>
            </div>
            <input aria-label="Layer (t)"
              type="range"
              min={20}
              max={80}
              step={5}
              value={layerThickness_um}
              onChange={(e) => setLayerThickness_um(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-amber-500"
            />
          </div>

          {/* Hatch Spacing */}
          <div className="space-y-1">
            <div className="flex justify-between text-[11px] font-mono">
              <span className="text-slate-400">Hatch (h)</span>
              <span className="text-purple-400 font-bold">{hatchSpacing_um} μm</span>
            </div>
            <input aria-label="Hatch (h)"
              type="range"
              min={50}
              max={180}
              step={5}
              value={hatchSpacing_um}
              onChange={(e) => setHatchSpacing_um(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-purple-500"
            />
          </div>

          {/* Laser Wavelength */}
          <div className="space-y-1">
            <label className="text-[11px] font-mono text-slate-400">Laser Wavelength</label>
            <select aria-label="Laser Wavelength"
              value={laserWavelength}
              onChange={(e) => setLaserWavelength(e.target.value as any)}
              className="w-full bg-[#080d1a] text-slate-200 border border-slate-700 rounded-lg px-2 py-1 text-xs font-mono focus:border-sky-500 outline-none"
            >
              <option value="IR_1064nm">IR Fiber (1064 nm)</option>
              <option value="Green_515nm">Green (515 nm - Cu/Al)</option>
              <option value="Blue_450nm" disabled>Blue (450 nm — material absorptivity unavailable)</option>
            </select>
          </div>
        </div>
      </div>

      {/* MAIN VIEWPORT: 3D CANVAS & METRICS */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* LEFT/CENTER: Interactive Canvas (8 Cols) */}
        <div className="lg:col-span-8 space-y-3">
          <div className="p-3.5 rounded-xl bg-[#090e18] border border-[#162032] space-y-3">
            {/* View Switcher & Map Mode Controls */}
            <div className="flex flex-wrap items-center justify-between gap-2">
              {/* 3 Orthogonal Views */}
              <div className="flex items-center gap-1 bg-[#060a12] p-1 rounded-lg border border-slate-800 text-xs">
                <button
                  type="button"
                  onClick={() => setViewAngle("top-down")}
                  className={`px-2.5 py-1 rounded-md font-mono transition ${
                    viewAngle === "top-down" ? "bg-sky-500/20 text-sky-300 font-bold border border-sky-500/40" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Top-Down (X-Y)
                </button>
                <button
                  type="button"
                  onClick={() => setViewAngle("longitudinal-side")}
                  className={`px-2.5 py-1 rounded-md font-mono transition ${
                    viewAngle === "longitudinal-side" ? "bg-sky-500/20 text-sky-300 font-bold border border-sky-500/40" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Longitudinal (X-Z)
                </button>
                <button
                  type="button"
                  onClick={() => setViewAngle("transverse-front")}
                  className={`px-2.5 py-1 rounded-md font-mono transition ${
                    viewAngle === "transverse-front" ? "bg-sky-500/20 text-sky-300 font-bold border border-sky-500/40" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Transverse Overlap (Y-Z)
                </button>
              </div>

              {/* Heatmap Field Mode */}
              <div className="flex items-center gap-1 bg-[#060a12] p-1 rounded-lg border border-slate-800 text-xs">
                <button
                  type="button"
                  onClick={() => setMapMode("temperature")}
                  className={`px-2 py-1 rounded-md font-mono text-[11px] transition ${
                    mapMode === "temperature" ? "bg-rose-500/20 text-rose-300 font-bold border border-rose-500/30" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Temperature (T)
                </button>
                <button
                  type="button"
                  onClick={() => setMapMode("solidification-front")}
                  className={`px-2 py-1 rounded-md font-mono text-[11px] transition ${
                    mapMode === "solidification-front" ? "bg-amber-500/20 text-amber-300 font-bold border border-amber-500/30" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Mushy Front
                </button>
                <button
                  type="button"
                  onClick={() => setMapMode("cooling-rate")}
                  className={`px-2 py-1 rounded-md font-mono text-[11px] transition ${
                    mapMode === "cooling-rate" ? "bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/30" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Cooling Rate (dT/dt)
                </button>
                <button
                  type="button"
                  onClick={() => setMapMode("thermal-gradient")}
                  className={`px-2 py-1 rounded-md font-mono text-[11px] transition ${
                    mapMode === "thermal-gradient" ? "bg-purple-500/20 text-purple-300 font-bold border border-purple-500/30" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Gradient (G)
                </button>
              </div>

              {/* Visual Toggles */}
              <div className="flex items-center gap-1 text-xs">
                <button
                  type="button"
                  onClick={() => setShowOverlays(!showOverlays)}
                  className={`px-2 py-1 rounded-md font-mono text-[10px] border transition ${
                    showOverlays ? "bg-sky-500/10 text-sky-300 border-sky-500/30" : "bg-slate-900 text-slate-500 border-slate-800"
                  }`}
                >
                  Geometry Contours
                </button>
                <button
                  type="button"
                  onClick={() => setShowMeshVectors(!showMeshVectors)}
                  className={`px-2 py-1 rounded-md font-mono text-[10px] border transition ${
                    showMeshVectors ? "bg-amber-500/10 text-amber-300 border-amber-500/30" : "bg-slate-900 text-slate-500 border-slate-800"
                  }`}
                >
                  Marangoni &amp; Lag
                </button>
              </div>
            </div>

            {/* Canvas Container */}
            <div className="relative rounded-xl overflow-hidden border border-slate-800 bg-[#060913]">
              {!pyResult && (
                <div role="status" className="px-3 py-1.5 text-[10px] font-mono text-amber-300 bg-amber-500/10 border-b border-amber-500/30">
                  {solverError ? "Provisional client-side heuristic field; Python solve failed." : "Provisional client-side heuristic field; Python solve pending."}
                </div>
              )}
              <canvas
                ref={canvasRef}
                width={780}
                height={460}
                onMouseMove={handleCanvasMouseMove}
                onMouseLeave={() => setProbePos(null)}
                className="w-full h-[400px] sm:h-[460px] object-cover cursor-crosshair block"
              />

              {/* Floating Real-Time Probe Overlay */}
              <div className="absolute top-3 left-3 p-2.5 rounded-lg bg-[#0a1120]/90 backdrop-blur-md border border-slate-700/60 shadow-lg text-xs font-mono space-y-1 pointer-events-none">
                <div className="flex items-center gap-1.5 text-sky-400 font-bold text-[11px]">
                  <Crosshair className="w-3.5 h-3.5 text-sky-400 animate-spin" />
                  <span>Interactive Probe Coordinates</span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-[10px] text-slate-300">
                  <span>X: <strong className="text-white">{probeData.x_um} μm</strong></span>
                  <span>Y: <strong className="text-white">{probeData.y_um} μm</strong></span>
                  <span>Z: <strong className="text-white">{probeData.z_um} μm</strong></span>
                </div>
                <div className="pt-1 border-t border-slate-800 grid grid-cols-2 gap-2 text-[10px]">
                  <span>Temperature: <strong className="text-rose-400">{Math.round(probeData.temp)} °C</strong></span>
                  <span>Cooling: <strong className="text-emerald-400">{probeData.coolingRate.toExponential(2)} K/s</strong></span>
                </div>
                <div className="text-[10px] text-slate-400">
                  State:{" "}
                  <span className={`font-bold ${probeData.isVapor ? "text-cyan-300" : probeData.isLiquid ? "text-amber-400" : probeData.isMushy ? "text-orange-400" : "text-slate-300"}`}>
                    {probeData.isVapor ? "Vapor / Keyhole Plasma" : probeData.isLiquid ? "Liquid Melt" : probeData.isMushy ? "Mushy (Solidification Front)" : "Solid Matrix"}
                  </span>
                </div>
              </div>

              {/* Floating Regime Indicator Badge */}
              {pyResult && (
                <div className="absolute bottom-3 right-3 p-2 rounded-lg bg-[#0b1326]/90 backdrop-blur-md border border-slate-700 text-xs font-mono flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full animate-ping" style={{ backgroundColor: pyResult.defectDiagnostics.lackOfFusionStatus === "Pass" ? "#10b981" : "#f59e0b" }} />
                  <span className="text-slate-200">Regime: <strong className="text-white">{pyResult.meltPoolGeometry.regime}</strong></span>
                </div>
              )}
            </div>
          </div>

          {/* 2D P-V Process Window Interactive Map */}
          {pyResult?.processWindowMap && (
            <div className="p-3.5 rounded-xl bg-[#090e18] border border-[#162032] space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Grid className="w-4 h-4 text-emerald-400" />
                  <h4 className="text-xs font-bold text-white font-mono">
                    2D Dynamic Power-Velocity (P-v) Process Window &amp; Defect Map
                  </h4>
                </div>
                <span className="text-[10px] font-mono text-slate-400">
                  Click point to load parameters instantly
                </span>
              </div>

              <div className="grid grid-cols-7 gap-1.5 p-2 bg-[#060a12] rounded-lg border border-slate-800/80">
                {pyResult.processWindowMap.grid.map((pt, idx) => {
                  const isCurrent = Math.abs(pt.power_W - laserPower_W) < 40 && Math.abs(pt.speed_mm_s - scanSpeed_mms) < 200;
                  return (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => {
                        setLaserPower_W(pt.power_W);
                        setScanSpeed_mms(pt.speed_mm_s);
                      }}
                      className={`p-1.5 rounded text-left transition relative border ${
                        isCurrent
                          ? "ring-2 ring-sky-400 border-white shadow-[0_0_10px_rgba(56,189,248,0.5)] z-10"
                          : "border-slate-800/60 hover:border-slate-600"
                      }`}
                      style={{ backgroundColor: `${pt.color}15` }}
                      title={`${pt.power_W} W, ${pt.speed_mm_s} mm/s: ${pt.regime} (W=${pt.width_um}um, D=${pt.depth_um}um)`}
                    >
                      <div className="flex justify-between items-center text-[9px] font-mono">
                        <span className="font-bold text-white">{pt.power_W}W</span>
                        <span className="text-slate-400">{pt.speed_mm_s}</span>
                      </div>
                      <div className="text-[8px] font-mono truncate mt-0.5" style={{ color: pt.color }}>
                        {pt.regime.split(" ")[0]}
                      </div>
                      <div className="text-[8px] text-slate-400">
                        {pt.width_um}x{pt.depth_um}μm
                      </div>
                    </button>
                  );
                })}
              </div>

              <div className="flex flex-wrap items-center gap-3 text-[10px] font-mono text-slate-400 pt-1">
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded bg-emerald-500" /> Optimal Conduction Melting (&gt;99.9%)</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded bg-rose-500" /> Keyhole Vaporization Pores</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded bg-amber-500" /> Lack of Fusion (Unmelted)</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded bg-purple-500" /> Plateau-Rayleigh Balling</span>
              </div>
            </div>
          )}
        </div>

        {/* RIGHT: Detailed Physics, Geometry & Solidification Diagnostics (4 Cols) */}
        <div className="lg:col-span-4 space-y-3">
          {/* Melt Pool Geometric Dimensions Card */}
          <div className="p-3.5 rounded-xl bg-[#090e18] border border-[#162032] space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center gap-2">
                <Box className="w-4 h-4 text-sky-400" />
                <h4 className="text-xs font-bold text-white font-mono">Ergiyik Havuzu Geometrisi</h4>
              </div>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-sky-500/20 text-sky-300 border border-sky-500/30">
                Goldak 3D
              </span>
            </div>

            {pyResult && (
              <div className="space-y-2 text-xs font-mono">
                <div className="grid grid-cols-3 gap-2 p-2 bg-[#060a12] rounded-lg border border-slate-800">
                  <div className="text-center">
                    <span className="text-[10px] text-slate-400 block">Length (L)</span>
                    <strong className="text-sm text-sky-300">{pyResult.meltPoolGeometry.length_um} μm</strong>
                  </div>
                  <div className="text-center border-x border-slate-800">
                    <span className="text-[10px] text-slate-400 block">Width (W)</span>
                    <strong className="text-sm text-emerald-300">{pyResult.meltPoolGeometry.width_um} μm</strong>
                  </div>
                  <div className="text-center">
                    <span className="text-[10px] text-slate-400 block">Depth (D)</span>
                    <strong className="text-sm text-amber-300">{pyResult.meltPoolGeometry.depth_um} μm</strong>
                  </div>
                </div>

                <div className="space-y-1.5 text-[11px] text-slate-300">
                  <div className="flex justify-between py-0.5 border-b border-slate-800/60">
                    <span className="text-slate-400">Depth/Width (D/W):</span>
                    <span className="font-bold text-white">{pyResult.meltPoolGeometry.depthToWidthRatio_D_over_W}</span>
                  </div>
                  <div className="flex justify-between py-0.5 border-b border-slate-800/60">
                    <span className="text-slate-400">Aspect Ratio (L/W):</span>
                    <span className="font-bold text-white">{pyResult.meltPoolGeometry.aspectRatio_L_over_W}</span>
                  </div>
                  <div className="flex justify-between py-0.5 border-b border-slate-800/60">
                    <span className="text-slate-400">Volumetric Energy Density (VED):</span>
                    <span className="font-bold text-sky-400">{pyResult.processParameters.volumetricEnergyDensity_J_mm3} J/mm³</span>
                  </div>
                  <div className="flex justify-between py-0.5 border-b border-slate-800/60">
                    <span className="text-slate-400">Normalized Enthalpy (ΔH/h_s):</span>
                    <span className="font-bold text-purple-300">{pyResult.processParameters.normalizedEnthalpy}</span>
                  </div>
                  <div className="flex justify-between py-0.5">
                    <span className="text-slate-400">Effective Absorptivity (η_eff):</span>
                    <span className="font-bold text-emerald-400">{Math.round(pyResult.processParameters.effectiveAbsorptivity * 100)}%</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Defect Diagnostics & Risk Matrix */}
          <div className="p-3.5 rounded-xl bg-[#090e18] border border-[#162032] space-y-2.5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-rose-400" />
                <h4 className="text-xs font-bold text-white font-mono">Defect &amp; Porosity Analytics</h4>
              </div>
              {pyResult && (
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-bold ${
                    pyResult.defectDiagnostics.lackOfFusionStatus === "Pass"
                      ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                      : "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                  }`}
                >
                  {pyResult.defectDiagnostics.lackOfFusionStatus === "Pass" ? "PASSED (Dense)" : "RISK REGIME"}
                </span>
              )}
            </div>

            {pyResult && (
              <div className="space-y-2 text-xs font-mono">
                {/* Lack of Fusion */}
                <div className="p-2 bg-[#060a12] rounded-lg border border-slate-800 space-y-1">
                  <div className="flex justify-between text-[11px]">
                    <span className="text-slate-400">Lack of Fusion (LoF):</span>
                    <span className={`font-bold ${pyResult.defectDiagnostics.lackOfFusionStatus === "Pass" ? "text-emerald-400" : "text-amber-400"}`}>
                      Index: {pyResult.defectDiagnostics.lackOfFusionOverlapIndex}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-400 leading-relaxed">
                    {pyResult.defectDiagnostics.lackOfFusionRisk}
                  </p>
                </div>

                {/* Keyhole & Hydrodynamics */}
                <div className="p-2 bg-[#060a12] rounded-lg border border-slate-800 space-y-1">
                  <div className="flex justify-between text-[11px]">
                    <span className="text-slate-400">Keyhole Porosity Risk:</span>
                    <span className="text-rose-400 font-bold">{pyResult.defectDiagnostics.keyholePorosityRisk.split(" ")[0]}</span>
                  </div>
                  <div className="flex justify-between text-[10px] text-slate-400">
                    <span>Knudsen Recoil Pressure:</span>
                    <strong className="text-slate-200">{pyResult.hydrodynamicsAndRecoil.knudsenRecoilPressure_kPa} kPa</strong>
                  </div>
                  <div className="flex justify-between text-[10px] text-slate-400">
                    <span>Marangoni Number (Ma):</span>
                    <strong className="text-amber-300">{pyResult.hydrodynamicsAndRecoil.marangoniNumber}</strong>
                  </div>
                </div>

                {/* Balling & Recoater */}
                <div className="p-2 bg-[#060a12] rounded-lg border border-slate-800 space-y-1">
                  <div className="flex justify-between text-[11px]">
                    <span className="text-slate-400">Plateau-Rayleigh Balling:</span>
                    <span className="text-purple-300 font-bold">{pyResult.defectDiagnostics.ballingInstabilityRisk.split(" ")[0]}</span>
                  </div>
                  <div className="flex justify-between text-[10px] text-slate-400">
                    <span>Residual Stress (Upper Bound):</span>
                    <strong className="text-slate-200">{pyResult.defectDiagnostics.effectiveResidualStress_MPa} MPa</strong>
                  </div>
                  <div className="flex justify-between text-[10px] text-slate-400">
                    <span>Recoater Blade Crash Risk:</span>
                    <strong className="text-slate-200">{pyResult.defectDiagnostics.recoaterCrashRisk.split(" ")[0]}</strong>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Solidification Kinetics & Microstructure Prediction */}
          <div className="p-3.5 rounded-xl bg-[#090e18] border border-[#162032] space-y-2.5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-emerald-400" />
                <h4 className="text-xs font-bold text-white font-mono">Solidification Kinetics &amp; Microstructure</h4>
              </div>
              <span className="text-[10px] font-mono text-slate-400">Hunt CET Model</span>
            </div>

            {pyResult && (
              <div className="space-y-2 text-xs font-mono">
                <div className="p-2 bg-[#060a12] rounded-lg border border-slate-800 space-y-1.5">
                  <div className="flex justify-between text-[11px]">
                    <span className="text-slate-400">Thermal Gradient (G):</span>
                    <span className="font-bold text-white">{pyResult.solidificationKinetics.thermalGradient_G_K_um} K/μm</span>
                  </div>
                  <div className="flex justify-between text-[11px]">
                    <span className="text-slate-400">Solidification Velocity (R):</span>
                    <span className="font-bold text-emerald-400">{pyResult.solidificationKinetics.solidificationRate_R_mm_s} mm/s</span>
                  </div>
                  <div className="flex justify-between text-[11px]">
                    <span className="text-slate-400">Cooling Rate (G·R):</span>
                    <span className="font-bold text-rose-400">{pyResult.solidificationKinetics.coolingRate_K_s.toExponential(2)} K/s</span>
                  </div>
                </div>

                <div className="p-2 bg-[#060a12] rounded-lg border border-slate-800 space-y-1">
                  <div className="text-[10px] text-slate-400">Predicted Morphology:</div>
                  <div className="text-[11px] font-bold text-sky-300">
                    {pyResult.solidificationKinetics.microstructureMorphology}
                  </div>
                  <div className="grid grid-cols-2 gap-2 pt-1 border-t border-slate-800 text-[10px] text-slate-300">
                    <div>PDAS (λ₁): <strong className="text-white">{pyResult.solidificationKinetics.primaryDendriteArmSpacing_PDAS_um} μm</strong></div>
                    <div>SDAS (λ₂): <strong className="text-white">{pyResult.solidificationKinetics.secondaryDendriteArmSpacing_SDAS_um} μm</strong></div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
