# Standards & Qualification Handbook for Metal Additive Manufacturing (`STANDARDS.md`)

This handbook provides the authoritative, exhaustive specification breakdown of governing **ASTM**, **ISO**, and **ISO/ASTM** standards for Laser Powder Bed Fusion (PBF-LB/M) of metallic materials, including feedstock quality, process qualification, density determination, mechanical testing, metallographic image analysis, and design constraints.

> **Compliance Notice**: In accordance with Rule 1 in [`RULES.md`](../../RULES.md), all specifications, property thresholds, and test protocols are codified in English. Numerical criteria have been cross-verified against peer-reviewed aerospace qualification documentation in [`PROOF.md`](../../PROOF.md).

---

## Table of Contents
1. [ASTM F3055: Ti-6Al-4V with Powder Bed Fusion](#1-astm-f3055-ti-6al-4v-with-powder-bed-fusion)
2. [ASTM F2924: Ti-6Al-4V Structural & Aircraft Applications](#2-astm-f2924-ti-6al-4v-structural--aircraft-applications)
3. [ASTM B962: Relative Density via Archimedes' Principle](#3-astm-b962-relative-density-via-archimedes-principle)
4. [ASTM E8 / E8M: Tension Testing of Metallic Additive Materials](#4-astm-e8--e8m-tension-testing-of-metallic-additive-materials)
5. [ASTM E1245 & ASTM E384: Porosity & Vickers Microhardness](#5-astm-e1245--astm-e384-porosity--vickers-microhardness)
6. [ISO/ASTM 52900 & ISO/ASTM 52911: Terminology & AM Design Rules](#6-isoastm-52900--isoastm-52911-terminology--am-design-rules)

---

## 1. ASTM F3055: Ti-6Al-4V with Powder Bed Fusion

**Standard Title**: *Standard Specification for Additive Manufacturing Titanium-6 Aluminum-4 Vanadium with Powder Bed Fusion*  
**Applicable Alloy Grades**: Ti-6Al-4V Grade 5 (UNS R56400) and Ti-6Al-4V Grade 23 ELI (Extra Low Interstitial, UNS R56401).

### 1.1 Classification of Components
ASTM F3055 establishes four component classification tiers based on processing history, thermal state, and inspection severity:
- **Class 1**: As-built (AB) condition. Parts that have not undergone thermal stress relief or post-process HIP. *Permitted strictly for non-critical non-structural prototypes; removal from build plate without prior stress relief is generally prohibited due to catastrophic distortion risks.*
- **Class 2**: Stress Relieved (SR) condition. Parts thermally treated while anchored to the build substrate to relieve macro residual stresses.
- **Class 3**: Hot Isostatically Pressed (HIP) condition. Components subjected to simultaneous high temperature and isostatic Argon pressure to close internal shrinkage and lack-of-fusion voids.
- **Class 4**: Solution Treated and Aged (STA) or custom heat-treated condition to tailor high-temperature creep or fatigue endurance.

### 1.2 Chemical Composition Requirements
The chemical composition of final additively manufactured parts and witness specimens must comply with the strict weight percentage limits below (analyzed per ASTM E1409 for $O_2$ & $N_2$, ASTM E1447 for $H_2$, and ASTM E2371 / ICP-OES for metallic elements):

| Element | Grade 5 (UNS R56400) [wt%] | Grade 23 ELI (UNS R56401) [wt%] | Method |
|---|---|---|---|
| **Aluminum (Al)** | 5.50 – 6.75 | 5.50 – 6.50 | ASTM E2371 / ICP-AES |
| **Vanadium (V)** | 3.50 – 4.50 | 3.50 – 4.50 | ASTM E2371 / ICP-AES |
| **Iron (Fe)** | $\le 0.30$ | $\le 0.25$ | ASTM E2371 |
| **Oxygen (O)** | $\le 0.20$ | $\le 0.13$ | ASTM E1409 (IGF) |
| **Nitrogen (N)** | $\le 0.05$ | $\le 0.03$ | ASTM E1409 (IGF) |
| **Carbon (C)** | $\le 0.08$ | $\le 0.08$ | ASTM E1941 (Combustion) |
| **Hydrogen (H)** | $\le 0.015$ ($150\text{ ppm}$) | $\le 0.0125$ ($125\text{ ppm}$) | ASTM E1447 (Inert Gas Fusion) |
| **Yttrium (Y)** | $\le 0.005$ | $\le 0.005$ | ASTM E2371 |
| **Other Elements, Each** | $\le 0.10$ | $\le 0.10$ | ICP-OES |
| **Other Elements, Total** | $\le 0.40$ | $\le 0.40$ | Summation |
| **Titanium (Ti)** | Balance | Balance | Difference |

### 1.3 Mechanical Property Acceptance Criteria
Mechanical testing must be conducted on test specimens manufactured concurrently on the same build plate, in both horizontal ($XY$, $0^\circ$) and vertical ($Z$, $90^\circ$) orientations.

| Heat Treatment Condition | Tensile Strength $R_m$ (UTS) | Yield Strength $R_{p0.2}$ (0.2% Offset) | Elongation at Break $A$ ($4D$) | Reduction of Area $Z$ |
|---|---|---|---|---|
| **Class 2: Stress Relieved (SR)** | $\ge 930\text{ MPa}$ ($135\text{ ksi}$) | $\ge 860\text{ MPa}$ ($125\text{ ksi}$) | $\ge 8\%$ | $\ge 15\%$ |
| **Class 3: HIPed (Grade 5)** | $\ge 895\text{ MPa}$ ($130\text{ ksi}$) | $\ge 828\text{ MPa}$ ($120\text{ ksi}$) | $\ge 10\%$ | $\ge 20\%$ |
| **Class 3: HIPed (Grade 23 ELI)** | $\ge 860\text{ MPa}$ ($125\text{ ksi}$) | $\ge 795\text{ MPa}$ ($115\text{ ksi}$) | $\ge 10\%$ | $\ge 25\%$ |

---

## 2. ASTM F2924: Ti-6Al-4V Structural & Aircraft Applications

**Standard Title**: *Standard Specification for Additive Manufacturing Titanium-6 Aluminum-4 Vanadium with Powder Bed Fusion*  
**Application Focus**: Critical load-bearing aerospace airframes, turbine housings, structural brackets, and rotating machinery.

### 2.1 Critical Requirements
1. **Mandatory HIP Protocol**: Class 3 HIP is mandatory for flight-critical structural parts. The component must undergo:
   - Temperature: $920^\circ\text{C} \pm 10^\circ\text{C}$ ($1688^\circ\text{F} \pm 25^\circ\text{F}$)
   - Isostatic Pressure: $\ge 100\text{ MPa}$ ($14.5\text{ ksi}$) in ultra-high purity Argon
   - Dwell duration: $120 \pm 10\text{ minutes}$
   - Cooling: Clean gas cool to $< 425^\circ\text{C}$ ($800^\circ\text{F}$) at controlled rate to prevent secondary distortion.
2. **First Article Inspection (FAI)**: Conformance to AS9102 / ISO 9001 quality frameworks, requiring non-destructive examination (NDE) including high-resolution X-ray Computed Tomography (micro-CT per ASTM E3166 / ASTM E1570) and Fluorescent Penetrant Inspection (FPI per ASTM E1417 Class 4).
3. **Feedstock Re-use Criteria**: Re-used powder must be documented in a batch genealogic ledger. Powder with oxygen exceeding $0.20\text{ wt}\%$ or showing signs of particle agglomeration / satellite satellite ablation must be quarantined.

---

## 3. ASTM B962: Relative Density via Archimedes' Principle

**Standard Title**: *Standard Test Methods for Density of Compacted or Sintered Powder Metallurgy (PM) Products Using Archimedes' Principle*

### 3.1 Mathematical Formulation
The buoyant immersion technique calculates apparent bulk specimen density ($\rho_{\text{sample}}$) by measuring specimen mass in air and suspended in an immersion fluid:

$$\rho_{\text{sample}} = \frac{m_{\text{air}}}{m_{\text{air}} - m_{\text{liq}}} \cdot (\rho_{\text{liq}} - \rho_{\text{air}}) + \rho_{\text{air}}$$

Where:
- $m_{\text{air}}$: Mass of the clean, dry test specimen in ambient air $[\text{g}]$.
- $m_{\text{liq}}$: Apparent mass of the specimen fully submerged in immersion liquid $[\text{g}]$.
- $\rho_{\text{liq}}$: Density of the reference immersion liquid at measured test temperature $T_{\text{liq}}$ $[\text{g/cm}^3]$.
- $\rho_{\text{air}}$: Density of ambient air (nominally $0.0012\text{ g/cm}^3$ at $20^\circ\text{C}, 101.325\text{ kPa}$).

### 3.2 Temperature Correction for Reference Liquids
For distilled water ($\text{H}_2\text{O}$):
$$\rho_{\text{water}}(T) = 0.99997 - 1.059 \times 10^{-5} (T - 4)^2 \quad [\text{g/cm}^3] \quad (T \text{ in } ^\circ\text{C})$$

For absolute ethanol ($\text{C}_2\text{H}_5\text{OH}$), widely preferred in AM due to lower surface tension and superior wetting of fine surface micro-crevices:
$$\rho_{\text{ethanol}}(T) = 0.80655 - 0.000846 \cdot (T - 15) \quad [\text{g/cm}^3]$$

### 3.3 Relative Density Percentage
$$\text{Relative Density } (\%) = \left( \frac{\rho_{\text{sample}}}{\rho_{\text{theoretical}}} \right) \times 100\%$$
- Ti-6Al-4V Theoretical Solid Density: $\rho_{\text{theoretical}} = 4.430\text{ g/cm}^3$
- 316L Stainless Steel: $\rho_{\text{theoretical}} = 7.950\text{ g/cm}^3$
- AlSi10Mg: $\rho_{\text{theoretical}} = 2.680\text{ g/cm}^3$
- Inconel 718: $\rho_{\text{theoretical}} = 8.190\text{ g/cm}^3$

### 3.4 Open Porosity & Oil Impregnation Protocol
When specimen relative density is below $98.5\%$ or open surface-connected pores exist, liquid penetration into interior voids causes erroneous over-estimation of density. In accordance with ASTM B962 Section 7:
1. Impregnate open voids with light paraffin oil (density $\rho_{\text{oil}} \approx 0.850\text{ g/cm}^3$) under vacuum ($< 5\text{ kPa}$) for 30 minutes.
2. Wipe excess oil from outer surfaces with an absorbent lint-free cloth.
3. Weigh oil-impregnated specimen in air ($m_{\text{oil, air}}$) and submerged in water ($m_{\text{oil, liq}}$):
   $$\rho_{\text{bulk}} = \frac{m_{\text{air}} \cdot \rho_{\text{water}}}{m_{\text{oil, air}} - m_{\text{oil, liq}}}$$

---

## 4. ASTM E8 / E8M: Tension Testing of Metallic Additive Materials

**Standard Title**: *Standard Test Methods for Tension Testing of Metallic Materials*

### 4.1 Specimen Geometries for Additive Manufacturing
Due to the constraints of LPBF build envelopes and high material cost, proportional sub-size specimens are frequently utilized:

1. **Standard Proportional Round Specimen ($12.5\text{ mm}$ Nominal Diameter)**:
   - Gauge Length ($G$): $50.0 \pm 0.1\text{ mm}$ ($4D$)
   - Nominal Diameter ($D$): $12.5 \pm 0.2\text{ mm}$
   - Transition Fillet Radius ($R$): $\ge 10\text{ mm}$
   - Length of Reduced Section ($A$): $\ge 56\text{ mm}$
2. **Sub-Size Round Specimen ($6.0\text{ mm}$ Gauge Diameter)**:
   - Gauge Length ($G$): $30.0 \pm 0.1\text{ mm}$ ($5D$)
   - Gauge Diameter ($D$): $6.0 \pm 0.1\text{ mm}$
   - Fillet Radius ($R$): $\ge 6.0\text{ mm}$
   - Reduced Section ($A$): $\ge 36\text{ mm}$
3. **Sub-Size Round Specimen ($4.0\text{ mm}$ Gauge Diameter - High Density Mini-Coupon)**:
   - Gauge Length ($G$): $20.0 \pm 0.1\text{ mm}$ ($5D$)
   - Gauge Diameter ($D$): $4.0 \pm 0.1\text{ mm}$
   - Fillet Radius ($R$): $\ge 4.0\text{ mm}$
4. **Machining vs As-Built Surfaces**: Tensile coupons must be manufactured as oversized cylinders ($+1.0\text{ mm}$ machining envelope) and CNC lathe-turned to final dimensions. As-built unmachined surfaces degrade measured elongation and fatigue life by $30 - 50\%$ due to surface notch stress concentrations ($R_a = 8 - 15\,\mu\text{m}$).

### 4.2 Strain Rate Control Regimes
Testing must be performed on an electromechanical universal testing machine calibrated to ASTM E4 with an extensometer conforming to ASTM E83 Class B2:
- **Elastic and Yielding Region**: Strain rate control set to:
  $$\dot{\varepsilon} = 0.005 \pm 0.002\text{ mm/(mm}\cdot\text{min)} \quad (8.3 \times 10^{-5}\text{ s}^{-1})$$
  Maintained through $0.2\%$ plastic offset yield strength ($R_{p0.2}$).
- **Plastic Flow to Rupture**: Separation rate increased up to:
  $$\dot{\varepsilon}_{\text{plastic}} \le 0.5\text{ mm/(mm}\cdot\text{min)} \quad (8.3 \times 10^{-3}\text{ s}^{-1})$$

---

## 5. ASTM E1245 & ASTM E384: Porosity & Vickers Microhardness

### 5.1 ASTM E1245: Quantitative Metallographic Porosity Analysis
**Standard Title**: *Standard Practice for Determining the Inclusion or Second-Phase Constituent Content of Metals by Automatic Image Analysis*

1. **Specimen Preparation**:
   - Metallographic mounting in conductive phenolic resin.
   - Grinding with SiC papers: P400, P800, P1200, P2400 under water lubrication.
   - Diamond polishing: $9\,\mu\text{m}, 3\,\mu\text{m}, 1\,\mu\text{m}$ poly-crystalline diamond suspension.
   - Final chemomechanical polish: $0.04\,\mu\text{m}$ colloidal silica suspension ($\text{OP-S}$) with $10\%\, \text{H}_2\text{O}_2$ for titanium alloys.
2. **Sampling & Statistical Validation**:
   - Inspection planes: Both $XY$ (transverse, perpendicular to build direction) and $XZ / YZ$ (longitudinal, parallel to build direction).
   - Minimum sample size: $\ge 20$ independent, non-overlapping fields of view captured at $100\times$ or $200\times$ optical magnification.
3. **Image Segmentation & Pore Morphology Classification**:
   - Total Porosity Area Fraction: $A_A = \frac{\sum A_{\text{pores}}}{A_{\text{total}}} = V_V$ (Delphic volume fraction).
   - **Circularity Index**: $C = \frac{4\pi A}{P^2}$ (where $A$ is pore area, $P$ is perimeter).
     - *Keyhole Pores / Gas Entrapment*: $C \ge 0.70$ (highly spherical, aspect ratio $< 1.5$).
     - *Lack of Fusion (LoF)*: $C < 0.50$ with acute notch vertices ($< 45^\circ$) containing un-melted powder particles.

### 5.2 ASTM E384: Microindentation Hardness (Vickers)
**Standard Title**: *Standard Test Method for Microindentation Hardness of Materials*

1. **Indenter Geometry**:
   - Diamond right pyramid with square base and face angle $\theta = 136^\circ 00'$.
2. **Vickers Hardness Equation**:
   $$\text{HV} = 0.1891 \cdot \frac{F}{d^2} \quad [\text{kgf/mm}^2] \quad (F \text{ in N}, d \text{ in mm})$$
   $$\text{HV} = 1.8544 \cdot \frac{F_{\text{kgf}}}{d^2} \quad [\text{kgf/mm}^2]$$
   Where $d = \frac{d_1 + d_2}{2}$ is the arithmetic mean of both diagonals measured via calibrated optical microscope.
3. **Standard Test Conditions**:
   - Applied load: HV0.3 ($2.942\text{ N}$) or HV0.5 ($4.903\text{ N}$).
   - Dwell time: $10 - 15\text{ seconds}$.
4. **Indentation Spacing Constraints**:
   - Center-to-center distance between neighboring indents: $\ge 2.5 \times d$ (preferred $\ge 3.0 \times d$) to eliminate residual plastic strain hardening interference.
   - Distance from specimen edge to indent center: $\ge 2.5 \times d$.

---

## 6. ISO/ASTM 52900 & ISO/ASTM 52911: Terminology & AM Design Rules

### 6.1 ISO/ASTM 52900: Terminology & Fundamentals
**Standard Title**: *Additive Manufacturing — General Principles — Fundamentals and Vocabulary*
- **PBF-LB/M**: Powder Bed Fusion — Laser Beam / Metal. The standard classification code for selective laser melting / direct metal laser sintering.
- **Machine Coordinate System**:
  - $+Z$ axis: Normal to the build substrate pointing in the upward build growth direction.
  - $+X$ axis: Parallel to the front of the machine, typically collinear with the recoater blade transit direction.
  - $+Y$ axis: Orthogonal to $X$ and $Z$, directed toward the rear chamber wall.

### 6.2 ISO/ASTM 52911: Design for Metal Powder Bed Fusion (PBF-LB/M)
**Standard Title**: *Additive Manufacturing — Design — Part 1: Laser-Based Powder Bed Fusion of Metals*

1. **Self-Supporting Overhang Angles**:
   - Critical angle: $\theta_{\text{crit}} \ge 40^\circ - 45^\circ$ measured relative to the horizontal build plate plane.
   - Downskin surfaces at angles $\theta < 40^\circ$ require support structures to prevent molten liquid sinking into un-sintered powder (dross formation) and thermal expansion curling that causes recoater blade jamming.
2. **Thin Wall & Feature Size Thresholds**:
   - Minimum unsupported vertical wall thickness: $t_{\text{wall}} \ge 0.4 - 0.6\text{ mm}$ (approx. $4 - 6\times$ laser spot diameter $d_{\text{spot}}$).
   - Minimum supported wall thickness: $t_{\text{supported}} \ge 0.3\text{ mm}$.
   - Minimum aspect ratio for slender vertical pins: Height-to-diameter ratio $H/D \le 8:1$ without lateral brace supports.
3. **Internal Conformal Cooling Channels**:
   - Minimum channel diameter: $D_{\text{channel}} \ge 1.0 - 1.5\text{ mm}$ to ensure complete powder clearance during ultrasonic depowdering.
   - Maximum horizontal circular channel diameter without supports: $D \le 6.0\text{ mm}$. For larger spans ($> 6.0\text{ mm}$), channels must be designed with self-supporting teardrop, diamond, or Gothic arch cross-sections ($\ge 45^\circ$ apex).
4. **Powder Evacuation Orifices**:
   - Sealed cavities are strictly prohibited. Every internal chamber must incorporate at least two powder drain ports with diameter $D_{\text{drain}} \ge 3.0 - 5.0\text{ mm}$ positioned at opposite vertices to enable clean gas flushing.
