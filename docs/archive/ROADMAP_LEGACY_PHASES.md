# LPBF & Metallurgy Simulation Roadmap (`ROADMAP.md`)

This roadmap defines the phased developmental milestones for the **Metalliksa Additive Manufacturing & Metallurgy Intelligence Platform**. It is a planning document, not a claim that every checked item is production-ready. Every completed milestone must undergo dual academic and functional verification and be registered in [`PROOF.md`](../../PROOF.md).

---

## Phase Overview

```
[Ground Truth Data] ➔ [Thermal & Melt Pool Physics] ➔ [Microstructure & Solidification]
                                                                                        │
[Digital Twin Interop]  [Defect & Fatigue Prediction]  [Residual Stress & Distortion]
```

---

## North-Star Product Target: LPBF Defect Digital Twin

The primary product goal is not only to solve temperature fields. Given a CAD
part (STL), direct toolpath (CLI / G-Code), or parametric benchmark pattern,
along with powder/feedstock specification, machine profile, and process parameters,
Metalliksa must produce a traceable, uncertainty-aware map of melt-pool
behavior and defect risk across the part:

`CAD / CLI + powder + machine + P/v/h/t + scan strategy`
`→ scanner kinematics (acceleration & skywriting)`
`→ thermal history → melt-pool geometry/stability`
`→ LoF / keyhole / balling risk → 3D defect map & relative density (%99.X)`

### 3-Tier Toolpath & Kinematics Ingestion Architecture
1. **Tier 1 (Core & High Precision): Direct Toolpath Import (CLI / G-Code):**
   - Parse Common Layer Interface (`.cli`) and open G-Code/Open-Laser vectors directly.
   - Zero guessing of machine paths: provides exact hatch vectors, contour passes, and scan order.
2. **Tier 2 (Agile R&D Screening): Parametric Benchmark Patterns:**
   - Instant parameter optimization without CAD files: Single Track, 90° Turnaround (sharp corners), Multi-track Meander, and Island / Checkerboard (e.g. 5x5 mm).
3. **Tier 3 (User Showcase & Rapid Inspection): In-App STL Slicing:**
   - Drag-and-drop STL with lightweight 2D polygon slicing (`BasicSTLSlicer`) and automatic meander toolpath generation for instant 3D visualization.

The system must distinguish a **keyhole regime** from **keyhole porosity** and
must not claim an exact porosity percentage when powder gas content, atmosphere,
packing, or machine-specific evidence is unavailable. Outputs therefore include
risk bands, predicted porosity ranges, uncertainty, spatial location, and the
evidence/assumptions used.

GO-MELT is a reference thermal backend and benchmark, not the complete product
target. Metalliksa must beat a declared GO-MELT baseline on at least one
reproducible axis—error at equal runtime, runtime at equal error, or validated
part-level defect prediction—without hiding unsupported physics or validation
gaps.

## Phase: Ground Truth Data Foundation & Standards (✅ COMPLETED)
- [x] **5-Tier Relational Schema**: `Build` $\rightarrow$ `ProcessParams` $\rightarrow$ `Sample` $\rightarrow$ `Properties` $\rightarrow$ `Source`.
- [x] **Curated Literature Datasets**: Peer-reviewed ground truth for Ti-6Al-4V, 316L SS, and AlSi10Mg with resolvable DOIs.
- [x] **Derived Quantities Engine**: Real-time calculation of $E_L$ (LED), $E_A$ (AED), $E_V$ (VED), $I_0$ (Peak Intensity), and $\Delta H / h_s$ (Normalized Enthalpy).
- [x] **Iso-VED Limitation Demonstrator**: Interactive sandbox demonstrating laser spot diameter and thermal dwell time decoupling.
- [x] **Standards Integration**: ASTM F3055, ASTM B962 (Archimedes), ASTM E8/E8M (Tensile), ASTM E1245 (Porosity).
- [x] **Measured melt-pool W/D catalog**: NIST AMB2022-03 Table 4 + Guo 2024 Table 3 in `meltpool_literature_catalog.py`. AlSi10Mg / Ti-6Al-4V measured isolated tracks: honest gaps (PROOF 023). Solver-echo batches are not ground truth.

