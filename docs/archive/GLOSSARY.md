# Metallurgy & Additive Manufacturing Terminology Glossary (`GLOSSARY.md`)

This glossary provides authoritative, mathematically formulated, and physically grounded definitions of fundamental terms, governing dimensionless numbers, microstructural metrics, and defect mechanisms in Laser Powder Bed Fusion (PBF-LB/M) and physical metallurgy.

> **Compliance Notice**: In accordance with Rule 1 in [`RULES.md`](../../RULES.md), all definitions, physical formulations, and scientific terms are documented in English.

---

## 1. Energy Density & Heat Input Metrics

### Linear Energy Density (LED, $E_L$)
- **Definition**: The total laser thermal energy delivered per unit length of travel along a single scan vector.
- **Mathematical Formula**:
  $$E_L = \frac{P}{v} \quad \left[\frac{\text{J}}{\text{mm}} \text{ or } \frac{\text{kJ}}{\text{m}}\right]$$
  Where $P$ is laser power $[\text{W}]$ and $v$ is scan velocity $[\text{mm/s}]$.
- **Physical Significance**: Primary metric for single-track continuity, melt pool track cross-sectional area, and bead stability. Prevents track balling at high values and humping at extreme scan velocities.

### Areal Energy Density (AED, $E_A$)
- **Definition**: The laser energy deposited per unit planar area of the powder layer surface during hatching.
- **Mathematical Formula**:
  $$E_A = \frac{P}{v \cdot h} = \frac{E_L}{h} \quad \left[\frac{\text{J}}{\text{mm}^2}\right]$$
  Where $h$ is hatch spacing $[\text{mm}]$.
- **Physical Significance**: Determines surface track-to-track overlap and planar remelting fraction. Critical for optimizing top-surface roughness and preventing inter-track lack-of-fusion voids.

### Volumetric Energy Density (VED, $E_V$)
- **Definition**: The nominal thermal energy input per unit volume of powder bed.
- **Mathematical Formula**:
  $$E_V = \frac{P}{v \cdot h \cdot t} = \frac{E_A}{t} \quad \left[\frac{\text{J}}{\text{mm}^3}\right]$$
  Where $t$ is nominal powder layer thickness $[\text{mm}]$.
- **The "VED Fallacy" & Physical Limitations**:
  While widely used as an initial heuristic, VED is fundamentally non-unique. It omits:
  1. The laser beam spot diameter ($d_{\text{spot}}$) and peak Gaussian intensity ($I_0 = \frac{4P}{\pi d_{\text{spot}}^2}$).
  2. The thermal interaction dwell time ($\tau = \frac{d_{\text{spot}}}{v}$).
  3. Dynamic powder absorptivity variations ($\eta$) and heat conduction into the substrate.
  *Two sets of parameters with identical VED ($66.7\text{ J/mm}^3$) can produce completely different metallurgical outcomes: one in deep keyhole vaporization (high intensity, small spot) and the other in incomplete melting/lack of fusion (low intensity, large spot).*

---

## 2. Fluid Dynamics & Instability Phenomena

### Marangoni Effect / Marangoni Convection
- **Definition**: Thermocapillary fluid motion inside the molten pool driven by spatial gradients in surface tension ($\gamma$).
- **Mathematical Formulation**:
  The shear stress at the liquid-gas interface is governed by:
  $$\tau_{\text{surface}} = \nabla_s \gamma = \frac{\partial \gamma}{\partial T} \nabla T + \frac{\partial \gamma}{\partial C} \nabla C$$
  Where $\frac{\partial \gamma}{\partial T}$ is the temperature coefficient of surface tension and $\nabla T$ is the radial thermal gradient.
- **Fluid Flow Patterns**:
  - **Negative $\frac{\partial \gamma}{\partial T}$ (Pure metals & clean alloys)**: Surface tension is highest at the cooler outer melt pool perimeter and lowest at the hot center. Fluid flows outward from center to edge, creating a shallow, wide, bowl-shaped melt pool.
  - **Positive $\frac{\partial \gamma}{\partial T}$ (Alloys with surface-active solutes like Sulfur or Oxygen, e.g., in steel)**: Surface tension increases with temperature. Fluid flows inward toward the laser spot center and plunges downward, producing a deep, narrow penetration profile.

