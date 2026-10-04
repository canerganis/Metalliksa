import React, { useState, useEffect, useMemo } from "react";
import {
  Search,
  Database,
  Atom,
  Sparkles,
  Zap,
  ShieldCheck,
  AlertTriangle,
  Layers,
  Activity,
  ArrowRight,
  RefreshCw,
  ExternalLink,
  ChevronRight,
  Boxes,
  Compass,
  Cpu,
  Info,
  Table,
  Gauge,
  Sliders,
} from "lucide-react";
import {
  pythonComputationService,
  PythonDFTOutcome,
  isDftUnavailable,
} from "../services/pythonComputationService";
import {
  UNAVAILABLE_TEXT,
  directionLabel,
  formatOrUnavailable,
  formatZener,
  provenanceLine,
} from "../utils/elasticityDisplay";

export interface MPDoc {
  material_id: string;
  formula_pretty: string;
  symmetry?: {
    crystal_system?: string;
    symbol?: string;
    number?: number;
    point_group?: string;
  };
  energy_above_hull?: number;
  formation_energy_per_atom?: number;
  band_gap?: number;
  is_stable?: boolean;
  is_metal?: boolean;
  is_magnetic?: boolean;
  ordering?: string;
  total_magnetization?: number;
  theoretical?: boolean;
  k_voigt?: number;
  k_reuss?: number;
  k_vrh?: number;
  g_voigt?: number;
  g_reuss?: number;
  g_vrh?: number;
  universal_anisotropy?: number;
  homogeneous_poisson?: number;
  volume?: number;
  density?: number;
  density_atomic?: number;
  nsites?: number;
  elements?: string[];
  chemsys?: string;
}

// Built-in curated DFT benchmark library for instant fallback & high-speed exploration
const CURATED_MP_PRESETS: MPDoc[] = [
  {
    material_id: "mp-13",
    formula_pretty: "Fe3C",
    symmetry: { crystal_system: "Orthorhombic", symbol: "Pnma", number: 62, point_group: "mmm" },
    energy_above_hull: 0.024,
    formation_energy_per_atom: 0.076,
    band_gap: 0,
    is_stable: false,
    is_metal: true,
    is_magnetic: true,
    ordering: "FM",
    total_magnetization: 5.82,
    theoretical: false,
    k_vrh: 228.4,
    g_vrh: 74.2,
    universal_anisotropy: 0.88,
    homogeneous_poisson: 0.36,
    volume: 154.2,
    density: 7.68,
    density_atomic: 0.103,
    nsites: 16,
    elements: ["Fe", "C"],
    chemsys: "C-Fe",
  },
  {
    material_id: "mp-19009",
    formula_pretty: "LiFePO4",
    symmetry: { crystal_system: "Orthorhombic", symbol: "Pnma", number: 62, point_group: "mmm" },
    energy_above_hull: 0,
    formation_energy_per_atom: -2.312,
    band_gap: 3.72,
    is_stable: true,
    is_metal: false,
    is_magnetic: true,
    ordering: "AFM",
    total_magnetization: 0,
    theoretical: false,
    k_vrh: 96.5,
    g_vrh: 52.8,
    universal_anisotropy: 0.42,
    homogeneous_poisson: 0.26,
    volume: 291.4,
    density: 3.59,
    density_atomic: 0.096,
    nsites: 28,
    elements: ["Li", "Fe", "P", "O"],
    chemsys: "Fe-Li-O-P",
  },
  {
    material_id: "mp-2554",
    formula_pretty: "Ni3Al",
    symmetry: { crystal_system: "Cubic", symbol: "Pm-3m", number: 221, point_group: "m-3m" },
    energy_above_hull: 0,
    formation_energy_per_atom: -0.425,
    band_gap: 0,
    is_stable: true,
    is_metal: true,
    is_magnetic: true,
    ordering: "FM",
    total_magnetization: 0.72,
    theoretical: false,
    k_vrh: 178.6,
    g_vrh: 81.4,
    universal_anisotropy: 0.15,
    homogeneous_poisson: 0.31,
    volume: 44.8,
    density: 7.42,
    density_atomic: 0.089,
    nsites: 4,
    elements: ["Ni", "Al"],
    chemsys: "Al-Ni",
  },
  {
    material_id: "mp-3083",
    formula_pretty: "Ti3AlC2",
    symmetry: { crystal_system: "Hexagonal", symbol: "P6_3/mmc", number: 194, point_group: "6/mmm" },
    energy_above_hull: 0,
    formation_energy_per_atom: -0.742,
    band_gap: 0,
    is_stable: true,
    is_metal: true,
    is_magnetic: false,
    ordering: "NM",
    total_magnetization: 0,
    theoretical: false,
    k_vrh: 165.2,
    g_vrh: 124.8,
    universal_anisotropy: 0.32,
    homogeneous_poisson: 0.19,
    volume: 148.9,
    density: 4.25,
    density_atomic: 0.081,
    nsites: 12,
    elements: ["Ti", "Al", "C"],
    chemsys: "Al-C-Ti",
  },
  {
    material_id: "mp-2133",
    formula_pretty: "ZnO",
    symmetry: { crystal_system: "Hexagonal", symbol: "P6_3mc", number: 186, point_group: "6mm" },
    energy_above_hull: 0,
    formation_energy_per_atom: -1.785,
    band_gap: 0.73, // DFT standard PBE underestimate
    is_stable: true,
    is_metal: false,
    is_magnetic: false,
    ordering: "NM",
    total_magnetization: 0,
    theoretical: false,
    k_vrh: 142.1,
    g_vrh: 46.8,
    universal_anisotropy: 0.28,
    homogeneous_poisson: 0.35,
    volume: 48.6,
    density: 5.56,
    density_atomic: 0.082,
    nsites: 4,
    elements: ["Zn", "O"],
    chemsys: "O-Zn",
  },
  {
    material_id: "mp-735",
    formula_pretty: "NiTi",
    symmetry: { crystal_system: "Cubic", symbol: "Pm-3m", number: 221, point_group: "m-3m" },
    energy_above_hull: 0,
    formation_energy_per_atom: -0.384,
    band_gap: 0,
    is_stable: true,
    is_metal: true,
    is_magnetic: false,
    ordering: "NM",
    total_magnetization: 0,
    theoretical: false,
    k_vrh: 148.2,
    g_vrh: 58.6,
    universal_anisotropy: 0.44,
    homogeneous_poisson: 0.34,
    volume: 27.2,
    density: 6.45,
    density_atomic: 0.073,
    nsites: 2,
    elements: ["Ni", "Ti"],
    chemsys: "Ni-Ti",
  },
  {
    material_id: "mp-1894",
    formula_pretty: "WC",
    symmetry: { crystal_system: "Hexagonal", symbol: "P-6m2", number: 187, point_group: "-6m2" },
    energy_above_hull: 0,
    formation_energy_per_atom: -0.218,
    band_gap: 0,
    is_stable: true,
    is_metal: true,
    is_magnetic: false,
    ordering: "NM",
    total_magnetization: 0,
    theoretical: false,
    k_vrh: 384.5,
    g_vrh: 286.2,
    universal_anisotropy: 0.12,
    homogeneous_poisson: 0.18,
    volume: 20.8,
    density: 15.63,
    density_atomic: 0.096,
    nsites: 2,
    elements: ["W", "C"],
    chemsys: "C-W",
  },
];

