# LPBF thermal contract: equations, evidence, and scope

Status: source-to-equation audit in progress (2026-09-28). This document separates code implementation, numerical verification, and experimental validation. A correct code path does not establish that the selected physical model is adequate for a process case.

## Executed reference thermal contract

The shared reference thermal path uses volumetric enthalpy and temperature on a fixed grid. In compact form its intended balance is

\[
\frac{\partial H}{\partial t}=\nabla\cdot(k\nabla T)+q'''-q'''_{\mathrm{boundary}},\qquad H=\rho h(T),
\]

where \(H\) is J/m³, \(h\) is J/kg, \(q'''\) is W/m³, \(k\) is W/(m K), and time is seconds. Material tables and constitutive laws remain versioned inputs; the four currently admitted identities remain governed by the canonical registry.

| Contract term | Implementation | Scientific basis / distinction | Current evidence and limitation |
|---|---|---|---|
| SI input conversion | [`thermal_si_inputs`](../python/lpbf_core_physics.py#L174) converts °C to K, µm to m, mm/s to m/s, and laser power × absorptivity to W. | Unit conversions are dimensional identities, not a material-validation source. | Explicit conversion boundary reviewed; no unit mismatch found in this boundary. |
| Enthalpy and latent heat | [`enthalpy_table`](../python/lpbf_core_physics.py#L189) delegates to the versioned material registry; [`transient`](../python/lpbf_simulation.py#L398) advances volumetric enthalpy and inverts the table to recover temperature. | Fixed-grid enthalpy formulations for conduction-controlled phase change are described by Voller, Swaminathan & Thomas (1990), [DOI 10.1002/nme.1620300419](https://doi.org/10.1002/nme.1620300419). | The equation family is established; this does not verify the alloy data, latent-heat curve, or mushy-zone interpolation. Existing properties include estimates and incomplete independent provenance. |
| Internal conduction | [`conduction_rate`](../python/lpbf_simulation.py#L315) evaluates each internal face once with harmonic face conductivity and applies equal-and-opposite rates; exterior faces are insulated. | Fourier conduction and conservative finite-volume balance; the discrete pair cancellation is an implementation invariant. | Shared-core contract tests and flux checks cover software behavior. Equal/opposite bookkeeping is not an independent comparison with a known solution. |
| Moving laser source | [`integrated_source`](../python/lpbf_core_physics.py#L78) integrates cell weights at two time quadrature nodes, then normalizes them over the represented active domain. The solver reports minimum captured half-space mass. | A Gaussian source and its normalization are model choices that require measured beam/profile and absorption evidence for a physical case; they are not a universal LPBF law. | Software source normalization and capture gates are tested. Case-specific beam profile, absorptivity and source-depth uncertainty are not established for IN718 case 0. |
| Surface and support losses | [`transient`](../python/lpbf_simulation.py#L510) applies explicit bottom-boundary and convection plus Stefan–Boltzmann radiation terms. | Convection coefficient, emissivity, support contact and bottom boundary are setup-dependent inputs. | Bookkeeping and unit path are present; boundary parameter provenance/ranges need source records for any validation case. |
| Global energy check | [`transient`](../python/lpbf_simulation.py#L625) compares integrated input, recorded boundary loss and stored enthalpy. | This is a conservation/implementation diagnostic. It reuses the solver's own rates and is not an independent physical validation. | The current closure threshold is 1%. Closure passes do not establish spatial or temporal convergence. |

## Verification and validation gates

* **Software correctness:** tests establish API contracts, unit conversions, deterministic identity and implementation invariants.
* **Numerical verification:** compare against analytic/manufactured solutions and perform systematic mesh/time refinement. The method of manufactured solutions is a code-verification approach, not an experiment: Brady, Herrmann & Lopez (2012), [DOI 10.1016/j.jcp.2011.12.040](https://doi.org/10.1016/j.jcp.2011.12.040); Roache (2002), [DOI 10.1115/1.1436090](https://doi.org/10.1115/1.1436090).
* **Experimental validation:** requires a source-bound process case, measured/uncertain material and beam inputs, a compatible observation operator, and uncertainty-aware comparison. NIST AM-Bench publishes separate process and optical measurement artifacts; use the [official measurement/result descriptions](https://www.nist.gov/document/am-bench-amb2022-03-measurement-and-result-descriptions-v10) and [beam measurement report](https://doi.org/10.6028/NIST.AMS.100-67), preserving source files and derived transcriptions as distinct identities.

Current LPBF mesh/time evidence is `inconclusive`; the IN718 Table 4 experimental residual is withheld because the current solver's observation operator and beam binding are not equivalent to the six optical sections. Results remain `unvalidated`. No convergence, backend parity, energy closure, or synthetic data should be presented as experimental validation.
