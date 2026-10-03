import React, { useState, useMemo } from "react";
import { useEscapeToClose } from "./AccessibleModal";
import {
  BookOpen,
  Search,
  Check,
  Cpu,
  Layers,
  ArrowRight,
  ShieldCheck,
  Battery,
  Droplets,
  Flame,
  Activity,
  Filter,
  Sparkles,
  Info,
  ExternalLink,
  ChevronRight,
  Zap,
} from "lucide-react";
import { EXTENDED_CIRCUIT_LIBRARY, CircuitModelDoc } from "../data/circuitModelLibrary";
import { CircuitTopology } from "./EquivalentCircuitBuilder";

interface CircuitLibraryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectModel: (topology: CircuitTopology) => void;
  activeModelId?: string;
}

export function CircuitLibraryModal({
  isOpen,
  onClose,
  onSelectModel,
  activeModelId,
}: CircuitLibraryModalProps) {
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [activeDoc, setActiveDoc] = useState<CircuitModelDoc>(
    EXTENDED_CIRCUIT_LIBRARY.find((m) => m.id === activeModelId) || EXTENDED_CIRCUIT_LIBRARY[0]
  );

  // Categories list
  const categories = [
    { id: "all", label: "All Circuit Models", icon: Layers, count: EXTENDED_CIRCUIT_LIBRARY.length },
    { id: "battery", label: "Battery & Intercalation", icon: Battery, count: EXTENDED_CIRCUIT_LIBRARY.filter((m) => m.category === "battery").length },
    { id: "corrosion", label: "Corrosion & Passive Films", icon: ShieldCheck, count: EXTENDED_CIRCUIT_LIBRARY.filter((m) => m.category === "corrosion").length },
    { id: "coating", label: "Protective Coatings", icon: Droplets, count: EXTENDED_CIRCUIT_LIBRARY.filter((m) => m.category === "coating").length },
    { id: "solid-state", label: "Solid-State Ceramics", icon: Cpu, count: EXTENDED_CIRCUIT_LIBRARY.filter((m) => m.category === "solid-state").length },
    { id: "fuel-cell", label: "Fuel Cells & MEA", icon: Flame, count: EXTENDED_CIRCUIT_LIBRARY.filter((m) => m.category === "fuel-cell").length },
  ];

  // Filtered models
  const filteredModels = useMemo(() => {
    return EXTENDED_CIRCUIT_LIBRARY.filter((model) => {
      const matchesCategory = selectedCategory === "all" || model.category === selectedCategory;
      const q = searchQuery.toLowerCase().trim();
      const matchesSearch =
        !q ||
        model.name.toLowerCase().includes(q) ||
        model.description.toLowerCase().includes(q) ||
        model.cdcNotation.toLowerCase().includes(q) ||
        model.physicalPhenomenon.toLowerCase().includes(q);
      return matchesCategory && matchesSearch;
    });
  }, [selectedCategory, searchQuery]);

  useEscapeToClose(isOpen, onClose);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Circuit model library"
        className="bg-[#090e18] border border-[#1e2d46] rounded-2xl w-full max-w-6xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Top Header */}
        <div className="p-5 border-b border-[#162032] flex items-center justify-between bg-[#050810]/70">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-sky-500/10 border border-sky-400/30 text-sky-400">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white font-mono flex items-center gap-2">
                <span>Equivalent Circuit Model Library (ECM Pre-Sets)</span>
                <span className="text-xs px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 font-mono border border-sky-400/30 font-normal">
                  {EXTENDED_CIRCUIT_LIBRARY.length} Standard Models
                </span>
              </h2>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                Load curated, peer-reviewed equivalent circuit models with pre-configured parameters, Boukamp CDC notation, &amp; data fitting guides.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 rounded-xl bg-[#0c1424] border border-[#1e2d46] hover:border-slate-500 text-xs font-mono text-slate-300 hover:text-white transition-all"
          >
            ✕ Close
          </button>
        </div>

        {/* Filter & Search Bar */}
        <div className="p-4 border-b border-[#162032] bg-[#070b14] flex flex-col md:flex-row items-center justify-between gap-3">
          {/* Search Box */}
          <div className="relative w-full md:w-80">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by model, CDC (e.g. R(CR)), or mechanism..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl pl-9 pr-3 py-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-400 placeholder:text-slate-600"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 text-xs font-mono"
              >
                ✕
              </button>
            )}
          </div>

          {/* Category Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto w-full md:w-auto pb-1 md:pb-0 scrollbar-none">
            {categories.map((cat) => {
              const Icon = cat.icon;
              const isSelected = selectedCategory === cat.id;
              return (
                <button
                  key={cat.id}
                  type="button"
                  onClick={() => setSelectedCategory(cat.id)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-mono whitespace-nowrap transition-all ${
                    isSelected
                      ? "bg-sky-500/20 border border-sky-400 text-sky-200 font-bold"
                      : "bg-[#090e18] border border-[#162032] text-slate-400 hover:text-slate-200 hover:border-slate-700"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{cat.label}</span>
                  <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-[#050810] text-slate-400">
                    {cat.count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Content Body: Left Model Cards List & Right Detailed Inspector */}
        <div className="grid grid-cols-1 lg:grid-cols-12 flex-1 overflow-hidden min-h-0">
          {/* Left Column: Models List */}
          <div className="lg:col-span-5 border-r border-[#162032] overflow-y-auto p-4 space-y-2.5 bg-[#050810]/40 max-h-[60vh] lg:max-h-none">
            {filteredModels.length === 0 ? (
              <div className="text-center py-12 text-slate-500 font-mono text-xs">
                No equivalent circuits matching "{searchQuery}"
              </div>
            ) : (
              filteredModels.map((model) => {
                const isSelected = activeDoc.id === model.id;
                return (
                  <div
                    key={model.id}
                    onClick={() => setActiveDoc(model)}
                    className={`p-3.5 rounded-xl border transition-all cursor-pointer relative group ${
                      isSelected
                        ? "bg-[#0c1424] border-sky-400/80 shadow-[0_0_16px_rgba(56,189,248,0.15)]"
                        : "bg-[#090e18] border-[#162032] hover:border-slate-700 hover:bg-[#0c1322]"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2">
                          <span
                            className={`text-[9px] px-1.5 py-0.5 rounded font-mono font-bold uppercase ${
                              model.category === "battery"
                                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                                : model.category === "corrosion"
                                ? "bg-rose-500/10 text-rose-400 border border-rose-500/30"
                                : model.category === "coating"
                                ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/30"
                                : model.category === "solid-state"
                                ? "bg-purple-500/10 text-purple-400 border border-purple-500/30"
                                : "bg-amber-500/10 text-amber-400 border border-amber-500/30"
                            }`}
                          >
                            {model.category}
                          </span>
                          <span className="text-[10px] font-mono text-sky-400/90 font-bold bg-sky-500/10 px-2 py-0.5 rounded border border-sky-400/20">
                            {model.cdcNotation}
                          </span>
                        </div>
                        <h4 className="text-xs font-bold text-white font-mono mt-1.5 line-clamp-1">
                          {model.name}
                        </h4>
                      </div>

                      <ChevronRight className={`w-4 h-4 text-slate-500 transition-transform ${isSelected ? "translate-x-1 text-sky-400" : ""}`} />
                    </div>

                    <p className="text-[11px] text-slate-400 font-mono mt-2 line-clamp-2 leading-relaxed">
                      {model.description}
                    </p>

                    <div className="mt-3 flex items-center justify-between text-[10px] font-mono border-t border-[#162032] pt-2 text-slate-500">
                      <span>Stages: {model.topology.branches.length}</span>
                      <span>Freq: {model.suggestedFrequencyRange}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Right Column: Model Detail Documentation & Quick Load */}
          <div className="lg:col-span-7 overflow-y-auto p-5 space-y-5 bg-[#090e18]">
            {/* Model Title & Load Button Bar */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#162032] pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-sky-400 font-bold uppercase tracking-wider">
                    {activeDoc.categoryLabel}
                  </span>
                  <span className="text-slate-600">|</span>
                  <span className="text-xs font-mono text-slate-400">
                    CDC: <strong className="text-sky-300 font-bold">{activeDoc.cdcNotation}</strong>
                  </span>
                </div>
                <h3 className="text-base font-bold text-white font-mono mt-1">
                  {activeDoc.name}
                </h3>
              </div>

              <button
                type="button"
                onClick={() => {
                  onSelectModel(activeDoc.topology);
                  onClose();
                }}
                className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white text-xs font-mono font-bold shadow-[0_0_16px_rgba(56,189,248,0.4)] transition-all whitespace-nowrap active:scale-95"
              >
                <Zap className="w-4 h-4 fill-current" />
                <span>Instantly Load Model</span>
              </button>
            </div>

            {/* Description & Physical Phenomenon */}
            <div className="grid grid-cols-1 gap-3 text-xs font-mono">
              <div className="p-3.5 bg-[#050810] rounded-xl border border-[#162032] space-y-1">
                <span className="text-slate-500 uppercase tracking-wider text-[10px] flex items-center gap-1.5 font-bold">
                  <Info className="w-3.5 h-3.5 text-sky-400" />
                  Physical Electrochemical Phenomenon
                </span>
                <p className="text-slate-300 leading-relaxed">
                  {activeDoc.physicalPhenomenon}
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="p-3 bg-[#050810] rounded-xl border border-[#162032] space-y-1">
                  <span className="text-slate-500 uppercase tracking-wider text-[10px] font-bold block">
                    Nyquist Plot Signature (-Z'' vs Z')
                  </span>
                  <p className="text-slate-300 text-[11px] leading-relaxed">
                    {activeDoc.nyquistShapeDesc}
                  </p>
                </div>

                <div className="p-3 bg-[#050810] rounded-xl border border-[#162032] space-y-1">
                  <span className="text-slate-500 uppercase tracking-wider text-[10px] font-bold block">
                    Bode Frequency Characteristics
                  </span>
                  <p className="text-slate-300 text-[11px] leading-relaxed">
                    {activeDoc.bodeCharacteristics}
                  </p>
                </div>
              </div>
            </div>

            {/* Key Parameter Table */}
            <div className="space-y-2 font-mono">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5 text-sky-400" />
                  Extractable Physical Parameters ({activeDoc.keyParameters.length})
                </span>
                <span className="text-[10px] text-slate-400">
                  Recommended Sweep: {activeDoc.suggestedFrequencyRange}
                </span>
              </div>

              <div className="border border-[#162032] rounded-xl overflow-hidden bg-[#050810]">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#090e18] border-b border-[#162032] text-[10px] text-slate-400 uppercase">
                    <tr>
                      <th className="p-2.5 font-semibold">Symbol</th>
                      <th className="p-2.5 font-semibold">Parameter Name</th>
                      <th className="p-2.5 font-semibold">Typical Range</th>
                      <th className="p-2.5 font-semibold">Physical Interpretation</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#162032] text-[11px]">
                    {activeDoc.keyParameters.map((param, pIdx) => (
                      <tr key={pIdx} className="hover:bg-[#0c1424] transition-colors">
                        <td className="p-2.5 text-sky-300 font-bold whitespace-nowrap">
                          {param.symbol}
                        </td>
                        <td className="p-2.5 text-slate-200 whitespace-nowrap">
                          {param.name}
                        </td>
                        <td className="p-2.5 text-amber-300 whitespace-nowrap">
                          {param.typicalRange}
                        </td>
                        <td className="p-2.5 text-slate-400 leading-normal">
                          {param.physicalMeaning}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Data Fitting Best Practices */}
            <div className="p-3.5 bg-sky-500/5 rounded-xl border border-sky-500/20 text-xs font-mono space-y-1">
              <span className="text-sky-400 font-bold text-[11px] flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5" />
                Data Fitting Guidelines &amp; Quality Control
              </span>
              <p className="text-slate-300 text-[11px] leading-relaxed">
                {activeDoc.fittingNotes}
              </p>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-[#162032] bg-[#050810] flex items-center justify-between text-xs font-mono">
          <span className="text-slate-500 text-[11px]">
            Selected: <strong className="text-white">{activeDoc.name}</strong> ({activeDoc.cdcNotation})
          </span>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl bg-[#090e18] border border-[#1e2d46] hover:border-slate-500 text-slate-300 text-xs"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => {
                onSelectModel(activeDoc.topology);
                onClose();
              }}
              className="flex items-center gap-1.5 px-5 py-2 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-xs transition-all shadow-[0_0_12px_rgba(56,189,248,0.3)]"
            >
              <Zap className="w-3.5 h-3.5 fill-current" />
              <span>Load Into Workspace</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
