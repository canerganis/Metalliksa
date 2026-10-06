# LPBF alloy capability and IN625 data gate — 2026-09-23

`python/lpbf_material_capabilities.py` emits the current machine-readable
authority/capability audit (`python python/lpbf_material_capabilities.py`). It
reports build-job snapshots, transient registry inputs, model-specific adapter
values, source ranges and unavailable routes separately; it does not supply
properties to solvers or make a validation claim. IN625 remains
`thermal-screening-only` in this report.

## Current four-alloy capability

`python/four_alloy_materials.py` defines the locked identities, aliases, thermal
screening constants, slicer density, Marangoni and inherent-strain adapter
values, and literature P–v windows. Build-job
accepts only these identities. The transient registry derives estimated
solid/liquid endpoints from those constants; its interpolation is an assumed
constitutive model. A material hash identifies content, not source quality or
experimental validity. Sources: `python/four_alloy_materials.py`,
`python/lpbf_build_job_solver.py`, `python/lpbf_material_registry.py`,
`python/nist_ambench_2018_02.py`, and `PROOF.md` entries 012 and 016.

| Identity | Build-job thermal/slicer | Marangoni / inherent strain adapters | Transient material route | Direct melt-pool comparison in this repo | AMB2018-02 IN625 coverage | Same-physics GPU qualification |
| --- | --- | --- | --- | --- | --- | --- |
| Ti-6Al-4V (`ti6al4v`) | Screening available | Values present; model-level qualification open | `estimated-legacy` | Track class and W/D envelope; no full temperature property validation | `no_coverage` | Open |
| 316L (`ss316l`) | Screening available | Values present; model-level qualification open | `estimated-legacy` | Track class and W/D envelope; no full temperature property validation | `no_coverage` | Open |
| AlSi10Mg (`alsi10mg`) | Screening available | Values present; model-level qualification open | `estimated-legacy` | Read-style conduction class; published W/D absent in this fixture | `no_coverage` | Open |
| IN718 (`in718`) | Screening available | Values present; model-level qualification open | `estimated-legacy` | Track class and W/D envelope; no full temperature property validation | `proxy_only` | Open |

The W/D check is a factor-of-two *screening* envelope, per `PROOF.md` entry
012. The IN625 NIST comparison attached to build-job does not turn IN718 into
a directly validated case (`python/nist_ambench_2018_02.py`). An explicit
`cuda:0` pilot now passes same-input CPU/GPU numerical parity for bounded
single-track IN718 and 316L examples, including final 3D temperature fields,
energy balance and melt-pool dimensions. General GPU qualification remains open
across the parameter range, other alloys and independent measurements; the
pilot does not change the material capability rows above.

## IN625 solid thermal source package