---

## Phase: Analytical & Numerical Melt-Pool Thermal Screening (🟡 IN PROGRESS)
- [x] **Analytical Moving Heat Source**: Rosenthal 3D steady-state point source solver.
- [x] **3D Interactive Melt Pool Visualizer**: Dynamic isotherm geometry ($T_{\text{liquidus}}$, $T_{\text{solidus}}$, $T_{\text{vaporization}}$).
- [x] **Eagar-Tsai 3D Distributed Heat Source**: Finite 1/e² Gaussian (`eagar-tsai-v1`) on the Melt Pool 3D lab. Build Job verdict stays `rosenthal-screening-v1`. Not powder-bed k degradation and not Goldak FEA.
- [x] **Goldak double-ellipsoid field**: Fachinotti–Cardona (2008) erf-corrected Nguyen integral (`goldak-v1`). Beam-seeded axes, not FEA.
- [x] **Dynamic Keyhole Vaporization Depth**: Fabbro cylindrical keyhole (`fabbro-keyhole-v1`, Appl. Sci. 2020) on Goldak/ET lab paths. Fresnel \(A\) only (no stacked \(\eta_\mathrm{eff}\)). Recoil is Knight \(0.54 P_\mathrm{sat}(T_s)\) with \(T_s\le T_v\), not collapse CFD.
- [x] **Marangoni Convection (screening)**: Heiple–Roper \(\partial\gamma/\partial T\) sign + 30–60 ppm S inversion (`marangoni-heiple-v1`). Reports Ma / flow direction / \(\mathrm{Pe}_{Ma}\). Not Navier–Stokes CFD and not a W/D fit.
- [x] **Measured W/D catalog**: `meltpool-lit-catalog-v1` (NIST AMB2022-03 Table 4, Guo 2024 Table 3). AlSi10Mg left as `no measured track`. Ti-6Al-4V PROOF 003 stays asymptotic. Solver-echo datasets are not ground truth.
- [ ] **GO-MELT Baseline Harness**: Reproduce a bounded GO-MELT case with identical inputs, hardware, mesh/time-step policy, warm-up accounting, error norms, memory, and wall-clock reporting. Do not generalize the published 678× comparison beyond its stated uniform-mesh baseline.
- [ ] **Part-to-Solver Input Contract**: Convert CAD local geometry, powder state, machine/laser profile, layer plan, and scan strategy into one versioned process vector and preserve it in every result.

---

## Phase: Microstructure & Rapid Solidification Kinetics (🟡 IN PROGRESS)
- [x] **Thermal Gradient ($G$) and Solidification Rate ($R$) Mapping**: Liquidus stations on the Melt Pool conduction field (`solidification-front-v1`). $G=|\nabla T|$, $R=v n_x\cos\theta$. Not a CAFE solver.
- [x] **Solidification Morphology Criteria**: Hunt 1984 $G/R$ screening bands. Not Gäumann CET (no $N_0$ calibration) and not a Build Job input.
- [x] **Microstructural Scale Estimation**: Hunt–Lu $\lambda_1 \propto G^{-1/2}R^{-1/4}$ (LPBF µm cells) and Kirkwood $\lambda_2 \propto \dot{T}^{-1/3}$ with $\dot{T}=G\cdot R$.
- [x] **Solid-State Phase Transformation Models** (notes only, no invented fractions):
  - Ti-6Al-4V: $\beta \rightarrow \alpha'$ when cooling $> 410\text{ K/s}$ (Ahmed & Rack 1998).
  - 316L SS: Austenite cellular / dendritic network (spacing from PDAS/SDAS only).
  - AlSi10Mg: $\alpha$-Al with eutectic Si network (not quantified).

