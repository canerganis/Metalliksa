# Shared LPBF thermal core: equation, units, and evidence crosswalk

Status: **partial evidence map; scientific validation is not established**.
Scope here is the reference `lpbf_simulation.transient` enthalpy finite-volume
path and its shared source/conduction operators. Analytical Rosenthal/Goldak,
layered-support, CUDA, and OpenFOAM paths are distinct contracts and are not
silently covered by this map.

## Implemented contract

| Term | Implemented form and code | Units / boundary | Evidence and limitation |
|---|---|---|---|
| Stored thermal state | `H = rho * (h(T) - h(T0))`; initialize `H=0`, recover `h=H/rho+h0`; accepted step updates `H += dt * (passive_rate + source)`. `python/lpbf_simulation.py` (`transient`) | `rho`: kg m⁻³; specific `h`: J kg⁻¹; `H`: J m⁻³; `dt`: s; rate/source: W m⁻³; `T`: K. Density is fixed at the reference state for stationary-grid conservation. | Enthalpy formulation is established in phase-change numerical literature, e.g. [Voller, Cross & Markatos (1987)](https://onlinelibrary.wiley.com/doi/10.1002/nme.1620240119). This citation supports the method family, not Metalliksa's constitutive properties or result validity. Material properties remain estimated and uncertainty is not quantified. |
| Internal conduction | Harmonic face conductivity `kf=2*kL*kR/(kL+kR)`; pair rate `kf*(TR-TL)/dx²`, added to one cell and subtracted from the other; inactive faces are masked. [Rate operator](../python/lpbf_simulation.py#L315) (`L315-L325`); [transient rate/diagonal operator](../python/lpbf_simulation.py#L328) (`L328-L349`). | `k`: W m⁻¹ K⁻¹; `T`: K; `dx`: m; rate: W m⁻³. Exterior faces are insulated in this operator. | Pairwise construction implies zero volume-summed internal transfer (up to floating-point summation). The independent small-grid heterogeneous face regression is `python/test_lpbf_shared_thermal_conduction_faces.py`; it checks unequal `k`, signs, inactive faces, spacing scaling, and global pair cancellation. This is an operator software invariant, not physical validation. Kadioglu et al. (2008), below, derive the harmonic mean under specific subcell assumptions; coarse-grid accuracy remains problem dependent. |
| Moving Gaussian source | Cell-integrated Gaussian weights with two equal-weight time-quadrature nodes; each node contributes `0.5 * weights * power/(captured_mass*dx³)`. `python/lpbf_core_physics.py` (`gaussian_interval`, `cell_weights`, `GAUSS_NODES`); `python/lpbf_heat_source.py:L25-L37` | `power`: W; lengths converted to m; normalized cell weights are dimensionless; volumetric source: W m⁻³. Domain capture must pass the configured minimum; accepted source is renormalized to the requested absorbed power over represented cells. | [NIST DLMF §7.2](https://dlmf.nist.gov/7.2) defines `erf/erfc`, the math functions used for Gaussian interval integration. It does not support the LPBF absorptivity, penetration-depth, or beam-profile assumptions. Those require source-specific experimental evidence; the present source model remains assumed/unvalidated. |
| Base boundary | Where the selected contract uses an isothermal base, the half-cell term is `2*k*(T-T0)/dx²`, subtracted from rate. `python/lpbf_simulation.py` (`transient`) | Equivalent base-face heat flux: W m⁻²; divided by cell width to rate: W m⁻³. This is a fixed-temperature Dirichlet boundary at `T0`. | Boundary selection is model configuration. The boundary discretization has not been matched to an independent base-flux measurement. Layered support has a separate contact-resistance operator and requires its own verification. |
| Exposed top boundary | `q_loss = h_conv*(T-T0) + emissivity*sigma*(T⁴-T0⁴)`, subtracted from the top-cell rate. [Top loss](../python/lpbf_simulation.py#L532) (`L532-L534`). | `h_conv`: W m⁻² K⁻¹; `sigma`: W m⁻² K⁻⁴; surface loss: W m⁻²; rate after `/dx`: W m⁻³. | `sigma=5.670374419…×10⁻⁸ W m⁻² K⁻⁴` is the exact 2022 CODATA value in [NIST CODATA](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=958143). This verifies the constant and unit only. The convection coefficient, emissivity, ambient choice, and applicability to the modeled LPBF surface are assumptions requiring source/uncertainty evidence. The NIST gas-flow measurements below constrain setup transferability; they supply no melt-surface `h_conv`. |
| Timestep and integration | Explicit first-order Euler; `dt` bounded by requested maximum, diffusion/stability row sum, scan events, and a source sensible-increment limiter. [Step assembly](../python/lpbf_simulation.py#L513) (`L513-L548`), [enthalpy update](../python/lpbf_simulation.py#L559) (`L559-L561`), and [source limiter](../python/lpbf_heat_source.py#L25) (`L25-L37`). | Time in seconds; rate in W m⁻³; volumetric enthalpy in J m⁻³. | This is the implemented numerical contract, not a cited physical law. Milton's one-dimensional boundary-stability analysis below does not establish the implemented `0.9` factor or stability of the complete nonlinear enthalpy/source update. The code enforces a 250,000-step budget and fails on material validity bounds rather than clipping. Temporal and spatial resolution still require separate convergence evidence. |
| External units | Request geometry in µm, scan speed in mm/s, and temperatures in °C are converted at input/geometry boundaries; solver coordinates, `dx`, time, and temperature are SI (`m`, `s`, `K`). `python/lpbf_core_physics.py:calculate_mesh_domain`; `python/lpbf_simulation.py:validate`, `transient` | SI dimensional consistency follows BIPM definitions for `m`, `kg`, `s`, `K`, `J`, and `W`. | [BIPM SI Brochure, 9th edition, updated 2026](https://doi.org/10.59161/AUEZ1291). This is a unit-system authority, not a code-conversion or model validation result. |

## Model-specific assumptions and numerical choices

The equations below describe this reference implementation. A mathematical or
method citation supports only the stated construction; it supplies no missing
material measurements, parameter uncertainty, or experimental validation.

### Enthalpy, phase fraction, and inversion

[enthalpy_table](../python/lpbf_material_registry.py#L190) constructs
`h(T) = integral(Cp(theta) dtheta) + L*f(T)`, with an arbitrary sensible-enthalpy
reference at the first table temperature and
`f(T) = clip((T-Ts)/(Tl-Ts), 0, 1)`. `Cp` is in J kg⁻¹ K⁻¹, `L` and `h` in
J kg⁻¹, and `f` is dimensionless. Trapezoidal integration is exact for the
represented piecewise-linear `Cp` between its knots; this does not establish
accuracy or measured provenance of the property values. The grid combines 12,000
uniform temperatures from 273.15 K to the boiling limit with property knots
and the solidus/liquidus temperatures. Temperature recovery uses linear
[inverse interpolation](../python/lpbf_simulation.py#L595) in that table.

**Method versus material gate:** Voller's enthalpy-method citation above does
not establish the linear liquid-fraction law, phase temperatures, latent heat,
or adequacy of this inversion resolution. Require independently evaluated
enthalpy/inverse-interpolation errors and a suitable phase-change reference
problem for numerical verification. Material-specific source ranges and
uncertainty remain separate requirements. Neither a dense table nor an
energy-ledger pass establishes these missing results.

### Packed powder and irreversible conductivity switching

[Reference density](../python/lpbf_simulation.py#L455) is
`rho_ref = rho(T0)*packingFraction` in cells with `z > 0`, and `rho(T0)` below;
it is fixed throughout the stationary-grid update. In powder cells,
[conductivity](../python/lpbf_simulation.py#L507) is
`k(T)*powderConductivityRatio` until the accepted state first satisfies
`T >= Tl`; [the persistent ever-melted flag](../python/lpbf_simulation.py#L627)
then causes subsequent steps to use full `k(T)`, including after cooling.
This threshold is liquidus, not solidus or the first nonzero liquid fraction.
The packed reference density remains fixed after this conductivity switch;
densification, shrinkage, and evolving porosity are not resolved here.

**Measurement applicability gate:** [Zhang, Lane, Whiting & Chou (2019), NIST](https://www.nist.gov/publications/thermal-properties-metallic-powder-laser-powder-bed-fusion-additive-manufacturing)
reports effective powder thermal properties for IN625 and Ti-6Al-4V using
laser-flash measurements and an inverse model. It supports the need for
powder-specific characterization, not a universal conductivity ratio or this
irreversible transition rule. Require matching alloy, powder morphology,
packing, atmosphere, temperature range, and uncertainty; those measurements
do not establish IN718 parameters or the validity of the switch.

### Source quadrature and beam-diameter convention

[GAUSS_NODES](../python/lpbf_core_physics.py#L7) maps two-point Gauss-Legendre
quadrature onto an accepted interval: nodes `c = 1/2 +/- 1/(2*sqrt(3))`, weights
`1/2`, and sample times `t + c*dt`. [NIST DLMF §3.5(v)](https://dlmf.nist.gov/3.5#v)
is a mathematical reference for Gauss quadrature; DLMF §7.2 above covers the
Gaussian interval functions. Neither proves the moving-source integration
error is small for the requested speed, mesh, and accepted timestep. Separate
source/time refinement evidence is needed; the enthalpy update remains Euler.

The implemented profile is `exp(-2*r^2/w^2)` at normal incidence, with
[`w = beamDiameter_um*0.5e-6`](../python/lpbf_core_physics.py#L118) in metres.
Thus the input diameter is interpreted as `2*w`, the ideal Gaussian 1/e²
intensity diameter. For this ideal profile, the derived transverse standard
deviation is `w/2`, so `D4sigma = 2*w`; that identity does not determine the
profile of a measured non-Gaussian beam. [ISO 11146-1:2021, official scope](https://www.iso.org/standard/77769.html)
concerns beam-width/divergence measurements for stigmatic and simple
astigmatic beams. Its scope is a metrology reference, not proof of this
machine's beam map or a claim of standard compliance. Record the measurement
convention, profile, calibration and uncertainty before mapping an experimental
diameter to the model. Domain capture and renormalization preserve requested
absorbed power in the represented cells; they do not validate absorption or
penetration. Domain-extent sensitivity remains a separate numerical gate.

### Base, ambient, and gray radiation

The reference base is held at preheat `T0`; the same `T0` is used as gas and
radiative-surroundings temperature in [the top loss](../python/lpbf_simulation.py#L532).
Side faces have no external heat-transfer term in this contract. The scalar
emissivity assumes gray radiation with an effective total hemispherical
emissivity; it is not automatically equal to laser absorptivity or a spectral,
directional pyrometry emissivity. [Deisenroth et al. (2021), NIST](https://www.nist.gov/publications/measurement-uncertainty-surface-temperature-distributions-laser-powder-bed-fusion)
demonstrates temperature/emissivity measurement and uncertainty analysis for
a specific high-purity nickel experiment. It provides a measurement-method
reference, not transferable IN718 emissivity values or uncertainty bounds.
**Physical-parameter gate:** base temperature/thermal coupling, ambient and
surroundings, gas coefficient, surface state and emissivity need matching
measurements and uncertainty. The CODATA constant alone supplies none of them;
numerical domain/base-location sensitivity must also be checked independently.

### Timestep safety factors and failure limits

[The initial step bound](../python/lpbf_simulation.py#L513) includes
`0.12*dx^2/max(k/(rho*Cp))`, `w/(4*v)`, the requested maximum step, final time,
and scan events. [The boundary/conduction row-sum bound](../python/lpbf_simulation.py#L535)
uses `0.9*rho*Cp_min/max(diagonal, 1e-30)`, with `Cp_min` from the property
table and the current radiation secant coefficient. [source_limited_step](../python/lpbf_heat_source.py#L25)
limits the combined passive-plus-source rate using
`allowed = min(25 K*rho*Cp/max(abs(rate), 1e-30))`; it accepts when
`allowed >= dt*(1-1e-12)`, otherwise retries with `dt = 0.95*allowed` and
reintegrates the moving source. At most 12 attempts are made before failure.
The reference loop raises when its accepted-step count exceeds 250,000.

These coefficients, denominator floors, comparison tolerance, and work limits
are implementation choices. The 25 K expression is a sensible-capacity
limiter, not a proven maximum temperature change through a nonlinear phase
transition. Neither Milton's boundary-stability reference nor Gauss
quadrature establishes stability, accuracy, or convergence of this complete
update. Preserve these settings while deriving/checking their applicable
conditions; retry success and staying below the step budget are not accuracy
evidence.

## Primary-source applicability and uncertainty gates

The following sources support bounded methodological or experimental claims.
They do not validate this implementation or assign universal material values.
Source review: 2026-09-28; code locators refer to the current checkout and must
be refreshed when the corresponding functions move.

1. **Harmonic face averaging.** [Kadioglu, Nourgaliev & Mousseau (2008),
   INL/EXT-08-13999](https://inldigitallibrary.inl.gov/content/uploads/50/2026/04/3952796.pdf),
   sections 4.1-4.3 and 5-6, derives the harmonic face mean using piecewise
   constant cell conductivity and steady subcell flux balance. Its nonlinear
   conduction examples show that harmonic and arithmetic averaging can have
   different coarse-grid errors; neither is universally more accurate.
   The report uses a different time integrator and is not an LPBF benchmark.
   **Gate:** the paired-face conservation check at
   [L341-L348](../python/lpbf_simulation.py#L341) does not establish
   heterogeneous-field accuracy. Require a resolved variable-conductivity
   reference/refinement study for the intended powder/solid contrasts before
   claiming that this face model is accurate for that regime.

2. **Explicit convection/radiation stability.** [Milton (1973),
   *Stability criteria for explicit finite difference solutions of the parabolic
   diffusion equation with non-linear boundary conditions*](https://onlinelibrary.wiley.com/doi/abs/10.1002/nme.1620070105),
   publisher abstract, studies a one-dimensional transient conduction problem
   with convective and radiative boundaries. This is contextual evidence that
   boundary cooling enters timestep restrictions. It is not a derivation for
   Metalliksa's three-dimensional, temperature-dependent enthalpy update.
   **Gate:** [L535-L542](../python/lpbf_simulation.py#L535) uses the table-minimum
   heat capacity, the current conductive row sum, and a factored radiation
   secant coefficient with a `0.9` multiplier. The citation proves neither
   that multiplier nor stability across changing properties, phase intervals,
   activation events, or source-limiter retries. Those need a derivation and
   targeted numerical evidence for this exact update; passing the limiter
   alone does not establish convergence.

3. **IN718 powder absorptivity.** [Honda & Watanabe (2025),
   *Measurement of Laser Absorptivity of Inconel Powders with Additive
   Manufacturing Machine*](https://www.jstage.jst.go.jp/article/matertrans/66/1/66_MT-M2024124/_html/-char/en),
   sections 2-4, reports powder measurements in an SLM280 under argon with a
   1070 nm Gaussian beam, over approximately 150-400 °C. The reported value
   near 0.6 and absence of significant temperature dependence apply to those
   conditions. They do not establish a molten/keyhole, bare-plate, other
   wavelength, or universal IN718 value. **Gate:** the constant absorptivity
   applied in [thermal_si_inputs, L174-L181](../python/lpbf_core_physics.py#L174)
   needs provenance matching the powder state, optical conditions, machine,
   and temperature regime, with measurement uncertainty and an explicit
   extrapolation boundary. This reference changes no input value.

4. **Source calibration and penetration.** [Ross et al. (2022),
   *Volumetric heat source calibration for laser powder bed fusion*](https://www.sciencedirect.com/science/article/pii/S221486042200656X),
   publisher abstract, describes inverse calibration of a double-ellipsoid
   source against measured solidification-boundary temperatures for conduction
   and transition melt pools. Fitted source parameters represent absorption
   and vapor-depression effects; they are not direct measurements of
   Metalliksa's Gaussian penetration parameter. Here
   [cell_weights, L27-L34](../python/lpbf_core_physics.py#L27) distributes energy
   in depth, while [L543-L548](../python/lpbf_simulation.py#L543) selects the
   bare-plate penetration input or powder-layer thickness.
   **Gate (project inference):** matching a melt pool by fitting absorptivity
   and penetration establishes calibration only. Freeze the source family and
   fitted parameters before evaluation on independent held-out observations,
   and assess parameter identifiability and measurement/numerical uncertainty.
   No evidence here establishes that powder-layer thickness equals optical
   penetration or that the fitted source resolves missing melt-flow physics.

5. **Convection coefficient and environment.** [Weaver et al. (2021),
   NIST AMS 100-43](https://nvlpubs.nist.gov/nistpubs/ams/NIST.AMS.100-43.pdf),
   abstract and sections 2-3, measures gas-speed profiles for nozzle/gas
   configurations and finds substantial position dependence. It measures gas
   flow, not the heat-transfer coefficient at a molten surface; its hot-wire
   sensor heat-transfer treatment is not a melt-pool boundary condition.
   **Gate (project inference):** the uniform `convection_W_m2K` at
   [L532-L534](../python/lpbf_simulation.py#L532) remains a setup-dependent
   assumption until supported by matching geometry, flow, gas properties,
   temperature, and uncertainty evidence. Do not transfer a sensor coefficient
   or a coefficient from another machine as a validated surface value. The
   fixed base at [L526-L531](../python/lpbf_simulation.py#L526), surface
   emissivity, and use of preheat as ambient also need separate evidence.

6. **Published LPBF boundary and surface-source example.** [Ma et al. (2015),
   NIST](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=919064),
   sections 2.2 and 2.4, describes a three-dimensional single-track thermal
   model with top-surface convection/radiation, adiabatic remaining surfaces,
   and a moving Gaussian surface heat flux. It is a methodological example,
   not the boundary contract of Metalliksa's reference transient: this code
   holds its base at preheat, omits side-surface transfer, and distributes the
   Gaussian in depth. Ma et al. used IN625 and their own material/process
   assumptions; none of those values or the reported model behavior transfers
   to IN718 without matched evidence. **Gate:** compare the implemented
   boundary/source equations on their own terms, and retain material/process
   properties as estimated until independently sourced with uncertainty.

7. **Finite-volume conservation construction.** [NIST FiPy 3.4.5 finite-volume
   documentation](https://pages.nist.gov/fipy/en/3.4.5/numerical/discret.html)
   derives control-volume transient and face-flux diffusion discretizations
   and describes zero-flux as the natural cell-centered boundary condition.
   This supports the general finite-volume method family and natural no-flux
   boundary semantics; it does not independently verify Metalliksa's Python,
   its harmonic face interpolation, nonlinear enthalpy inversion, or explicit
   update. **Gate:** retain the separate manufactured-solution, conservation,
   stability, mesh/time-refinement, and experimental evidence requirements.

## Conservation and validation status

- **Internal conduction:** paired-face discrete sum is zero by construction for
  equal cell volumes; the independent face test is the applicable software
  check. Layered contact-resistance and all backend implementations must be
  verified separately.
- **Energy ledger:** the run ledger integrates the same computed source and
  boundary arrays used by the update. Separately,
  `python/test_lpbf_shared_thermal_energy_oracle.py` reconstructs absorbed input
  from accepted laser-on intervals and base/top boundary losses from pre-update
  state, then compares with final `sum(H)*cell_volume`. The oracle passed for
  one bounded 316L reference/default-powder run. This is a software-level
  integral/accounting consistency check for that selected CPU transient; it is
  not a conservation proof for all requests, a check of beam absorption
  physics, another solver/backend, or experimental validation. It currently
  reads pre-update solver state at the source-limiter seam and independently
  reassembles the selected boundary equations; that scope and coupling must
  remain visible.
- **Manufactured solution:** `python/test_lpbf_conduction_manufactured.py`
  verifies second-order spatial consistency for the insulated constant-k
  conduction operator only (8/16/32/64 refinement ratios
  3.98461/3.99615/3.99904). This does not verify source integration, phase
  enthalpy, boundaries, transient order, GPU, or experiment.
- **Convergence:** the frozen P4 v2 fixed-5-µm time study has three accepted-dt
  levels and energy-ledger closure `3.57e-13`, but geometry trend is unresolved;
  temporal convergence remains **inconclusive**. Spatial mesh convergence is a
  separate **inconclusive** gate.
- **Backend parity:** the current CPU/PyTorch CUDA/Warp CUDA same-contract test
  passes on its frozen IN718 request. Parity establishes implementation
  agreement within tolerances; it does not establish convergence or physical
  validity.
- **Experiment:** the current model has no matching measured beam profile and
  six-section optical observer for NIST AMB2022-03 Table 4. Comparison therefore
  withholds numerical residuals and remains **unvalidated**.

For verification terminology, [Veeraragavan et al. (2016)](https://doi.org/10.1016/j.jcp.2015.12.004)
describes manufactured solutions as a solver-verification method. Its paper is
methodology evidence, not an LPBF measurement dataset.

[ASME's verification, validation and uncertainty framework](https://www.asme.org/codes-standards/publications-information/verification-validation-uncertainty)
separates implementation/mathematical verification from agreement with the
physical world. [BIPM's GUM publications](https://www.bipm.org/en/web/guest/publications/guides),
including JCGM 100 and its Monte Carlo supplement JCGM 101, provide uncertainty
evaluation methodology. They assign no uncertainty to this model by citation
alone. Keep measured-input uncertainty, model assumptions, numerical error,
and experimental comparison evidence explicit; no standards-compliance or
validation claim follows from this crosswalk.

## Evidence still required

1. Close the applicability gates above: derive/check stability for the exact
   nonlinear update, establish variable-conductivity accuracy, and obtain
   matching base-boundary, convection, optical, and emissivity evidence with
   uncertainty. Also quantify enthalpy-table/inversion error, justify the
   liquid-fraction and powder-transition assumptions, and check source/time
   and domain-extent sensitivity. The cited methods and measurements do not
   close these gates.
2. Extend the bounded energy oracle to additional contracts/backends only with
   independent pre-update inputs and explicit scope. Keep broad/full-run energy
   conservation **not verified** beyond the one tested reference case; do not
   infer beam, material, or experiment validity from its pass.
3. Establish a converged mesh/time sequence with preflighted memory and compute
   cost. Preserve the current inconclusive statuses until the stated gates pass.
4. Keep source/parameter uncertainty, numerical verification, CPU/GPU parity,
   and experimental validation as separate evidence classes.
