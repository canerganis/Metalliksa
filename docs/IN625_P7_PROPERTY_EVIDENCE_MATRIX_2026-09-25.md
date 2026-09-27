# IN625 P7 property evidence matrix — 2026-09-25

## Decision

IN625 remains **thermal-screening-only**. The existing bounded bare-plate
enthalpy path is an unvalidated numerical screening model. `fullTransient` and
`buildJob` remain unavailable. The evidence reviewed here does not support
assembling a complete, lot-matched table through an independently established
boiling boundary, or qualifying flow, powder-bed, optical, evaporation, or
production predictions.

“Not established” below means the source or artifact reviewed does not provide
enough evidence to make that claim; it does not mean the physical property is
zero or unknowable. No values are inferred from unrelated alloy lots, states,
or models in this matrix.

## Required property evidence

The target identity for a future process-matched admission is the material
actually used in the selected case, not generic UNS N06625. For an AMB2018
comparison, retain the applicable NIST material certificate, powder/plate
state, and case identity as a source-bound identity. AMB2018-01 reports its
powder composition and particle-size distribution; AMB2018-02 separately
identifies bare IN625 substrates and has its own substrate certificate. A
shared alloy name does not establish that these are the same heat, lot, or
surface condition. [NIST AMB2018-01 record](https://ambench.nist.gov/data?id=2),
[AMB2018-02 description](https://www.nist.gov/ambench/amb2018-02-description)

| Property / identity input | Source, chemistry/lot/state, and evidence type | Published/model-valid range | Uncertainty evidence | Gate status | Missing evidence for admission |
| --- | --- | --- | --- | --- | --- |
| Material chemistry and lot identity | NIST AMB2018-01 powder record identifies IN625 powder, mass composition Ni-20.61Cr-8.82Mo-3.97Nb-0.81Fe-0.39Ti-0.30Al-0.18Si-0.04Mn-0.02C-0.012N, and D10/D50/D90 16.4/30.6/47.5 µm. NIST says the powder was from one lot and virgin powder was used. AMB2018-02 bare plates are a distinct substrate population with a material certificate linked from its description. This is measured/certified identity evidence, not a thermophysical property table. | Lot-specific record only; no temperature interval. | Composition method/certificate is provided by NIST; it does not quantify uncertainty for the thermophysical properties below. | **Partial identity evidence; not a property admission.** AMB2018-01 powder identity must not be silently assigned to AMB2018-02 plate material. | Pin exact benchmark case and certificate bytes/revision; transcribe all reported chemistry, limits, and measurement methods; establish whether the thermal-property specimen is the same heat/lot and relevant state. |
| Solid specific heat, Cp(T) | Georgia Tech Gen3 CSP IN625 page describes repeated measurements (at least three), STA 449 F3, argon purge/protective gas, sample mass 117–118 mg. Special Metals bulletin Table 2 separately labels Cp values “calculated.” Neither source is identified as the NIST AMB2018-01 or -02 material lot. | Georgia Tech downloadable workbook contains measured-temperature coverage; the web page does not state endpoints. Special Metals table is −18 to 982 °C. Neither supports liquid/boiling coverage. | Georgia Tech states 95% confidence uncertainties are in the workbook. Special Metals table does not state pointwise uncertainty on the cited page. The current runtime snapshot instead uses Sabau/JMatPro solid Cp fit, not either source’s measured curve. | **Solid-only evidence; insufficient for full transient.** | Archive and review the actual workbook bytes and uncertainty columns; identify chemistry, heat treatment, and measurement range; obtain a state-/lot-matched Cp(T) to the chosen upper bound or document a separately validated constitutive model with quantified uncertainty. |
| Solid thermal conductivity, k(T) | Georgia Tech measures diffusivity and Cp, then calculates k=αCpρ using constant assumed density 8.44 g/cm³. Special Metals bulletin Table 3 reports measurements on material annealed at 2100 °F for one hour. Neither is documented as the NIST benchmark lot. | Georgia Tech workbook coverage is not stated on its page; Special Metals table is −18 to 982 °C. No liquid/boiling coverage. | Georgia Tech 95% confidence bars are in workbook; k is derived and depends on measured α/Cp plus assumed ρ. Special Metals page gives no uncertainty. Sabau’s runtime k law is JMatPro-calculated in the solid and a fixed liquid constant, not a measured table. | **Solid-only; model and measurement authorities are distinct.** | Preserve raw α, Cp, covariance/error propagation, density assumption, and specimen state. Require liquid k evidence or a documented validated model and quantified uncertainty; avoid combining independent curves as if co-measured. |
| Solid/mushy/liquid Cp(T), k(T), H(T), latent heat, solidus/liquidus | Sabau et al. (2020), Appendix B and “Setup of STLF Simulation Model and Material Properties”: solid Cp and k are JMatPro-calculated fits; liquid Cp=700 J/kg K and k=30 W/m K; latent heat=290 kJ/kg; fraction solid interpolated linearly over 1290–1350 °C. Current local snapshot applies these as a separate literature-model screening authority and bounds evaluation to 273.15–1623.15 K. | Source model defines solidification range 1290–1350 °C; runtime refuses below 273.15 K or above 1623.15 K. This is not a boiling-range property law. The linear mushy interpolation is an implementation assumption. | No quantified material-property/model uncertainty or independent property validation in the source/runtime snapshot. Model basis is literature/JMatPro, not a lot-matched raw experimental curve. | **Admitted only as bounded, unvalidated bare-plate screening.** Does not satisfy P7 full-transient gate. | Establish material composition/lot and model input identity; quantify model discrepancy/uncertainty; verify phase/latent inputs against applicable measurements; add validated above-liquidus/superheat behavior only with bounded source support. |
| Solid density ρ(T) | Georgia Tech assumes a constant 8.44 g/cm³, citing Special Metals. Special Metals is a supplier bulletin value; current local `density-assumption-v1.json` explicitly labels it fixed, not measured for this model and not lot-matched. | Constant assumed value; no supported T range in the local artifact. Not a thermal-expansion or liquid-density law. | No uncertainty supplied for the local assumption; Georgia Tech page calls it an assumption. | **Screening assumption only.** | Obtain temperature-dependent density for the same chemistry/state, with range and uncertainty; for evolving mass/volume, specify a consistent density/continuity formulation rather than substituting ρ(T) into a fixed-mass energy equation. |
| Liquid density ρ_l(T) | Sabau Appendix B gives a liquid density/Boussinesq relation with reference density 7700 kg/m³ for its simulated alloy; this is a constitutive model, not a disclosed same-lot measurement. Leitner (2021 thesis) reports electromagnetic-levitation results for BÖHLER L625; its composition/product identity is not established as NIST AMB powder or plate. | Sabau model is used for liquid-flow simulations; no independently stated validity-to-boiling interval found. Leitner tabulates a finite liquid-temperature fit/table around and above liquidus; do not extrapolate it to boiling. | Sabau fit uncertainty not quantified in the reviewed source. Leitner tabulates density uncertainties for BÖHLER L625 (e.g. near liquidus approximately 75 kg/m³); uncertainty applies to that specimen and fitted values, not NIST material. | **Unmatched liquid evidence; rejected for IN625 full-transient admission.** | Need measured/model-validated ρ_l(T), composition-linked to selected lot, traceable temperature/pressure/oxygen conditions, full stated validity interval to the solver stop, and uncertainty/covariance. |
| Dynamic viscosity μ(T) | Sabau Appendix B reports calculated liquid viscosity (figure), compares the curve with a relation from Mills et al.; paper identifies selected properties as literature-based or JMatPro calculations. Leitner’s work covers levitation properties but the inspected source evidence does not supply a matching, qualified μ(T) series for the benchmark lot. | Liquid-only curve over the study’s simulated range; no demonstrated validity up to normal boiling. Exact endpoints and digitized source values are not encoded in the local archive. | Sabau curve/model uncertainty not quantified. Any separate comparison is not same-lot metrology. | **Model-only, incomplete provenance; fails gate.** | Identify exact constitutive source/software settings and specimen composition; obtain traceable viscosity data or validate model with uncertainty over the required temperature range; archive source bytes and conditions. |
| Surface tension γ(T), derivative dγ/dT | Sabau says no experimental dγ/dT data specifically for IN625 was found in its review; its IN625 dγ/dT is JMatPro-calculated, approximately −4×10⁻⁴ N/m at liquidus to −2.4×10⁻⁴ N/m above 2500 °C. Leitner reports measured electromagnetic-levitation γ(T) and tabular uncertainty estimates for BÖHLER L625, a different product/specimen. | Sabau provides modeled liquid trend from liquidus to above 2500 °C, not a demonstrated boiling-valid measured law. Leitner finite measured/fitted liquid interval only. | Sabau model uncertainty not quantified. Leitner tabular γ uncertainties are about 11–12 mN/m near the reported temperatures for its BÖHLER sample; not transferable to NIST material. | **Required for Marangoni flow; current candidate evidence is model-only or chemistry/state-mismatched.** | Match composition and surface-active elements (especially O/S), surface atmosphere/pressure, temperature interval and uncertainty; validate γ and dγ/dT for the relevant surface state. |
| Powder optical input / absorptivity Aλ | Balbaa & Elbestawi (2022) report diffuse-reflectance spectroscopy of IN625 powder over 400–1400 nm and give 0.62 at 1070 nm as an EOS M280 example via powder reflectance/Kubelka–Munk treatment. This is powder-state evidence; available citation does not establish AMB2018 lot identity. Sabau separately uses model assumptions/estimates: 0.5 in a comparison and about 0.3 as a believed-more-accurate IN625 value at 1.064 µm. | Powder DRS 400–1400 nm; single example at 1070 nm. Sabau’s modeled/assumed values are process-model inputs, not universal temperature-dependent absorption. | No lot- and state-matched uncertainty established in the reviewed record. Model/example values are not uncertainty-bounded absorptivity curves. | **No general optical law admitted.** Current bare-plate screening takes explicit absorbed watts, so it does not require or infer Aλ. | For powder-bed: identify exact powder lot, particle morphology/PSD/oxidation, wavelength/beam profile, measurement method and uncertainty. For bare plate: measure or justify surface-state/wavelength/temperature-dependent coupling; keep it separate from powder reflectance. |
| Bare-plate absorptivity and beam profile | NIST AMB2018-02 provides a bare IN625 substrate benchmark and process/measurement context, not by itself a measured irradiance/absorptivity map. Sabau discusses estimated absorptivity inputs. Current screening avoids the gap by receiving absorbed power explicitly. | Case- and machine-specific, not a transferable alloy constant. | No exact beam irradiance profile and absorbed-power calibration bound into the current IN625 local source snapshot. | **Explicit absorbed-power screening input only; no inference.** | For an experimental AMB reproduction bind beam profile, spot definition, laser power calibration, absorptivity/coupling evidence and measurement operator to exact case and source revisions. |
| Total hemispherical emissivity ε(T) | Sabau study considers ε=0.7 as a thermal-radiation model input. This is a selected simulation assumption, not a lot-/surface-/temperature-matched measured curve. Bare-plate screening has adiabatic boundaries and no radiative-loss term. | Single assumed simulation value; range not established. | No uncertainty in the reviewed source evidence. | **Not admitted to current model; required by a loss-inclusive transient.** | Obtain state-/surface-/temperature- and wavelength-band-appropriate emissivity with uncertainty, including oxidation/roughness and atmosphere conditions. |
| Vapor pressure, evaporation enthalpy/mass flux, boiling boundary | Sabau formulates an evaporation heat-flux model using saturation pressure, evaporation latent heat and Hertz–Knudsen–Langmuir mass flux, but its reviewed property evidence does not establish an independently measured IN625 normal boiling point and full vapor-pressure curve for the selected lot. A temperature threshold cited by another paper as evaporation onset is not equivalent to a measured normal boiling boundary. | No complete, lot-matched vapor-pressure curve or certified boiling-validity interval established. | Not quantified for the target composition/pressure. | **Hard blocker for a solver required to advance through boiling.** Existing bounded model stops at liquidus; do not extend it. | Establish alloy vapor composition/activity, pressure-dependent vapor-pressure relation, latent heat(s), evaporation coefficient/condensation treatment, and uncertainty; define a documented validity boundary before enabling such runs. |
| Powder bulk/apparent density, packing and bed conductivity | NIST gives AMB2018-01 PSD and powder chemistry; the reviewed material record does not provide the coupled temperature-dependent powder-bed density/conductivity needed here. Dense-solid 8.44 g/cm³ cannot substitute for powder-bed apparent density or effective conductivity. | Not established for target powder placement/packing or temperature interval. | Not established. | **Unavailable for powder-bed admission.** | Measure/trace apparent density, packing fraction/porosity, bed conductivity/contact model, particle morphology/size and relevant powder reuse/state; validate against same lot/process. |

## Source-backed facts and limits

- Sabau et al. identify the thermophysical inputs as literature-selected or
  JMatPro-calculated, state a 290 kJ/kg latent heat and 1290–1350 °C freezing
  interval, and explicitly report no experimental IN625 surface-tension
  coefficient found in their literature review. Their solid Cp/k fits and
  liquid constants are therefore useful model inputs, not raw lot data. The
  same paper’s liquid density and viscosity/thermocapillary inputs are not an
  independently uncertainty-bounded, AMB-lot-matched property table.
  [Sabau et al. (2020), DOI 10.1007/s11663-020-01808-w](https://doi.org/10.1007/s11663-020-01808-w)
- Georgia Tech’s page states that Cp and diffusivity points average at least
  three measurements and that workbook data include 95% confidence
  uncertainties; its conductivity is calculated using k=αCpρ and assumed
  constant density. These are meaningful solid-state evidence, but they do not
  close liquid/boiling properties or lot matching.
  [Georgia Tech Gen3 CSP IN625](https://gen3csp.gatech.edu/inconel-alloy-625/)
- Leitner reports levitation-based liquid-property work on BÖHLER L625. The
  source is valuable for method and bounded liquid density/surface-tension
  evidence, but product/chemistry and specimen identity differ or are
  unestablished relative to NIST AMB2018 material. Do not merge the curves as
  if they describe one lot.
  [Leitner thesis (TU Graz, 2021)](https://www.tugraz.at/fileadmin/user_upload/Institute/IEP/Thermophysics_Group/Files/Diss-LeitnerThomas.pdf)
- Balbaa & Elbestawi’s 0.62 example concerns IN625 powder diffuse reflectance at
  the EOS M280 1070 nm wavelength. It is not molten-surface absorptivity,
  temperature-dependent coupling, or proof of AMB lot identity.
  [Balbaa & Elbestawi (2022), DOI 10.3390/jmmp6010002](https://doi.org/10.3390/jmmp6010002)
- NIST AMB2018-02 is a useful bare-plate validation target: its page describes
  IN625 single tracks, measured in-situ melt-pool length/cooling behavior, and
  substrate certification links. That makes it a possible model validation
  route, not proof that present screening inputs match its plate.
  [NIST AMB2018-02](https://www.nist.gov/ambench/amb2018-02-description)

## Current local artifact and runtime boundary

The local `data/benchmark/in625-bareplate-screening/` archive contains a
derived thermal snapshot and a separate fixed density assumption, not raw
publisher data or an experimental dataset. The thermal snapshot’s SHA-256 is
`f47b07e4c8288b8c7177001f069a254be3410bace43ad5ea2f73168ac4466f07`; it covers
273.15–1623.15 K and declares unvalidated literature-model screening. The
separate 8440 kg/m³ density is explicitly fixed and not lot-matched. The
current route uses explicit absorbed watts, a bare substrate, bounded enthalpy
conduction and adiabatic faces; it does not infer absorptivity, solve flow,
include evaporation, or validate against AMB2018-02. CPU/CUDA parity is
numerical implementation evidence only.

The official capability remains `admission: thermal-screening-only`,
`buildJob.available: false`, and `fullTransient.available: false`; its stated
reason is absence of a source-backed five-property table through independently
supported boiling temperature with required optical and flow inputs. Preserve
this boundary until evidence and validation gates below are met.

## Recommended scientific data-admission route

1. **Choose one case and one identity.** For a bare-plate demonstration, pin
   AMB2018-02’s exact substrate certificate, source data revision, machine/case,
   and surface preparation. For powder-bed work, pin one powder lot and build
   record (AMB2018-01 and AMB2018-02 are separate benchmark scopes).
2. **Keep observation and constitutive model distinct.** Archive original
   source files plus publisher URL/DOI, citation, retrieval date, exact source
   locator, byte count, SHA-256, license/terms, and a transcription record.
   Every property point/fit should say measured, derived from measurements,
   model-predicted, assumed, or digitized; include specimen chemistry, product
   form, heat treatment, atmosphere, pressure, instrument, temperature range,
   units, uncertainty and covariance where available.
3. **Do not splice to manufacture a complete table.** A candidate assembled
   from separate sources stays a multi-authority candidate unless chemistry,
   state, lot equivalence and compatible uncertainty are demonstrated. Mark
   unsupported intervals as missing; do not interpolate across a phase change
   or extrapolate to boiling without a validated model and stated uncertainty.
4. **Validate each scope before enabling it.** Check units, monotonic/range and
   phase consistency, enthalpy integration/inversion, density and mass/energy
   consistency, independent reference points, and sensitivity/uncertainty.
   Then compare predictions against the matching NIST measurement operator and
   case inputs. CPU/GPU parity verifies implementation equivalence, not
   physical validity.
5. **Admit capabilities separately.** A complete bare-plate thermal screen
   need not imply powder-bed, fluid flow, evaporation, build-job, or production
   support. Require evidence for each additional physics and data domain before
   opening its capability flag. Keep a blocked reason in the registry when
   any mandatory evidence or validation is absent.

No code, registry, source data, or capability flag is changed by this evidence
review. The existing gate remains closed for P7 full-transient and build-job
admission.

## 2026-09-27 — Source-candidate follow-up

**Decision unchanged:** IN625 remains `thermal-screening-only`, with
`sourceValidityRange_K: null`; full-transient and build-job admission stay
closed. The runtime interval 273.15–1623.15 K is an implementation boundary,
not an independently established source-validity interval. The following are
**unverified candidates for data admission**. Their primary publication records
were reviewed, but complete property tables, specimen identities and quantified
uncertainties were not acquired or qualified. No candidate values were added to
the material authority.

| Primary source | Evidence visible in the publication record | Access and admission limits |
| --- | --- | --- |
| [Kaschnitz et al. (2019), DOI 10.1007/s10765-019-2490-8](https://link.springer.com/article/10.1007/s10765-019-2490-8) | Measured diffusivity from −120 to 1250 °C, Cp from −170 to 1250 °C, and expansion from −150 to 1295 °C; room-temperature density measured by Archimedes balance. Conductivity is derived from measured properties. | Publisher abstract inspected; subscription full text and numerical uncertainty tables not acquired. Useful solid-state candidate, without demonstrated target-lot equivalence or liquid/optical/vapor coverage. |
| [Heugenhauser and Kaschnitz (2019), DOI 10.32908/hthp.v48.726](https://www.oldcitypublishing.com/journals/hthp-home/hthp-issue-contents/hthp-volume-48-number-4-2019/17793-2/) | Publisher abstract reports solid/liquid density and expansion up to 1400 °C, an initial 930 °C / 1 h heat treatment, and a detailed uncertainty analysis. | Full text and tables not acquired. The lower-temperature sign differs between indexed descriptions and must be resolved from the original table before transcription. No boiling-range or target-lot claim follows. |
| [Phillips et al., NASA NTRS 20240007954 (2024)](https://ntrs.nasa.gov/citations/20240007954) | Primary presentation record compares competing IN625/718 vendor formulations using electrostatic levitation; indexed topics include density, viscosity and surface tension. | Record indexed, but direct page/API/PPTX retrieval failed in this environment. Actual measurement ranges, compositions, uncertainty and numerical results remain unverified. This is a retrieval lead only. |
| [O'Flynn et al. (2020), DOI 10.1080/00325899.2020.1805547](https://journals.sagepub.com/doi/10.1080/00325899.2020.1805547) | Abstract reports measured expansion, Cp and diffusivity of metal-injection-moulded IN625/718 from room temperature to 1000–1200 °C, with conductivity derived from these measurements. | Restricted full text not acquired; exact alloy/property endpoints and uncertainty require the tables. MIM material state cannot be silently assigned to LPBF powder or plate. |

The [Georgia Tech IN625 page](https://gen3csp.gatech.edu/inconel-alloy-625/)
was rechecked: it describes at least three repeats, workbook uncertainties at
95% confidence, and conductivity derived using an assumed constant density.
The linked workbook could not be retrieved in this review; its temperature
endpoints, uncertainty columns and specimen identity remain unverified.

**Next concrete acquisition:** obtain the NASA presentation, both Kaschnitz
papers' original tables, and the Georgia Tech workbook through permitted
publisher/repository access. Preserve original bytes, retrieval URL/date and
SHA-256; transcribe chemistry/state, temperature endpoints, units, methods and
uncertainty before deciding whether any bounded property record is admissible.
Do not merge different specimens into a qualified table without an explicit
equivalence and uncertainty argument. Optical, powder-bed, flow and vapor
requirements remain independently open. This follow-up changes no model,
registry, source snapshot or capability flag and establishes no experimental
validation.

### Original-file acquisition and inspection — 2026-09-27, 12:42 UTC

This acquisition supersedes the NASA and Georgia Tech access limitations above.
Permitted public downloads succeeded after the sandbox network restriction was
resolved. Original files and their URL, UTC retrieval time, byte count and
SHA-256 are preserved in
[`candidate-acquisition-2026-09-27.json`](sources/in625/candidate-acquisition-2026-09-27.json).
The [property inspection](sources/in625/candidate-property-inspection-2026-09-27.json)
records source locators, evidence classes, unresolved fields and the workbook's
20 numeric rows. Neither file changes the runtime material authority.

| Original artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| [Georgia Tech workbook](sources/in625/georgia-tech-inconel625.xlsx) | 11,127 | `aa4821bf2845333af590e9b384c781c46df18529e718a66adad65155a4df8b60` |
| [NASA presentation](sources/in625/nasa-20240007954-inconel-properties.pptx) | 18,301,541 | `fe5ef34928d67f9967dfa06bc0f55439560a1ed81f0d9ddbc08cfc835a589bcb` |

**Georgia Tech:** `Sheet1!A1:G21` contains 20 temperature points from **260 to
1000 °C (533.15–1273.15 K)**, with Cp, diffusivity and conductivity and separate
95% confidence uncertainty columns. Cp units are J/g-K; diffusivity units are
mm²/s. The database method interpolates measured Cp onto the diffusivity
temperature coordinates. Conductivity is derived using an assumed 8440 kg/m³
density; recalculation reproduces all 20 values within `4.98e-14 W/m-K`.
The archived [uncertainty method](sources/in625/georgia-tech-uncertainty.html)
assumes negligible density uncertainty. Lot, chemistry and heat treatment are
not established by these acquired records. This closes the workbook-access and
temperature/uncertainty-column gaps, but supplies neither liquid properties nor
a complete uncertainty budget for transfer to the target LPBF material.

**NASA:** slide 4 identifies ESPI IN625 lot **DK 15344B** and different ESPI and
Böhler compositions. Slides 6–8 contain density, surface-tension and viscosity
plots/fits; their IN625 plots mark `T_L = 1630 K`. Density and surface-tension
fit tables contain plus/minus coefficient entries, but confidence level,
coverage factor, covariance and full uncertainty budget are not established.
Exact numerical measurement series and range endpoints are not tabulated, and
the PPTX has no embedded spreadsheet. The finite near-liquidus plot ranges
(including undercooled density points) must not become inferred boiling-range
validity. The displayed viscosity equation and coefficient units have not been
reconciled with its plotted values, so they must not be implemented as a law.
Instrument capability ranges on slide 3 are not specimen measurement conditions.

**Remaining acquisition:** obtain the NASA numeric series, fit conventions and
uncertainty/specimen-condition details through permitted public supplementary
data or a separately authorized author request; obtain the Kaschnitz original
tables. Establish chemistry/state/lot applicability before combining records.
The new files are **source-inspected, unverified candidates for admission**;
`sourceValidityRange_K` for the current runtime snapshot remains `null`,
full-transient/build-job stay closed, and experimental validation remains
unestablished.

## 2026-09-27 source and runtime gate re-audit

The `in625_thermal_material.py` property coefficients were not changed in the
current working diff. Sabau et al. 2020 Appendix B reproduces the solid
`Cp(T)` and `k(T)` curves as JMatPro-calculated values; its setup lists liquid
`Cp=700 J/(kg K)`, liquid `k=30 W/(m K)`, latent heat `290 kJ/kg`, and a
linear liquid fraction across 1290–1350 °C as model inputs. These are not
independent measurements of the target powder/substrate lot and the article
does not establish quantified property uncertainty for this runtime table.
The 273.15 K enthalpy reference and linear mushy-region Cp/k bridges are local
model choices, not source-validated ranges. [Sabau et al. 2020](https://link.springer.com/article/10.1007/s11663-020-01808-w)

Special Metals' separate bulletin labels its Cp table calculated; it identifies
the conductivity table as Battelle measurements on material annealed at
2100 °F for one hour and reports density 8.44 g/cm³. The bulletin does not
establish the same AM lot, density-vs-temperature, liquid/powder density, or
quantified uncertainty. [Special Metals IN625 bulletin, p. 2](https://www.specialmetals.com/documents/technical-bulletins/inconel/inconel-alloy-625.pdf)

The new helper's hash/content `accepted` result pins the current generated
screening snapshot; it does not independently hash the source paper or close
the scientific uncertainty gate. Capability remains `unvalidated`,
`sourceValidityRange_K: null`, `fullTransientAdmitted: false`, and
`experimentalValidation: false`. IN625 therefore remains **thermal-screening-
only**; full transient and build-job admission are not supported.