---

## Phase: Macro-Scale Inherent Strain & Part Distortion (🔵 UPCOMING)
- [ ] **Inherent Strain Tensor Calibration**: Derivation of anisotropic inherent strains ($\varepsilon_{xx}^*, \varepsilon_{yy}^*, \varepsilon_{zz}^*$) from local thermal history.
- [ ] **Voxelized Multi-Layer Finite Element Solver**: Fast layer-by-layer mechanical relaxation.
- [ ] **Baseplate Springback & Support Separation**: Simulating residual stress release post-EDM wire cut.

---

## Phase: Part-Level Defect and Porosity Digital Twin (🟡 CORE PRODUCT MILESTONE)
- [ ] **Defect Taxonomy and Output Contract**: Return separate LoF, keyhole, balling, and gas-pore risk; never collapse all of them into a single VED score or binary “keyhole” label.
- [ ] **Scanner Kinematics & Delay Physics**: Galvanometer mirror inertia, acceleration/deceleration profiles ($a_{\text{max}}$), jump/mark delays, and skywriting simulation to capture localized thermal spikes at vector endpoints and turnarounds.
- [ ] **LoF Physics (🟡 Harkin Criterion)**: Semi-elliptical inter-track and inter-layer overlap model: $(h/W)^2 + (t/D)^2 \le 1$ (Harkin et al. 2023) evaluated across vectors, borders, and layer rotations.
- [ ] **Keyhole Porosity (🔴 King & Cunningham Criteria)**: Normalized enthalpy $\Delta H / h_s$ scaling and aspect ratio threshold ($D/W > 1.5$) combined with high-speed X-ray vapor depression collapse conditions at scanner turnaround points.
- [ ] **Balling Instability (🟣 Rayleigh-Plateau Criterion)**: Melt pool cylindrical capillary breakup criterion ($L/W > \pi \approx 3.14$) and Yadroitsev continuity threshold under high scan speeds or insufficient laser power.
- [ ] **3D Spatial Defect Mapping (Three.js)**: Direct visualization of defect coordinates on the transparent 3D part geometry (yellow LoF, red Keyhole, purple Balling markers/voxels).
- [ ] **Relative Density (%99.X) & UQ Integration**: Cumulative defect volume integration ($1 - V_{\text{pore}}/V_{\text{total}}$) and probability density functions $P(\text{Defect})$ under laser/powder stochastic variation via Monte Carlo UQ.
- [ ] **Powder/Atmosphere Gas-Pore Prior**: Include particle-size distribution, packing, morphology, reuse state, oxygen/moisture/gas evidence, chamber conditions, and an explicit unknown state when unavailable.
- [ ] **Part-Level Porosity Aggregation**: Map voxel/track/layer risks back to the CAD part and report a porosity interval, defect locations, dominant mechanism, confidence, and out-of-domain warning.
- [ ] **Experimental Holdout Validation**: Validate single-track, multi-track, and multi-layer cases with melt-pool measurements and XCT/Archimedes porosity where available; calibration and holdout builds must remain separate.
- [ ] **High-Fidelity Hotspot Escalation**: Use the fast multilevel thermal solver globally and invoke a more expensive thermal-fluid/keyhole model only for high-risk regions.
- [ ] **Murakami $\sqrt{\text{area}}$ Fatigue Model**: Add only after defect morphology and size distributions are validated against independent CT and mechanical data.

---

## Phase: Autonomous Closed-Loop Optimization (🔵 UPCOMING)
- [ ] **Bayesian Process Window Optimization**: Optimize productivity against predicted defect risk and uncertainty, not a universal relative-density target; use the validated part-level defect digital twin as the objective.
- [ ] **Generative In-Situ Defect Mitigation**: Feed-forward parameter adaptation for thin walls, overhangs, and bulk regions.