### Rayleigh-Plateau Capillary Instability (Balling Phenomenon)
- **Definition**: Spontaneous hydrodynamic breakup of an elongated liquid melt cylinder into discrete, isolated spherical droplets driven by surface energy minimization.
- **Mathematical Threshold**:
  Occurs when the aspect ratio of the melt pool exceeds $\pi$:
  $$\frac{L_{\text{pool}}}{W_{\text{pool}}} > \pi \approx 3.1415$$
  Where $L_{\text{pool}}$ is pool length and $W_{\text{pool}}$ is pool width.
- **Physical Significance**: In LPBF, excessive scan velocity elongates the melt pool tail. When $L/W > \pi$, capillary pressure perturbations $\Delta P = \gamma / R$ grow exponentially, severing continuous scan tracks into balls and causing severe lack-of-fusion pores and high surface roughness.

### Recoil Pressure ($P_{\text{recoil}}$)
- **Definition**: The reactive compressive pressure exerted downward on the melt pool surface by escaping high-velocity vaporized metal atoms when surface temperature approaches or exceeds the boiling point ($T_b$).
- **Mathematical Formula** (Hertz-Knudsen formulation):
  $$P_{\text{recoil}}(T) = 0.54 P_0 \exp\left[ \frac{\Delta H_v}{k_B T_b} \left( 1 - \frac{T_b}{T} \right) \right]$$
  Where $\Delta H_v$ is latent heat of vaporization, $P_0$ is ambient pressure, and $k_B$ is Boltzmann's constant. Recoil pressure is the primary driving force opening keyhole depressions.

---

## 3. Solidification & Microstructural Transformations

### Secondary Dendrite Arm Spacing (SDAS, $\lambda_2$)
- **Definition**: The average physical distance between adjacent secondary branches of columnar or equiaxed dendrites in the rapidly solidified cellular microstructure.
- **Mathematical Scaling Law**:
  $$\lambda_2 = B \cdot \dot{T}^{-n} = B \cdot (G \cdot R)^{-n}$$
  Where:
  - $\dot{T} = \frac{\partial T}{\partial t} = G \cdot R$ is the local cooling rate $[\text{K/s}]$.
  - $G = |\nabla T|$ is the temperature gradient at the solidification front $[\text{K/m}]$.
  - $R$ is the solidification front velocity $[\text{m/s}]$.
  - $B$ is an alloy-specific kinetic coarsening constant, and exponent $n \approx 0.33 - 0.40$.
- **Significance in LPBF**: Because LPBF cooling rates reach $10^5 - 10^7\text{ K/s}$, $\lambda_2$ is reduced to sub-micron scales ($0.3 - 1.0\,\mu\text{m}$), yielding yield strengths $20 - 40\%$ higher than conventional cast materials via Hall-Petch boundary strengthening.

