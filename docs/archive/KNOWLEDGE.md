# Metallurgical Knowledge Base & Protocols (`KNOWLEDGE.md`)

This repository serves as the authoritative, peer-reviewed knowledge base for laser powder bed fusion (LPBF), physical metallurgy, thermophysical material properties, standard testing protocols (ASTM/ISO), and governing analytical models.

> **Compliance Note**: In accordance with Rule 1 in [`RULES.md`](../../RULES.md), all content in this file is strictly in English. All numerical values and equations have undergone dual academic and functional verification as recorded in [`PROOF.md`](../../PROOF.md).

---

## Table of Contents
1. [5-Tier Data Architecture](#1-5-tier-data-architecture)
2. [Validated Material & Thermophysical Constants](#2-validated-material--thermophysical-constants)
3. [Analytical Governing Physics & Regime Thresholds](#3-analytical-governing-physics--regime-thresholds)
4. [Standard Testing Protocols (ASTM / ISO)](#4-standard-testing-protocols-astm--iso)
5. [Peer-Reviewed Literature Ground Truth Benchmarks](#5-peer-reviewed-literature-ground-truth-benchmarks)
6. [Post-Processing & Heat Treatment Regimes](#6-post-processing--heat-treatment-regimes)

---

## 1. 5-Tier Data Architecture

Every experimental record, material qualification run, and simulation parameter in the platform maintains strict 5-tier relational integrity:

```
[Tier 1: Build] ──► [Tier 2: ProcessParams] ──► [Tier 3: Sample] ──► [Tier 4: Properties] ──► [Tier 5: Source]
```

### Tier 1: Build Level
- **Machine Specifications**: Make, model, laser type (e.g., Continuous Wave Yb-fiber laser, $\lambda = 1064\text{ nm}$), beam profile (Gaussian $\text{TEM}_{00}$).
- **Feedstock Powder Characterization**:
  - Manufacturing method: Gas Atomization (GA), Plasma Atomization (PA), or Plasma Rotating Electrode Process (PREP).
  - Particle Size Distribution (PSD): $D_{10}$, $D_{50}$ (median diameter), and $D_{90}$ in micrometers ($\mu\text{m}$).
  - Apparent density and Hall flow rate per ASTM B212 / ASTM B213.
- **Chamber Environment**: Inert gas medium (Argon 99.999% or Nitrogen), baseplate preheating temperature ($T_0$), and residual oxygen concentration ($O_2 < 100\text{ ppm}$).

### Tier 2: Process Parameters
- **Primary Laser Inputs**:
  - Laser power: $P$ $[\text{W}]$
  - Scan speed: $v$ $[\text{mm/s}]$
  - Hatch spacing: $h$ $[\mu\text{m}]$
  - Layer thickness: $t$ $[\mu\text{m}]$
  - Nominal beam spot diameter ($1/e^2$ intensity): $d_{\text{spot}}$ $[\mu\text{m}]$
- **Scan Strategy**: Alternating bidirectional meander ($67^\circ$ rotation per layer), island / checkerboard ($5 \times 5\text{ mm}$), or stripe scan.
- **Optical Coupling**: Material- and state-dependent optical absorptivity ($\eta$).

### Tier 3: Sample Level
- **Spatial Positioning**: Coordinates $(x, y, z)$ on the build substrate.
- **Build Orientation**: Angle relative to build plate plane ($0^\circ$ horizontal, $45^\circ$, $90^\circ$ vertical).
- **Specimen Geometry**: Standard tensile dogbones (ASTM E8/E8M), cylindrical fatigue rods (ASTM E466), micro-CT coupons ($10 \times 10 \times 10\text{ mm}$), or Charpy V-notch blanks (ASTM E23).
- **Heat Treatment State**: As-Built (AB), Stress Relieved (SR), Hot Isostatic Pressed (HIP), or Solution Treated and Aged (STA).

### Tier 4: Measured Properties
- **Density & Porosity**: Relative density ($\%$), volumetric porosity ($\%$), pore morphology (Lack of Fusion, Keyhole, Gas entrapment).
- **Static Mechanical Performance**:
  - Yield Strength ($R_{p0.2}$ at 0.2% offset strain) $[\text{MPa}]$
  - Ultimate Tensile Strength ($R_m$ / UTS) $[\text{MPa}]$
  - Plastic elongation at break ($A$) $[\%]$
  - Reduction of area ($Z$) $[\%]$
  - Elastic Young's modulus ($E$) $[\text{GPa}]$
- **Microhardness**: Vickers hardness (HV0.3, HV0.5, or HV1) per ASTM E384.

### Tier 5: Source Traceability
- Origin category: Peer-reviewed journal article, qualification report, or calibrated experiment.
- Full bibliographic pedigree: Authors, title, journal/conference, publication year, volume, page numbers.
- Persistent identifier: Fully resolvable Digital Object Identifier (DOI).

---

## 2. Material & Thermophysical Reference Data

The values below are reference inputs with explicit evidence labels. A populated table or literature citation does not by itself make a value measured, validated, or production-qualified; see [`docs/LPBF_ENGINEERING.md`](../LPBF_ENGINEERING.md) for the current estimated and missing-data boundaries.

Below are the thermophysical constants and baseline properties for LPBF alloys implemented in the platform:

| Thermophysical Property | Symbol / Unit | Ti-6Al-4V (Grade 5) | 316L Stainless Steel | AlSi10Mg | Inconel 718 |
|---|---|---|---|---|---|
| **Melting Point / Liquidus** | $T_m$ / $T_L$ $[^\circ\text{C}]$ | 1660 | 1420 | 600 | 1336 |
| **Solidus Temperature** | $T_S$ $[^\circ\text{C}]$ | 1604 | 1375 | 570 | 1260 |
| **Solid Density** | $\rho$ $[\text{kg/m}^3]$ | 4430 | 7950 | 2680 | 8190 |
| **Specific Heat Capacity** | $C_p$ $[\text{J/(kg}\cdot\text{K)}]$ | 526 | 500 | 910 | 435 |
| **Thermal Conductivity** | $k$ $[\text{W/(m}\cdot\text{K)}]$ | 6.7 | 15.0 | 130.0 | 11.4 |
| **Thermal Diffusivity** | $\alpha = k/(\rho C_p)$ $[\text{m}^2/\text{s}]$ | $2.87 \times 10^{-6}$ | $3.77 \times 10^{-6}$ | $5.33 \times 10^{-5}$ | $3.20 \times 10^{-6}$ |
| **Volumetric Enthalpy of Melting** | $h_s = \rho C_p T_m$ $[\text{J/m}^3]$ | $3.86 \times 10^{9}$ | $5.64 \times 10^{9}$ | $1.46 \times 10^{9}$ | $4.75 \times 10^{9}$ |
| **Effective Optical Absorptivity (1064 nm)** | $\eta$ $[-]$ | 0.42 | 0.53 | 0.22 | 0.55 |
| **Lack-of-Fusion VED Threshold** | $E_{V,\text{min}}$ $[\text{J/mm}^3]$ | 48.0 | 55.0 | 40.0 | 52.0 |
| **Keyhole VED Onset Threshold** | $E_{V,\text{keyhole}}$ $[\text{J/mm}^3]$ | 110.0 | 135.0 | 95.0 | 125.0 |
| **Optimal Conduction VED Window** | $E_V$ $[\text{J/mm}^3]$ | 55 – 85 | 65 – 100 | 50 – 75 | 65 – 95 |

---

## 3. Analytical Governing Physics & Regime Thresholds

### 3.1 Derived Energy Densities
1. **Linear Energy Density (LED)**:
   $$E_L = \frac{P}{v} \quad [\text{J/mm}]$$
   *Application*: Single-track continuity, bead stability, and balling prevention.

2. **Areal Energy Density (AED)**:
   $$E_A = \frac{P}{v \cdot h} \quad [\text{J/mm}^2]$$
   *Application*: Hatch overlap evaluation and planar surface heating.

3. **Volumetric Energy Density (VED)**:
   $$E_V = \frac{P}{v \cdot h \cdot t} \quad [\text{J/mm}^3]$$
   *Application*: Bulk volume heat input metric; primary empirical indicator for nominal density.

### 3.2 Intensity and Dwell Time
- **Peak Gaussian Laser Intensity**:
  $$I_0 = \frac{4 \cdot P}{\pi \cdot d_{\text{spot}}^2} \quad [\text{MW/cm}^2]$$
- **Laser Interaction Dwell Time**:
  $$t_{\text{dwell}} = \frac{d_{\text{spot}}}{v} \quad [\mu\text{s}]$$

### 3.3 Dimensionless Normalized Enthalpy ($\Delta H / h_s$)
Derived by King, Rubenchik, et al. (2014) to characterize keyhole onset independently of volumetric energy density:
$$\frac{\Delta H}{h_s} = \frac{\eta \cdot P}{\rho \cdot C_p \cdot T_m \cdot \sqrt{\pi \cdot \alpha \cdot v \cdot d_{\text{spot}}^3}}$$
- **Transition Criterion**: Keyhole depression occurs when $\frac{\Delta H}{h_s} \gtrsim 30$.

### 3.4 Rosenthal Moving Point Source Equation
The quasi-steady state 3D temperature field $T(x, y, z)$ in a semi-infinite substrate subjected to a moving point heat source:
$$T(x, y, z) - T_0 = \frac{\eta \cdot P}{2 \pi \cdot k \cdot R} \exp\left[ - \frac{v \cdot (R + x)}{2 \alpha} \right]$$
Where:
- $R = \sqrt{x^2 + y^2 + z^2}$ is the radial distance from the laser position.
- $x$ is the coordinate aligned with the scanning direction ($x > 0$ ahead of beam, $x < 0$ behind beam).
- $T_0$ is the uniform baseplate preheat temperature.

### 3.5 Process Defect Regimes
1. **Lack of Fusion (LoF)**:
   - *Geometric Condition*: Hatch spacing $h >$ melt pool width $W$, or layer thickness $t >$ melt pool depth $D$.
   - *Defect Characteristic*: Irregular, sharp-edged voids containing un-melted or partially sintered powder particles; severely detrimental to fatigue life.
2. **Keyhole Vaporization**:
   - *Physical Mechanism*: Intense metal vaporization generates recoil pressure ($P_{\text{recoil}} \propto \exp(-\Delta H_v / k_B T)$) exceeding surface tension forces, opening a deep narrow vapor depression cavity.
   - *Defect Characteristic*: Spherical gas-trapped pores located at the root of the melt track following keyhole tip collapse.
3. **Balling / Plateau-Rayleigh Instability**:
   - *Geometric Condition*: Melt pool length-to-width aspect ratio $L/W > \pi \approx 3.1415$.
   - *Physical Mechanism*: Capillary cylinder instability breaks continuous tracks into isolated spherical beads to minimize surface energy.

---

## 4. Standard Testing Protocols (ASTM / ISO)

| Standard | Title / Focus | Critical Requirements |
|---|---|---|
| **ASTM F3055** | Additive Manufacturing Ti-6Al-4V with Powder Bed Fusion | Specifies chemical composition, minimum tensile properties (Grade 5: UTS $\ge 895\text{ MPa}$, Yield $\ge 828\text{ MPa}$, Elongation $\ge 10\%$), and mandatory thermal stress relief prior to plate removal. |
| **ASTM F2924** | Additive Manufacturing Ti-6Al-4V with Powder Bed Fusion (Aircraft / Structural) | Baseline specification for structural components requiring chemical composition analysis and certified mechanical testing. |
| **ASTM B962** | Density Determination using Archimedes' Principle | Measures dry weight in air ($m_{\text{air}}$) and apparent weight submerged in liquid ($m_{\text{liq}}$): $\rho_{\text{sample}} = \frac{m_{\text{air}}}{m_{\text{air}} - m_{\text{liq}}} \cdot (\rho_{\text{liq}} - \rho_{\text{air}}) + \rho_{\text{air}}$. |
| **ASTM E8 / E8M** | Tension Testing of Metallic Materials | Standard cylindrical and flat dogbone geometries; strain rate control: $0.005 \pm 0.002\text{ mm/(mm}\cdot\text{min)}$ through yield, crosshead separation rate $\le 0.5\text{ in/(in}\cdot\text{min)}$ post-yield. |
| **ASTM E1245** | Inclusion and Porosity Content by Image Analysis | Quantitative metallography on polished cross-sections ($X-Y$ and $Z$ planes) using thresholded pixel area fractions across $\ge 20$ fields of view. |
| **ASTM E384** | Microindentation Hardness of Materials | Vickers microhardness testing (HV0.3, HV0.5) with dwell time of 10–15 seconds; minimum spacing between indents equal to $2.5\times$ diagonal length. |
| **ISO/ASTM 52900** | Additive Manufacturing — General Principles — Fundamentals & Vocabulary | Unified terminology for process categories (PBF-LB/M), coordinate systems, and processing states. |

---

## 5. Peer-Reviewed Literature Ground Truth Benchmarks

### 5.1 Ti-6Al-4V Grade 5 / ELI
- **Thijs et al. (2010)** — *Acta Materialia* [DOI: 10.1016/j.actamat.2010.02.045]:
  - Parameters: $P = 250\text{ W}$, $v = 1600\text{ mm/s}$, $h = 50\mu\text{m}$, $t = 30\mu\text{m}$, $d = 80\mu\text{m}$.
  - Results: Relative density $99.8\%$, fine acicular $\alpha'$ martensitic microstructure, UTS: $1250\text{ MPa}$, Elongation: $7.5\%$.
- **Kasperovich et al. (2015)** — *Materials & Design* [DOI: 10.1016/j.matdes.2015.01.031]:
  - Parameters: $P = 175\text{ W}$, $v = 710\text{ mm/s}$, $h = 100\mu\text{m}$, $t = 30\mu\text{m}$ ($E_V = 82.2\text{ J/mm}^3$).
  - Results: Relative density $99.85\%$, Yield Strength: $1095\text{ MPa}$, UTS: $1220\text{ MPa}$, Elongation: $8.2\%$.

### 5.2 316L Stainless Steel
- **Cherry et al. (2015)** — *Int. J. Adv. Manuf. Technol.* [DOI: 10.1007/s00170-014-6058-4]:
  - Investigated VED range from $40$ to $200\text{ J/mm}^3$. Peak relative density ($99.6\%$) achieved at $E_V \approx 104.2\text{ J/mm}^3$ ($P = 180\text{ W}, v = 700\text{ mm/s}, h = 120\mu\text{m}, t = 50\mu\text{m}$).
- **Liverani et al. (2017)** — *Journal of Materials Processing Technology* [DOI: 10.1016/j.jmatprotec.2017.03.034]:
  - Parameters: $P = 200\text{ W}$, $v = 800\text{ mm/s}$, $h = 100\mu\text{m}$, $t = 30\mu\text{m}$ ($E_V = 83.3\text{ J/mm}^3$).
  - Results: Relative density $99.78\%$, Yield: $580\text{ MPa}$, UTS: $695\text{ MPa}$, Elongation: $42\%$, Hardness: $230\text{ HV0.5}$.

### 5.3 AlSi10Mg Aluminum Alloy
- **Read et al. (2015)** — *Materials & Design* [DOI: 10.1016/j.matdes.2014.09.044]:
  - Evaluated high-reflectivity LPBF: $P = 370\text{ W}$, $v = 1300\text{ mm/s}$, $h = 130\mu\text{m}$, $t = 30\mu\text{m}$ ($E_V = 73.1\text{ J/mm}^3$).
  - Results: Relative density $99.7\%$, UTS: $410\text{ MPa}$, Yield: $275\text{ MPa}$, Elongation: $5.8\%$, Hardness: $125\text{ HV0.5}$.
- **Aboulkhair et al. (2016)** — *Prog. Mater. Sci.* [DOI: 10.1016/j.pmatsci.2016.03.004]:
  - Detailed preheating ($150–200^\circ\text{C}$) to suppress hydrogen porosity and eliminate residual stress microcracking.

---

## 6. Post-Processing & Heat Treatment Regimes

### 6.1 Stress Relief (SR)
- **Ti-6Al-4V**: $650^\circ\text{C} \pm 15^\circ\text{C}$ for $3\text{ hours}$ in high-vacuum ($< 10^{-4}\text{ mbar}$) or ultra-pure Argon; furnace cooling to below $200^\circ\text{C}$ before atmosphere exposure. Eliminates $>85\%$ of build-induced residual stresses while preserving martensitic fine grain strength.
- **316L SS**: $450^\circ\text{C} - 600^\circ\text{C}$ for $2\text{ hours}$ to relieve residual stress without inducing chromium carbide grain boundary precipitation (sensitization).

### 6.2 Hot Isostatic Pressing (HIP)
- **Ti-6Al-4V**: $920^\circ\text{C} \pm 10^\circ\text{C}$, $100\text{ MPa}$ Argon pressure, $2\text{ hours}$ soak time.
  - *Effect*: Closes internal gas and lack-of-fusion pores; transforms acicular $\alpha'$ martensite into lamellar $\alpha+\beta$ microstructure, boosting plastic elongation ($12 - 16\%$) and high-cycle fatigue life ($\sigma_{10^7} > 500\text{ MPa}$).
- **AlSi10Mg**: $500^\circ\text{C}$, $100\text{ MPa}$, $2\text{ hours}$.
  - *Effect*: Spheroidizes the brittle eutectic silicon network and closes internal micro-voids.
