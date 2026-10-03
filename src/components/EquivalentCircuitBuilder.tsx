import { useEscapeToClose } from "./AccessibleModal";
import { useInputBoundTask } from "../hooks/useInputBoundTask";
import { requestPythonAnalysis } from "../services/pythonAnalysis";
import { ResponsiveContainer } from './VisibleResponsiveContainer';
import { normalizePythonCnlsReport } from '../utils/pythonCnlsReport';
import React, { useState, useMemo, useCallback, useRef } from "react";
import {
  Activity,
  Layers,
  Zap,
  Plus,
  Trash2,
  Sliders,
  RotateCcw,
  Download,
  Copy,
  Check,
  Info,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  Battery,
  Droplets,
  Cpu,
  MoveHorizontal,
  FolderOpen,
  Code,
  Gauge,
  HelpCircle,
  BookOpen,
  Upload,
  Play,
  Lock,
  Unlock,
  FileText,
  CheckCircle2,
  AlertTriangle,
  GripVertical,
  RefreshCw,
  SlidersHorizontal,
  ChevronRight,
  MousePointerClick,
  FileSpreadsheet,
  RadioTower,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ScatterChart,
  Scatter,
  ComposedChart,
} from "recharts";
import { EXTENDED_CIRCUIT_LIBRARY, CircuitModelDoc } from "../data/circuitModelLibrary";
import { CircuitLibraryModal } from "./CircuitLibraryModal";
import { PresetCircuitLibraryPanel } from "./PresetCircuitLibraryPanel";
import { CNLSFittingStudio } from "./CNLSFittingStudio";
import { PlotlyEISViewer } from "./PlotlyEISViewer";
import { SyntheticNoiseStressStudio } from "./SyntheticNoiseStressStudio";
import {
  ExperimentalEISDataset,
  RawEISPoint,
  CNLSFitReport,
  WeightingMethod,
  ParameterFitResult,
} from "../types/eisData";
import {
  parseEISFile,
  EXPERIMENTAL_BENCHMARKS,
} from "../utils/eisFileParser";
import {
  extractAdjustableParameters,
  applyParametersToTopology,
} from "../utils/cnlsOptimizer";

// =========================================================================
// 1. TYPES & CIRCUIT TOPOLOGY STRUCTURES
// =========================================================================

export type CircuitElementType = "R" | "C" | "CPE" | "W" | "Wo" | "Ws" | "L" | "G" | "TLM_open" | "TLM_short" | "CC" | "HN";

export interface CircuitElement {
  id: string;
  type: CircuitElementType;
  name: string;
  label: string;
  value: number; // Primary value (R in Ohms, C in Farads, Q in S*s^n, sigma in Ohm*s^-0.5, L in Henries, Rg in Ohms, Rion in Ohms)
  unit: string;
  exponent?: number; // For CPE: n (0.01 to 1.0); For Ws/Wo/G/CC/HN: tau (s) or alpha; For TLM: alpha
  secondaryValue?: number; // e.g. Rct for TLM, beta for HN
  isFixed?: boolean; // Locked during CNLS fitting
  description: string;
}

export type BlockConnection = "series" | "parallel";

export interface CircuitBranch {
  id: string;
  connection: BlockConnection;
  name: string;
  elements: CircuitElement[];
}

export interface CircuitTopology {
  id: string;
  name: string;
  category: "battery" | "corrosion" | "coating" | "fuel-cell" | "solid-state" | "bio-sensor" | "custom";
  description: string;
  cdcNotation: string;
  branches: CircuitBranch[];
}

export interface EISFrequencyPoint {
  frequency: number; // Hz
  omega: number; // rad/s
  zReal: number; // Ohm
  zImag: number; // Ohm
  minusZImag: number; // Ohm
  zMag: number; // Ohm
  phaseDeg: number; // degrees
  logFreq: number;
  logZMag: number;
}

// =========================================================================
// 2. STANDARD PRESET EQUIVALENT CIRCUITS
// =========================================================================

export const STANDARD_CIRCUIT_PRESETS: CircuitTopology[] = EXTENDED_CIRCUIT_LIBRARY.map(
  (m) => m.topology
);

// Palette definitions for Drag & Drop
export interface PaletteItem {
  type: CircuitElementType;
  name: string;
  label: string;
  defaultUnit: string;
  defaultValue: number;
  defaultExponent?: number;
  defaultSecondaryValue?: number;
  description: string;
  glyph: string;
  color: string;
  category: string;
}

export const ELEMENT_PALETTE: PaletteItem[] = [
  {
    type: "R",
    name: "R",
    label: "Resistor (R)",
    defaultUnit: "Ω",
    defaultValue: 10.0,
    description: "Ohmic electrolyte solution resistance (Rs) or faradaic charge-transfer resistance (Rct).",
    glyph: "R",
    color: "from-amber-500/20 to-orange-500/20 text-amber-400 border-amber-400/40",
    category: "Resistive",
  },
  {
    type: "C",
    name: "C",
    label: "Ideal Capacitor (C)",
    defaultUnit: "F",
    defaultValue: 1e-5,
    description: "Ideal capacitive Helmholtz electric double-layer or planar dielectric layer.",
    glyph: "C",
    color: "from-sky-500/20 to-blue-500/20 text-sky-400 border-sky-400/40",
    category: "Capacitive",
  },
  {
    type: "CPE",
    name: "Q",
    label: "Constant Phase Element (CPE)",
    defaultUnit: "S·sⁿ",
    defaultValue: 2.5e-5,
    defaultExponent: 0.88,
    description: "Non-ideal interfacial capacitive dispersion accounting for surface roughness and fractal porosity.",
    glyph: "CPE",
    color: "from-purple-500/20 to-indigo-500/20 text-purple-400 border-purple-400/40",
    category: "Dispersive",
  },
  {
    type: "W",
    name: "W",
    label: "Semi-Infinite Warburg (W)",
    defaultUnit: "Ω·s⁻⁰·⁵",
    defaultValue: 45.0,
    description: "Semi-infinite planar solid-state ionic or liquid mass transport diffusion (45° tail).",
    glyph: "W",
    color: "from-emerald-500/20 to-teal-500/20 text-emerald-400 border-emerald-400/40",
    category: "Diffusive",
  },
  {
    type: "Wo",
    name: "Wo",
    label: "Open / Transmissive Warburg (Wo)",
    defaultUnit: "Ω",
    defaultValue: 80.0,
    defaultExponent: 0.5,
    description: "Finite-length Nernst boundary diffusion with constant surface concentration (tanh loop).",
    glyph: "Wo",
    color: "from-teal-500/20 to-cyan-500/20 text-teal-400 border-teal-400/40",
    category: "Diffusive",
  },
  {
    type: "Ws",
    name: "Ws",
    label: "Short / Reflective Warburg (Ws)",
    defaultUnit: "Ω",
    defaultValue: 100.0,
    defaultExponent: 1.2,
    description: "Finite-length intercalation diffusion with impermeable/blocking boundary (coth vertical tail).",
    glyph: "Ws",
    color: "from-cyan-500/20 to-blue-500/20 text-cyan-400 border-cyan-400/40",
    category: "Diffusive",
  },
  {
    type: "TLM_open",
    name: "TLM_op",
    label: "Bisquert Open Porous TLM",
    defaultUnit: "Ω",
    defaultValue: 50.0, // R_ion
    defaultExponent: 0.90, // alpha
    defaultSecondaryValue: 200.0, // R_ct
    description: "Bisquert transmission line with blocking current collector (supercapacitors, Li-ion porous cathodes).",
    glyph: "TLMo",
    color: "from-blue-600/20 to-indigo-600/20 text-indigo-400 border-indigo-400/40",
    category: "Transmission Line",
  },
  {
    type: "TLM_short",
    name: "TLM_sh",
    label: "Bisquert Short / Transmissive TLM",
    defaultUnit: "Ω",
    defaultValue: 40.0, // R_ion
    defaultExponent: 0.92, // alpha
    defaultSecondaryValue: 150.0, // R_ct
    description: "Bisquert transmission line with transmissive boundary (DSSC solar cells, catalytic membranes).",
    glyph: "TLMs",
    color: "from-indigo-600/20 to-violet-600/20 text-violet-400 border-violet-400/40",
    category: "Transmission Line",
  },
  {
    type: "G",
    name: "G",
    label: "Gerischer Element (G)",
    defaultUnit: "Ω",
    defaultValue: 120.0,
    defaultExponent: 0.2,
    description: "Coupled homogeneous chemical reaction with diffusion (SOFC cathodes, chemical kinetics).",
    glyph: "G",
    color: "from-yellow-500/20 to-amber-500/20 text-yellow-400 border-yellow-400/40",
    category: "Kinetic",
  },
  {
    type: "CC",
    name: "CC",
    label: "Cole-Cole Dielectric (CC)",
    defaultUnit: "Ω",
    defaultValue: 2500.0,
    defaultExponent: 0.85,
    description: "Cole-Cole symmetric dielectric relaxation element for solid electrolytes and polymers.",
    glyph: "CC",
    color: "from-fuchsia-500/20 to-pink-500/20 text-fuchsia-400 border-fuchsia-400/40",
    category: "Dielectric",
  },
  {
    type: "HN",
    name: "HN",
    label: "Havriliak-Negami (HN)",
    defaultUnit: "Ω",
    defaultValue: 5000.0,
    defaultExponent: 0.82,
    defaultSecondaryValue: 0.75,
    description: "Asymmetric dielectric relaxation for solid polymers, ceramic grains, and anti-corrosion barrier paints.",
    glyph: "HN",
    color: "from-pink-500/20 to-rose-500/20 text-pink-400 border-pink-400/40",
    category: "Dielectric",
  },
  {
    type: "L",
    name: "L",
    label: "Inductor (L)",
    defaultUnit: "H",
    defaultValue: 1e-6,
    description: "High-frequency lead inductance, cable reactance, or low-frequency pitting adsorption loops.",
    glyph: "L",
    color: "from-rose-500/20 to-pink-500/20 text-rose-400 border-rose-400/40",
    category: "Reactive",
  },
];

