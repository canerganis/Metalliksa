# Database & API Specification (`SCHEMA.md`)

This document defines the architectural data schemas, TypeScript interfaces, JSON Schema validation structures, REST/IPC API endpoints, and data serialization formats governing the **Metalliksa Additive Manufacturing & Metallurgy Intelligence Platform**.

> **Compliance Notice**: In accordance with Rule 4 in [`RULES.md`](../../RULES.md), qualification records enforce strict 5-tier referential integrity (`Build` $\rightarrow$ `ProcessParams` $\rightarrow$ `Sample` $\rightarrow$ `Properties` $\rightarrow$ `Source`). Research imports, synthetic UI fixtures, and user-supplied drafts may exist in separate evidence or demonstration paths, but they must remain explicitly labelled as unverified and must not be promoted to certified or measured records by schema validation alone.

---

## Table of Contents
1. [5-Tier Relational Architecture Overview](#1-5-tier-relational-architecture-overview)
2. [TypeScript Interface Specifications](#2-typescript-interface-specifications)
3. [JSON Schema (Draft 2020-12) Validation Definitions](#3-json-schema-draft-2020-12-validation-definitions)
4. [API Endpoints & Request/Response Contracts](#4-api-endpoints--requestresponse-contracts)
5. [Data Interchange & Export Formats](#5-data-interchange--export-formats)

---

## 1. 5-Tier Relational Architecture Overview

Every specimen, qualification dataset, and simulation run is organized across five hierarchical, foreign-key linked tiers:

```
┌────────────────────────────────────────────────────────┐
│  TIER 1: BUILD (Build Metadata, Machine, Powder Lot)   │
└──────────────────────────┬─────────────────────────────┘
                           │ 1:N
┌──────────────────────────▼─────────────────────────────┐
│  TIER 2: PROCESSPARAMS (Laser Power, Speed, Beam Spot) │
└──────────────────────────┬─────────────────────────────┘
                           │ 1:N
┌──────────────────────────▼─────────────────────────────┐
│  TIER 3: SAMPLE (Geometry, Spatial Coords, Orientation)│
└──────────────────────────┬─────────────────────────────┘
                           │ 1:1
┌──────────────────────────▼─────────────────────────────┐
│  TIER 4: PROPERTIES (Density, Tensile, Hardness, Voids)│
└──────────────────────────┬─────────────────────────────┘
                           │ N:1
┌──────────────────────────▼─────────────────────────────┐
│  TIER 5: SOURCE (DOI, Authors, Testing Standards, Lab) │
└────────────────────────────────────────────────────────┘
```

---

## 2. TypeScript Interface Specifications

These TypeScript interfaces are the single source of truth for frontend components (`src/types/lpbfDataFoundation.ts`) and backend microservices (`server.ts`, `routes/physics.ts`, `routes/characterization.ts`).

```typescript
export type LPBFAlloyId = "ti6al4v" | "ss316l" | "alsi10mg" | "in718";

export type ProcessRegime = 
  | "Lack of Fusion (LoF)"
  | "Stable Conduction"
  | "Keyhole Vaporization"
  | "Balling / Plateau-Rayleigh Instability";

export type ScanStrategy = 
  | "Meander (67° alternating rotation)"
  | "Stripe (5mm width, 90° rotation)"
  | "Island / Checkerboard (5x5mm)"
  | "Unidirectional Continuous"
  | "Bidirectional (0°/90°)";

export type HeatTreatmentCondition = 
  | "As-Built"
  | "Stress Relieved (SR)"
  | "Hot Isostatic Pressed (HIP)"
  | "Solution Treated & Aged (STA)"
  | "Annealed";

export type DensityMethod = 
  | "Archimedes (ASTM B962)"
  | "Optical Microscopy Image Analysis (ASTM E1245)"
  | "X-ray Micro-Computed Tomography (Micro-CT)";

// ==========================================
// TIER 1: BUILD LEVEL
// ==========================================
export interface LPBFBuild {
  id: string;                          // Primary Key: e.g., "bld-2026-ti64-01"
  buildJobName: string;
  alloyId: LPBFAlloyId;
  alloyName: string;
  machineModel: string;                // e.g. "EOS M290", "SLM Solutions 280HL"
  powderLotNumber: string;
  powderAtomization: "Gas Atomized (GA)" | "Plasma Atomized (PA)" | "PREP";
  powderD10_um: number;
  powderD50_um: number;                // Median diameter [µm]
  powderD90_um: number;
  buildDate: string;                   // ISO-8601 date string
  facility: string;
  notes?: string;
}

// ==========================================
// TIER 2: PROCESS PARAMETERS LEVEL
// ==========================================
export interface LPBFProcessParams {
  id: string;                          // Primary Key: e.g., "prm-ti64-v1200"
  buildId: string;                     // Foreign Key -> LPBFBuild.id
  laserPower_W: number;                // P [W] (e.g. 200)
  scanSpeed_mm_s: number;              // v [mm/s] (e.g. 900)
  hatchSpacing_um: number;             // h [µm] (e.g. 100)
  layerThickness_um: number;           // t [µm] (e.g. 30)
  beamSpotDiameter_um: number;         // d_spot (1/e²) [µm] (e.g. 80)
  scanStrategy: ScanStrategy;
  baseplatePreheat_C: number;          // T_0 [°C] (e.g. 150)
  chamberAtmosphere: string;           // e.g. "Argon 99.999% (<50 ppm O2)"
  opticalAbsorptivity: number;         // η [-] (0.30 - 0.70)
  
  // Derived Physical Metrics
  derived: {
    linearEnergyDensity_J_mm: number;      // E_L = P / v [J/mm]
    arealEnergyDensity_J_mm2: number;      // E_A = P / (v · h) [J/mm²]
    volumetricEnergyDensity_J_mm3: number; // E_V = P / (v · h · t) [J/mm³]
    peakLaserIntensity_MW_cm2: number;     // I_0 = 4P / (π · d²) [MW/cm²]
    normalizedEnthalpy_dH_hs: number;      // ΔH / h_s (King et al.)
    pecletNumber: number;                  // Pe = v · d / (2α)
    predictedRegime: ProcessRegime;
  };
}

// ==========================================
// TIER 3: SAMPLE SPECIMEN LEVEL
// ==========================================
export interface LPBFSample {
  id: string;                          // Primary Key: e.g., "smp-ti64-s01"
  processParamsId: string;             // Foreign Key -> LPBFProcessParams.id
  sampleCode: string;                  // Unique tracking tag
  locationOnPlate: {
    x_mm: number;
    y_mm: number;
    z_mm: number;
  };
  buildOrientationDeg: 0 | 45 | 90;    // Angle relative to substrate (0° = Horizontal)
  heatTreatment: HeatTreatmentCondition;
  specimenGeometry: 
    | "Cylindrical Tensile (ASTM E8)"
    | "Flat Dogbone"
    | "Cubic Density (10x10x10mm)"
    | "Charpy Impact"
    | "Metallographic Coupon";
}

// ==========================================
// TIER 4: MEASURED PROPERTIES LEVEL
// ==========================================
export interface LPBFMeasuredProperties {
  id: string;                          // Primary Key: e.g., "prp-ti64-s01"
  sampleId: string;                    // Foreign Key -> LPBFSample.id (1:1)
  relativeDensity_pct: number;         // e.g. 99.85 %
  porosity_pct: number;                // e.g. 0.15 %
  densityMeasurementMethod: DensityMethod;
  yieldStrength_MPa?: number;          // R_p0.2 [MPa]
  ultimateTensileStrength_MPa?: number;// R_m / UTS [MPa]
  elongationAtBreak_pct?: number;      // A [%]
  reductionOfArea_pct?: number;        // Z [%]
  hardness_value?: number;             // e.g. 345
  hardness_scale?: "HV0.3" | "HV0.5" | "HV1" | "HRC";
  youngsModulus_GPa?: number;
  defectMorphology?: 
    | "Dense (<0.1% pores)"
    | "Lack of Fusion (irregular, un-melted powder)"
    | "Keyhole Pores (spherical, root of melt pool)"
    | "Gas Porosity / Balling";
  microstructureDescription?: string;
}

// ==========================================
// TIER 5: SOURCE & CITATION LEVEL
// ==========================================
export interface SourceCitation {
  id: string;                          // Primary Key: e.g., "src-thijs-2010"
  sourceType: "literature" | "experimental" | "internal_qualification";
  citation: string;
  title: string;
  authors: string;
  journal: string;
  year: number;
  doi: string;                         // Fully resolvable DOI (e.g. "10.1016/j.actamat.2010.02.045")
  url?: string;
  testingStandards: string[];          // e.g. ["ASTM F3055", "ASTM B962", "ASTM E8/E8M"]
  labOrganization: string;
}

// ==========================================
// UNIFIED 5-TIER TRACEABLE AGGREGATE
// ==========================================
export interface TraceableLPBFRecord {
  id: string;
  build: LPBFBuild;
  params: LPBFProcessParams;
  sample: LPBFSample;
  properties: LPBFMeasuredProperties;
  source: SourceCitation;
}
```

---

## 3. JSON Schema (Draft 2020-12) Validation Definitions

The JSON Schema specification validates incoming experimental batches, API inputs, and automated ingests:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://metallix.ai/schemas/lpbf-traceable-record.json",
  "title": "TraceableLPBFRecord",
  "type": "object",
  "required": ["id", "build", "params", "sample", "properties", "source"],
  "properties": {
    "id": { "type": "string" },
    "build": {
      "type": "object",
      "required": ["id", "buildJobName", "alloyId", "machineModel", "powderLotNumber", "powderD50_um"],
      "properties": {
        "id": { "type": "string" },
        "buildJobName": { "type": "string" },
        "alloyId": { "enum": ["ti6al4v", "ss316l", "alsi10mg", "in718"] },
        "powderD10_um": { "type": "number", "minimum": 5 },
        "powderD50_um": { "type": "number", "minimum": 15, "maximum": 60 },
        "powderD90_um": { "type": "number", "maximum": 100 }
      }
    },
    "params": {
      "type": "object",
      "required": ["laserPower_W", "scanSpeed_mm_s", "hatchSpacing_um", "layerThickness_um", "beamSpotDiameter_um"],
      "properties": {
        "laserPower_W": { "type": "number", "minimum": 20, "maximum": 2000 },
        "scanSpeed_mm_s": { "type": "number", "minimum": 50, "maximum": 5000 },
        "hatchSpacing_um": { "type": "number", "minimum": 20, "maximum": 500 },
        "layerThickness_um": { "type": "number", "minimum": 15, "maximum": 200 },
        "beamSpotDiameter_um": { "type": "number", "minimum": 20, "maximum": 300 }
      }
    },
    "sample": {
      "type": "object",
      "required": ["sampleCode", "buildOrientationDeg", "heatTreatment"],
      "properties": {
        "buildOrientationDeg": { "enum": [0, 45, 90] },
        "heatTreatment": { "type": "string" }
      }
    },
    "properties": {
      "type": "object",
      "required": ["relativeDensity_pct", "densityMeasurementMethod"],
      "properties": {
        "relativeDensity_pct": { "type": "number", "minimum": 80, "maximum": 100.0 }
      }
    },
    "source": {
      "type": "object",
      "required": ["doi", "testingStandards"],
      "properties": {
        "doi": { "type": "string", "pattern": "^10\\.\\d{4,9}/[-._;()/:A-Za-z0-9]+$" }
      }
    }
  }
}
```

---

## 4. API Endpoints & Request/Response Contracts

The platform exposes dedicated REST API routes (`server.ts` and `/routes/*`):

### 4.1 Rosenthal 3D Thermal Field
- **Endpoint**: `POST /api/physics/rosenthal`
- **Request Body**:
```json
{
  "alloyId": "ti6al4v",
  "laserPower_W": 200,
  "scanSpeed_mm_s": 900,
  "baseplatePreheat_C": 150,
  "absorptivity": 0.42,
  "gridExtent": {
    "xRange_um": [-500, 300],
    "yRange_um": [-200, 200],
    "zRange_um": [-250, 0],
    "step_um": 10
  }
}
```
- **Response Body**:
```json
{
  "status": "success",
  "meltPoolDimensions": {
    "length_um": 348.5,
    "width_um": 126.2,
    "depth_um": 63.1,
    "aspectRatio_L_W": 2.76,
    "isBallingInstability": false
  },
  "maxCoolingRate_K_s": 1.45e6,
  "temperatureMatrixSummary": {
    "peakTemp_C": 2840,
    "liquidusIsothermPointsCount": 1420
  }
}
```

### 4.2 Material Record Registration & Ingest
- **Endpoint**: `POST /api/materials/specimens`
- **Request Body**: Accepts a `TraceableLPBFRecord` object.
- **Response**: Returns HTTP 201 with a verified UUID and schema-valid physics metrics. Schema validity is not experimental validation, calibration, standards compliance, or production qualification.

---

## 5. Data Interchange & Export Formats

### 5.1 Flat CSV Format Specification
For integration with statistical analysis suites (Python pandas, R, JMP), the platform exports 5-tier records into a single denormalized CSV table with prefixed columns:
- `build_id`, `build_job_name`, `build_alloy`, `build_machine`, `build_powder_lot`, `build_powder_d50`
- `param_power_w`, `param_speed_mms`, `param_hatch_um`, `param_layer_um`, `param_spot_um`, `param_ved_jmm3`, `param_intensity_mwcm2`, `param_regime`
- `sample_code`, `sample_orientation_deg`, `sample_heat_treatment`, `sample_geometry`
- `prop_relative_density_pct`, `prop_density_method`, `prop_yield_mpa`, `prop_uts_mpa`, `prop_elongation_pct`, `prop_hardness_hv`
- `src_doi`, `src_authors`, `src_journal`, `src_year`, `src_standards`

### 5.2 NIST Additive Manufacturing Materials Database (AMMD) Compatibility
The JSON structure maps directly to the XML/JSON schema schemas endorsed by the NIST AMMD project and ISO/ASTM 52900, ensuring seamless long-term archival across aerospace qualification repositories.