### Martensitic Transformation ($\beta \rightarrow \alpha'$)
- **Definition**: A diffusionless, athermal shear transformation that converts the high-temperature Body-Centered Cubic (BCC, $\beta$) phase in titanium alloys into a supersaturated, metastable Hexagonal Close-Packed (HCP, $\alpha'$) acicular needle microstructure.
- **Kinetic Criterion**:
  Occurs when the cooling rate through the $\beta$-transus temperature ($T_\beta \approx 995^\circ\text{C}$ for Ti-6Al-4V) exceeds the critical cooling rate:
  $$\dot{T} \ge \dot{T}_{\text{crit}} \approx 410\text{ K/s}$$
  *Since LPBF cooling rates exceed $10^5\text{ K/s}$, the as-built microstructure of LPBF Ti-6Al-4V is almost $100\%$ fine acicular $\alpha'$ martensite.*
- **Crystallographic Orientation (Burgers Relationship)**:
  $$\{110\}_\beta \parallel \{0001\}_{\alpha'}, \quad \langle 1\bar{1}1 \rangle_\beta \parallel \langle 11\bar{2}0 \rangle_{\alpha'}$$

### Lamellar Thickness ($\lambda_\alpha$)
- **Definition**: The physical width of individual $\alpha$-phase platelets/laths organized in Widmanstätten (basketweave) or parallel colony packets, developed after decomposition of $\alpha'$ martensite during post-build annealing or HIP.
- **Physical Impact**: Follows a Hall-Petch-type relationship with yield strength:
  $$\sigma_y = \sigma_0 + k_\alpha \cdot \lambda_\alpha^{-1/2}$$
  Sub-micron lamellar thicknesses produced by controlled sub-transus heat treatments provide an optimal combination of high tensile yield strength ($> 850\text{ MPa}$) and high fracture toughness ($K_{1c} > 60\text{ MPa}\sqrt{\text{m}}$).

### Columnar-to-Equiaxed Transition (CET)
- **Definition**: The morphological transition of solidifying grain structure from elongated columnar grains aligned with the heat extraction direction ($+Z$) to randomly oriented, equiaxed grains.
- **Governing Parameter (Hunt's Criterion)**:
  The morphology depends on the ratio of thermal gradient $G$ to growth velocity $R$:
  $$\text{Morphology} \propto \frac{G^n}{R}$$
  - High $G/R$: Promotes steep planar/cellular-columnar growth with strong epitaxial texture along $\langle 001 \rangle$.
  - Low $G/R$ with high undercooling $\Delta T$: Promotes equiaxed nucleation ahead of the solidification front, suppressing anisotropic columnar grain growth.

---

## 4. Mechanical Mechanics & Stress State

### Residual Stress Tensor ($\boldsymbol{\sigma}_{ij}$)
- **Definition**: The internal multi-axial stress field remaining within the printed component after cooling to room temperature in the absence of external applied loads.
- **Mathematical Representation**:
  $$\boldsymbol{\sigma} = \begin{bmatrix} \sigma_{xx} & \tau_{xy} & \tau_{xz} \\ \tau_{yx} & \sigma_{yy} & \tau_{yz} \\ \tau_{zx} & \tau_{zy} & \sigma_{zz} \end{bmatrix}$$
- **Temperature Gradient Mechanism (TGM)**:
  1. **Heating Phase**: Laser rapidly heats the top layer, but thermal expansion is constrained by the cold surrounding substrate, inducing compressive plastic strain ($\varepsilon_p < 0$).
  2. **Cooling Phase**: Upon solidification and cooling, the plastically deformed layer attempts to shrink, but is restrained by the rigid baseplate. This generates severe tensile residual stresses ($\sigma_{xx}, \sigma_{yy} \ge 600 - 850\text{ MPa}$ for Ti-6Al-4V) in the top layers, balanced by compressive stresses in the interior and bending moments across the substrate.
- **Consequences**: Severe part distortion, delamination from supports, baseplate warping, and degraded fatigue crack initiation thresholds if not relieved via SOP-03.

---

## 5. Process Defect Taxonomies

### Lack of Fusion (LoF)
- **Definition**: Planar or volumetric voids formed by insufficient local heat input, resulting in incomplete melting between adjacent scan tracks or successive powder layers.
- **Geometric Criteria**:
  $$h > W_{\text{melt}} \quad \text{or} \quad t > D_{\text{melt}}$$
  Where $h$ is hatch spacing, $W_{\text{melt}}$ is melt pool width, $t$ is layer thickness, and $D_{\text{melt}}$ is depth.
- **Defect Characteristic**: Highly irregular morphology with sharp crack-like vertices containing un-melted or partially sintered spherical powder particles. Most damaging defect for high-cycle fatigue life.

### Keyhole Porosity
- **Definition**: Near-spherical gas cavities trapped at the root of the fusion zone caused by the collapse of deep vapor depressions during high-intensity laser processing.
- **Onset Criterion**: King et al. dimensionless normalized enthalpy:
  $$\frac{\Delta H}{h_s} \ge 30$$
- **Morphology**: Highly spherical pores (circularity $C \ge 0.70$) concentrated along the deepest penetration line of the laser track.

### Denudation Zone
- **Definition**: The powder-free clearance zone formed on both sides of a laser scan track where powder particles have been swept away.
- **Physical Mechanism**: Bernoulli suction effect induced by the high-velocity upward metal vapor jet, which entrains surrounding ambient shielding gas and draws adjacent loose powder particles into the melt pool.