// =========================================================================
// 3. COMPLEX IMPEDANCE MATH ENGINE
// =========================================================================

interface ComplexNumber {
  re: number;
  im: number;
}

function complexAdd(a: ComplexNumber, b: ComplexNumber): ComplexNumber {
  return { re: a.re + b.re, im: a.im + b.im };
}

function complexMultiply(a: ComplexNumber, b: ComplexNumber): ComplexNumber {
  return {
    re: a.re * b.re - a.im * b.im,
    im: a.re * b.im + a.im * b.re,
  };
}

function complexDivide(a: ComplexNumber, b: ComplexNumber): ComplexNumber {
  const denom = b.re * b.re + b.im * b.im;
  if (denom === 0) return { re: 1e12, im: 0 };
  return {
    re: (a.re * b.re + a.im * b.im) / denom,
    im: (a.im * b.re - a.re * b.im) / denom,
  };
}

function complexSqrt(a: ComplexNumber): ComplexNumber {
  const r = Math.sqrt(a.re * a.re + a.im * a.im);
  const theta = Math.atan2(a.im, a.re);
  const sqrtR = Math.sqrt(r);
  return {
    re: sqrtR * Math.cos(theta / 2),
    im: sqrtR * Math.sin(theta / 2),
  };
}

function complexTanh(a: ComplexNumber): ComplexNumber {
  // tanh(x + iy) = (sinh(2x) + i*sin(2y)) / (cosh(2x) + cos(2y))
  const denom = Math.cosh(2 * a.re) + Math.cos(2 * a.im);
  if (denom === 0) return { re: 1.0, im: 0.0 };
  return {
    re: Math.sinh(2 * a.re) / denom,
    im: Math.sin(2 * a.im) / denom,
  };
}

function complexCoth(a: ComplexNumber): ComplexNumber {
  const tanhVal = complexTanh(a);
  return complexDivide({ re: 1, im: 0 }, tanhVal);
}

function complexPower(a: ComplexNumber, p: number): ComplexNumber {
  const r = Math.sqrt(a.re * a.re + a.im * a.im);
  if (r === 0) return { re: 0, im: 0 };
  const theta = Math.atan2(a.im, a.re);
  const rPow = Math.pow(r, p);
  return {
    re: rPow * Math.cos(p * theta),
    im: rPow * Math.sin(p * theta),
  };
}

function complexInvert(a: ComplexNumber): ComplexNumber {
  return complexDivide({ re: 1, im: 0 }, a);
}

function calculateElementImpedance(el: CircuitElement, omega: number): ComplexNumber {
  const w = Math.max(1e-6, omega);

  switch (el.type) {
    case "R": {
      return { re: Math.max(1e-6, el.value), im: 0 };
    }
    case "C": {
      const c = Math.max(1e-15, el.value);
      return { re: 0, im: -1 / (w * c) };
    }
    case "CPE": {
      const q = Math.max(1e-15, el.value);
      const n = Math.max(0.01, Math.min(1.0, el.exponent ?? 0.88));
      const wn = Math.pow(w, n);
      const mag = 1 / (q * wn);
      const phi = (n * Math.PI) / 2;
      return {
        re: mag * Math.cos(phi),
        im: -mag * Math.sin(phi),
      };
    }
    case "W": {
      const sigma = Math.max(1e-6, el.value);
      const val = sigma / Math.sqrt(w);
      return { re: val, im: -val };
    }
    case "Wo": {
      // Open / Nernst transmissive diffusion: Z = Rd * tanh(sqrt(jw tau)) / sqrt(jw tau)
      const rd = Math.max(1e-6, el.value);
      const tau = Math.max(1e-6, el.exponent ?? 0.5);
      const jwTau: ComplexNumber = { re: 0, im: w * tau };
      const arg = complexSqrt(jwTau);
      if (Math.abs(arg.re) < 1e-8 && Math.abs(arg.im) < 1e-8) {
        return { re: rd, im: 0 };
      }
      const tanhArg = complexTanh(arg);
      const div = complexDivide(tanhArg, arg);
      return { re: rd * div.re, im: rd * div.im };
    }
    case "Ws": {
      // Reflective / Intercalation short diffusion: Z = Rd * coth(sqrt(jw tau)) / sqrt(jw tau)
      const rd = Math.max(1e-6, el.value);
      const tau = Math.max(1e-6, el.exponent ?? 1.0);
      const jwTau: ComplexNumber = { re: 0, im: w * tau };
      const arg = complexSqrt(jwTau);
      if (Math.abs(arg.re) < 1e-8 && Math.abs(arg.im) < 1e-8) {
        return { re: rd / 3, im: -1 / (w * (tau / rd) + 1e-30) };
      }
      const cothArg = complexCoth(arg);
      const div = complexDivide(cothArg, arg);
      return { re: rd * div.re, im: rd * div.im };
    }
    case "TLM_open": {
      // Bisquert Open Transmission Line: Z_TLM = sqrt(R_ion * zeta) * coth(sqrt(R_ion / zeta))
      const rIon = Math.max(1e-6, el.value);
      const rCt = Math.max(1e-6, el.secondaryValue ?? 200.0);
      const alpha = Math.max(0.01, Math.min(1.0, el.exponent ?? 0.90));
      const qd = 1.5e-4;
      
      const phi = (alpha * Math.PI) / 2;
      const qwn = qd * Math.pow(w, alpha);
      const yCpe: ComplexNumber = { re: qwn * Math.cos(phi), im: qwn * Math.sin(phi) };
      const yInt: ComplexNumber = { re: 1 / rCt + yCpe.re, im: yCpe.im };
      const zeta = complexInvert(yInt);

      const ratio = complexDivide({ re: rIon, im: 0 }, zeta);
      const gammaL = complexSqrt(ratio);
      const zChar = complexSqrt(complexMultiply({ re: rIon, im: 0 }, zeta));

      if (Math.abs(gammaL.re) < 1e-8 && Math.abs(gammaL.im) < 1e-8) {
        return { re: rIon / 3 + zeta.re, im: zeta.im };
      }
      const cothVal = complexCoth(gammaL);
      return complexMultiply(zChar, cothVal);
    }
    case "TLM_short": {
      // Bisquert Short Transmission Line: Z_TLM = sqrt(R_ion * zeta) * tanh(sqrt(R_ion / zeta))
      const rIon = Math.max(1e-6, el.value);
      const rCt = Math.max(1e-6, el.secondaryValue ?? 150.0);
      const alpha = Math.max(0.01, Math.min(1.0, el.exponent ?? 0.92));
      const qd = 2.0e-4;

      const phi = (alpha * Math.PI) / 2;
      const qwn = qd * Math.pow(w, alpha);
      const yCpe: ComplexNumber = { re: qwn * Math.cos(phi), im: qwn * Math.sin(phi) };
      const yInt: ComplexNumber = { re: 1 / rCt + yCpe.re, im: yCpe.im };
      const zeta = complexInvert(yInt);

      const ratio = complexDivide({ re: rIon, im: 0 }, zeta);
      const gammaL = complexSqrt(ratio);
      const zChar = complexSqrt(complexMultiply({ re: rIon, im: 0 }, zeta));

      if (Math.abs(gammaL.re) < 1e-8 && Math.abs(gammaL.im) < 1e-8) {
        return zeta;
      }
      const tanhVal = complexTanh(gammaL);
      return complexMultiply(zChar, tanhVal);
    }
    case "G": {
      // Gerischer: Z = Rg / (1 + (jw tau)^alpha)^0.5
      const rg = Math.max(1e-6, el.value);
      const tg = Math.max(1e-6, el.exponent ?? 0.1);
      const alpha = 1.0;
      const jwTg: ComplexNumber = { re: 0, im: w * tg };
      const jwPow = complexPower(jwTg, alpha);
      const onePlus = complexAdd({ re: 1, im: 0 }, jwPow);
      const sqrtTerm = complexSqrt(onePlus);
      return complexDivide({ re: rg, im: 0 }, sqrtTerm);
    }
    case "CC": {
      // Cole-Cole: Z = R0 / (1 + (jw tau)^alpha)
      const r0 = Math.max(1e-6, el.value);
      const tau = Math.max(1e-12, el.exponent ?? 1e-4);
      const alpha = 0.85;
      const jwTau: ComplexNumber = { re: 0, im: w * tau };
      const jwPow = complexPower(jwTau, alpha);
      const denom = complexAdd({ re: 1, im: 0 }, jwPow);
      return complexDivide({ re: r0, im: 0 }, denom);
    }
    case "HN": {
      // Havriliak-Negami: Z = R0 / ((1 + (jw tau)^alpha)^beta)
      const r0 = Math.max(1e-6, el.value);
      const tau = Math.max(1e-12, el.exponent ?? 1e-4);
      const alpha = Math.max(0.01, Math.min(1.0, el.exponent ?? 0.82));
      const beta = Math.max(0.01, Math.min(1.0, el.secondaryValue ?? 0.75));
      const jwTau: ComplexNumber = { re: 0, im: w * tau };
      const inner = complexAdd({ re: 1, im: 0 }, complexPower(jwTau, alpha));
      const denom = complexPower(inner, beta);
      return complexDivide({ re: r0, im: 0 }, denom);
    }
    case "L": {
      const l = Math.max(1e-12, el.value);
      return { re: 0, im: w * l };
    }
    default:
      return { re: 1e-3, im: 0 };
  }
}

