import React, { useState, useEffect, useRef } from "react";
import { Calculator, AlertTriangle, Table2, Beaker, Cuboid, Activity, Compass } from "lucide-react";
import { pythonComputationService, PythonDFTOutcome } from "../services/pythonComputationService";
import { ElasticityResultPanel } from "./MaterialsProjectElasticityPanel";
import { SYMMETRY_FIELDS, ElasticityFormState, buildElasticityInput, CrystalSystem, InputMode } from "../utils/elasticityInput";
import { createElasticityRequestGate } from "../utils/elasticityRequestGate";

interface MaterialsProjectExplorerProps {
  onSelectToCrystal?: (formula: string, crystalSystem: string) => void;
}

export function MaterialsProjectExplorer({ onSelectToCrystal }: MaterialsProjectExplorerProps) {
  const [form, setForm] = useState<ElasticityFormState>({
    input_mode: 'custom',
    crystal_system: 'cubic',
    cij: {},
    k_vrh: '',
    g_vrh: '',
    density: '',
    formula: '',
    molar_mass: '',
    atoms_per_formula_unit: ''
  });

  const requestGate = useRef(createElasticityRequestGate());
  const [pythonDftResult, setPythonDftResult] = useState<PythonDFTOutcome | null>(null);
  const [isComputing, setIsComputing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Unmount safety
  useEffect(() => {
    return () => {
      requestGate.current.invalidate();
    };
  }, []);

  const handleChange = (updater: (prev: ElasticityFormState) => ElasticityFormState) => {
    setForm(prev => {
      const next = updater(prev);
      return next;
    });
    // Invalidate results upon any edit
    setPythonDftResult(null);
    setErrorMsg(null);
    requestGate.current.invalidate();
    setIsComputing(false);
  };

  const handleCijChange = (field: string, value: string) => {
    handleChange(prev => ({
      ...prev,
      cij: { ...prev.cij, [field]: value }
    }));
  };

  const calculate = async () => {
    let payload;
    try {
      payload = buildElasticityInput(form);
    } catch (e: any) {
      setPythonDftResult(null);
      setErrorMsg(e.message);
      return;
    }

    const currentGen = requestGate.current.begin();
    setErrorMsg(null);
    setIsComputing(true);
    setPythonDftResult(null);

    try {
      const res = await pythonComputationService.calculateDFTProperties(payload);
      if (requestGate.current.isCurrent(currentGen)) {
        setPythonDftResult(res);
        setIsComputing(false);
      }
    } catch (err: any) {
      if (requestGate.current.isCurrent(currentGen)) {
        setErrorMsg(err.message || "Network error occurred during elasticity calculation.");
        setIsComputing(false);
      }
    }
  };

  const renderCijInputs = () => {
    if (form.input_mode !== 'custom') return null;
    const fields = SYMMETRY_FIELDS[form.crystal_system] || [];

    return (
      <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-3 mt-3">
        {fields.map(f => (
          <div key={f} className="flex flex-col gap-1">
            <label htmlFor={`input-${f}`} className="text-[10px] text-slate-400 font-mono uppercase">
              {f.toUpperCase()} (GPa)
            </label>
            <input
              id={`input-${f}`}
              type="number"
              step="any"
              value={form.cij[f] || ''}
              onChange={(e) => handleCijChange(f, e.target.value)}
              className="bg-[#050810] border border-[#1e2d46] rounded px-2 py-1.5 text-xs text-white font-mono placeholder:text-slate-600 focus:outline-none focus:border-sky-400 focus:ring-1 focus:ring-sky-400/50 transition-colors"
              placeholder="e.g. 150.5"
            />
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3.5 bg-[#090e18] p-5 rounded-2xl border border-[#162032] shadow-sm">
        <div className="w-12 h-12 rounded-xl bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400 shrink-0 shadow-[0_0_16px_rgba(14,165,233,0.25)]">
          <Table2 className="w-6 h-6" />
        </div>
        <div>
          <h2 className="text-lg font-extrabold text-white font-mono tracking-wide uppercase flex items-center gap-2">
            Continuum Elasticity Homogenization
            <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 text-[10px] border border-amber-500/20 font-normal">
              Not a DFT Calculation
            </span>
          </h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5 leading-relaxed">
            User-supplied single-crystal elastic constants or isotropic moduli homogenization.
            Computes Voigt-Reuss-Hill moduli, mechanical stability, directional bounds, and Debye properties.
          </p>
        </div>
      </div>

      {/* Main Input Form */}
      <div className="bg-[#090e18] p-5 rounded-2xl border border-[#162032] space-y-6">

        {/* Modes Toggle */}
        <div className="flex flex-wrap items-center gap-3 border-b border-[#162032] pb-4">
          <label className="text-[11px] font-mono text-slate-400 uppercase tracking-wider font-bold">Input Mode:</label>
          <div role="group" aria-label="Input mode" className="flex bg-[#050810] border border-[#1e2d46] rounded-lg p-0.5">
            <button
              type="button"
              aria-pressed={form.input_mode === 'custom'}
              onClick={() => handleChange(p => ({ ...p, input_mode: 'custom' }))}
              className={`px-4 py-1.5 rounded-md text-xs font-mono transition-colors ${
                form.input_mode === 'custom'
                  ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30'
                  : 'text-slate-400 hover:text-slate-300 border border-transparent'
              }`}
            >
              Custom C_ij
            </button>
            <button
              type="button"
              aria-pressed={form.input_mode === 'isotropic'}
              onClick={() => handleChange(p => ({ ...p, input_mode: 'isotropic' }))}
              className={`px-4 py-1.5 rounded-md text-xs font-mono transition-colors ${
                form.input_mode === 'isotropic'
                  ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30'
                  : 'text-slate-400 hover:text-slate-300 border border-transparent'
              }`}
            >
              Isotropic K/G
            </button>
          </div>
        </div>

        {/* Dynamic Fields */}
        <div className="space-y-4">
          {form.input_mode === 'custom' && (
            <div className="space-y-2">
              <label htmlFor="crystal-system-select" className="text-[11px] font-mono text-slate-300 uppercase font-bold flex items-center gap-1.5">
                <Cuboid className="w-3.5 h-3.5 text-sky-400" />
                Crystal Symmetry
              </label>
              <select
                id="crystal-system-select"
                value={form.crystal_system}
                onChange={(e) => handleChange(p => ({ ...p, crystal_system: e.target.value as CrystalSystem }))}
                className="bg-[#050810] border border-[#1e2d46] rounded-lg px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-sky-400 focus:ring-1 focus:ring-sky-400/50 block w-full sm:w-64"
              >
                <option value="cubic">Cubic</option>
                <option value="hexagonal">Hexagonal</option>
                <option value="trigonal">Trigonal</option>
                <option value="tetragonal">Tetragonal</option>
                <option value="orthorhombic">Orthorhombic</option>
                <option value="isotropic">Isotropic</option>
              </select>

              <div className="pt-2">
                <span className="text-[11px] font-mono text-slate-400">Independent Elastic Constants (C_ij)</span>
                {renderCijInputs()}
              </div>
            </div>
          )}

          {form.input_mode === 'isotropic' && (
            <div className="space-y-2">
              <span className="text-[11px] font-mono text-slate-300 uppercase font-bold flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-emerald-400" />
                Isotropic Moduli
              </span>
              <div className="flex gap-4 pt-1">
                <div className="flex flex-col gap-1 w-32">
                  <label htmlFor="input-k" className="text-[10px] text-slate-400 font-mono uppercase">Bulk Mod. K (GPa)</label>
                  <input
                    id="input-k"
                    type="number"
                    step="any"
                    value={form.k_vrh}
                    onChange={(e) => handleChange(p => ({ ...p, k_vrh: e.target.value }))}
                    className="bg-[#050810] border border-[#1e2d46] rounded px-2 py-1.5 text-xs text-white font-mono placeholder:text-slate-600 focus:border-emerald-400 focus:ring-1 focus:ring-emerald-400/50"
                  />
                </div>
                <div className="flex flex-col gap-1 w-32">
                  <label htmlFor="input-g" className="text-[10px] text-slate-400 font-mono uppercase">Shear Mod. G (GPa)</label>
                  <input
                    id="input-g"
                    type="number"
                    step="any"
                    value={form.g_vrh}
                    onChange={(e) => handleChange(p => ({ ...p, g_vrh: e.target.value }))}
                    className="bg-[#050810] border border-[#1e2d46] rounded px-2 py-1.5 text-xs text-white font-mono placeholder:text-slate-600 focus:border-emerald-400 focus:ring-1 focus:ring-emerald-400/50"
                  />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Global Optional Properties */}
        <div className="border-t border-[#162032] pt-4 space-y-3">
          <span className="text-[11px] font-mono text-slate-300 uppercase font-bold flex items-center gap-1.5">
            <Beaker className="w-3.5 h-3.5 text-purple-400" />
            Physical Properties (Optional)
          </span>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="flex flex-col gap-1">
              <label htmlFor="input-formula" className="text-[10px] text-slate-400 font-mono uppercase">Chemical Formula</label>
              <input
                id="input-formula"
                type="text"
                value={form.formula}
                onChange={(e) => handleChange(p => ({ ...p, formula: e.target.value }))}
                placeholder="e.g. Ni3Al"
                className="bg-[#050810] border border-[#1e2d46] rounded px-2 py-1.5 text-xs text-white font-mono placeholder:text-slate-600 focus:border-purple-400"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="input-density" className="text-[10px] text-slate-400 font-mono uppercase">Density (g/cm³)</label>
              <input
                id="input-density"
                type="number"
                step="any"
                value={form.density}
                onChange={(e) => handleChange(p => ({ ...p, density: e.target.value }))}
                placeholder="e.g. 4.43"
                className="bg-[#050810] border border-[#1e2d46] rounded px-2 py-1.5 text-xs text-white font-mono placeholder:text-slate-600 focus:border-purple-400"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="input-mm" className="text-[10px] text-slate-400 font-mono uppercase">Molar Mass (g/mol)</label>
              <input
                id="input-mm"
                type="number"
                step="any"
                value={form.molar_mass}
                onChange={(e) => handleChange(p => ({ ...p, molar_mass: e.target.value }))}
                placeholder="Paired w/ Atoms"
                className="bg-[#050810] border border-[#1e2d46] rounded px-2 py-1.5 text-xs text-white font-mono placeholder:text-slate-600 focus:border-purple-400"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="input-atoms" className="text-[10px] text-slate-400 font-mono uppercase">Atoms / Formula</label>
              <input
                id="input-atoms"
                type="number"
                step="any"
                value={form.atoms_per_formula_unit}
                onChange={(e) => handleChange(p => ({ ...p, atoms_per_formula_unit: e.target.value }))}
                placeholder="e.g. 4"
                className="bg-[#050810] border border-[#1e2d46] rounded px-2 py-1.5 text-xs text-white font-mono placeholder:text-slate-600 focus:border-purple-400"
              />
            </div>
          </div>
          <p className="text-[10px] text-slate-500 font-mono">
            Acoustic velocities require density. Debye temperature also requires a known composition or the paired molar mass and atoms per formula unit.
          </p>
        </div>

        {/* Error Bar */}
        {errorMsg && (
          <div role="alert" className="p-3 bg-amber-950/30 border border-amber-800/50 rounded-lg text-amber-300 text-xs font-mono flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Calculate Action */}
        <div className="flex justify-end pt-2">
          <button
            type="button"
            onClick={calculate}
            disabled={isComputing}
            className="px-5 py-2.5 bg-sky-500 hover:bg-sky-400 active:bg-sky-600 disabled:opacity-50 disabled:cursor-not-allowed text-slate-950 font-mono font-bold text-xs rounded-xl flex items-center gap-2 transition-colors shadow-[0_0_12px_rgba(14,165,233,0.25)]"
          >
            <Calculator className="w-4 h-4" />
            <span>{isComputing ? 'Computing Tensor...' : 'Calculate Elasticity'}</span>
          </button>
        </div>
      </div>

      {/* Results Panel */}
      {(isComputing || pythonDftResult) ? (
        <div className="bg-[#090e18] p-5 rounded-2xl border border-[#162032]">
          <ElasticityResultPanel outcome={pythonDftResult} computing={isComputing} />
        </div>
      ) : (
        <p role="status" className="text-sm text-slate-400">Unavailable — enter elastic inputs and select Calculate Elasticity.</p>
      )}
    </div>
  );
}
