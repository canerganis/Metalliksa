# LPBF alloy capability and evidence matrix — 2026-09-24

This snapshot is generated from `python/lpbf_material_capabilities.py`'s
`material_capability_report()` authority. Input availability and content
identity do not establish experimental validation or source quality.

| Alloy | Build-job screening | Full transient thermal | Marangoni / inherent-strain adapters | GPU status | Evidence boundary |
| --- | --- | --- | --- | --- | --- |
| Ti-6Al-4V | Available, `rosenthal-screening-v1` | Available through legacy registry snapshot | Inputs present; qualification open | Same-physics qualification open | Estimated screening inputs; no source-validity range; no experimental qualification |
| 316L stainless steel | Available, `rosenthal-screening-v1` | Available through legacy registry snapshot | Inputs present; qualification open | Same-physics qualification open | Estimated screening inputs; no source-validity range; no experimental qualification |
| AlSi10Mg | Available, `rosenthal-screening-v1` | Available through legacy registry snapshot | Inputs present; qualification open | Same-physics qualification open | Estimated screening inputs; no source-validity range; no experimental qualification |
| Inconel 718 | Available, `rosenthal-screening-v1` | Available through legacy registry snapshot | Inputs present; qualification open | Same-physics qualification open | Estimated screening inputs; no source-validity range; NIST Case 0 comparison unavailable under current material/beam/operator evidence |
| Inconel 625 | Not admitted to build-job or slicer map | Not admitted to general transient solver | Unavailable | Bounded bare-plate CPU/CUDA numerical parity only | Separate 3D bare-substrate enthalpy screen, 273.15–1623.15 K; model-based properties, unvalidated; density is a fixed supplier-bulletin assumption and not lot-matched |

## IN625 bounded route

The separate IN625 screen uses material revision
`f47b07e4c8288b8c7177001f069a254be3410bace43ad5ea2f73168ac4466f07`. It takes
absorbed power explicitly, enforces the model temperature bounds and source
capture gate, and models adiabatic bare substrate. It does not model powder,
optical absorptivity, melt-pool flow, evaporation, keyhole behavior or an
experimental measurement operator.

The 576-cell/4-step CPU–RTX 4060 `cuda:0` synthetic case in
`docs/IN625_BAREPLATE_GPU_SCREENING_2026-09-24.md` produced bitwise-identical
temperature and specific-enthalpy fields. The separate browser acceptance run
used 1,152 cells and 11 steps; CPU and `cuda:0` both produced field SHA-256
`90670c1176da50ec2014a62076f057ebac6e39635e29beb390227a1598f58354`, with
maximum and RMS temperature differences of 0 K. A synthetic 1500 K initial-
state witness also entered the mushy interval on both backends (128 cells,
33 steps, 4 mushy cells, peak 1565.46 K); see
`docs/IN625_MUSHY_CPU_CUDA_SCREENING_2026-09-24.md`. These establish
implementation parity for the bounded model and cases tested, not physical
alloy qualification.

The four existing alloys retain their historical model inputs and screening
admission. Their source-validity ranges remain unspecified and the capability
report marks full-transient and auxiliary adapter evidence as unvalidated/open.
Do not transfer this matrix into production-readiness or material-certification
claims.