| Property | Source location and material state | Available data and unit | Usable scope here |
| --- | --- | --- | --- |
| Specific heat `Cp(T)` | [Special Metals INCONEL alloy 625 bulletin, Table 2, PDF p. 2](https://www.specialmetals.com/documents/technical-bulletins/inconel/inconel-alloy-625.pdf); footnote marks values as calculated | −18…1093 °C; J/(kg K) | Combined with `k(T)` only −18…982 °C |
| Solid conductivity `k(T)` | Same bulletin, Table 3, PDF p. 2; Battelle measurements, material annealed 2100 °F for 1 h | −157…982 °C; W/(m K) | Combined with `Cp(T)` only −18…982 °C |
| Reference density and melting interval | Same bulletin, Table 2, PDF p. 2 | 8.44 g/cm³; 1290…1350 °C | Reference facts, not a temperature-dependent density law |
| Alternative solid fit | [NIST-hosted Yang et al. 2021 paper, Table 1, PDF p. 8](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=932570) | `Cp = 0.2437 T + 338.39` J/(kg K), `k = 0.0153 T + 5.2366` W/(m K); Kelvin interpretation of `T` inferred from Table 1 units and room-temperature agreement | Paper gives no explicit fit validity range; no extrapolation into liquid phase |
| Powder conductivity | [NIST Zhang et al. 2019 abstract](https://www.nist.gov/publications/thermal-properties-metallic-powder-laser-powder-bed-fusion-additive-manufacturing) | 0.65 at 100 °C, 1.02 W/(m K) at 500 °C | Separate powder state; never substitute for bulk solid |

`python/in625_thermal_material.py` retains the bulletin-only solid `k(T)` and
`Cp(T)` interpolation over −18…982 °C; that function still rejects melting.
It also supplies a separate, bounded LPBF fusion-enthalpy *literature-model
screening* snapshot, described below. The bulletin's bulk product condition
is not an LPBF powder or liquid property table.

## IN625 bounded fusion-enthalpy screening

The source-backed thermal-only registry calls are
`thermal_screening_material("IN625")` and
`thermal_screening_at("IN625", temperature_K)`. Aliases `IN625`,
`Inconel 625`, and `Inconel-625` resolve to one deterministic revision.
The capability is restricted to mass-specific sensible and fusion enthalpy,
heat capacity, conductivity, and liquid fraction from **273.15 to 1623.15 K**.
It is labelled `unvalidated-literature-model-screening`; no laser, powder,
flow, vapor, geometry, or full transient prediction is claimed. The full
`material()` transient route, build-job and four-alloy allowlist remain closed.

| Input used | Value / rule | Primary locator and evidence class |
| --- | --- | --- |
| Solid `Cp(T)` | `362 + 0.125 T + 0.0001741 T² − 7.527126×10⁻⁸ T³` J/(kg K), `T` in K | [Sabau et al. 2020, Appendix B](https://doi.org/10.1007/s11663-020-01808-w); JMatPro-calculated solid-phase fit, not a measured curve |
| Solid `k(T)` | `4.93 + 0.01575 T` W/(m K), `T` in K | Same Appendix B; JMatPro-calculated fit |
| Liquid endpoint | `Cp=700` J/(kg K), `k=30` W/(m K) | Same Appendix B, liquid-phase model constants; used only through the melting interval ending at liquidus |
| Fusion interval | 1290…1350 °C = 1563.15…1623.15 K; linear liquid fraction | Same paper, “Setup of STLF Simulation Model and Material Properties” |
| Latent heat | 290 kJ/kg = 290000 J/kg | Same section; literature/model input |
| Mushy constitutive rule | Linear interpolation from solid `Cp,k` at solidus to liquid constants at liquidus; uniform distribution of fusion latent heat over 60 K | Explicit implementation screening assumption, **not** an independently measured property |

The specific enthalpy reference is `h(273.15 K)=0`; the solid polynomial is
integrated analytically, then the mushy sensible interpolation and 290 kJ/kg
latent term are integrated exactly. The content hash includes the formula
coefficients, temperature limits, model assumptions, source locator, and
uncertainty label. It is an identity for these inputs, not evidence of
experimental validity. Sabau et al. do not provide a quantified uncertainty
for these constitutive inputs or a stated safe extrapolation range; the
implementation therefore stops at liquidus and does not predict liquid
superheating.

[Lin et al. 2020, Table 2](https://yan.cee.illinois.edu/files/2021/08/LinAM.pdf)
provides a distinct constant-property IN625 model: solid/liquid density
8440/7640 kg/m³, `Cp` 550/500 J/(kg K), `k` 10/23.2 W/(m K), fusion latent
heat 223 kJ/kg, solidus/liquidus 1563/1623 K, emissivity 0.4, absorptivity
0.445 and liquid viscosity 0.006 Pa s. Its **3000 K is labelled an evaporation
temperature**, not an independently established boiling point. These numbers
are documented as a competing model, not silently mixed into the Sabau
snapshot. The different latent heat, optical and liquid values are material
model uncertainty. Sabau et al. also label emissivity 0.7 as a simulation
assumption and discuss absorptivity 0.3/0.5 sensitivity; neither is used by
the bounded enthalpy call.

## Missing evidence before broader admission

The full transient registry requires a source-backed, positive five-column table
`[T_K, rho_kg_m3, k_W_mK, Cp_J_kgK, viscosity_Pa_s]` extending at least to
boiling temperature, plus solidus, liquidus, latent heat, absorptivity,
emissivity and surface-tension slope (`python/lpbf_material_registry.py`). The
sources above offer different liquid *model* constants but no defensible
single material table through an independently supported boiling temperature.
The 3000 K Lin evaporation threshold cannot be substituted for boiling in
the existing transient contract. Temperature-dependent density, viscosity,
powder state and optical calibration are also unresolved. The NIST solid fit
has no stated validity interval. Extending any solid fit into superheated
liquid or through vapor would invent model input.

IN625 remains `available=false` in the transient catalog without a complete
supplied table, while `thermalOnlyAvailable=true` identifies the bounded
enthalpy screening call. The four-alloy build-job identity allowlist still
rejects it. The separate legacy `lpbf_thermal_solver.py` secondary table still
contains estimated IN625 melt-pool constants; those are not this source-bounded
registry snapshot and do not establish validation. Any future full thermal admission needs source, material state,
units, temperature span, interpolation, uncertainty and numerical comparison.
Separate build-job, slicer, fatigue and qualification evidence would be
required for those features. [NIST AM-Bench 2018 benchmark description](https://www.nist.gov/ambench/amb2018-02-description)
describes bare-plate IN625 tracks; its melt-pool measurements are a comparison
target, not a thermophysical property source or approval of the model.
