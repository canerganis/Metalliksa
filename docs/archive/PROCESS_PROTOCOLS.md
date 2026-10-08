# Laboratory & Production Standard Operating Procedures (`PROCESS_PROTOCOLS.md`)

This document defines the binding Standard Operating Procedures (SOPs) for powder characterization, machine setup, chamber inerting, recoater leveling, and post-build thermal post-processing for metal additive manufacturing (PBF-LB/M).

> **Compliance Notice**: In accordance with Rule 1 in [`RULES.md`](../../RULES.md), all procedural steps, safety thresholds, and quality checkpoints are codified in English. Every procedure references binding ASTM and ISO testing standards.

---

## Table of Contents
1. [SOP-01: Gas-Atomized Metal Powder Quality Assurance & Characterization](#sop-01-gas-atomized-metal-powder-quality-assurance--characterization)
2. [SOP-02: Machine Setup, Substrate Preheating, Inert Atmosphere, & Recoater Calibration](#sop-02-machine-setup-substrate-preheating-inert-atmosphere--recoater-calibration)
3. [SOP-03: Post-Build Thermal Processing: Stress Relief (SR) & Hot Isostatic Pressing (HIP)](#sop-03-post-build-thermal-processing-stress-relief-sr--hot-isostatic-pressing-hip)

---

## SOP-01: Gas-Atomized Metal Powder Quality Assurance & Characterization

**Applicability**: Virgin and recycled Ti-6Al-4V Grade 5 / Grade 23 ELI, 316L Stainless Steel, AlSi10Mg, and Inconel 718.

### 1.1 Scope & Objective
To ensure powder feedstock meets particle size distribution (PSD), flowability, packing density, and moisture limits before loading into the LPBF machine dosing hopper, preventing layer spreading defects and interstitial contamination.

### 1.2 Step-by-Step Procedure

#### Step 1: Representative Sampling (ASTM B215)
1. Do not sample solely from the top surface of the powder drum. Use a certified stainless steel dual-tube sampling thief or rotary riffle splitter per ASTM B215 (Method A or Method B).
2. Extract samples from upper, middle, and lower thirds of the container. Blend extracted portions to create a representative $500\text{ g}$ master lot.

#### Step 2: Particle Size Distribution (PSD) Analysis (ASTM B822 / ISO 13320)
1. Measure PSD using dry laser diffraction (Fraunhofer or Mie scattering model).
2. Optical settings: Ensure refractive index and absorption index match the target alloy (e.g., Ti-6Al-4V: Refractive index $2.65$, absorption $3.1$).
3. **Acceptance Thresholds**:
   - $D_{10} \ge 15.0 - 20.0\,\mu\text{m}$ (fine satellites below $10\,\mu\text{m}$ must be $< 3\%$ to prevent agglomeration and airborne health hazards).
   - $D_{50} = 30.0 - 38.0\,\mu\text{m}$ (median diameter).
   - $D_{90} \le 45.0 - 53.0\,\mu\text{m}$ (particles $> 63\,\mu\text{m}$ must be $0\%$ to prevent recoater streaking).
   - Span Index: $\text{Span} = \frac{D_{90} - D_{10}}{D_{50}} \le 1.20$.

#### Step 3: Flowability Testing (ASTM B213 / ASTM B964)
1. Ensure the calibrated Hall Flowmeter funnel ($2.54\text{ mm}$ orifice) is vibration-free and grounded to prevent electrostatic buildup.
2. Weigh $50.0 \pm 0.1\text{ g}$ of powder. Block the funnel discharge orifice with a finger, pour the powder sample, start a digital stopwatch upon release, and stop when the last powder exits.
3. **Acceptance Threshold**:
   - Hall Flow Rate $\le 25.0 - 30.0\text{ s / 50 g}$ for Ti-6Al-4V and Inconel 718.
   - For powders that do not flow spontaneously through Hall funnel (e.g., AlSi10Mg due to surface oxide cohesion), test via Carney Funnel ($5.08\text{ mm}$ orifice per ASTM B964).

#### Step 4: Apparent & Tap Density (ASTM B212 / ASTM B527)
1. Measure apparent density ($\rho_{\text{apparent}}$) using a $25\text{ cm}^3$ cylindrical cup.
2. Measure tap density ($\rho_{\text{tap}}$) using an automated tap density tester ($3000$ taps at $250\text{ taps/min}$).
3. **Evaluation Criteria**:
   - Hausner Ratio: $H = \frac{\rho_{\text{tap}}}{\rho_{\text{apparent}}} \le 1.20$.
   - Carr's Compressibility Index: $C = 100 \times \left( 1 - \frac{\rho_{\text{apparent}}}{\rho_{\text{tap}}} \right) \le 15\%$.

#### Step 5: Moisture Control & Dehydration Protocol
1. Measure moisture content using a loss-on-drying (LOD) infrared moisture analyzer or Karl Fischer titration.
2. If moisture exceeds $> 0.05\text{ wt}\%$ ($500\text{ ppm}$), subject powder to vacuum bake-out:
   - Temperature: $80^\circ\text{C} - 100^\circ\text{C}$ (maximum $70^\circ\text{C}$ for AlSi10Mg to prevent oxide thickening).
   - Vacuum level: $< 10\text{ mbar}$ for $4 - 6\text{ hours}$.
   - Store in sealed containers under dry Nitrogen or Argon blanket with active desiccant packs.

#### Step 6: Powder Recycling Limits
1. Recycled powder must pass through an automated ultrasonic sieve ($53\,\mu\text{m}$ or $63\,\mu\text{m}$ screen mesh) under protective Argon.
2. Record cumulative reuse cycles. Maximum reuse cycles without virgin powder blending: 10 cycles.
3. Measure interstitial oxygen pick-up via Inert Gas Fusion (ASTM E1409). Quarantine lot if oxygen exceeds $0.20\text{ wt}\%$ (Grade 5) or $0.13\text{ wt}\%$ (Grade 23 ELI).

---

## SOP-02: Machine Setup, Substrate Preheating, Inert Atmosphere, & Recoater Calibration

### 2.1 Scope & Objective
To establish calibrated baseline chamber conditions, mechanical coater alignment, and oxygen-depleted processing environments prior to initiating laser exposure.

### 2.2 Step-by-Step Procedure

#### Step 1: Substrate Build Plate Preparation
1. Verify substrate material matches the deposition alloy (e.g., Grade 5 titanium substrate for Ti-6Al-4V builds; 304/316 for stainless steel).
2. Inspect substrate surface roughness: Plate must be face-milled or surface-ground to $R_a = 1.6 - 3.2\,\mu\text{m}$.
3. Degrease plate thoroughly with electronic-grade Isopropyl Alcohol (IPA) and lint-free wipes.
4. Mount substrate plate onto build elevator and torque clamping bolts in a crisscross sequence to the manufacturer's specified torque ($25 - 35\text{ N}\cdot\text{m}$).

#### Step 2: Recoater Blade Calibration & Leveling
1. Select recoater blade geometry:
   - **Hard Blade** (Silicon carbide or ceramic): Mandatory for high-density structural components with no critical overhangs to enforce exact layer thickness.
   - **Soft / Flexible Blade** (Silicone rubber or carbon fiber brush): Mandatory for delicate lattice structures or thin tall walls susceptible to thermal warping.
2. Mount dial test indicator on the laser optics bridge or recoater carriage.
3. Traverse recoater blade across the 4 corners of the build plate:
   - **Leveling Tolerance**: Maximum height variation across the entire plate must be $\le 20\,\mu\text{m}$.
   - Set zero-gap reference position with a precision feeler gauge ($25\,\mu\text{m}$ nominal gap).
4. Verify powder dosing factor is set to $120\% - 150\%$ of theoretical layer volume to ensure continuous powder coverage without starvation.

#### Step 3: Chamber Evacuation & Inert Gas Purging
1. Clean chamber internal glass laser window using anhydrous ethanol and optical lens wipes; inspect protective glass for spatter pits or optical coatings degradation.
2. Close and latch process chamber door.
3. Initiate vacuum pull-down to $< 10\text{ mbar}$ (on vacuum-equipped machines) to eliminate trapped ambient air and moisture from internal insulation.
4. Purge chamber with ultra-high purity Argon (Grade 5.0, purity $\ge 99.999\%$, $O_2 < 2\text{ ppm}$, $H_2O < 3\text{ ppm}$).
5. Continuous Oxygen Sensor Monitoring:
   - Monitored via calibrated Zirconia electrochemical oxygen sensor.
   - **Safety Interlock**: Laser firing is hardware-interlocked and strictly prohibited until $O_2 < 100\text{ ppm}$ ($0.01\%$).
   - Target steady-state operating oxygen level during build: $O_2 \le 40 - 50\text{ ppm}$.

#### Step 4: Substrate Preheating & Thermal Stabilization
1. Set substrate heating elements:
   - Ti-6Al-4V: $T_0 = 150^\circ\text{C} - 200^\circ\text{C}$
   - AlSi10Mg: $T_0 = 150^\circ\text{C} - 200^\circ\text{C}$ (suppresses hydrogen bubbling and cracking)
   - 316L SS: $T_0 = 80^\circ\text{C} - 100^\circ\text{C}$
   - Crack-susceptible nickel superalloys / refractory metals: $T_0 = 500^\circ\text{C} - 800^\circ\text{C}$ (high-temperature induction/resistive substrate).
2. **Thermal Soak Dwell Time**: Maintain target preheat temperature for minimum **45 minutes** prior to spreading the first layer, ensuring complete thermal expansion stabilization across the plate and elevator column.

#### Step 5: Recirculating Gas Flow Velocity Check
1. Start recirculating blower. Verify laminar gas knife flow across the powder bed:
   - Gas velocity: $1.8 - 2.2\text{ m/s}$ measured at bed centerline.
   - Purpose: Continuously sweep condensate vapor and spatter plumes away from the optical path toward the particulate filter without aerodynamically entraining fine powder bed particles.

---

## SOP-03: Post-Build Thermal Processing: Stress Relief (SR) & Hot Isostatic Pressing (HIP)

### 3.1 Scope & Objective
To relieve high tensile residual stresses induced by steep thermal gradients and to eliminate internal lack-of-fusion and gas porosity, restoring fatigue endurance and ductility in accordance with ASTM F3055 and ASTM F2924.

### 3.2 SOP-03A: Thermal Stress Relief Annealing (SR)

> **CRITICAL RULE**: Parts and sacrificial support structures **MUST NOT** be cut from the build plate (via wire EDM or saw) prior to stress relief annealing. Cutting un-relieved parts releases trapped residual stresses ($> 800\text{ MPa}$), causing severe unrecoverable dimensional warping or instantaneous cracking.

#### Ti-6Al-4V Stress Relief Thermal Cycle
1. **Atmosphere**: Vacuum furnace ($< 10^{-4}\text{ mbar}$) or inert Argon atmosphere ($99.999\%$ purity) to prevent oxygen embrittlement (alpha-case formation).
2. **Heating Ramp**: $5^\circ\text{C} - 10^\circ\text{C / min}$ up to $650^\circ\text{C} \pm 10^\circ\text{C}$ ($1200^\circ\text{F} \pm 25^\circ\text{F}$).
3. **Isothermal Dwell**: Hold at $650^\circ\text{C}$ for $180 \pm 15\text{ minutes}$ ($3.0\text{ hours}$).
4. **Cooling**: Inert gas furnace cool to below $200^\circ\text{C}$ ($400^\circ\text{F}$) before chamber opening.
5. **Expected Outcome**: Relieves $\ge 85\%$ of peak residual stresses while preserving the high-strength fine acicular martensitic microstructure ($R_{p0.2} \ge 860\text{ MPa}$).

#### 316L Stainless Steel Stress Relief
1. Temperature: $450^\circ\text{C} - 550^\circ\text{C}$ for $120\text{ minutes}$ in protective Argon.
2. *Prohibition*: Do not heat between $600^\circ\text{C} - 850^\circ\text{C}$ to avoid chromium carbide ($Cr_{23}C_6$) sensitization and loss of corrosion resistance.

---

### 3.3 SOP-03B: Hot Isostatic Pressing (HIP) per ASTM F3055 / ASTM F2924

#### Objective
To apply simultaneous isostatic gas pressure and elevated temperature, activating creep and plastic yield mechanisms that collapse internal lack-of-fusion voids, gas pores, and microcracks, elevating relative density to $\ge 99.9\%$ and extending fatigue life.

#### Ti-6Al-4V Standard Aerospace HIP Cycle

```
Temperature (°C)
  1000 ─┐                         ┌───────────────────────┐ [920°C ± 10°C, 100 MPa Ar, 2h]
   800 ─┤                        /                         \
   600 ─┤                       /                           \
   400 ─┤      [5-10°C/min]    /                             \ Controlled Cooling
   200 ─┤  Ramp + Pressurize  /                               \ [<20°C/min to 300°C]
     0 ─┴────────────────────┴───────────────────────────────┴────────────────────►
       0                    90                              210                  Time (min)
```

1. **Vessel Preparation**: Clean parts via ultrasonic solvent bath; dry completely.
2. **Heating & Pressurization**:
   - Ramp temperature at $5^\circ\text{C} - 10^\circ\text{C / min}$ concurrently with Argon gas pressurization.
3. **HIP Dwell Setpoints**:
   - **Temperature**: $920^\circ\text{C} \pm 10^\circ\text{C}$ ($1688^\circ\text{F} \pm 25^\circ\text{F}$), safely below the $\beta$-transus temperature ($T_\beta \approx 995^\circ\text{C}$) to avoid excessive grain coarsening.
   - **Argon Pressure**: $100 \pm 5\text{ MPa}$ ($1000\text{ bar}$ / $14.5\text{ ksi}$).
   - **Soak Time**: $120 \pm 10\text{ minutes}$ ($2.0\text{ hours}$).
4. **Controlled Cooling**: Cool at rate $\le 20^\circ\text{C / min}$ under pressure down to $< 300^\circ\text{C}$ before depressurization.

#### Metallurgical Transformation & Microstructural Evolution
- **As-Built State**: Non-equilibrium acicular $\alpha'$ hexagonal martensite needles within prior-$\beta$ columnar grains. High yield strength ($> 1000\text{ MPa}$) but low ductility ($5 - 8\%$).
- **Post-HIP State**: Full decomposition of $\alpha'$ martensite into equilibrium lamellar $\alpha + \beta$ colonies (Widmanstätten / basketweave structure) with intergranular $\beta$ laths ($1.0 - 2.5\,\mu\text{m}$ thickness).
- **Mechanical Validation**:
  - Yield Strength ($R_{p0.2}$): $830 - 890\text{ MPa}$
  - Ultimate Tensile Strength (UTS): $900 - 980\text{ MPa}$
  - Plastic Tensile Elongation ($A$): $12\% - 16\%$ (exceeding ASTM F3055 $\ge 10\%$ threshold)
  - Relative Density: $\ge 99.92\%$ measured via ASTM B962 Archimedes method.