interface MaterialsProjectExplorerProps {
  onSelectToCrystal?: (formula: string, crystalSystem: string) => void;
}

export function MaterialsProjectExplorer({ onSelectToCrystal }: MaterialsProjectExplorerProps) {
  const [query, setQuery] = useState<string>("Fe3C");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<MPDoc[]>(CURATED_MP_PRESETS);
  const [selectedDoc, setSelectedDoc] = useState<MPDoc>(CURATED_MP_PRESETS[0]);
  const [activeTab, setActiveTab] = useState<
    "dft-overview" | "elastic-tensors" | "python-dft-tensor" | "electronic" | "ai-analysis"
  >("dft-overview");

  // Python continuum-elasticity (6x6 C_ij homogenisation, not DFT) state
  const [pythonDftResult, setPythonDftResult] = useState<PythonDFTOutcome | null>(null);
  const [isDftComputing, setIsDftComputing] = useState<boolean>(false);
  const dftUnavailable = pythonDftResult && isDftUnavailable(pythonDftResult) ? pythonDftResult : null;
  const dftResult = pythonDftResult && !isDftUnavailable(pythonDftResult) ? pythonDftResult : null;

  // Compute the Python elasticity result on selectedDoc change (the previous result is cleared first)
  useEffect(() => {
    let isMounted = true;
    setIsDftComputing(true);
    setPythonDftResult(null);

    pythonComputationService
      .calculateDFTProperties({
        formula: selectedDoc.formula_pretty,
        material_id: selectedDoc.material_id,
        crystal_system: selectedDoc.symmetry?.crystal_system,
        space_group: selectedDoc.symmetry?.symbol,
        // Only what the record carries: no 165 / 78 GPa or 7.85 g/cm^3 stand-ins (the engine answers
        // "unavailable" when it has nothing to work from), and no cell site count (not atoms per formula unit).
        k_vrh: selectedDoc.k_vrh,
        g_vrh: selectedDoc.g_vrh,
        density: selectedDoc.density,
        formation_energy_per_atom: selectedDoc.formation_energy_per_atom,
        energy_above_hull: selectedDoc.energy_above_hull,
        band_gap: selectedDoc.band_gap,
      })
      .then((res) => {
        if (isMounted) {
          setPythonDftResult(res);
          setIsDftComputing(false);
        }
      })
      .catch((err) => {
        console.warn("Python elasticity error:", err);
        if (isMounted) setIsDftComputing(false);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedDoc]);

  // AI Interpretation State
  const [aiAnalysis, setAiAnalysis] = useState<string>("");
  const [aiLoading, setAiLoading] = useState<boolean>(false);

  const executeSearch = async (searchFormula: string) => {
    const term = searchFormula.trim();
    if (!term) return;

    setLoading(true);
    setError(null);

    try {
      // Determine if query is material_id (starts with mp- or mvc-) or formula
      const isMpId = term.toLowerCase().startsWith("mp-") || term.toLowerCase().startsWith("mvc-");
      const url = isMpId
        ? `/api/materials-project/search?material_id=${encodeURIComponent(term)}`
        : `/api/materials-project/search?formula=${encodeURIComponent(term)}`;

      const res = await fetch(url);
      const rawText = await res.text();
      let json: any = {};
      try {
        json = JSON.parse(rawText);
      } catch {
        throw new Error(res.ok ? "Invalid data from Materials Project" : `Error (${res.status}): ${rawText.substring(0, 80)}`);
      }

      if (!res.ok) {
        throw new Error(json.error || `Materials Project API returned HTTP ${res.status}`);
      }

      if (json.data && json.data.length > 0) {
        setResults(json.data);
        setSelectedDoc(json.data[0]);
      } else {
        // Check if matching curated presets
        const localMatch = CURATED_MP_PRESETS.filter(
          (p) =>
            p.formula_pretty.toLowerCase() === term.toLowerCase() ||
            p.material_id.toLowerCase() === term.toLowerCase()
        );
        if (localMatch.length > 0) {
          setResults(localMatch);
          setSelectedDoc(localMatch[0]);
        } else {
          setError(`No materials found for "${term}". Try formulas like Fe3C, LiFePO4, Ti3AlC2, Ni3Al, or mp-id.`);
        }
      }
    } catch (err: any) {
      console.warn("Falling back to local DFT dataset:", err);
      // Fallback search in presets
      const localMatch = CURATED_MP_PRESETS.filter((p) =>
        p.formula_pretty.toLowerCase().includes(term.toLowerCase())
      );
      if (localMatch.length > 0) {
        setResults(localMatch);
        setSelectedDoc(localMatch[0]);
      } else {
        setError(`Materials Project query note: ${err.message}. Showing local benchmark entries.`);
      }
    } finally {
      setLoading(false);
    }
  };

  // Perform AI Metallurgical Analysis for selected compound
  const runAiAnalysis = async (doc: MPDoc) => {
    setAiLoading(true);
    try {
      const prompt = `As a Senior Computational Materials Scientist, evaluate the DFT and thermodynamic properties of this material from the Materials Project:
- Formula: ${doc.formula_pretty} (ID: ${doc.material_id})
- Crystal System: ${doc.symmetry?.crystal_system || "N/A"} (${doc.symmetry?.symbol || "N/A"})
- Energy Above Hull (E_hull): ${doc.energy_above_hull?.toFixed(4) || "0"} eV/atom (${doc.is_stable ? "Thermally Stable on Convex Hull" : "Metastable / Decomposition prone"})
- Formation Energy: ${doc.formation_energy_per_atom?.toFixed(4) || "N/A"} eV/atom
- Bulk Modulus (K_VRH): ${doc.k_vrh ? `${doc.k_vrh} GPa` : "Not computed"}
- Shear Modulus (G_VRH): ${doc.g_vrh ? `${doc.g_vrh} GPa` : "Not computed"}
- Pugh's Ductility Ratio (K/G): ${doc.k_vrh && doc.g_vrh ? (doc.k_vrh / doc.g_vrh).toFixed(2) : "N/A"}
- Poisson's Ratio: ${doc.homogeneous_poisson?.toFixed(2) || "N/A"}
- Electronic State: ${doc.is_metal ? "Metallic Conductor" : `Semiconductor/Insulator (Eg = ${doc.band_gap} eV)`}
- Magnetism: ${doc.is_magnetic ? `${doc.ordering} with ${doc.total_magnetization} mu_B/f.u.` : "Non-magnetic"}

Provide an in-depth engineering assessment:
1. **Thermodynamic & Phase Stability**: Is this phase stable during typical heat treatment, or will it decompose into competing phases?
2. **Mechanical Behavior & Brittleness**: Interpret Pugh's ratio (K/G > 1.75 = ductile, < 1.75 = brittle), directional bonding stiffness, and cleavage tendency.
3. **Metallurgical & Industrial Role**: Where is this phase encountered? (e.g. secondary precipitate, intermetallic gamma prime, battery intercalation host, MAX phase, wear coating, or carbide embrittlement agent).
4. **Processing & Alloying Guidelines**: How to stabilize or suppress this phase via microalloying and cooling rate.`;

      const res = await fetch("/api/metallurgy/consult", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });

      const rawText = await res.text();
      let data: any = {};
      try {
        data = JSON.parse(rawText);
      } catch {
        throw new Error(res.ok ? "Invalid server response." : `Server error (${res.status})`);
      }

      setAiAnalysis(data.reply || data.text || "No analysis available.");
    } catch (err: any) {
      setAiAnalysis("AI consultation failed. Check server connection.");
    } finally {
      setAiLoading(false);
    }
  };

  // Calculate Young's Modulus & Pugh Ratio if K and G are available
  const mechanicalStats = useMemo(() => {
    const K = selectedDoc.k_vrh;
    const G = selectedDoc.g_vrh;
    if (!K || !G) return null;

    const E = (9 * K * G) / (3 * K + G);
    const pughRatio = K / G;
    const isDuctile = pughRatio > 1.75;
    const cauchyPressure = K - (5 / 3) * G; // Positive implies metallic bonding / ductility

    return {
      youngsModulus: parseFloat(E.toFixed(1)),
      pughRatio: parseFloat(pughRatio.toFixed(2)),
      isDuctile,
      cauchyPressure: parseFloat(cauchyPressure.toFixed(1)),
    };
  }, [selectedDoc]);

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-[#090e18] p-5 rounded-2xl border border-[#162032] shadow-sm">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-xl bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400 shadow-[0_0_16px_rgba(14,165,233,0.25)]">
            <Database className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-extrabold text-white font-mono tracking-wide uppercase">
                Materials Project DFT & Crystallography Explorer
              </h2>
              <span className="px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 text-[10px] font-mono border border-sky-500/40">
                Live Next-Gen API
              </span>
            </div>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              Thermodynamic Convex Hull (E_hull), Elastic Tensors (Voigt-Reuss-Hill), Band Gaps & Space Groups
            </p>
          </div>
        </div>

        {/* Search Bar */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            executeSearch(query);
          }}
          className="flex items-center gap-2 w-full md:w-auto"
        >
          <div className="relative flex-1 md:w-64">
            <input aria-label="Search Materials Project by formula or material ID"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. Fe3C, LiFePO4, mp-13..."
              className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl px-3.5 py-2 pl-9 text-xs text-white font-mono placeholder:text-slate-500 focus:outline-none focus:border-sky-400"
            />
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-mono font-bold text-xs rounded-xl flex items-center gap-1.5 transition shadow-[0_0_12px_rgba(14,165,233,0.3)] shrink-0"
          >
            {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
            <span>Fetch DFT</span>
          </button>
        </form>
      </div>

      {/* Preset Pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs font-mono">
        <span className="text-slate-400 text-[11px] whitespace-nowrap">Benchmark Phases:</span>
        {CURATED_MP_PRESETS.map((p) => (
          <button
            key={p.material_id}
            type="button"
            onClick={() => {
              setQuery(p.formula_pretty);
              executeSearch(p.formula_pretty);
            }}
            className={`px-2.5 py-1 rounded-lg border transition whitespace-nowrap text-[11px] ${
              selectedDoc.material_id === p.material_id
                ? "bg-sky-500/20 border-sky-400 text-sky-200"
                : "bg-[#090e18] border-[#162032] text-slate-400 hover:text-slate-200"
            }`}
          >
            {p.formula_pretty} <span className="text-[9px] text-slate-500">({p.material_id})</span>
          </button>
        ))}
      </div>

      {/* Error alert if any */}
      {error && (
        <div className="p-3 bg-amber-950/30 border border-amber-800/50 rounded-xl text-amber-300 text-xs font-mono flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Search Results Row if multiple */}
      {results.length > 1 && (
        <div className="flex items-center gap-2 overflow-x-auto p-1 bg-[#090e18] rounded-xl border border-[#162032]">
          <span className="text-slate-400 text-[11px] font-mono px-2">Matches ({results.length}):</span>
          {results.map((doc) => (
            <button
              key={doc.material_id}
              type="button"
              onClick={() => setSelectedDoc(doc)}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono transition flex items-center gap-1.5 whitespace-nowrap ${
                selectedDoc.material_id === doc.material_id
                  ? "bg-sky-500/20 text-sky-300 border border-sky-400/40 font-bold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <span>{doc.formula_pretty}</span>
              <span className="text-[10px] text-slate-500">[{doc.material_id}]</span>
              <span className={`text-[9px] px-1 py-0.2 rounded ${doc.is_stable ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-500/20 text-amber-400"}`}>
                {doc.symmetry?.crystal_system || "Crystal"}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Main Material Detail Card */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Crystallography & Thermodynamic Hull */}
        <div className="lg:col-span-7 space-y-6">
          <div className="bg-[#090e18] p-5 rounded-2xl border border-[#162032] space-y-5">
            {/* Title & Material ID Banner */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#162032] pb-4">
              <div>
                <div className="flex items-center gap-3">
                  <h3 className="text-2xl font-black text-white font-mono tracking-tight">
                    {selectedDoc.formula_pretty}
                  </h3>
                  <a
                    href={`https://next-gen.materialsproject.org/materials/${selectedDoc.material_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-2.5 py-1 rounded bg-[#050810] border border-[#1e2d46] text-sky-400 hover:text-sky-300 text-xs font-mono flex items-center gap-1 transition"
                  >
                    <span>{selectedDoc.material_id}</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
                <span className="text-xs text-slate-400 font-mono mt-0.5 block">
                  Chemical System: <strong className="text-slate-300">{selectedDoc.chemsys || selectedDoc.elements?.join("-")}</strong> • Sites: {selectedDoc.nsites || "N/A"}
                </span>
              </div>

              {/* Stability Badge */}
              <div className="flex items-center gap-2">
                {selectedDoc.energy_above_hull !== undefined && selectedDoc.energy_above_hull <= 0.005 ? (
                  <span className="px-3 py-1 rounded-lg bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 font-mono text-xs font-bold flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Convex Hull Stable</span>
                  </span>
                ) : (
                  <span className="px-3 py-1 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-300 font-mono text-xs font-bold flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                    <span>Metastable (+{(selectedDoc.energy_above_hull || 0).toFixed(3)} eV/atom)</span>
                  </span>
                )}
              </div>
            </div>

            {/* Navigation Tabs */}
            <div className="flex items-center gap-1.5 p-1 bg-[#050810] rounded-xl border border-[#162032] overflow-x-auto text-xs font-mono">
              <button
                type="button"
                onClick={() => setActiveTab("dft-overview")}
                className={`px-3 py-1.5 rounded-lg transition whitespace-nowrap flex items-center gap-1.5 ${
                  activeTab === "dft-overview"
                    ? "bg-sky-500/20 text-sky-300 border border-sky-500/40 font-bold"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Compass className="w-3.5 h-3.5" />
                <span>Thermodynamics & Symmetry</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("elastic-tensors")}
                className={`px-3 py-1.5 rounded-lg transition whitespace-nowrap flex items-center gap-1.5 ${
                  activeTab === "elastic-tensors"
                    ? "bg-sky-500/20 text-sky-300 border border-sky-500/40 font-bold"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Boxes className="w-3.5 h-3.5" />
                <span>Elastic Tensors (VRH)</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("python-dft-tensor")}
                className={`px-3 py-1.5 rounded-lg transition whitespace-nowrap flex items-center gap-1.5 ${
                  activeTab === "python-dft-tensor"
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold shadow-[0_0_10px_rgba(16,185,129,0.2)]"
                    : "text-emerald-400/80 hover:text-emerald-300"
                }`}
              >
                <Cpu className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
                <span>Elastic C_ij &amp; Debye (continuum, not DFT)</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("electronic")}
                className={`px-3 py-1.5 rounded-lg transition whitespace-nowrap flex items-center gap-1.5 ${
                  activeTab === "electronic"
                    ? "bg-sky-500/20 text-sky-300 border border-sky-500/40 font-bold"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Zap className="w-3.5 h-3.5" />
                <span>Electronic & Magnetism</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setActiveTab("ai-analysis");
                  if (!aiAnalysis && !aiLoading) runAiAnalysis(selectedDoc);
                }}
                className={`px-3 py-1.5 rounded-lg transition whitespace-nowrap flex items-center gap-1.5 ${
                  activeTab === "ai-analysis"
                    ? "bg-purple-500/20 text-purple-300 border border-purple-500/40 font-bold"
                    : "text-purple-400 hover:text-purple-200"
                }`}
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>AI Phase Assessment</span>
              </button>
            </div>

            {/* TAB 1: THERMODYNAMICS & SYMMETRY */}
            {activeTab === "dft-overview" && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 font-mono text-xs">
                  <div className="p-3 bg-[#050810] rounded-xl border border-[#162032] space-y-1">
                    <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Crystal System</span>
                    <span className="text-sm font-bold text-sky-400">{selectedDoc.symmetry?.crystal_system || "N/A"}</span>
                  </div>
                  <div className="p-3 bg-[#050810] rounded-xl border border-[#162032] space-y-1">
                    <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Space Group Symbol</span>
                    <span className="text-sm font-bold text-emerald-400">{selectedDoc.symmetry?.symbol || "N/A"}</span>
                    <span className="text-[10px] text-slate-500 block">No. {selectedDoc.symmetry?.number || "N/A"}</span>
                  </div>
                  <div className="p-3 bg-[#050810] rounded-xl border border-[#162032] space-y-1">
                    <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Point Group</span>
                    <span className="text-sm font-bold text-amber-400">{selectedDoc.symmetry?.point_group || "N/A"}</span>
                  </div>
                  <div className="p-3 bg-[#050810] rounded-xl border border-[#162032] space-y-1">
                    <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Formation Energy (ΔHf)</span>
                    <span className="text-sm font-bold text-white">
                      {selectedDoc.formation_energy_per_atom !== undefined
                        ? `${selectedDoc.formation_energy_per_atom.toFixed(3)} eV/atom`
                        : "N/A"}
                    </span>
                  </div>
                  <div className="p-3 bg-[#050810] rounded-xl border border-[#162032] space-y-1">
                    <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Energy Above Hull (E_hull)</span>
                    <span className={`text-sm font-bold ${
                      (selectedDoc.energy_above_hull || 0) <= 0.005 ? "text-emerald-400" : "text-amber-400"
                    }`}>
                      {selectedDoc.energy_above_hull !== undefined
                        ? `${selectedDoc.energy_above_hull.toFixed(4)} eV/atom`
                        : "0.0000 eV"}
                    </span>
                  </div>
                  <div className="p-3 bg-[#050810] rounded-xl border border-[#162032] space-y-1">
                    <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Theoretical Density</span>
                    <span className="text-sm font-bold text-sky-300">
                      {selectedDoc.density ? `${selectedDoc.density.toFixed(2)} g/cm³` : "N/A"}
                    </span>
                  </div>
                </div>

                <div className="p-4 bg-[#050810] rounded-xl border border-[#162032] space-y-2 font-mono text-xs">
                  <span className="text-slate-400 text-[11px] font-bold block uppercase tracking-wider">
                    Convex Hull Thermodynamic Significance:
                  </span>
                  <p className="text-slate-300 text-xs leading-relaxed">
                    {selectedDoc.energy_above_hull === 0 || (selectedDoc.energy_above_hull && selectedDoc.energy_above_hull <= 0.005) ? (
                      <span>
                        <strong className="text-emerald-400">Thermodynamically Stable:</strong> This compound lies on the T = 0 K DFT energy convex hull. It resists thermal decomposition and persists as an equilibrium phase in the alloy matrix.
                      </span>
                    ) : (
                      <span>
                        <strong className="text-amber-400">Metastable Phase:</strong> This phase has an energy +{(selectedDoc.energy_above_hull || 0).toFixed(3)} eV/atom above the convex hull. It may decompose into equilibrium ground states under high-temperature exposure or prolonged aging.
                      </span>
                    )}
                  </p>
                </div>
              </div>
            )}

            {/* TAB 2: ELASTIC TENSORS */}
            {activeTab === "elastic-tensors" && (
              <div className="space-y-4">
                {mechanicalStats ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
                      <div className="p-3 bg-[#050810] rounded-xl border border-[#162032]">
                        <span className="text-[10px] text-slate-400 block uppercase">Bulk Modulus (K_VRH)</span>
                        <span className="text-base font-bold text-sky-400">{selectedDoc.k_vrh} GPa</span>
                      </div>
                      <div className="p-3 bg-[#050810] rounded-xl border border-[#162032]">
                        <span className="text-[10px] text-slate-400 block uppercase">Shear Modulus (G_VRH)</span>
                        <span className="text-base font-bold text-emerald-400">{selectedDoc.g_vrh} GPa</span>
                      </div>
                      <div className="p-3 bg-[#050810] rounded-xl border border-[#162032]">
                        <span className="text-[10px] text-slate-400 block uppercase">Young's Modulus (E)</span>
                        <span className="text-base font-bold text-amber-400">{mechanicalStats.youngsModulus} GPa</span>
                      </div>
                      <div className="p-3 bg-[#050810] rounded-xl border border-[#162032]">
                        <span className="text-[10px] text-slate-400 block uppercase">Poisson's Ratio (ν)</span>
                        <span className="text-base font-bold text-white">{selectedDoc.homogeneous_poisson?.toFixed(2) || "N/A"}</span>
                      </div>
                    </div>

                    {/* Pugh's Ductility / Brittleness Bar */}
                    <div className="p-4 bg-[#050810] rounded-xl border border-[#162032] space-y-3 font-mono text-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-300 font-bold flex items-center gap-1.5">
                          <Activity className="w-4 h-4 text-sky-400" />
                          <span>Pugh's Ductility / Brittleness Ratio (K/G):</span>
                        </span>
                        <span className={`text-base font-bold px-2 py-0.5 rounded ${
                          mechanicalStats.isDuctile
                            ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                            : "bg-rose-500/20 text-rose-400 border border-rose-500/40"
                        }`}>
                          K/G = {mechanicalStats.pughRatio} ({mechanicalStats.isDuctile ? "Ductile" : "Brittle"})
                        </span>
                      </div>

                      <div className="space-y-1">
                        <div className="flex justify-between text-[10px] text-slate-500">
                          <span>Brittle Regime (&lt; 1.75)</span>
                          <span className="text-slate-400 font-bold">Critical Threshold 1.75</span>
                          <span>Ductile Metallic (&gt; 1.75)</span>
                        </div>
                        <div className="w-full bg-[#0c1322] h-2.5 rounded-full overflow-hidden border border-[#162032] relative">
                          <div
                            className={`h-full ${
                              mechanicalStats.isDuctile
                                ? "bg-gradient-to-r from-teal-500 to-emerald-400"
                                : "bg-gradient-to-r from-rose-500 to-amber-500"
                            }`}
                            style={{ width: `${Math.min(100, (mechanicalStats.pughRatio / 3.5) * 100)}%` }}
                          ></div>
                        </div>
                      </div>

                      <p className="text-[11px] text-slate-400 leading-relaxed">
                        According to Pugh's empirical criterion, $K/G &gt; 1.75$ indicates metallic ductile bonding, whereas $K/G &lt; 1.75$ points to covalent directional bonding and cleavage brittleness.
                        {selectedDoc.universal_anisotropy !== undefined && (
                          <span className="block mt-1">
                            Universal Elastic Anisotropy ($A^U$): <strong className="text-white">{selectedDoc.universal_anisotropy.toFixed(2)}</strong> (0 = completely isotropic).
                          </span>
                        )}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="p-6 text-center text-slate-400 font-mono text-xs bg-[#050810] rounded-xl border border-[#162032]">
                    Full Voigt-Reuss-Hill elastic tensor matrix has not been computed via DFT for this compound yet.
                  </div>
                )}
              </div>
            )}

            {/* TAB: PYTHON CONTINUUM-ELASTICITY 6x6 TENSOR & DEBYE (supplied/library C_ij; not DFT) */}
            {activeTab === "python-dft-tensor" && (
              <div className="space-y-4 font-mono text-xs">
                {/* Engine Telemetry & Header */}
                <div className="p-3 bg-[#050810] rounded-xl border border-emerald-500/30 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                    <span className="text-emerald-300 font-bold">
                      {pythonDftResult?.engine || "MetalliX Continuum Elasticity Engine"}
                    </span>
                    <span className="text-slate-500">•</span>
                    <span className="text-slate-400">
                      Compute Time: <strong className="text-white">{pythonDftResult ? `${pythonDftResult.computeTimeMs} ms` : UNAVAILABLE_TEXT}</strong>
                    </span>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
                    6x6 Stiffness Inversion & Anisotropy
                  </span>
                </div>

                {isDftComputing ? (
                  <div className="py-12 text-center text-slate-400 space-y-2">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto text-emerald-400" />
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
            )}

            {/* TAB 3: ELECTRONIC & MAGNETISM */}
            {activeTab === "electronic" && (
              <div className="space-y-4 font-mono text-xs">
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  <div className="p-3 bg-[#050810] rounded-xl border border-[#162032]">
                    <span className="text-[10px] text-slate-400 block uppercase">Electronic State</span>
                    <span className={`text-sm font-bold ${selectedDoc.is_metal ? "text-emerald-400" : "text-amber-400"}`}>
                      {selectedDoc.is_metal ? "Metallic (Conductor)" : "Non-Metallic"}
                    </span>
                  </div>
                  <div className="p-3 bg-[#050810] rounded-xl border border-[#162032]">
                    <span className="text-[10px] text-slate-400 block uppercase">DFT Band Gap (Eg)</span>
                    <span className="text-sm font-bold text-sky-400">
                      {selectedDoc.band_gap !== undefined ? `${selectedDoc.band_gap.toFixed(2)} eV` : "0.00 eV"}
                    </span>
                  </div>
                  <div className="p-3 bg-[#050810] rounded-xl border border-[#162032]">
                    <span className="text-[10px] text-slate-400 block uppercase">Magnetic Ordering</span>
                    <span className="text-sm font-bold text-purple-400">
                      {selectedDoc.ordering || (selectedDoc.is_magnetic ? "Magnetic" : "Non-Magnetic (NM)")}
                    </span>
                  </div>
                </div>

                <div className="p-4 bg-[#050810] rounded-xl border border-[#162032] space-y-2">
                  <span className="text-[11px] text-slate-300 font-bold block uppercase">
                    Total Spin Magnetization:
                  </span>
                  <div className="text-sm text-white font-bold">
                    {selectedDoc.total_magnetization !== undefined
                      ? `${selectedDoc.total_magnetization.toFixed(2)} µB / formula unit`
                      : "0.00 µB"}
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Magnetic spin polarization directly influences the free energy (ΔG γ→α) of austenite and ferrite phases as well as martensite start temperature (Ms).
                  </p>
                </div>
              </div>
            )}

            {/* TAB 4: AI PHASE ASSESSMENT */}
            {activeTab === "ai-analysis" && (
              <div className="p-4 bg-[#050810] rounded-xl border border-purple-500/30 space-y-3 font-mono text-xs">
                <div className="flex items-center justify-between border-b border-[#162032] pb-2">
                  <span className="text-purple-300 font-bold flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-purple-400" />
                    <span>GPT-6 Metallurgical Consultation ({selectedDoc.formula_pretty})</span>
                  </span>
                  <button
                    type="button"
                    onClick={() => runAiAnalysis(selectedDoc)}
                    disabled={aiLoading}
                    className="px-2 py-1 bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 rounded text-[10px] transition flex items-center gap-1"
                  >
                    <RefreshCw className={`w-3 h-3 ${aiLoading ? "animate-spin" : ""}`} />
                    <span>Re-evaluate</span>
                  </button>
                </div>

                {aiLoading ? (
                  <div className="py-8 text-center text-slate-400 space-y-2">
                    <RefreshCw className="w-5 h-5 animate-spin mx-auto text-purple-400" />
                    <p className="text-xs">Analyzing DFT convex hull, Pugh ductility ratio, and metallurgical phase behavior...</p>
                  </div>
                ) : aiAnalysis ? (
                  <div className="text-slate-300 text-xs leading-relaxed whitespace-pre-wrap max-h-80 overflow-y-auto pr-1">
                    {aiAnalysis}
                  </div>
                ) : (
                  <div className="text-slate-500 text-center py-4">Click Re-evaluate to generate analysis.</div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Quick Metallurgical Summary & Cross-Tool Integrations */}
        <div className="lg:col-span-5 space-y-6">
          <div className="bg-[#090e18] p-5 rounded-2xl border border-[#162032] space-y-5">
            <div className="flex items-center justify-between border-b border-[#162032] pb-3">
              <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider flex items-center gap-2">
                <Atom className="w-4 h-4 text-sky-400" />
                <span>Unit Cell & Composition</span>
              </h3>
            </div>

            {/* Elements constituent list */}
            <div className="space-y-2 font-mono text-xs">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Constituent Elements</span>
              <div className="flex flex-wrap gap-1.5">
                {selectedDoc.elements?.map((el, idx) => (
                  <span
                    key={idx}
                    className="px-2.5 py-1 rounded bg-[#050810] border border-[#1e2d46] text-sky-300 font-bold"
                  >
                    {el}
                  </span>
                ))}
              </div>
            </div>

            {/* Cell Volume & Atomic Density */}
            <div className="grid grid-cols-2 gap-3 font-mono text-xs">
              <div className="p-3 bg-[#050810] rounded-xl border border-[#162032]">
                <span className="text-[10px] text-slate-400 block">Unit Cell Volume</span>
                <span className="text-sm font-bold text-white">
                  {selectedDoc.volume ? `${selectedDoc.volume.toFixed(1)} Å³` : "N/A"}
                </span>
              </div>
              <div className="p-3 bg-[#050810] rounded-xl border border-[#162032]">
                <span className="text-[10px] text-slate-400 block">Atomic Sites (N)</span>
                <span className="text-sm font-bold text-emerald-400">{selectedDoc.nsites || "N/A"} atoms</span>
              </div>
            </div>

            {/* Cross-Tool Actions */}
            <div className="p-4 bg-[#050810] rounded-xl border border-[#162032] space-y-3 font-mono text-xs">
              <span className="text-slate-300 font-bold block uppercase tracking-wider text-[11px]">
                MetalliX Cross-Tool Interactivity
              </span>
              <p className="text-slate-400 text-[11px]">
                Inspect this crystal system in the 3D Crystallography Lab or integrate it into the alloy design engine.
              </p>

              <div className="space-y-2">
                <a
                  href={`https://next-gen.materialsproject.org/materials/${selectedDoc.material_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-full py-2 px-3 bg-[#0c1322] hover:bg-[#162032] text-sky-300 border border-[#1e2d46] rounded-xl flex items-center justify-between transition"
                >
                  <span className="flex items-center gap-1.5">
                    <ExternalLink className="w-3.5 h-3.5" />
                    <span>Open on Materials Project Portal</span>
                  </span>
                  <ChevronRight className="w-4 h-4 text-slate-500" />
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
