# IN625 P7 source gate — 2026-09-24

## Decision

IN625 remains **partial**. A model-specific bare-substrate conduction screening
path now exists and has CPU/CUDA numerical parity, but primary sources do not
establish one exact LPBF material lot with a complete, temperature-valid set of
density, conductivity, heat capacity, viscosity/flow, vaporization, and optical
inputs through the solver's boiling boundary. Powder-bed/full-transient
capability stays closed; the scoped bare-plate GPU result is not scientific
qualification.

## Evidence by property

| Property | Source evidence | Gate limitation |
| --- | --- | --- |
| Solid Cp and thermal diffusivity | Georgia Tech Gen3 CSP IN625 page describes repeated measurements (at least three) and 95% confidence uncertainties; conductivity is derived as `k = alpha Cp rho` with density assumed constant at 8.44 g/cm³. | Solid specimen measurements; derived `k`; no liquid/boiling-range table or LPBF lot identity. |
| Liquid density, viscosity, surface tension | Containerless levitation studies report liquid properties for BÖHLER L625. | BÖHLER composition differs from the NIST AM-Bench IN625 powder record; available measurement intervals are finite and far below a complete boiling range. |
| Powder optical input | Balbaa and Elbestawi report diffuse-reflectance measurements for IN625 powder over 400–1400 nm; the paper gives 0.62 at 1070 nm as an EOS M280 example. | Powder reflectance-derived input; not a temperature-dependent molten-surface or keyhole absorptivity law, and not proven to be the NIST bare-plate lot. |
| LPBF lot identity | NIST AM-Bench 2018 record identifies AMB2018-01 IN625 powder composition and particle sizes. | The record supplies no matching full high-temperature thermophysical/optical property table. Alloy name alone does not establish lot identity across the other studies. |

## Primary sources

- [Georgia Tech Gen3 CSP — Inconel 625 thermophysical data](https://gen3csp.gatech.edu/inconel-alloy-625/) — repeat counts, uncertainty notes, and conductivity derivation.
- [Leitner, *Thermophysical property measurement of industrial metals and alloys using electromagnetic levitation*](https://www.tugraz.at/fileadmin/user_upload/Institute/IEP/Thermophysics_Group/Files/Diss-LeitnerThomas.pdf) — containerless BÖHLER L625 measurement campaign and composition.
- [Balbaa & Elbestawi, 2022, DOI 10.3390/jmmp6010002](https://doi.org/10.3390/jmmp6010002) — IN625 powder diffuse reflectance and the 1070 nm EOS M280 example.
- [NIST AM-Bench 2018 IN625 material record](https://ambench.nist.gov/data?id=2) — identified powder lot, composition, and particle-size distribution.

The sources support useful, separately bounded records. Combining them into
one boiling-range LPBF table would require unverified lot equivalence,
unsupported high-temperature extrapolation, and a powder-to-melt optical
substitution. No such substitutions were made. A future admission requires
source-backed validity and uncertainty for each required property, plus
numerical checks and CPU/GPU parity on that same admitted material revision.

## Scoped bare-plate screening route

The project now exposes `in625_bareplate_field.run_cpu/run_cuda` for a separate
3D bare-substrate conduction model. Its material revision is the bounded
JMatPro-derived constitutive snapshot; density is the supplier bulletin's
8.44 g/cm³ used as an explicitly constant, not lot-matched assumption. The
laser input is an explicit absorbed-W boundary; this route does not infer a
universal absorptivity or mix the separate NIST optical measurement into the
material table. The finite-volume domain has six adiabatic faces and a moving
normalized Gaussian surface source; a shared 1/1.01 source-capture gate rejects
truncated sources before normalization.

This is a **model-specific numerical screening admission only**. NIST
AMB2018-02 is a bare-plate IN625 benchmark and therefore matches the geometry
class, but the current four-step smoke did not run or compare an AMB case.
The material source does not publish an independent validity span or
uncertainty for the JMatPro/mushy model; the registry continues to report
`sourceValidityRange_K: null`. No powder-bed, build-job, full transient, or
experimental-validity claim follows. Details and current numerical values are
in [the scoped report](IN625_BAREPLATE_GPU_SCREENING_2026-09-24.md).
