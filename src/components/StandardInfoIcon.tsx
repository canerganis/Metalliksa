import React, { useState, useRef, useEffect } from "react";
import { Info, X, ExternalLink, Copy, Check, BookOpen, ShieldCheck } from "lucide-react";

export interface StandardDetails {
  standardCode: string;
  secondaryCodes?: string[];
  title: string;
  governingBody: string;
  methodology: string;
  equations?: string;
  validRange?: string;
  criticalNotes?: string;
}

export const METALLURGICAL_STANDARDS: Record<string, StandardDetails> = {
  stress: {
    standardCode: "ASTM E8 / E8M-24",
    secondaryCodes: ["ISO 6892-1:2019", "ASTM E21", "NIST SP 330"],
    title: "Standard Test Methods for Tension Testing of Metallic Materials",
    governingBody: "ASTM Committee E28 on Mechanical Testing / ISO TC 164/SC 1",
    methodology:
      "Defines tension specimen geometries, strain rates, and continuous yield strength (0.2% offset Rp0.2) vs ultimate tensile strength (Rm) determination. Conversion adheres to SI base definition 1 MPa = 1 N/mm² = 10⁶ Pa and US customary definition 1 ksi = 1000 psi = 6.894757 MPa.",
    equations: "1 ksi = 6.894757 MPa | 1 MPa = 0.1450377 ksi | 1 GPa = 1000 MPa | 1 bar = 0.1 MPa",
    validRange: "Applicable across all ductile, brittle, and ultra-high-strength structural and aerospace alloys.",
    criticalNotes:
      "ASTM E21 governs elevated temperature tension testing; ASTM E8M standardizes SI metric testing protocols.",
  },
  hardness: {
    standardCode: "ASTM E140",
    secondaryCodes: ["ISO 18265:2013", "ASTM E18", "ASTM E92", "ASTM E10", "DIN 50150"],
    title: "Standard Hardness Conversion Tables for Metals",
    governingBody: "ASTM Committee E28 / ISO TC 164/SC 3 Hardness Testing",
    methodology:
      "Linear interpolation between the published conversion numbers of ASTM E140 Table 1 (Rockwell C range) and Table 2 (Rockwell B range) for non-austenitic steels: HRC, HRB, Vickers HV, Brinell HBW (10 mm carbide ball, 3000 kgf, Table 1), Brinell HB(S) (10 mm steel ball, 3000 kgf, Table 2) and Knoop HK (500 gf and over), with HV as the pivot. Tensile strength Rm is estimated from HV by interpolation in ISO 18265 Table A.1 (unalloyed and low-alloy steels). Outside the tabulated range a value is reported as unavailable; nothing is extrapolated or clamped. Converted values (Rockwell included) are reported as whole numbers.",
    equations:
      "Piecewise-linear interpolation between tabulated rows (no fitted formula) | Rm from HV per ISO 18265 Table A.1",
    validRange: "HRC 20-68 (HV 238-940) | HRB 55-100 (HV 100-240) | HBW 226-634 (HV 238-674) | HB(S) 100-240 (HV 100-240) | HK 112-920 | Rm: HV 80-650 | Leeb HLD: not converted",
    criticalNotes:
      "Approximate conversion for non-austenitic steels per ASTM E140 / ISO 18265 tables; not a substitute for direct testing. The tables used here are for non-austenitic steels only; converted values are estimates, not measurements.",
  },
  temperature: {
    standardCode: "ITS-90 / NIST SP 811",
    secondaryCodes: ["ASTM E344", "ISO 80000-5:2019", "AMS 2750G"],
    title: "International Temperature Scale of 1990 & Pyrometry Standards",
    governingBody: "CIPM / BIPM / ASTM Committee E20 on Temperature Measurement",
    methodology:
      "Governs absolute thermodynamic temperature conversions used in metallurgical kinetics, diffusion activation energy (Q/RT), homologous temperature ratios (TH = T / Tm), and pyrometric survey compliance per SAE AMS 2750G.",
    equations: "K = °C + 273.15 | °R = 1.8 × K | °F = 1.8 × °C + 32 | °R = °F + 459.67",
    validRange: "Thermodynamic absolute zero (0 K / -273.15 °C) to liquidus melting (>3000 K)",
    criticalNotes:
      "Rankine (°R) is required for US customary thermodynamic Arrhenius diffusion calculations; Kelvin (K) is required for SI thermodynamic calculations.",
  },
  toughness: {
    standardCode: "ASTM E399-24",
    secondaryCodes: ["ASTM E1820-23", "ASTM E23", "ISO 12135", "ISO 148-1"],
    title: "Standard Test Method for Linear-Elastic Plane-Strain Fracture Toughness (KIC)",
    governingBody: "ASTM Committee E08 on Fatigue and Fracture / ISO TC 164/SC 4",
    methodology:
      "Governs measurement of plane-strain fracture toughness KIC under fatigue precracked notched bend or compact tension CT specimens. Charpy V-notch CVN impact energy converts between Joules and foot-pound force.",
    equations: "1 MPa√m = 0.910048 ksi√in | 1 ksi√in = 1.09884 MPa√m | 1 J = 0.737562 ft-lbf",
    validRange: "KIC: 10 to 250 MPa√m | CVN: 2 to 300 J",
    criticalNotes:
      "Valid plane-strain thickness criterion requires specimen thickness B ≥ 2.5(KIC / σys)². Charpy CVN conversions represent empirical upper-shelf/lower-shelf correlation bounds.",
  },
  grain_length: {
    standardCode: "ASTM E112-13(2021)",
    secondaryCodes: ["ISO 643:2019", "ASTM E1382", "DIN EN ISO 643"],
    title: "Standard Test Methods for Determining Average Grain Size",
    governingBody: "ASTM Committee E04 on Metallography / ISO TC 17/SC 7",
    methodology:
      "Standardizes comparison, planimetric (Jeffries), and lineal intercept (Heyn) methods. ASTM micro-grain size number G is defined such that NA = 2^(G-1) grains per square inch at 100× magnification.",
    equations: "NA = 2^(G-1) grains/in² @ 100× | Planimetric mean diameter d̄ = 0.254 · √(2^(1-G)) mm | Mean lineal intercept ℓ̄ = 10^(-(G + 3.288)/6.643856) mm",
    validRange: "ASTM G: -3 to +16 (Coarse ingot grains to ultra-fine submicron nanocrystals)",
    criticalNotes:
      "ISO 643 grain size index m matches ASTM G within rounding (m = G). Hall-Petch yield strength scales inversely with d^(-1/2).",
  },
  corrosion: {
    standardCode: "ASTM G1 & ASTM G31-21",
    secondaryCodes: ["NACE TM0169", "ISO 8407:2021", "ASTM G59"],
    title: "Standard Practice for Preparing, Cleaning, and Evaluating Corrosion Test Specimens",
    governingBody: "ASTM Committee G01 on Corrosion of Metals / NACE International",
    methodology:
      "Standardizes immersion mass-loss corrosion rate calculations converting between metric penetration rate (mm/year) and US customary (mils per year, mpy), incorporating metal density ρ.",
    equations: "CR (mm/yr) = (87.6 × W) / (A × t × ρ) | 1 mm/yr = 39.3701 mpy | 1 mpy = 0.0254 mm/yr",
    validRange: "0.0001 mm/yr (passive aerospace titanium) to >50 mm/yr (active acid attack)",
    criticalNotes:
      "W = mass loss (mg), A = area (cm²), t = exposure time (hours), ρ = alloy density (g/cm³).",
  },
  report_matrix: {
    standardCode: "ISO/IEC 17025:2017",
    secondaryCodes: ["EN 10204 3.1 / 3.2", "ASTM E8/E8M", "ASTM E140", "Nadcap MTL"],
    title: "General Requirements for the Competence of Testing and Calibration Laboratories",
    governingBody: "ISO Committee on Conformity Assessment (CASCO) / Nadcap",
    methodology:
      "Establishes technical competence, traceability of measurement standards, and test certificate reporting conformity. Standardizes EN 10204 Type 3.1 inspection certificate dual-unit SI / US Customary reporting.",
    equations: "Dual-unit reporting (EN 10204 certificate units): SI (MPa, HV, °C, J) + US Customary (ksi, HRC, °F, ft-lbf)",
    validRange: "Global aerospace, defense, nuclear, and pressure vessel engineering documentation.",
    criticalNotes:
      "Requires recorded calibration traceability to NIST/PTB standards and documented measurement uncertainty.",
  },
  weldability: {
    standardCode: "IIW Carbon Equivalent / Pcm equations",
    secondaryCodes: ["WES 3001 (Pcm)"],
    title: "Carbon Equivalent (IIW CE / Pcm) and in-house preheat heuristic",
    governingBody: "International Institute of Welding (IIW) / Japan Welding Engineering Society (Pcm)",
    methodology:
      "Computes IIW CE and Ito-Bessyo Pcm as indicators of hydrogen-induced cold cracking susceptibility in heat-affected zones. The preheat temperature shown beside them is an unsourced in-house heuristic, not an AWS D1.1 value or procedure; it does not prescribe preheat or interpass temperatures.",
    equations: "CE(IIW) = C + Mn/6 + (Cr+Mo+V)/5 + (Ni+Cu)/15 | Pcm = C + Si/30 + (Mn+Cu+Cr)/20 + Ni/60 + Mo/15 + V/10 + 5B",
    validRange: "Carbon and low-alloy structural steels (CE: 0.20 to 0.70)",
    criticalNotes:
      "Qualify preheat and interpass temperature per the governing code and procedure qualification, not from this tool.",
  },
  diffusion: {
    standardCode: "Fick's 2nd Law / ASTM E1077",
    secondaryCodes: ["ASM Handbook Vol 4", "ISO 2639", "SAE AMS 2759/7"],
    title: "Standard Test Methods for Estimating Depth of Decarburization & Carburizing Kinetics",
    governingBody: "ASTM Committee E04 / SAE Aerospace Materials Division",
    methodology:
      "Applies non-steady-state error function solution to Fick's Second Law: (Cx - C0)/(Cs - C0) = 1 - erf(x / 2√(Dt)). D(T) follows Arrhenius relationship with temperature-dependent austenite lattice diffusivity.",
    equations: "Cx(x, t) = Cs - (Cs - C0) · erf(x / (2√(D·t))) | D = D0 · exp(-Q / (R·T))",
    validRange: "Carburizing, nitriding, and decarburization between 450 °C and 1100 °C",
    criticalNotes:
      "Effective case depth (ECD) is conventionally defined at 0.40% C or 50 HRC / 513 HV per ISO 2639.",
  },
  schaeffler: {
    standardCode: "Schaeffler-type Cr_eq / Ni_eq equivalents",
    secondaryCodes: ["Schaeffler (1949) constitution diagram"],
    title: "Chromium / Nickel equivalents with a coarse rule-based phase class",
    governingBody: "Not a standard: published Schaeffler-type equivalents",
    methodology:
      "Calculates Chromium equivalent (ferrite stabilizer) and Nickel equivalent (austenite stabilizer) with Schaeffler-type coefficients and assigns a coarse rule-based phase class. It is not the WRC-1992 formulation and does not predict a measured ferrite number.",
    equations: "Creq = Cr + Mo + 1.5·Si + 0.5·Nb | Nieq = Ni + 30·C + 0.5·Mn + 30·N",
    validRange: "Dissimilar welds and stainless clad steels (Creq: 0 to 40, Nieq: 0 to 35)",
    criticalNotes:
      "The ferrite value shown is a rule-based class value (0 / 15 / 80 or a linear estimate), not a measured FN; measure FN per AWS A4.2 for qualification.",
  },
  xrd: {
    standardCode: "ASTM E975-13 & Bragg's Law",
    secondaryCodes: ["ICDD PDF-4+", "ISO 20203", "SAE HS-784"],
    title: "Standard Practice for X-Ray Determination of Retained Austenite in Steel with Near Random Crystallographic Orientation",
    governingBody: "ASTM Committee E04 on Metallography / ICDD",
    methodology:
      "Governs constructive interference of monochromatic X-rays (Cu Kα λ = 1.5406 Å) through crystal planes. Solves Bragg's Law nλ = 2d·sin(θ) and Scherrer crystallite size broadening τ = Kλ / (β·cos(θ)).",
    equations: "nλ = 2d·sin(θ) | d_hkl = a / √(h² + k² + l²) for cubic lattices",
    validRange: "Diffraction angles 2θ: 10° to 150° across FCC, BCC, and HCP crystal structures",
    criticalNotes:
      "ASTM E975 requires multi-peak integration (e.g. (200)α, (211)α, (200)γ, (220)γ, (311)γ) to correct for preferred orientation.",
  },
  hall_petch: {
    standardCode: "ASTM E112 / Hall-Petch Relation",
    secondaryCodes: ["ISO 643", "NIST Metallurgy Monograph"],
    title: "Grain Boundary Strengthening Formulation & Microstructural Quantification",
    governingBody: "ASTM Committee E04 / International Metallurgical Societies",
    methodology:
      "Quantifies dislocation pile-up at grain boundaries: σy = σ0 + ky · d^(-1/2), connecting ASTM G grain size directly to yield strength increment.",
    equations: "σy = σ0 + ky · d^(-1/2) | d = 254 · √(2^(1-G)) µm (ASTM E112 planimetric diameter)",
    validRange: "Grain diameters d: 1 µm to 500 µm (breakdown occurs in sub-15nm nanocrystals)",
    criticalNotes:
      "ky is the Hall-Petch locking parameter (~0.5–0.7 MPa·m^(1/2) for steel, ~0.07 MPa·m^(1/2) for pure Al).",
  },
  transformation: {
    standardCode: "ASTM A1033-18 & Andrews (1965)",
    secondaryCodes: ["Grange Formulation", "ISO 13576", "AMS 2759"],
    title: "Standard Practice for Quantitative Measurement and Reporting of Hypoeutectoid Carbon and Low-Alloy Steel Phase Transformations",
    governingBody: "ASTM Committee A01 on Steel, Stainless Steel and Related Alloys",
    methodology:
      "Calculates martensite start (Ms), bainite start (Bs), and austenitizing equilibrium temperatures (Ac1, Ac3) from steel alloy composition using Andrews' empirical linear regression equations.",
    equations: "Ms (°C) = 539 - 423C - 30.4Mn - 17.7Ni - 12.1Cr - 7.5Mo | Ac3 (°C) = 910 - 203√C - 15.2Ni + 44.7Si + 104V + 31.5Mo",
    validRange: "Carbon content 0.05% to 0.85% wt%, total alloy additions < 8 wt%",
    criticalNotes:
      "High cooling rates (> Critical Cooling Rate) required to avoid bainitic/ferritic bays and achieve 100% martensite at Ms.",
  },
};

