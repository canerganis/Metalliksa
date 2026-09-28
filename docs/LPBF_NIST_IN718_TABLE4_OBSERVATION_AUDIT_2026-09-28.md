# IN718 NIST AMB2022-03 Table 4 gözlem kapısı denetimi

**Durum: gözlem verisinin kimliği ve ölçüm eşlemesi kısmen doğrulandı; model karşılaştırması hâlâ `unavailable` / `unvalidated`.** Bu not yalnızca NIST kaynağının neyi ölçtüğünü ve mevcut karşılaştırma sözleşmesinde neyin eksik olduğunu kaydeder. Hiçbir solver çalıştırılmadı, residual hesaplanmadı ve doğrulama statüsü yükseltilmedi.

## Kaynak kimliği ve hashler

| Kaynak | Kesin konum | SHA-256 / durum |
|---|---|---|
| NIST publisher workbook, `AMB2022-718-SH1-MeltPool_Cross-Section_Measurement_Results.xlsx` | [NIST PDR DOI 10.18434/mds2-2718](https://data.nist.gov/od/id/mds2-2718), asset URL [`…/AMB2022-718-SH1-MeltPool_Cross-Section_Measurement_Results.xlsx`](https://data.nist.gov/od/ds/ark:/88434/mds2-2718/AMB2022-718-SH1-MeltPool_Cross-Section_Measurement_Results.xlsx) | `2cfaac96aaca3dabb77b7029f842cdcc7e75c5a2cf3577d0734823246364a931`, 25,811 B; local file bytes and NIST sidecar match. |
| NIST workbook checksum sidecar | [PDR sidecar](https://data.nist.gov/od/ds/ark:/88434/mds2-2718/AMB2022-718-SH1-MeltPool_Cross-Section_Measurement_Results.xlsx.sha256) | `770c0826e53e42c242110e69c032f2cbc74f6183048c43a530c5b62e746ae09b`; contents equal workbook SHA above. |
| Local six-image, case-0 source manifest | [`data/benchmark/nist-amb2022-03-optical/official/single-track-case0/manifest.json`](../data/benchmark/nist-amb2022-03-optical/official/single-track-case0/manifest.json) | `85ec5ce316a2d51c87854b644aef3fc0d601ca884e5a316d23e9a1dc6158b03e`; each listed image has a publisher SHA sidecar and independently recomputed local SHA. |
| Local transcription consumed by the comparison adapter | [`data/benchmark/nist-amb2022-03-optical/table4-aggregate-v2.json`](../data/benchmark/nist-amb2022-03-optical/table4-aggregate-v2.json) | `d1b36dfa2e01a3537093c481e249ce52df6b8879c1c67480ddb9aa10799133da`; explicitly a local transcription, not NIST-issued raw data. |
| NIST methods/challenge PDF v1.01 | [NIST asset](https://www.nist.gov/document/amb2022-03-measurement-and-challenge-descriptions-version-101), Table 2 / §2.2 pp. 4–5 (PDF pp. 3–4); §3.4 pp. 13–14; §4.1.4 p. 16 (PDF p. 15) | Publisher PDF SHA-256: **unknown** (not present in the local evidence assets; network download from this runner was unavailable). |
| Weaver et al., NIST-hosted measurement paper | [NIST-hosted PDF, publication id 957295](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=957295), Table 4 p. 6 (PDF p. 5), Appendix 3/Table 7 pp. 14–15 (PDF pp. 13–14) | Publisher PDF SHA-256: **unknown** (no publisher checksum found or local PDF available). Page/table citations identify claims, but do not constitute byte-hash verification of this PDF. |

The local ingestion manifest fixes the workbook name, size, URL, and checksum authority to the NIST-published sidecar; the manifest itself is not asserted to be NIST-published or signed. The local workbook was read-only inspected; its six Case 0 rows reproduce the rounded Table 4 means and standard deviations. The local JSON hash binds the exact comparison transcription. Do not describe the hash of that JSON as the hash of the NIST article or workbook.

## Case 0: condition and measurement operator

The current candidate is **case 0**: IN718 plate `AMB2022-718-SH1-BP1`, bare plate, 285 W, 960 mm/s, nominal 67 µm `D4σ`, 10 mm single-track scan in +X; substrate/chamber 23.5 ± 1 °C; argon; reported surface roughness `Ra=5.8 µm`. The exact laser condition and repeat count are in NIST methods PDF Table 1/Table 2, pp. 4–5 (PDF pp. 3–4); plate treatment is §2.1 p. 3 (PDF p. 2); scan direction and length are Table 1 p. 4 (PDF p. 3). The optical cross-sections are ex-situ dark-field/optical geometry, not temperature or powder-bed observations (NIST methods §3.4.1 pp. 13–14; NIST results paper Table 4 p. 6).

NIST results paper Table 4 reports **six measurements: three repeat tracks × two cross-sections per track**. The local publisher workbook maps them as follows. Position is along the track from its start; `P3` is at 4.9 mm and `P4` at 6.0 mm. The corresponding six original NIST TIFF asset URLs are recorded in the local manifest above.

| Repeat | P3, 4.9 mm: depth / width (µm) | Original TIFF SHA-256 | P4, 6.0 mm: depth / width (µm) | Original TIFF SHA-256 |
|---|---:|---|---:|---|
| Line 0_1 | 139.863 / 141.795 | `deb2cc34e97d2fad6120f9d5f6e59692c52e53601711d83ae580c18683c91720` | 138.483 / 134.619 | `96d6d81d890c7cc9944aecb9f74c0e5d44eead61d1fcf684dfaca3bbf1a8c747` |
| Line 0_2 | 142.209 / 133.653 | `878c4cb98b2631f2be2f92749db61191973f6f4f88376edf34c6b7bb77398a12` | 138.138 / 136.482 | `e22eab832ad9e9780d63319d4e9c3670b07c2dc38b23a1c2bbc7af7f4e99d70b` |
| Line 0_3 | 141.864 / 135.792 | `289fe25bccafee3174695e24ae2336650aaf8d797245287efc95246c27067bea` | 137.724 / 135.378 | `c03d00680c90d10f9852ae29e4d418b2fb52ab1508299c26378a4b0a9fb04f6d` |

For each original TIFF, its sidecar contains the same SHA-256 shown above; both sidecar and image bytes were checked locally. The case-0 files are `Single_Track_Cross_Sections/AMB2022-718-SH1-BP1-P{3,4}-L0-{1,2,3}.tif` under the exact PDR asset base URL `https://data.nist.gov/od/ds/ark:/88434/mds2-2718/`. Thus the six-row mapping is source/hash-bound to the workbook and six image assets; it is not six independent builds. Workbook-derived means are depth 139.7135 µm and width 136.2865 µm, which round to the paper's 139.7 and 136.3 µm. Sample SDs recomputed from the six rows are 1.9406 and 2.8694 µm, rounding to Table 4's 1.9 and 2.9 µm.

### Source discrepancy to preserve

The NIST methods/challenge PDF §4.1.4 p. 16 says the geometry challenge average/SD uses three repeat tracks and **four** cross-sections `(P1, P2, P3, P4)`. The NIST results paper Table 4 p. 6 instead states six measurements `(three tracks, two cross-sections per track)`, and the publisher workbook for case 0 contains precisely P3/P4 for Lines 0_1–0_3 (six rows, not twelve). Therefore the present Table 4 case-0 comparison must follow the six measurements actually represented by the Table 4 result/workbook; do not silently mix the methods-PDF four-section count with this result table. Broader “four-section” mappings remain `unknown` until the discrepancy is reconciled from NIST source records.

## What W and D mean; uncertainty and repeats

NIST methods §3.4.1 p. 14 (PDF p. 13) defines single-track depth from the plate's original top surface, ignoring material hump above that surface, perpendicular to the top surface; width is parallel to it. NIST results paper §Measurement Methods, p. 4 (PDF p. 3), says the reported single-track depth and width are the **largest boundary distances**, not necessarily at track center or at the top surface. This is a cross-sectional, etched optical-boundary operator. It is not a melt-threshold contour or a point sample at the scan midpoint. The publisher's local case-0 image manifest gives the image-based operator as a bounding rectangle with the rectangle top at specimen surface; that metadata belongs to the local manifest and is not asserted as text from the publisher paper.

For case 0, NIST results paper Table 4 p. 6 reports: width mean 136.3 µm, SD 2.9 µm, expanded uncertainty `U(k=2)=6.2 µm`; depth mean 139.7 µm, SD 1.9 µm, `U(k=2)=14.1 µm`. Appendix 3 pp. 14–15 explains four contributions: optical resolution (0.5 µm), boundary selection (±6 pixels), estimated variability along the track (5% depth, 2% width), and standard uncertainty of the mean from repeat measurements; combined uncertainty uses root-sum-square and `U` is twice the combined standard uncertainty (`k=2`). The paper's Table 7 gives the case-specific budget. These U values are different from sample SD and neither is a model-validation interval. The machine-readable transcription currently retains mean and SD, **not U or its budget**; those cells are missing from its comparison interface and must remain `unknown` there until the schema/source binding is extended. NIST asset PDF SHA-256 remains unknown as stated above.

## Beam profile and `D4σ` applicability

Methods PDF Table 1 p. 4 identifies a rotationally symmetric Gaussian laser energy distribution and a nominal 67 µm spot for baseline case 0; Table 2 p. 5 labels the geometry challenge diameter `D4σ`. Results paper §Results p. 6 explicitly defines `σ=D4σ/4`; its Table 4 lists 67 µm. This supports the *nominal size convention* for case 0. It does **not** provide a hash-bound, measured two-dimensional intensity map, its ellipticity/astigmatism, calibration uncertainty, or pointwise profile data in the local evidence set. Those quantities are `unknown`.

The current shared Gaussian source uses `exp(-2 r²/w²)` with input diameter interpreted as `D=2w`. For an ideal circular Gaussian this algebraically corresponds to `D4σ=2w`; a nominal D4σ number plus a stated Gaussian family is a convention-level mapping, not proof that the actual machine profile equals the solver's ideal profile. Existing model gate correctly requires a verified measured-profile artifact and exact D4σ-to-input binding; those requirements are not met by this Table 4 workbook alone.

## Existing comparison/API gate and decision

The source catalog binds publisher workbook `nist-amb2022-03-optical-xlsx-official-v1` to its exact publisher hash and a local aggregate source separately binds the Table 4 transcription (`server/lpbfSourceCatalog.ts`, `server/lpbfNistComparisonService.ts`). The Python observer is `python/lpbf_nist_in718_comparison.py`; it checks source identity, case process, run/material contract, beam evidence, optical operator and convergence. It returns `unavailable`, `validationStatus=unvalidated`, and `errors=null` on a failed gate. In the current source it rejects every case because the implemented run still carries a single midpoint result: it unconditionally records that the six-section observer is not implemented. A caller-set `observationCount=6` cannot pass.

**Decision: no residual and no experimental-validation claim.** The local workbook and six image bindings support mapping the Table 4 case, but the six P3/P4 observations must not be described as satisfying the formal geometry challenge's midpoint and four-section requirements. At most, a future comparison at those two Table 4 positions could be a bounded Table 4 replication/screening; it is not a formal challenge pass. Numerical comparison remains unavailable until an optical-boundary observation operator is explicitly defined and independently checked against the etched sections; the cited sources describe the measured maximum boundary distances but do not specify an equivalent model-field contour/isotherm extraction rule. The measured beam profile must also be independently established and bound, and convergence must pass on the same frozen run identity. The NIST results/methods PDF byte hashes are unknown in the local evidence, so the reported expanded-U values remain article-referenced but are not yet hash-bound source records; do not transfer them into a typed uncertainty contract or open an uncertainty-aware comparison gate until those publisher bytes are acquired and verified. Even after these gates, residuals are screening/model-comparison evidence, not proof of general LPBF validity.

### Hashes of inspected local artifacts

- Workbook: `2cfaac96aaca3dabb77b7029f842cdcc7e75c5a2cf3577d0734823246364a931`
- Publisher workbook sidecar bytes: `770c0826e53e42c242110e69c032f2cbc74f6183048c43a530c5b62e746ae09b`
- Case-0 micrograph manifest: `85ec5ce316a2d51c87854b644aef3fc0d601ca884e5a316d23e9a1dc6158b03e`
- Table 4 local aggregate v2: `d1b36dfa2e01a3537093c481e249ce52df6b8879c1c67480ddb9aa10799133da`
- Current local result table reports `validationStatus=unvalidated`; no solver run or test was performed for this audit.
