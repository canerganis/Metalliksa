/** Original property evidence; source archiving never admits a constitutive law. */
import { createHash } from 'node:crypto';
import { lstatSync, readFileSync } from 'node:fs';
import path from 'node:path';
import type { LpbfSourceDocument } from '../src/types/lpbfSource';
import type { LpbfSourceCatalogEntry } from './lpbfSourceCatalog';
import { artifactDirectory } from './lpbfArtifactStore';
import { validateSourceDocument } from './lpbfSourceRepository';

const sourceRoot = () => path.resolve('docs/sources/in625');
type Artifact = LpbfSourceDocument['artifacts'][number];
const gtArtifacts: Artifact[] = [
  { relativePath: 'georgia-tech-inconel625.xlsx', byteSize: 11127,
    sha256: 'aa4821bf2845333af590e9b384c781c46df18529e718a66adad65155a4df8b60',
    sourceUrl: 'https://gen3csp.gatech.edu/wp-content/uploads/2020/10/Inconel625.xlsx' },
  { relativePath: 'georgia-tech-inconel625-page.html', byteSize: 76255,
    sha256: '7182d05b63e8b8b47252af42c099c49c3b66df539c4beca7cc3d6bbcb0ef28b8',
    sourceUrl: 'https://gen3csp.gatech.edu/inconel-alloy-625/' },
  { relativePath: 'georgia-tech-uncertainty.html', byteSize: 109839,
    sha256: '13526bee6fc1d99c92a895b759a325957b4e9eb7325ead9bf8f8b3b855b9d911',
    sourceUrl: 'https://gen3csp.gatech.edu/uncertainty/' },
];
const nasaArtifacts: Artifact[] = [
  { relativePath: 'nasa-20240007954-inconel-properties.pptx', byteSize: 18301541,
    sha256: 'fe5ef34928d67f9967dfa06bc0f55439560a1ed81f0d9ddbc08cfc835a589bcb',
    sourceUrl: 'https://ntrs.nasa.gov/api/citations/20240007954/downloads/Inconel%20Thermophysical%20Properties%20Study_FINAL.pptx' },
  { relativePath: 'nasa-20240007954-metadata.json', byteSize: 5528,
    sha256: 'f2395f58c1d300719b2f42c93702396298eea57d3b49c0612c2a74a5fef01301',
    sourceUrl: 'https://ntrs.nasa.gov/api/citations/20240007954' },
];

function entry(root: string, datasetId: string, title: string, citation: string,
  url: string, artifacts: Artifact[], details: NonNullable<LpbfSourceDocument['sourceContext']>): LpbfSourceCatalogEntry {
  return { datasetId, title, sourceRoot: root, loadDocument() {
    artifactDirectory(root);
    for (const artifact of artifacts) {
      const filename = path.join(root, artifact.relativePath);
      const stat = lstatSync(filename);
      if (!stat.isFile() || stat.isSymbolicLink() || stat.size !== artifact.byteSize) throw new Error('Property source artifact size or file identity mismatch');
      if (createHash('sha256').update(readFileSync(filename)).digest('hex') !== artifact.sha256) throw new Error('Property source artifact hash mismatch');
    }
    return validateSourceDocument({ schemaVersion: 1, datasetId, materialId: 'in625', processScope: 'material-characterization',
      source: { url, citation, version: 'local-source-archive-2026-09-27-v1', terms: null,
        termsMissingReason: 'Public access was verified; reuse terms for all archived content have not been established.' },
      artifacts,
      sourceContext: { ...details, publisher_artifact_kind: 'primary-thermophysical-property-data',
        admission_status: 'unverified-candidate', model_admission: false,
        experimental_validation: 'unvalidated', melt_pool_comparison_eligible: false,
        runtime_source_validity_range_K: null,
        source_context_origin: 'Local inspection of exact original publisher artifacts; not a new measurement or admitted material law.' } });
  } };
}