function calculateBranchImpedance(branch: CircuitBranch, omega: number): ComplexNumber {
  if (!branch.elements || branch.elements.length === 0) {
    return { re: 0, im: 0 };
  }

  if (branch.connection === "series") {
    let zTotal: ComplexNumber = { re: 0, im: 0 };
    for (const el of branch.elements) {
      const zEl = calculateElementImpedance(el, omega);
      zTotal = complexAdd(zTotal, zEl);
    }
    return zTotal;
  } else {
    const capElements = branch.elements.filter((e) => e.type === "C" || e.type === "CPE");
    const resAndDiffElements = branch.elements.filter((e) => e.type !== "C" && e.type !== "CPE");

    if (capElements.length > 0 && resAndDiffElements.length > 0) {
      let yCap: ComplexNumber = { re: 0, im: 0 };
      for (const cap of capElements) {
        const zCap = calculateElementImpedance(cap, omega);
        const ySingleCap = complexInvert(zCap);
        yCap = complexAdd(yCap, ySingleCap);
      }

      let zFaradaic: ComplexNumber = { re: 0, im: 0 };
      for (const el of resAndDiffElements) {
        const zEl = calculateElementImpedance(el, omega);
        zFaradaic = complexAdd(zFaradaic, zEl);
      }
      const yFaradaic = complexInvert(zFaradaic);
      const yTotal = complexAdd(yCap, yFaradaic);
      return complexInvert(yTotal);
    } else {
      let yTotal: ComplexNumber = { re: 0, im: 0 };
      for (const el of branch.elements) {
        const zEl = calculateElementImpedance(el, omega);
        const yEl = complexInvert(zEl);
        yTotal = complexAdd(yTotal, yEl);
      }
      return complexInvert(yTotal);
    }
  }
}

export function calculateCircuitEIS(
  topology: CircuitTopology,
  minFreq: number = 0.01,
  maxFreq: number = 100000,
  pointsPerDecade: number = 12
): EISFrequencyPoint[] {
  const points: EISFrequencyPoint[] = [];

  const logMin = Math.log10(minFreq);
  const logMax = Math.log10(maxFreq);
  const totalDecades = logMax - logMin;
  const totalPoints = Math.max(20, Math.round(totalDecades * pointsPerDecade));

  for (let i = 0; i <= totalPoints; i++) {
    const logF = logMin + (i / totalPoints) * (logMax - logMin);
    const f = Math.pow(10, logF);
    const omega = 2 * Math.PI * f;

    let zTotal: ComplexNumber = { re: 0, im: 0 };
    for (const branch of topology.branches) {
      const zBranch = calculateBranchImpedance(branch, omega);
      zTotal = complexAdd(zTotal, zBranch);
    }

    const zReal = zTotal.re;
    const zImag = zTotal.im;
    const minusZImag = -zImag;
    const zMag = Math.sqrt(zReal * zReal + zImag * zImag);
    const phaseDeg = (Math.atan2(zImag, zReal) * 180) / Math.PI;

    points.push({
      frequency: Number(f.toFixed(4)),
      omega: Number(omega.toFixed(4)),
      zReal: Number(zReal.toFixed(4)),
      zImag: Number(zImag.toFixed(4)),
      minusZImag: Number(Math.max(0, minusZImag).toFixed(4)),
      zMag: Number(zMag.toFixed(4)),
      phaseDeg: Number(phaseDeg.toFixed(2)),
      logFreq: Number(logF.toFixed(3)),
      logZMag: Number(Math.log10(Math.max(1e-4, zMag)).toFixed(3)),
    });
  }

  return points.sort((a, b) => b.frequency - a.frequency);
}

// =========================================================================
// 4. MAIN DRAG-AND-DROP EQUIVALENT CIRCUIT BUILDER COMPONENT
// =========================================================================

