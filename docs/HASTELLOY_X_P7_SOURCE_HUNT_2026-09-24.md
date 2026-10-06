# Hastelloy X P7 source review — 2026-09-24

## Decision

Do not admit Hastelloy X through the full melting-range alloy data gate. The sources reviewed do not provide one chemistry/state-matched, uncertainty-bounded set of heat capacity, enthalpy, conductivity, and density across the solid-to-liquid range. Scheel et al. is suitable for a source-labelled, bounded pilot only if measured quantities are kept distinct from assumptions. No runtime property curves or alloy registry entry are added by this review.

## Source findings

- Scheel et al. (2023), LPBF as-deposited Hastelloy X: DSC Cp/enthalpy coverage is reported from 30 to 1500 °C, fusion enthalpy is 225 kJ/kg, and solidus/liquidus are 1357.6/1399.5 °C. Room-temperature density is 8352 kg/m³ ±2% and treated as constant. Solid thermal diffusivity/conductivity coverage ends below melting; conductivity at solidus is extrapolated and the liquid model applies a 15× factor rather than a liquid-state conductivity measurement. Reported uncertainty is incomplete for the full property set.
  - [Article DOI](https://doi.org/10.1016/j.ijmecsci.2023.108583)
  - [Open full text](https://digitalcollection.zhaw.ch/bitstream/11475/29349/3/2023_Scheel-etal_Advancing-efficiency-reliability-in-thermal-analysis-in-LPBF.pdf)
- NASA AM thermophysical database: relevant L-PBF Hastelloy X context and solid-range property measurements, but no matched complete melting-range property set was established in this review. It remains contextual support, not a full gate pass.
  - [NASA JANNAF/AIAA report](https://ntrs.nasa.gov/api/citations/20220013752/downloads/Metal_AM_Processes_JANNAF_9-28-2022.pdf)
  - [NASA ASTM ICAM report](https://ntrs.nasa.gov/api/citations/20220016247/downloads/ASTM_ICAM_Material%20Properties_10-31-2022_FInal.pdf)
- NIMS TPDB experiment 264: the accessible record identifies a melt-state density measurement by electrostatic levitation. Its accessible file inventory does not establish Cp, conductivity, or enthalpy, and chemistry/LPBF state matching was not established. Keep this density evidence separate; do not splice it into the Scheel property revision.
  - [NIMS dataset DOI 10.48505/nims.5721](https://mdr.nims.go.jp/datasets/908a2bb0-1bb8-4404-ba30-ee7c0a2e9843)

## Pilot boundary

A bounded numerical pilot may use only the source-covered Cp and fusion enthalpy. Any liquid conductivity, temperature-dependent density, or other unmeasured input must be separately labelled as an assumption and excluded from claims of measured validation. The pilot would not qualify Hastelloy X, establish process validity, or satisfy P7.

## Gate and next action

- P7 alternate-alloy full-range data gate: not passed.
- Hastelloy X runtime alloy admission: closed.
- Next source step: capture source bytes, exact tables/curves, chemistry/state metadata, and uncertainty for any proposed property revision; inspect the raw NIMS analysis file before making claims beyond the accessible dataset metadata.
- Preserve P4 failed, P5 unavailable, and P6 partial statuses. Continue with the separately scoped physics closure and GPU scale/performance work; do not infer qualification from CPU/CUDA parity.

## NIMS experiment 264 visibility boundary

The public MDR metadata identifies a Nilaco-supplied melt-state Hastelloy X
specimen, but exposes no elemental composition percentages, chemistry/specimen
identifier, numerical density points, or uncertainty. Its files include a
density analysis and an ambiguously named ESL text file; the public record does
not establish surface-tension or viscosity fit results for this specimen.
NIMS documents that its broader oscillating-drop method can derive surface
tension and viscosity, but that general method description is not evidence that
experiment 264 publishes those properties. No source files were downloaded or
scraped for this review; NIMS prohibits scraping and bulk acquisition. Keep the
dataset as a separate density-source lead until a permitted, source-specific
inspection establishes values and uncertainty.