export function in625GeorgiaTechPropertyCatalogEntry(root = sourceRoot()): LpbfSourceCatalogEntry {
  return entry(root, 'in625-georgia-tech-thermophysical-v1', 'IN625 Georgia Tech thermophysical measurements — unverified candidate',
    'Georgia Tech, Thermophysical Properties Database of Gen3 CSP Materials: Inconel 625 workbook and uncertainty methodology.',
    'https://gen3csp.gatech.edu/inconel-alloy-625/', gtArtifacts, {
      specimen: { description: 'Bulk IN625 specimens; chemistry, lot and heat treatment not established.', lot: null, chemistry: null, heat_treatment: null },
      measurement: { method: 'NETZSCH LFA 467 HT diffusivity and STA 449 F3 specific heat; argon purge/protective gas.',
        repeat_group_rule: 'Source page states a minimum of three measurements per point.' },
      retrieval_utc: '2026-09-27T12:42:27.506976+00:00',
      property_measurements: [
        { property: 'Specific heat', evidence_type: 'Measurement-derived mean; Cp interpolated to diffusivity coordinates', unit: 'J/g-K',
          temperature_range_K: [533.15, 1273.15], source_locator: 'Sheet1!D2:E21; temperature A2:A21',
          uncertainty: 'Reported 95% confidence uncertainty in column E; 20 temperature points.' },
        { property: 'Thermal diffusivity', evidence_type: 'Measurement mean', unit: 'mm²/s',
          temperature_range_K: [533.15, 1273.15], source_locator: 'Sheet1!F2:G21; temperature A2:A21',
          uncertainty: 'Reported 95% confidence uncertainty in column G.' },
        { property: 'Thermal conductivity', evidence_type: 'Derived from diffusivity, Cp and assumed constant density 8440 kg/m³', unit: 'W/m-K',
          temperature_range_K: [533.15, 1273.15], source_locator: 'Sheet1!B2:C21; temperature A2:A21',
          uncertainty: 'Reported 95% confidence uncertainty in column C; density uncertainty is assumed negligible by the source method.' },
      ],
      unresolved: ['Specimen lot, composition and heat treatment are not established; transfer to an LPBF material is unqualified.',
        'Solid-state temperature coverage does not provide liquid, optical, powder-bed, flow or vapor data.',
        'Source byte integrity and property measurements do not establish melt-pool validation or full-transient/build-job admission.'],
    });
}

export function in625NasaPropertyCatalogEntry(root = sourceRoot()): LpbfSourceCatalogEntry {
  return entry(root, 'in625-nasa-esl-20240007954-v1', 'IN625 NASA levitation property presentation — unverified candidate',
    'Phillips et al., Thermophysical Property Measurements and Comparison of Inconel 625 and 718 From Competing Vendor Formulations Using Electrostatic Levitation, 22nd Symposium on Thermophysical Properties, 2024. NASA NTRS 20240007954.',
    'https://ntrs.nasa.gov/citations/20240007954', nasaArtifacts, {
      specimen: { description: 'IN625 subset of a multi-alloy presentation; ESPI and Böhler formulations are distinct.',
        lot: 'ESPI IN625 DK 15344B; Böhler lot not established', chemistry: 'Composition table on slide 4; composition basis not established.', heat_treatment: null },
      measurement: { method: 'Electrostatic levitation; plots and fitted relations in a primary conference presentation.', repeat_group_rule: null },
      retrieval_utc: '2026-09-27T12:42:32.479142+00:00',
      property_measurements: [
        { property: 'Liquid density', evidence_type: 'Measurement plots and linear fits; includes undercooled points', unit: 'kg/m³',
          temperature_range_K: null, source_locator: 'Slide 6',
          uncertainty: 'Plus/minus fit coefficient entries; confidence level, covariance and complete budget not established.' },
        { property: 'Surface tension', evidence_type: 'Measurement plots and linear fits', unit: 'N/m',
          temperature_range_K: null, source_locator: 'Slide 7',
          uncertainty: 'Plus/minus fit coefficient entries; confidence level, covariance and complete budget not established.' },
        { property: 'Viscosity', evidence_type: 'Measurement plots and fit coefficients; equation conventions unresolved', unit: 'mPa·s',
          temperature_range_K: null, source_locator: 'Slide 8', uncertainty: 'Fit uncertainty not established.' },
      ],
      unresolved: ['Exact numeric measurement series and temperature endpoints are not tabulated; plot axes are not accepted validity bounds.',
        'Displayed viscosity equation and coefficient units have not been reconciled with plotted values; no constitutive law is admitted.',
        'Confidence/coverage factors, covariance, actual specimen atmosphere/pressure and target-lot equivalence remain unresolved.',
        'The presentation also contains IN718 data. No automatic transfer to either runtime material authority is performed.',
        'Full-transient/build-job admission and independent experimental validation remain unestablished.'],
    });
}