export function EquivalentCircuitBuilder() {
  // Active Circuit Topology
  const [activeTopology, setActiveTopology] = useState<CircuitTopology>(STANDARD_CIRCUIT_PRESETS[0]);
  const [selectedBranchId, setSelectedBranchId] = useState<string>(activeTopology.branches[0]?.id || "");
  const [selectedElementId, setSelectedElementId] = useState<string | null>(null);

  // Drag-and-drop state
  const [draggedItemType, setDraggedItemType] = useState<CircuitElementType | null>(null);
  const [draggedElementId, setDraggedElementId] = useState<string | null>(null);
  const [dragOverBranchId, setDragOverBranchId] = useState<string | null>(null);
  const [isDragOverNewSeries, setIsDragOverNewSeries] = useState(false);
  const [isDragOverNewParallel, setIsDragOverNewParallel] = useState(false);

  // Modals & Libraries
  const [isLibraryModalOpen, setIsLibraryModalOpen] = useState(false);
  const [isCNLSModalOpen, setIsCNLSModalOpen] = useState(false);
  useEscapeToClose(isCNLSModalOpen, () => setIsCNLSModalOpen(false));
  const [copiedCode, setCopiedCode] = useState(false);

  // Mode Selection: "designer" vs "preset-library" vs "fitter" vs "synthetic-stress"
  const [activeTab, setActiveTab] = useState<"designer" | "preset-library" | "automated-fit" | "synthetic-stress">("designer");

  // Frequency Sweep Settings
  const [minFreq, setMinFreq] = useState<number>(0.01);
  const [maxFreq, setMaxFreq] = useState<number>(100000);
  const [viewMode, setViewMode] = useState<"nyquist" | "bode-mag" | "bode-phase" | "residuals" | "drt">("nyquist");
  const [visualizerEngine, setVisualizerEngine] = useState<"plotly" | "recharts">("plotly");

  // =========================================================================
  // AUTOMATED PARAMETER FITTING STATE (Python Backend)
  // =========================================================================
  const [activeDataset, setActiveDataset] = useState<ExperimentalEISDataset>(EXPERIMENTAL_BENCHMARKS[0]);
  const [weighting, setWeighting] = useState<WeightingMethod>("modulus");
  const [maxIterations, setMaxIterations] = useState<number>(80);
  const fitTask = useInputBoundTask<{ report: CNLSFitReport; drtCurve: any; global: boolean }>(
    JSON.stringify([activeTopology, activeDataset, weighting, maxIterations]));
  const fitReport = fitTask.data?.report ?? null;
  const drtCurveData = fitTask.data?.drtCurve ?? null;
  const fitError = fitTask.error;
  const isFitting = fitTask.pending === "local";
  const isAutoFitting = fitTask.pending === "global";
  const autoFitSummary = fitTask.data?.global && fitReport ? {
    computeTimeMs: fitReport.executionTimeMs, reducedChiSquare: fitReport.reducedChiSquare,
    rSquared: fitReport.rSquared,
  } : null;

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Generate CDC Boukamp Circuit String
  const generatedCdcString = useMemo(() => {
    const branchStrings = activeTopology.branches.map((b) => {
      if (b.connection === "series") {
        return b.elements.map((el) => `${el.name}`).join("");
      } else {
        const elNames = b.elements.map((el) => el.name).join("");
        return `(${elNames})`;
      }
    });
    return branchStrings.join("");
  }, [activeTopology]);

  // Calculate EIS Frequency Response for Model
  const eisData = useMemo(() => {
    return calculateCircuitEIS(activeTopology, minFreq, maxFreq, 12);
  }, [activeTopology, minFreq, maxFreq]);

  // Selected Element Lookup
  const selectedElement = useMemo(() => {
    if (!selectedElementId) return null;
    for (const b of activeTopology.branches) {
      const el = b.elements.find((e) => e.id === selectedElementId);
      if (el) return { element: el, branchId: b.id };
    }
    return null;
  }, [activeTopology, selectedElementId]);

  // Derived Metrics
  const circuitMetrics = useMemo(() => {
    if (eisData.length === 0) return { r0: "0", rTotal: "0", polarizationResistance: "0", fPeak: "0", tau_ms: "0", maxPhaseDeg: "0" };
    const highFreqPt = eisData[0];
    const lowFreqPt = eisData[eisData.length - 1];
    const r0 = highFreqPt?.zReal || 0;
    const rTotal = lowFreqPt?.zReal || 0;

    let maxMinusZ = -1;
    let fPeak = 1000;
    let minPhase = 0;
    for (const pt of eisData) {
      if (pt.minusZImag > maxMinusZ) {
        maxMinusZ = pt.minusZImag;
        fPeak = pt.frequency;
      }
      if (pt.phaseDeg < minPhase) {
        minPhase = pt.phaseDeg;
      }
    }

    return {
      r0: r0.toFixed(3),
      rTotal: rTotal.toFixed(3),
      polarizationResistance: (rTotal - r0).toFixed(3),
      fPeak: fPeak > 1000 ? `${(fPeak / 1000).toFixed(2)} kHz` : `${fPeak.toFixed(2)} Hz`,
      tau_ms: ((1 / (2 * Math.PI * fPeak)) * 1000).toFixed(2),
      maxPhaseDeg: Math.abs(minPhase).toFixed(1),
    };
  }, [eisData]);

  // Merged Chart Data for Overlaid Experimental + Model Curves
  const chartPoints = useMemo<Array<{
    frequency: number; logFreq: number;
    modelZReal: number; modelMinusZImag: number; modelZMag: number; modelPhaseDeg: number;
    expZReal?: number; expMinusZImag?: number; expZMag?: number; expPhaseDeg?: number;
    resZRealPct?: number; resZImagPct?: number;
  }>>(() => {
    if (activeTab !== "automated-fit" && !fitReport) {
      return eisData.map((d) => ({
        ...d,
        modelZReal: d.zReal,
        modelMinusZImag: d.minusZImag,
        modelZMag: d.zMag,
        modelPhaseDeg: d.phaseDeg,
      }));
    }

    // Combine experimental points with model calculated points
    const expPoints = activeDataset.points.map((pt) => {
      // Find closest model frequency point
      const omega = 2 * Math.PI * pt.frequency;
      let zTotal: ComplexNumber = { re: 0, im: 0 };
      for (const branch of (fitReport?.topology ?? activeTopology).branches) {
        zTotal = complexAdd(zTotal, calculateBranchImpedance(branch, omega));
      }
      const modelMinusZImag = -zTotal.im;
      const modelZMag = Math.sqrt(zTotal.re ** 2 + zTotal.im ** 2);
      const modelPhase = (Math.atan2(zTotal.im, zTotal.re) * 180) / Math.PI;

      const resRePct = ((zTotal.re - pt.zReal) / Math.max(1e-6, pt.zMag)) * 100;
      const resImPct = ((modelMinusZImag - pt.minusZImag) / Math.max(1e-6, pt.zMag)) * 100;

      return {
        frequency: pt.frequency,
        logFreq: Number(Math.log10(pt.frequency).toFixed(3)),
        expZReal: pt.zReal,
        expMinusZImag: pt.minusZImag,
        expZMag: pt.zMag,
        expPhaseDeg: pt.phaseDeg,
        modelZReal: Number(zTotal.re.toFixed(4)),
        modelMinusZImag: Number(Math.max(0, modelMinusZImag).toFixed(4)),
        modelZMag: Number(modelZMag.toFixed(4)),
        modelPhaseDeg: Number(modelPhase.toFixed(2)),
        resZRealPct: Number(resRePct.toFixed(2)),
        resZImagPct: Number(resImPct.toFixed(2)),
      };
    });

    return expPoints.sort((a, b) => b.frequency - a.frequency);
  }, [activeTab, fitReport, eisData, activeDataset, activeTopology]);

  // =========================================================================
  // DRAG AND DROP HANDLERS
  // =========================================================================

  const handleDragStartFromPalette = (e: React.DragEvent, type: CircuitElementType) => {
    setDraggedItemType(type);
    setDraggedElementId(null);
    e.dataTransfer.setData("application/x-circuit-element-type", type);
    e.dataTransfer.effectAllowed = "copy";
  };

  const handleDragStartFromCircuit = (e: React.DragEvent, elementId: string, branchId: string) => {
    setDraggedElementId(elementId);
    setDraggedItemType(null);
    e.dataTransfer.setData("application/x-circuit-element-id", elementId);
    e.dataTransfer.setData("application/x-circuit-source-branch", branchId);
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDragOver = (e: React.DragEvent, branchId?: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = draggedElementId ? "move" : "copy";
    if (branchId) {
      setDragOverBranchId(branchId);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDropOnBranch = (e: React.DragEvent, targetBranchId: string) => {
    e.preventDefault();
    setDragOverBranchId(null);

    // If moving existing element
    if (draggedElementId) {
      const sourceBranchId = e.dataTransfer.getData("application/x-circuit-source-branch");
      if (!sourceBranchId) return;

      setActiveTopology((prev) => {
        let movedElement: CircuitElement | null = null;
        const newBranches = prev.branches.map((b) => {
          if (b.id === sourceBranchId) {
            const el = b.elements.find((e) => e.id === draggedElementId);
            if (el) movedElement = { ...el };
            return { ...b, elements: b.elements.filter((e) => e.id !== draggedElementId) };
          }
          return b;
        });

        if (movedElement) {
          return {
            ...prev,
            branches: newBranches.map((b) => (b.id === targetBranchId ? { ...b, elements: [...b.elements, movedElement!] } : b)),
          };
        }
        return prev;
      });

      setSelectedBranchId(targetBranchId);
      setDraggedElementId(null);
      return;
    }

    // If dropping new element from palette
    const type = (e.dataTransfer.getData("application/x-circuit-element-type") || draggedItemType) as CircuitElementType;
    if (type) {
      addElementToBranch(targetBranchId, type);
    }
    setDraggedItemType(null);
  };

  const handleDropNewBranch = (e: React.DragEvent, connection: BlockConnection) => {
    e.preventDefault();
    setIsDragOverNewSeries(false);
    setIsDragOverNewParallel(false);

    const type = (e.dataTransfer.getData("application/x-circuit-element-type") || draggedItemType || "R") as CircuitElementType;
    const newBranchId = `b-${Date.now()}`;
    const newEl = createDefaultElement(type, activeTopology.branches.length + 1);

    const newBranch: CircuitBranch = {
      id: newBranchId,
      connection,
      name: connection === "series" ? `Series Stage ${activeTopology.branches.length + 1}` : `Parallel Loop ${activeTopology.branches.length + 1}`,
      elements: [newEl],
    };

    setActiveTopology((prev) => ({
      ...prev,
      branches: [...prev.branches, newBranch],
    }));
    setSelectedBranchId(newBranchId);
    setSelectedElementId(newEl.id);
    setDraggedItemType(null);
    setDraggedElementId(null);
  };

  // Helper to create default element
  const createDefaultElement = (type: CircuitElementType, index: number): CircuitElement => {
    const paletteDef = ELEMENT_PALETTE.find((p) => p.type === type) || ELEMENT_PALETTE[0];
    const newElId = `el-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
    return {
      id: newElId,
      type,
      name: `${paletteDef.name}${index > 1 ? `_${index}` : ""}`,
      label: paletteDef.label,
      value: paletteDef.defaultValue,
      unit: paletteDef.defaultUnit,
      exponent: paletteDef.defaultExponent,
      isFixed: false,
      description: paletteDef.description,
    };
  };

  const addElementToBranch = (branchId: string, type: CircuitElementType) => {
    const newEl = createDefaultElement(type, activeTopology.branches.length + 1);
    setActiveTopology((prev) => ({
      ...prev,
      branches: prev.branches.map((b) => (b.id === branchId ? { ...b, elements: [...b.elements, newEl] } : b)),
    }));
    setSelectedElementId(newEl.id);
    setSelectedBranchId(branchId);
  };

  // Preset Selection
  const handleSelectPreset = (preset: CircuitTopology) => {
    setActiveTopology(JSON.parse(JSON.stringify(preset)));
    setSelectedBranchId(preset.branches[0]?.id || "");
    setSelectedElementId(null);
  };

  // Update Element Parameters
  const handleUpdateElement = (branchId: string, elementId: string, updates: Partial<CircuitElement>) => {
    setActiveTopology((prev) => ({
      ...prev,
      branches: prev.branches.map((b) =>
        b.id === branchId
          ? {
              ...b,
              elements: b.elements.map((el) => (el.id === elementId ? { ...el, ...updates } : el)),
            }
          : b
      ),
    }));
  };

  // Remove element from branch
  const handleRemoveElement = (branchId: string, elementId: string) => {
    setActiveTopology((prev) => ({
      ...prev,
      branches: prev.branches.map((b) =>
        b.id === branchId
          ? {
              ...b,
              elements: b.elements.filter((el) => el.id !== elementId),
            }
          : b
      ),
    }));
    if (selectedElementId === elementId) {
      setSelectedElementId(null);
    }
  };

  // Remove entire branch
  const handleRemoveBranch = (branchId: string) => {
    if (activeTopology.branches.length <= 1) return;
    setActiveTopology((prev) => ({
      ...prev,
      branches: prev.branches.filter((b) => b.id !== branchId),
    }));
    setSelectedBranchId(activeTopology.branches[0]?.id || "");
  };

  // =========================================================================
  // AUTOMATED PARAMETER FITTING WITH PYTHON BACKEND
  // =========================================================================

  const runFit = async (global: boolean) => {
    const request = fitTask.begin(global ? "global" : "local");
    try {
      const initialParams = extractAdjustableParameters(activeTopology);
      const result = await requestPythonAnalysis(global ? "/api/python/cnls-autofit" : "/api/python/cnls-fit",
        JSON.stringify({
          action: global ? "auto_fit" : "fit", topologyId: activeTopology.id,
          topology: activeTopology, points: activeDataset.points, parameters: initialParams, weighting,
          ...(global ? { maxGenerations: Math.max(60, maxIterations), populationSize: 40, polishLM: true }
            : { maxIterations }),
        }), request.signal);
      if (!request.isCurrent()) return;
      const report = normalizePythonCnlsReport(result, activeTopology, activeDataset, weighting, initialParams);
      request.publish({ report, drtCurve: null, global });
      try {
        const drt = await requestPythonAnalysis("/api/python/battery-corrosion-eis", JSON.stringify({
          action: "drt", frequencies: activeDataset.points.map(p => p.frequency),
          zReal: activeDataset.points.map(p => p.zReal), zImag: activeDataset.points.map(p => p.zImag),
          lambdaReg: 1e-3, numTau: 50,
        }), request.signal);
        if (drt.drtCurve) request.publish({ report, drtCurve: drt.drtCurve, global });
      } catch (error) {
        if (request.isCurrent()) console.warn("DRT unavailable:", error);
      }
    } catch (error) {
      request.fail(error);
    } finally {
      request.finish();
    }
  };
  const handleRunAutoFit = () => runFit(true);
  const handleRunPythonFit = () => runFit(false);

  // Apply Fitted Values directly to the Drag-and-Drop Circuit
  const handleApplyFittedParameters = () => {
    if (!fitReport || !fitReport.parameters) return;

    setActiveTopology(fitReport.topology);
  };

  // File Upload Handler
  const handleFileUpload = (file: File) => {
    const request = fitTask.begin('upload');
    const reader = new FileReader();
    request.signal.addEventListener('abort', () => reader.abort(), { once: true });
    reader.onerror = () => request.fail(new Error('Failed to read EIS file.'));
    reader.onload = (e) => {
      if (!request.isCurrent()) return;
      try {
        const text = e.target?.result as string;
        if (!text) return;
        const parsed = parseEISFile(text, file.name);
        setActiveDataset(parsed);
      } catch (err: any) {
        request.fail(new Error(`Failed to parse EIS file: ${err.message}`));
      } finally {
        request.finish();
      }
    };
    reader.readAsText(file);
  };

  // Export CSV
  const exportCsv = () => {
    const headers = "Frequency_Hz,Omega_rad_s,Z_Real_Ohm,Minus_Z_Imag_Ohm,Z_Magnitude_Ohm,Phase_Deg\n";
    const rows = eisData.map((d) => `${d.frequency},${d.omega},${d.zReal},${d.minusZImag},${d.zMag},${d.phaseDeg}`).join("\n");
    const blob = new Blob([headers + rows], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `EIS_Model_${activeTopology.id}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-5 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#162032] pb-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-lg bg-sky-500/10 border border-sky-400/30 text-sky-400">
                <Cpu className="w-5 h-5" />
              </div>
              <h2 className="text-base font-bold text-white font-mono uppercase tracking-wider flex items-center gap-2">
                <span>Drag-and-Drop Equivalent Circuit Modeler &amp; Python CNLS Fitter</span>
              </h2>
              <span className="px-2 py-0.5 rounded bg-sky-500/10 border border-sky-400/30 text-sky-300 text-[10px] font-mono font-bold">
                BOUKAMP CDC / CPYTHON 3.10+
              </span>
            </div>
            <p className="text-xs text-slate-400 font-mono">
              Build arbitrary electrochemical circuit topologies with Resistors (R), Capacitors (C), Constant Phase Elements (CPE/Q), Warburg (W/Ws), Inductors (L), &amp; Gerischer (G) and perform automated CNLS parameter fitting against experimental Nyquist data.
            </p>
          </div>

          {/* Mode Switcher & Library */}
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center bg-[#050810] p-1 rounded-xl border border-[#1e2d46]">
              <button
                type="button"
                onClick={() => setActiveTab("designer")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all ${
                  activeTab === "designer"
                    ? "bg-sky-500/20 text-sky-300 border border-sky-400/50 shadow-[0_0_10px_rgba(56,189,248,0.3)]"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <SlidersHorizontal className="w-3.5 h-3.5" />
                <span>Circuit Designer</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("preset-library")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all ${
                  activeTab === "preset-library"
                    ? "bg-purple-500/20 text-purple-300 border border-purple-400/50 shadow-[0_0_10px_rgba(168,85,247,0.3)]"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <BookOpen className="w-3.5 h-3.5 text-purple-400" />
                <span>Preset Circuit Library</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("automated-fit")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all ${
                  activeTab === "automated-fit"
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-400/50 shadow-[0_0_10px_rgba(16,185,129,0.3)]"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Activity className="w-3.5 h-3.5 text-emerald-400" />
                <span>Automated Data Fitting</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("synthetic-stress")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all ${
                  activeTab === "synthetic-stress"
                    ? "bg-amber-500/20 text-amber-300 border border-amber-400/50 shadow-[0_0_10px_rgba(245,158,11,0.3)]"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <RadioTower className="w-3.5 h-3.5 text-amber-400" />
                <span>⚡ Synthetic Noise &amp; Stress Test</span>
              </button>
            </div>

            <button
              type="button"
              onClick={() => setIsLibraryModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#0d1527] border border-[#1e2d46] hover:border-sky-400/50 text-xs font-mono text-slate-300 hover:text-sky-300 transition-all"
            >
              <FolderOpen className="w-3.5 h-3.5 text-sky-400" />
              <span>Full Catalog ({EXTENDED_CIRCUIT_LIBRARY.length} Models)</span>
            </button>
          </div>
        </div>

        {/* Quick Preset Selector Dropdown Menu & CDC Code Bar */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-center bg-[#050810]/60 p-3 rounded-xl border border-[#162032]">
          <div className="lg:col-span-8 flex flex-wrap items-center gap-2.5">
            {/* Categorized Dropdown Menu */}
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono text-sky-400 font-bold whitespace-nowrap flex items-center gap-1">
                <BookOpen className="w-3.5 h-3.5" />
                Preset Dropdown:
              </span>
              <select
                value={EXTENDED_CIRCUIT_LIBRARY.some((m) => m.id === activeTopology.id) ? activeTopology.id : ""}
                onChange={(e) => {
                  const doc = EXTENDED_CIRCUIT_LIBRARY.find((m) => m.id === e.target.value);
                  if (doc) {
                    handleSelectPreset(doc.topology);
                  }
                }}
                className="bg-[#0c1424] border border-[#1e2d46] hover:border-sky-400 focus:border-sky-400 rounded-lg px-2.5 py-1 text-xs font-mono text-slate-200 focus:outline-none transition-all cursor-pointer"
              >
                <option value="" disabled>Select Model to Load...</option>
                <optgroup label="── Battery & Intercalation ──">
                  {EXTENDED_CIRCUIT_LIBRARY.filter((m) => m.category === "battery").map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} [{m.cdcNotation}]
                    </option>
                  ))}
                </optgroup>
                <optgroup label="── Corrosion & Passivity ──">
                  {EXTENDED_CIRCUIT_LIBRARY.filter((m) => m.category === "corrosion").map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} [{m.cdcNotation}]
                    </option>
                  ))}
                </optgroup>
                <optgroup label="── Protective Coatings ──">
                  {EXTENDED_CIRCUIT_LIBRARY.filter((m) => m.category === "coating").map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} [{m.cdcNotation}]
                    </option>
                  ))}
                </optgroup>
                <optgroup label="── Solid-State Ceramics ──">
                  {EXTENDED_CIRCUIT_LIBRARY.filter((m) => m.category === "solid-state").map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} [{m.cdcNotation}]
                    </option>
                  ))}
                </optgroup>
                <optgroup label="── Fuel Cells & MEA ──">
                  {EXTENDED_CIRCUIT_LIBRARY.filter((m) => m.category === "fuel-cell").map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} [{m.cdcNotation}]
                    </option>
                  ))}
                </optgroup>
              </select>
            </div>

            {/* Quick 1-Click Pills */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 scrollbar-thin">
              {STANDARD_CIRCUIT_PRESETS.slice(0, 4).map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => handleSelectPreset(preset)}
                  className={`px-2 py-0.5 rounded text-[11px] font-mono transition-all whitespace-nowrap border ${
                    activeTopology.id === preset.id
                      ? "bg-sky-500/20 border-sky-400 text-sky-200 font-bold shadow-[0_0_8px_rgba(56,189,248,0.2)]"
                      : "bg-[#090e18] border-[#162032] text-slate-400 hover:border-slate-700 hover:text-slate-200"
                  }`}
                >
                  {preset.name}
                </button>
              ))}
            </div>
          </div>

          {/* CDC Code Display */}
          <div className="lg:col-span-4 flex items-center justify-between bg-[#090e18] border border-[#1e2d46] rounded-xl px-3 py-1.5">
            <div className="flex items-center gap-2">
              <Code className="w-3.5 h-3.5 text-sky-400" />
              <span className="text-[10px] font-mono text-slate-400">CDC:</span>
              <span className="text-xs font-mono font-bold text-sky-300">{generatedCdcString || "R(CR)"}</span>
            </div>
            <button
              type="button"
              onClick={() => {
                navigator.clipboard.writeText(generatedCdcString);
                setCopiedCode(true);
                setTimeout(() => setCopiedCode(false), 2000);
              }}
              className="p-1 rounded text-slate-400 hover:text-sky-300 hover:bg-sky-500/10"
              title="Copy CDC Code"
            >
              {copiedCode ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      {activeTab === "preset-library" ? (
        <div className="w-full">
          <PresetCircuitLibraryPanel
            currentTopology={activeTopology}
            onLoadTopology={(topo) => {
              handleSelectPreset(topo);
              setActiveTab("designer");
            }}
            onRunAutoFit={(topo) => {
              handleSelectPreset(topo);
              setActiveTab("automated-fit");
            }}
          />
        </div>
      ) : activeTab === "synthetic-stress" ? (
        <div className="w-full">
          <SyntheticNoiseStressStudio
            initialTopology={activeTopology}
            onExportToCNLS={(dataset, topo) => {
              setActiveDataset(dataset);
              setActiveTopology(topo);
              setActiveTab("automated-fit");
            }}
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Drag & Drop Circuit Builder & Element Inspector */}
          <div className="lg:col-span-7 space-y-6">
          {/* 1. DRAGGABLE ELEMENT TOOLBOX */}
          <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-[#162032] pb-2">
              <span className="text-xs font-bold text-white font-mono uppercase tracking-wider flex items-center gap-2">
                <GripVertical className="w-4 h-4 text-sky-400" />
                Element Toolbox (Drag onto Circuit Stages)
              </span>
              <span className="text-[10px] font-mono text-slate-500">Drag or Click to Add</span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
              {ELEMENT_PALETTE.map((p) => (
                <div
                  key={p.type}
                  draggable={true}
                  onDragStart={(e) => handleDragStartFromPalette(e, p.type)}
                  onClick={() => selectedBranchId && addElementToBranch(selectedBranchId, p.type)}
                  className={`p-2.5 rounded-xl border bg-gradient-to-b ${p.color} cursor-grab active:cursor-grabbing hover:scale-[1.03] transition-all text-center space-y-1 select-none shadow-sm`}
                  title={`${p.description} (Drag onto a stage or click to append)`}
                >
                  <div className="text-base font-bold font-mono">{p.glyph}</div>
                  <div className="text-[10px] font-mono font-bold truncate text-slate-200">{p.type}</div>
                  <div className="text-[9px] text-slate-400 font-mono truncate">{p.defaultUnit}</div>
                </div>
              ))}
            </div>
          </div>

          {/* 2. INTERACTIVE CIRCUIT SCHEMATIC & STAGE DROPZONES */}
          <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between border-b border-[#162032] pb-3 gap-2">
              <div className="flex items-center gap-2">
                <Sliders className="w-4 h-4 text-sky-400" />
                <span className="text-xs font-bold text-white font-mono uppercase tracking-wider">
                  Circuit Stages &amp; Topology Schematic
                </span>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  disabled={isAutoFitting || isFitting}
                  onClick={handleRunAutoFit}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gradient-to-r from-amber-500/20 via-orange-500/20 to-rose-500/20 border border-amber-400/50 hover:border-amber-300 text-xs font-mono font-bold text-amber-300 shadow-[0_0_12px_rgba(245,158,11,0.2)] transition-all disabled:opacity-50 cursor-pointer"
                  title="Run Python Differential Evolution global optimization to automatically estimate all circuit parameters from experimental Nyquist data"
                >
                  {isAutoFitting ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin text-amber-400" />
                      <span>Auto-Fitting (DE)...</span>
                    </>
                  ) : (
                    <>
                      <Zap className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
                      <span>⚡ One-Click Auto-Fit</span>
                    </>
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => handleDropNewBranch({ preventDefault: () => {} } as any, "series")}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-sky-500/10 border border-sky-400/30 hover:bg-sky-500/20 text-[11px] font-mono text-sky-300"
                >
                  <Plus className="w-3 h-3" />
                  <span>+ Series Stage</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleDropNewBranch({ preventDefault: () => {} } as any, "parallel")}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-purple-500/10 border border-purple-400/30 hover:bg-purple-500/20 text-[11px] font-mono text-purple-300"
                >
                  <Plus className="w-3 h-3" />
                  <span>+ Parallel Loop</span>
                </button>
              </div>
            </div>

            {/* Stages List & Visual Rails */}
            <div className="space-y-3">
              {activeTopology.branches.map((branch, bIdx) => {
                const isSelectedBranch = selectedBranchId === branch.id;
                const isDragOver = dragOverBranchId === branch.id;

                return (
                  <div
                    key={branch.id}
                    onDragOver={(e) => handleDragOver(e, branch.id)}
                    onDragLeave={handleDragLeave}
                    onDrop={(e) => handleDropOnBranch(e, branch.id)}
                    onClick={() => setSelectedBranchId(branch.id)}
                    className={`p-4 rounded-xl border transition-all ${
                      isDragOver
                        ? "bg-sky-500/15 border-sky-400 shadow-[0_0_16px_rgba(56,189,248,0.4)]"
                        : isSelectedBranch
                        ? "bg-[#0b1324] border-sky-400/50 shadow-md"
                        : "bg-[#050810] border-[#162032] hover:border-slate-700"
                    }`}
                  >
                    {/* Stage Header */}
                    <div className="flex items-center justify-between border-b border-[#162032] pb-2 mb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                          STAGE {bIdx + 1}
                        </span>
                        <span className="text-xs font-mono font-bold text-slate-200">{branch.name}</span>
                        <span
                          className={`text-[9px] font-mono px-1.5 py-0.2 rounded font-bold uppercase ${
                            branch.connection === "series" ? "bg-sky-500/20 text-sky-300 border border-sky-400/30" : "bg-purple-500/20 text-purple-300 border border-purple-400/30"
                          }`}
                        >
                          {branch.connection === "series" ? "Series Flow (Z = ∑ Zi)" : "Parallel Loop (1/Z = ∑ 1/Zi)"}
                        </span>
                      </div>

                      <div className="flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRemoveBranch(branch.id);
                          }}
                          disabled={activeTopology.branches.length <= 1}
                          className="p-1 rounded text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 disabled:opacity-30"
                          title="Remove Stage"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    {/* Circuit Elements in this stage */}
                    <div className="flex items-center gap-2 flex-wrap min-h-[52px] p-2 rounded-lg bg-[#020408] border border-dashed border-[#1e2d46]">
                      {branch.elements.length === 0 ? (
                        <div className="w-full text-center py-2 text-xs font-mono text-slate-500">
                          Drop an element here (R, C, CPE, W, L)
                        </div>
                      ) : (
                        branch.elements.map((el, eIdx) => {
                          const isElSelected = selectedElementId === el.id;
                          const paletteDef = ELEMENT_PALETTE.find((p) => p.type === el.type);

                          return (
                            <div
                              key={el.id}
                              draggable={true}
                              onDragStart={(e) => handleDragStartFromCircuit(e, el.id, branch.id)}
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedElementId(el.id);
                                setSelectedBranchId(branch.id);
                              }}
                              className={`flex items-center gap-2 px-3 py-2 rounded-xl border cursor-grab active:cursor-grabbing transition-all ${
                                isElSelected
                                  ? "bg-gradient-to-r from-sky-500/20 to-blue-500/20 border-sky-400 text-white shadow-[0_0_12px_rgba(56,189,248,0.3)]"
                                  : "bg-[#090e18] border-[#1e2d46] text-slate-300 hover:border-slate-600"
                              }`}
                            >
                              <div className="font-mono font-bold text-xs text-sky-400">{el.name}</div>
                              <div className="text-[11px] font-mono text-slate-300">
                                {el.value < 0.001
                                  ? el.value.toExponential(2)
                                  : el.value.toLocaleString(undefined, { maximumFractionDigits: 3 })}{" "}
                                {el.unit}
                              </div>
                              {el.type === "CPE" && (
                                <span className="text-[9px] font-mono px-1 rounded bg-purple-500/20 text-purple-300">
                                  n={el.exponent ?? 0.9}
                                </span>
                              )}
                              {el.isFixed && (
                                <span title="Locked during CNLS optimization"><Lock className="w-3 h-3 text-amber-400" aria-label="Locked during CNLS optimization" /></span>
                              )}
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleRemoveElement(branch.id, el.id);
                                }}
                                className="p-0.5 rounded text-slate-500 hover:text-rose-400"
                              >
                                <Trash2 className="w-3 h-3" />
                              </button>
                            </div>
                          );
                        })
                      )}

                      {/* Stage Inline Dropzone */}
                      <div className="text-[10px] font-mono text-slate-600 px-2 py-1 border border-dashed border-[#162032] rounded flex items-center gap-1">
                        <Plus className="w-3 h-3" /> Drop element to append
                      </div>
                    </div>
                  </div>
                );
              })}

              {/* Drop Zones for New Stages */}
              <div className="grid grid-cols-2 gap-3 pt-2">
                <div
                  onDragOver={(e) => {
                    e.preventDefault();
                    setIsDragOverNewSeries(true);
                  }}
                  onDragLeave={() => setIsDragOverNewSeries(false)}
                  onDrop={(e) => handleDropNewBranch(e, "series")}
                  className={`p-3 rounded-xl border border-dashed text-center transition-all cursor-pointer ${
                    isDragOverNewSeries
                      ? "bg-sky-500/20 border-sky-400 text-sky-200"
                      : "bg-[#050810]/60 border-[#1e2d46] text-slate-500 hover:border-slate-600"
                  }`}
                >
                  <div className="text-xs font-mono font-bold flex items-center justify-center gap-1">
                    <Plus className="w-3.5 h-3.5" /> Drop to Create Series Stage
                  </div>
                </div>

                <div
                  onDragOver={(e) => {
                    e.preventDefault();
                    setIsDragOverNewParallel(true);
                  }}
                  onDragLeave={() => setIsDragOverNewParallel(false)}
                  onDrop={(e) => handleDropNewBranch(e, "parallel")}
                  className={`p-3 rounded-xl border border-dashed text-center transition-all cursor-pointer ${
                    isDragOverNewParallel
                      ? "bg-purple-500/20 border-purple-400 text-purple-200"
                      : "bg-[#050810]/60 border-[#1e2d46] text-slate-500 hover:border-slate-600"
                  }`}
                >
                  <div className="text-xs font-mono font-bold flex items-center justify-center gap-1">
                    <Plus className="w-3.5 h-3.5" /> Drop to Create Parallel Loop
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* 3. COMPONENT PARAMETER INSPECTOR */}
          {selectedElement ? (
            <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-[#162032] pb-3">
                <div className="flex items-center gap-2">
                  <SlidersHorizontal className="w-4 h-4 text-sky-400" />
                  <span className="text-xs font-bold text-white font-mono uppercase tracking-wider">
                    Element Inspector: {selectedElement.element.name} ({selectedElement.element.label})
                  </span>
                </div>

                <button
                  type="button"
                  onClick={() =>
                    handleUpdateElement(selectedElement.branchId, selectedElement.element.id, {
                      isFixed: !selectedElement.element.isFixed,
                    })
                  }
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-mono font-bold border ${
                    selectedElement.element.isFixed
                      ? "bg-amber-500/20 text-amber-300 border-amber-400/50"
                      : "bg-[#050810] text-slate-400 border-[#1e2d46] hover:text-slate-200"
                  }`}
                >
                  {selectedElement.element.isFixed ? <Lock className="w-3 h-3 text-amber-400" /> : <Unlock className="w-3 h-3" />}
                  <span>{selectedElement.element.isFixed ? "Locked in Fit" : "Free Parameter"}</span>
                </button>
              </div>

              {/* Value Controls */}
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs text-slate-300 font-mono">Element Name / Label:</label>
                    <input
                      type="text"
                      value={selectedElement.element.name}
                      onChange={(e) =>
                        handleUpdateElement(selectedElement.branchId, selectedElement.element.id, {
                          name: e.target.value,
                        })
                      }
                      className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-400"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs text-slate-300 font-mono">
                      Magnitude Value ({selectedElement.element.unit}):
                    </label>
                    <input
                      type="number"
                      step="any"
                      value={selectedElement.element.value}
                      onChange={(e) =>
                        handleUpdateElement(selectedElement.branchId, selectedElement.element.id, {
                          value: parseFloat(e.target.value) || 1e-6,
                        })
                      }
                      className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-400"
                    />
                  </div>
                </div>

                {/* CPE Exponent Slider if CPE */}
                {selectedElement.element.type === "CPE" && (
                  <div className="p-3.5 rounded-xl bg-[#050810] border border-[#162032] space-y-2">
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-slate-300">Phase Exponent (n):</span>
                      <span className="text-purple-400 font-bold">{selectedElement.element.exponent ?? 0.88}</span>
                    </div>
                    <input
                      type="range"
                      min="0.10"
                      max="1.00"
                      step="0.01"
                      value={selectedElement.element.exponent ?? 0.88}
                      onChange={(e) =>
                        handleUpdateElement(selectedElement.branchId, selectedElement.element.id, {
                          exponent: parseFloat(e.target.value),
                        })
                      }
                      className="w-full h-1.5 bg-[#162032] rounded-lg appearance-none cursor-pointer accent-purple-400"
                    />
                    <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                      <span>0.50 (Warburg / Diffusion)</span>
                      <span>0.80-0.95 (Porous Electrode)</span>
                      <span>1.00 (Ideal Capacitor)</span>
                    </div>
                  </div>
                )}

                {/* Element Description */}
                <p className="text-xs text-slate-400 font-mono bg-[#050810] p-3 rounded-xl border border-[#162032]">
                  <span className="text-sky-400 font-bold">Physical Role: </span>
                  {selectedElement.element.description}
                </p>
              </div>
            </div>
          ) : (
            <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-6 text-center space-y-2">
              <MousePointerClick className="w-8 h-8 text-slate-600 mx-auto" />
              <div className="text-xs font-mono text-slate-400">
                Click any component in the schematic above to inspect and edit its physical parameters.
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Visualizer & Automated Parameter Fitting */}
        <div className="lg:col-span-5 space-y-6">
          {/* 1. SPECTRAL PLOTS (PLOTLY INTERACTIVE SUITE OR RECHARTS) */}
          <div className="space-y-4">
            <div className="flex items-center justify-between bg-[#090e18] border border-[#1e2d46] rounded-xl px-4 py-2">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-sky-400" />
                <span className="text-xs font-bold text-white font-mono uppercase tracking-wider">
                  Real-Time EIS Visualizer
                </span>
              </div>

              {/* Engine Switcher */}
              <div className="flex items-center gap-1 bg-[#050810] p-0.5 rounded-lg border border-[#1e2d46]">
                <button
                  type="button"
                  onClick={() => setVisualizerEngine("plotly")}
                  className={`px-2.5 py-1 rounded-md text-xs font-mono font-bold transition-all ${
                    visualizerEngine === "plotly"
                      ? "bg-sky-500/20 text-sky-300 border border-sky-400/40 shadow-sm"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                  title="Interactive Plotly with WebGL, 3D trajectory, 1:1 aspect, and real-time Python sync"
                >
                  Plotly Engine
                </button>
                <button
                  type="button"
                  onClick={() => setVisualizerEngine("recharts")}
                  className={`px-2.5 py-1 rounded-md text-xs font-mono transition-all ${
                    visualizerEngine === "recharts"
                      ? "bg-sky-500/20 text-sky-300 border border-sky-400/40 shadow-sm"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                  title="Classic chart view"
                >
                  Classic
                </button>
              </div>
            </div>

            {visualizerEngine === "plotly" ? (
              <PlotlyEISViewer
                topology={fitReport?.topology ?? activeTopology}
                minFreq={minFreq}
                maxFreq={maxFreq}
                pointsPerDecade={15}
                experimentalDataset={activeTab === "automated-fit" || fitReport ? activeDataset : null}
                fitReport={fitReport}
              />
            ) : (
              <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-5 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#162032] pb-3">
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-sky-400" />
                    <span className="text-xs font-bold text-white font-mono uppercase tracking-wider">
                      {viewMode === "nyquist"
                        ? "Nyquist Spectrum (-Z'' vs Z')"
                        : viewMode === "bode-mag"
                        ? "Bode Magnitude (|Z| vs f)"
                        : viewMode === "bode-phase"
                        ? "Bode Phase Angle (θ vs f)"
                        : viewMode === "residuals"
                        ? "Complex Residuals (ΔZ/|Z| %)"
                        : "DRT Relaxation Spectrum γ(ln τ)"}
                    </span>
                  </div>

                  {/* Plot Tabs */}
                  <div className="flex items-center gap-1 bg-[#050810] p-1 rounded-lg border border-[#1e2d46]">
                    {[
                      { id: "nyquist", label: "Nyquist" },
                      { id: "bode-mag", label: "|Z|" },
                      { id: "bode-phase", label: "Phase θ" },
                      { id: "residuals", label: "Residuals" },
                    ].map((tab) => (
                      <button
                        key={tab.id}
                        type="button"
                        onClick={() => setViewMode(tab.id as any)}
                        className={`px-2 py-0.5 rounded text-[11px] font-mono transition-all ${
                          viewMode === tab.id ? "bg-sky-500/20 text-sky-300 font-bold" : "text-slate-400 hover:text-slate-200"
                        }`}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Chart Area */}
                <div className="h-72 w-full bg-[#050810] rounded-xl border border-[#162032] p-2">
                  <ResponsiveContainer width="100%" height="100%">
                    {viewMode === "nyquist" ? (
                      <ComposedChart data={chartPoints} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#162032" />
                        <XAxis
                          dataKey="modelZReal"
                          name="Z' (Ω)"
                          stroke="#64748b"
                          tick={{ fill: "#64748b", fontSize: 10, fontFamily: "monospace" }}
                          label={{ value: "Z' / Real Impedance (Ω)", position: "insideBottom", offset: -5, fill: "#94a3b8", fontSize: 10 }}
                        />
                        <YAxis
                          dataKey="modelMinusZImag"
                          name="-Z'' (Ω)"
                          stroke="#64748b"
                          tick={{ fill: "#64748b", fontSize: 10, fontFamily: "monospace" }}
                          label={{ value: "-Z'' / Imaginary (Ω)", angle: -90, position: "insideLeft", fill: "#94a3b8", fontSize: 10 }}
                        />
                        <Tooltip
                          contentStyle={{ backgroundColor: "#090e18", borderColor: "#1e2d46", fontSize: 11, fontFamily: "monospace" }}
                          formatter={(val: any, name: string) => [`${Number(val).toFixed(2)} Ω`, name]}
                        />
                        <Legend wrapperStyle={{ fontSize: 11, fontFamily: "monospace", paddingTop: 8 }} />
                        <Line
                          type="monotone"
                          dataKey="modelMinusZImag"
                          name="Model Fitted Curve"
                          stroke="#38bdf8"
                          strokeWidth={2.5}
                          dot={false}
                        />
                        {(activeTab === "automated-fit" || fitReport) && (
                          <Scatter
                            dataKey="expMinusZImag"
                            name="Experimental Data (●)"
                            fill="#10b981"
                            shape="circle"
                          />
                        )}
                      </ComposedChart>
                    ) : viewMode === "bode-mag" ? (
                      <ComposedChart data={chartPoints} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#162032" />
                        <XAxis
                          dataKey="logFreq"
                          name="log(f)"
                          stroke="#64748b"
                          tick={{ fill: "#64748b", fontSize: 10, fontFamily: "monospace" }}
                          label={{ value: "log₁₀(Frequency / Hz)", position: "insideBottom", offset: -5, fill: "#94a3b8", fontSize: 10 }}
                        />
                        <YAxis
                          dataKey="modelZMag"
                          stroke="#64748b"
                          tick={{ fill: "#64748b", fontSize: 10, fontFamily: "monospace" }}
                          label={{ value: "|Z| Magnitude (Ω)", angle: -90, position: "insideLeft", fill: "#94a3b8", fontSize: 10 }}
                        />
                        <Tooltip contentStyle={{ backgroundColor: "#090e18", borderColor: "#1e2d46", fontSize: 11, fontFamily: "monospace" }} />
                        <Legend wrapperStyle={{ fontSize: 11, fontFamily: "monospace", paddingTop: 8 }} />
                        <Line type="monotone" dataKey="modelZMag" name="Model |Z|" stroke="#38bdf8" strokeWidth={2} dot={false} />
                        {(activeTab === "automated-fit" || fitReport) && (
                          <Scatter dataKey="expZMag" name="Exp |Z|" fill="#10b981" />
                        )}
                      </ComposedChart>
                    ) : viewMode === "bode-phase" ? (
                      <ComposedChart data={chartPoints} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#162032" />
                        <XAxis
                          dataKey="logFreq"
                          stroke="#64748b"
                          tick={{ fill: "#64748b", fontSize: 10, fontFamily: "monospace" }}
                          label={{ value: "log₁₀(Frequency / Hz)", position: "insideBottom", offset: -5, fill: "#94a3b8", fontSize: 10 }}
                        />
                        <YAxis
                          dataKey="modelPhaseDeg"
                          stroke="#64748b"
                          tick={{ fill: "#64748b", fontSize: 10, fontFamily: "monospace" }}
                          label={{ value: "Phase Angle θ (°)", angle: -90, position: "insideLeft", fill: "#94a3b8", fontSize: 10 }}
                        />
                        <Tooltip contentStyle={{ backgroundColor: "#090e18", borderColor: "#1e2d46", fontSize: 11, fontFamily: "monospace" }} />
                        <Legend wrapperStyle={{ fontSize: 11, fontFamily: "monospace", paddingTop: 8 }} />
                        <Line type="monotone" dataKey="modelPhaseDeg" name="Model Phase (°)" stroke="#a855f7" strokeWidth={2} dot={false} />
                        {(activeTab === "automated-fit" || fitReport) && (
                          <Scatter dataKey="expPhaseDeg" name="Exp Phase (°)" fill="#10b981" />
                        )}
                      </ComposedChart>
                    ) : (
                      <LineChart data={chartPoints} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#162032" />
                        <XAxis
                          dataKey="logFreq"
                          stroke="#64748b"
                          tick={{ fill: "#64748b", fontSize: 10, fontFamily: "monospace" }}
                          label={{ value: "log₁₀(f / Hz)", position: "insideBottom", offset: -5, fill: "#94a3b8", fontSize: 10 }}
                        />
                        <YAxis
                          stroke="#64748b"
                          tick={{ fill: "#64748b", fontSize: 10, fontFamily: "monospace" }}
                          label={{ value: "Residual Error (%)", angle: -90, position: "insideLeft", fill: "#94a3b8", fontSize: 10 }}
                        />
                        <ReferenceLine y={0} stroke="#475569" strokeDasharray="3 3" />
                        <Tooltip contentStyle={{ backgroundColor: "#090e18", borderColor: "#1e2d46", fontSize: 11, fontFamily: "monospace" }} />
                        <Legend wrapperStyle={{ fontSize: 11, fontFamily: "monospace", paddingTop: 8 }} />
                        <Line type="monotone" dataKey="resZRealPct" name="Real Res ΔZ'/|Z| %" stroke="#38bdf8" strokeWidth={1.5} dot={false} />
                        <Line type="monotone" dataKey="resZImagPct" name="Imag Res ΔZ''/|Z| %" stroke="#f43f5e" strokeWidth={1.5} dot={false} />
                      </LineChart>
                    )}
                  </ResponsiveContainer>
                </div>

                {/* Circuit Key Metrics */}
                <div className="grid grid-cols-3 gap-2">
                  <div className="p-2.5 rounded-xl bg-[#050810] border border-[#162032] text-center">
                    <div className="text-[10px] text-slate-500 font-mono">Solution Rs (R0)</div>
                    <div className="text-xs font-bold text-sky-400 font-mono">{circuitMetrics.r0} Ω</div>
                  </div>
                  <div className="p-2.5 rounded-xl bg-[#050810] border border-[#162032] text-center">
                    <div className="text-[10px] text-slate-500 font-mono">Polarization Rp</div>
                    <div className="text-xs font-bold text-purple-400 font-mono">{circuitMetrics.polarizationResistance} Ω</div>
                  </div>
                  <div className="p-2.5 rounded-xl bg-[#050810] border border-[#162032] text-center">
                    <div className="text-[10px] text-slate-500 font-mono">Characteristic f_peak</div>
                    <div className="text-xs font-bold text-emerald-400 font-mono">{circuitMetrics.fPeak}</div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* 2. AUTOMATED PARAMETER FITTER PANEL (PYTHON CNLS) */}
          <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-[#162032] pb-3">
              <div className="flex items-center gap-2">
                <Play className="w-4 h-4 text-emerald-400" />
                <span className="text-xs font-bold text-white font-mono uppercase tracking-wider">
                  Automated Parameter Fitting (Python Backend)
                </span>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-400/30 text-emerald-300 font-bold">
                LEVENBERG-MARQUARDT
              </span>
            </div>

            {/* Experimental Dataset Selection & Upload */}
            <div className="space-y-2">
              <label className="text-xs text-slate-300 font-mono block">Measurement data or synthetic training example:</label>
              <div className="flex items-center gap-2">
                <select
                  value={activeDataset.id}
                  onChange={(e) => {
                    const found = EXPERIMENTAL_BENCHMARKS.find((b) => b.id === e.target.value);
                    if (found) {
                      setActiveDataset(found);
                    }
                  }}
                  className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-400"
                >
                  {EXPERIMENTAL_BENCHMARKS.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.source === "benchmark" ? `[SYNTHETIC TRAINING] ${b.name}` : b.name} ({b.points.length} pts)
                    </option>
                  ))}
                </select>

                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={(e) => e.target.files?.[0] && handleFileUpload(e.target.files[0])}
                  className="hidden"
                  accept=".csv,.txt,.mpt,.dta,.z"
                />

                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-sky-500/10 border border-sky-400/30 text-xs font-mono text-sky-300 hover:bg-sky-500/20 whitespace-nowrap"
                >
                  <Upload className="w-3.5 h-3.5" />
                  <span>Upload</span>
                </button>
              </div>
              <span className="text-[10px] text-slate-500 font-mono block truncate">
                {activeDataset.source === "benchmark"
                  ? `Synthetic training data generated by a circuit model; not an experimental measurement. ${activeDataset.description}`
                  : `Imported measurement: ${activeDataset.sourceFilename || activeDataset.name}. ${activeDataset.description}`}
              </span>
            </div>

            {/* Weighting Method Selector */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[11px] text-slate-400 font-mono">Weighting Matrix:</label>
                <select
                  value={weighting}
                  onChange={(e) => setWeighting(e.target.value as WeightingMethod)}
                  className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                >
                  <option value="modulus">Modulus (1/|Z|²)</option>
                  <option value="proportional">Proportional (1/Z'², 1/Z''²)</option>
                  <option value="unit">Unit (1.0)</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] text-slate-400 font-mono">Max Iterations:</label>
                <input
                  type="number"
                  value={maxIterations}
                  onChange={(e) => setMaxIterations(parseInt(e.target.value, 10) || 50)}
                  className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                />
              </div>
            </div>

            {/* Action Buttons: One-Click Auto-Fit & Standard Local Polish */}
            <div className="space-y-2">
              <button
                type="button"
                onClick={handleRunAutoFit}
                disabled={isAutoFitting || isFitting}
                className="w-full py-3.5 rounded-xl bg-gradient-to-r from-amber-400 via-orange-500 to-rose-500 hover:from-amber-300 hover:to-rose-400 text-slate-950 font-bold text-xs font-mono uppercase tracking-wider flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(245,158,11,0.35)] transition-all disabled:opacity-50 cursor-pointer"
              >
                {isAutoFitting ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin text-slate-950" />
                    <span>Global Differential Evolution Search (Python)...</span>
                  </>
                ) : (
                  <>
                    <Zap className="w-4 h-4 fill-slate-950" />
                    <span>⚡ One-Click Auto-Fit (Global Optimization)</span>
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={handleRunPythonFit}
                disabled={isFitting || isAutoFitting}
                className="w-full py-2.5 rounded-xl bg-slate-900/80 hover:bg-slate-800 border border-slate-700/60 text-slate-300 font-bold text-xs font-mono uppercase tracking-wider flex items-center justify-center gap-2 transition-all disabled:opacity-50 cursor-pointer"
              >
                {isFitting ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin text-sky-400" />
                    <span>Polishing with Levenberg-Marquardt...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5 fill-current text-emerald-400" />
                    <span>Run Local Levenberg-Marquardt Polish</span>
                  </>
                )}
              </button>
            </div>

            {/* Auto-Fit Global Optimization Diagnostics Badge */}
            {autoFitSummary && (
              <div className="p-3 rounded-xl bg-gradient-to-r from-amber-500/10 via-orange-500/10 to-transparent border border-amber-400/30 text-amber-200 text-xs font-mono space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-bold flex items-center gap-1 text-amber-300">
                    <Sparkles className="w-3.5 h-3.5 text-amber-400" /> Global Auto-Fit Result (check convergence)
                  </span>
                  <span className="text-[10px] text-amber-400/80">{autoFitSummary.computeTimeMs} ms</span>
                </div>
                <div className="text-[11px] text-slate-300 grid grid-cols-2 gap-2 pt-1 border-t border-amber-500/20">
                  <div>Reduced χ²: <strong className="text-white font-mono">{autoFitSummary.reducedChiSquare.toExponential(2)}</strong></div>
                  <div>R² Score: <strong className="text-emerald-300 font-mono">{(autoFitSummary.rSquared == null ? "Unavailable" : autoFitSummary.rSquared.toFixed(4))}</strong></div>
                </div>
                <div className="text-[10px] text-slate-400 pt-0.5">
                  Review the result, then apply fitted parameters to the circuit.
                </div>
              </div>
            )}

            {/* Fitting Error Notice */}
            {fitError && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-400/30 text-rose-300 text-xs font-mono flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span>{fitError}</span>
              </div>
            )}

            {/* Fitting Results Summary Table */}
            {fitReport && (
              <div className="space-y-3 pt-2 border-t border-[#162032]">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span className="text-xs font-mono font-bold text-emerald-300">
                      {fitReport.converged ? "Convergence reported" : "Convergence not confirmed"} ({fitReport.iterations} iters)
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] font-mono text-slate-400">
                    <span>Reduced χ²: <strong className="text-sky-300">{fitReport.reducedChiSquare.toExponential(2)}</strong></span>
                    <span>R²: <strong className="text-emerald-300">{(fitReport.rSquared == null ? "Unavailable" : fitReport.rSquared.toFixed(4))}</strong></span>
                  </div>
                </div>

                {/* Parameter Table */}
                <div className="max-h-48 overflow-y-auto rounded-xl border border-[#162032] bg-[#050810] scrollbar-thin">
                  <table className="w-full text-[11px] font-mono text-slate-300">
                    <thead className="bg-[#090e18] text-slate-400 border-b border-[#162032] sticky top-0">
                      <tr>
                        <th className="p-2 text-left">Parameter</th>
                        <th className="p-2 text-right">Initial</th>
                        <th className="p-2 text-right">Fitted Value</th>
                        <th className="p-2 text-right">Error (±σ)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#162032]">
                      {fitReport.parameters.map((p, idx) => (
                        <tr key={idx} className="hover:bg-slate-800/30">
                          <td className="p-2 font-bold text-sky-400">{p.paramName}</td>
                          <td className="p-2 text-right text-slate-500">
                            {p.initialValue < 0.001 ? p.initialValue.toExponential(2) : p.initialValue.toFixed(3)}
                          </td>
                          <td className="p-2 text-right font-bold text-emerald-300">
                            {p.fittedValue < 0.001 ? p.fittedValue.toExponential(3) : p.fittedValue.toFixed(3)} {p.unit}
                          </td>
                          <td className="p-2 text-right text-slate-400">
                            {p.isFixed ? (
                              <span className="text-amber-400 text-[10px]">FIXED</span>
                            ) : (
                              (p.percentError == null ? "Unavailable" : `±${p.percentError.toFixed(1)}%`)
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Apply Fitted Values Button */}
                <button
                  type="button"
                  onClick={handleApplyFittedParameters}
                  className="w-full py-2.5 rounded-xl bg-sky-500/20 hover:bg-sky-500/30 border border-sky-400/50 text-sky-300 text-xs font-mono font-bold flex items-center justify-center gap-2 transition-all shadow-[0_0_12px_rgba(56,189,248,0.2)]"
                >
                  <Check className="w-3.5 h-3.5 text-sky-400" />
                  <span>Apply Fitted Parameters to Circuit Modeler</span>
                </button>


              </div>
            )}
          </div>
        </div>
      </div>
      )}

      {/* Circuit Library Modal */}
      <CircuitLibraryModal
        isOpen={isLibraryModalOpen}
        onClose={() => setIsLibraryModalOpen(false)}
        onSelectModel={(topo) => {
          handleSelectPreset(topo);
          setIsLibraryModalOpen(false);
        }}
      />

      {/* CNLS Full Fitting Studio Modal */}
      {isCNLSModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 overflow-y-auto">
          <div role="dialog" aria-modal="true" aria-label="CNLS fitting studio" className="bg-[#090e18] border border-[#1e2d46] rounded-2xl w-full max-w-6xl max-h-[92vh] overflow-y-auto p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-[#162032] pb-4">
              <div className="flex items-center gap-2">
                <Activity className="w-5 h-5 text-emerald-400" />
                <h3 className="text-base font-bold text-white font-mono uppercase">
                  CNLS Impedance Fitting Studio &amp; DRT Analysis
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setIsCNLSModalOpen(false)}
                className="px-3 py-1 rounded-lg bg-slate-800 text-slate-300 text-xs font-mono hover:bg-slate-700"
              >
                Close Studio
              </button>
            </div>
            <CNLSFittingStudio
              currentTopology={activeTopology}
              onApplyTopology={(topo) => {
                setActiveTopology(topo);
                setIsCNLSModalOpen(false);
              }}
              onClose={() => setIsCNLSModalOpen(false)}
            />
          </div>
        </div>
      )}
    </div>
  );
}