interface StandardInfoIconProps {
  category: keyof typeof METALLURGICAL_STANDARDS | string;
  customStandard?: Partial<StandardDetails>;
  className?: string;
  align?: "left" | "right" | "center";
  size?: "sm" | "md";
}

export const StandardInfoIcon: React.FC<StandardInfoIconProps> = ({
  category,
  customStandard,
  className = "",
  align = "right",
  size = "sm",
}) => {
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [isPinned, setIsPinned] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const popoverRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const std: StandardDetails = {
    ...(METALLURGICAL_STANDARDS[category] || {
      standardCode: "ASTM / ISO Standard",
      title: "Metallurgical Test & Conversion Standard",
      governingBody: "International Standardization Bodies",
      methodology: "Standardized cross-conversion and metallurgical measurement procedures.",
    }),
    ...customStandard,
  };

  // Close when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(event.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
        setIsPinned(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsOpen(false);
        setIsPinned(false);
      }
    };

    if (isOpen || isPinned) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, isPinned]);

  const handleCopyCode = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(`${std.standardCode} - ${std.title}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleToggleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isPinned) {
      setIsPinned(false);
      setIsOpen(false);
    } else {
      setIsPinned(true);
      setIsOpen(true);
    }
  };

  const handleMouseEnter = () => {
    if (!isPinned) {
      setIsOpen(true);
    }
  };

  const handleMouseLeave = () => {
    if (!isPinned) {
      setIsOpen(false);
    }
  };

  // Alignment positioning classes for popover
  const alignmentClass =
    align === "left"
      ? "left-0"
      : align === "center"
      ? "left-1/2 -translate-x-1/2"
      : "right-0";

  return (
    <div
      className={`relative inline-flex items-center ${className}`}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <button
        ref={buttonRef}
        type="button"
        onClick={handleToggleClick}
        aria-label={`View ${std.standardCode} standard info`}
        title={`View standard details: ${std.standardCode} (Click to pin)`}
        className={`inline-flex items-center justify-center rounded-full transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-sky-400/50 ${
          size === "sm" ? "w-4 h-4 text-[10px]" : "w-5 h-5 text-xs"
        } ${
          isPinned
            ? "bg-sky-500 text-slate-950 font-bold shadow-[0_0_8px_rgba(56,189,248,0.6)]"
            : isOpen
            ? "bg-sky-500/25 text-sky-300 border border-sky-400/60"
            : "text-slate-400 hover:text-sky-300 bg-slate-800/80 hover:bg-sky-950/60 border border-slate-700/80 hover:border-sky-500/50"
        }`}
      >
        <Info className={size === "sm" ? "w-2.5 h-2.5" : "w-3 h-3"} />
      </button>

      {/* Floating Tooltip / Popover */}
      {(isOpen || isPinned) && (
        <div
          ref={popoverRef}
          role="dialog"
          aria-modal="false"
          className={`absolute top-full mt-2 z-50 w-72 sm:w-80 md:w-96 p-3.5 bg-[#080d1a] border border-sky-500/40 rounded-xl shadow-2xl shadow-black/80 text-left backdrop-blur-md transition-all ${alignmentClass}`}
        >
          {/* Header */}
          <div className="flex items-start justify-between gap-2 pb-2.5 border-b border-[#162032]">
            <div className="flex-1">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-sky-500/20 text-sky-300 border border-sky-400/50 shadow-sm flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3 text-sky-400" />
                  {std.standardCode}
                </span>
                {isPinned && (
                  <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-amber-500/20 text-amber-300 border border-amber-400/40">
                    Pinned
                  </span>
                )}
              </div>
              <h4 className="text-xs font-bold text-white mt-1.5 leading-snug">
                {std.title}
              </h4>
              <p className="text-[10px] text-slate-400 font-mono mt-0.5">
                {std.governingBody}
              </p>
            </div>

            <div className="flex items-center gap-1 shrink-0">
              <button
                type="button"
                onClick={handleCopyCode}
                className="p-1 rounded text-slate-400 hover:text-sky-300 hover:bg-slate-800 transition"
                title="Copy standard designation"
              >
                {copied ? (
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                ) : (
                  <Copy className="w-3.5 h-3.5" />
                )}
              </button>

              <button
                type="button"
                onClick={() => {
                  setIsPinned(false);
                  setIsOpen(false);
                }}
                className="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
                title="Close standard info"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Body Content */}
          <div className="py-2.5 space-y-2 text-xs">
            {/* Methodology */}
            <div>
              <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block font-semibold">
                Scope &amp; Methodology:
              </span>
              <p className="text-slate-300 text-[11px] leading-relaxed mt-0.5">
                {std.methodology}
              </p>
            </div>

            {/* Equations if available */}
            {std.equations && (
              <div className="p-2 bg-[#050912] rounded-lg border border-[#162032] font-mono">
                <span className="text-[9px] text-sky-400 uppercase tracking-wider block font-bold mb-0.5">
                  Standard Conversion Relation:
                </span>
                <p className="text-[10px] text-slate-200 break-words font-semibold">
                  {std.equations}
                </p>
              </div>
            )}

            {/* Valid Range / Boundaries */}
            {std.validRange && (
              <div className="flex items-start gap-1.5 text-[11px]">
                <span className="text-[10px] font-mono text-slate-400 shrink-0 font-semibold">
                  Domain:
                </span>
                <span className="text-slate-300 text-[10px] font-mono">
                  {std.validRange}
                </span>
              </div>
            )}

            {/* Critical Notes */}
            {std.criticalNotes && (
              <div className="text-[10px] text-amber-300/90 bg-amber-500/10 border border-amber-500/20 p-2 rounded-lg leading-relaxed">
                <span className="font-bold block text-amber-300 mb-0.5 font-mono text-[9px] uppercase tracking-wide">
                  Metallurgical Precaution:
                </span>
                {std.criticalNotes}
              </div>
            )}

            {/* Cross references */}
            {std.secondaryCodes && std.secondaryCodes.length > 0 && (
              <div className="pt-1.5 border-t border-[#162032] flex items-center gap-1.5 flex-wrap">
                <span className="text-[9px] font-mono text-slate-400">Equivalent Standards:</span>
                {std.secondaryCodes.map((sec, idx) => (
                  <span
                    key={idx}
                    className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-slate-800 text-slate-300 border border-slate-700"
                  >
                    {sec}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Footer Hint */}
          <div className="pt-2 border-t border-[#162032] flex items-center justify-between text-[9px] text-slate-500 font-mono">
            <span>{isPinned ? "Click 'i' or 'X' to unpin" : "Click 'i' to keep pinned"}</span>
            <span className="text-sky-400">Verified ASTM / ISO</span>
          </div>
        </div>
      )}
    </div>
  );
};
