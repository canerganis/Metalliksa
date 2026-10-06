import { createHash } from 'node:crypto';
import { lstatSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { artifactDirectory } from './lpbfArtifactStore';
import { validateSourceDocument } from './lpbfSourceRepository';

/** Trusted server configuration, never supplied by an HTTP request. */
export interface LpbfSourceCatalogEntry {
  datasetId: string;
  title: string;
  sourceRoot: string;
  loadDocument: () => unknown;
}

function readJson(root: string, name: string) {
  const filename = path.join(artifactDirectory(root), name);
  const stat = lstatSync(filename);
  if (stat.isSymbolicLink() || !stat.isFile() || stat.size > 1024 * 1024) throw new Error('Invalid source metadata file');
  return JSON.parse(readFileSync(filename, 'utf8'));
}

/** Adapter for this specific reviewed README/manifest layout, not a generic
 * measurement importer. Unknown units and unreviewed HDF5 claims stay unchanged.
 */
export function nistIn718CatalogEntry(root = path.resolve('data/benchmark/nist-amb2022-03')): LpbfSourceCatalogEntry {
  return { datasetId: 'nist-mds2-2716', title: 'NIST AM Bench 2022 · IN718 bare plate', sourceRoot: root,
    loadDocument() {
      const manifest = readJson(root, 'manifest.json');
      const context = readJson(root, 'source-context.json');
      if (manifest.schema_version !== 1 || context.schema_version !== 1 || manifest.dataset_id !== 'nist-mds2-2716'
        || context.dataset_id !== manifest.dataset_id || context.source_version !== manifest.version
        || manifest.material !== 'IN718' || context.experiment?.material !== 'IN718'
        || manifest.process_scope !== 'bare-plate' || context.experiment?.process_scope !== 'bare-plate'
        || !Array.isArray(manifest.files)) throw new Error('Source manifest/context identity mismatch');
      const readme = manifest.files.find((item: any) => item.path === context.readme?.path);
      if (!readme || readme.sha256 !== context.readme.sha256 || readme.source_url !== context.readme.source_url) throw new Error('README context fingerprint mismatch');
      if (context.hdf5_review !== undefined) {
        const sources = manifest.files.filter((file: any) => file.kind !== 'readme');
        const reviewed = context.hdf5_review?.artifacts;
        if (!Array.isArray(reviewed) || reviewed.length !== sources.length || sources.some((file: any) =>
          reviewed.filter((ref: any) => ref?.path === file.path && ref.sha256 === file.sha256 && ref.source_url === file.source_url).length !== 1)) {
          throw new Error('HDF5 review fingerprint mismatch');
        }
      }
      return validateSourceDocument({ schemaVersion: 1, datasetId: manifest.dataset_id, materialId: 'in718', processScope: 'bare-plate',
        source: { url: 'https://doi.org/10.18434/mds2-2716', citation: manifest.citation, version: manifest.version,
          terms: context.source_terms?.summary, termsMissingReason: null },
        artifacts: manifest.files.map((file: any) => ({ relativePath: file.path, sha256: file.sha256, byteSize: file.bytes, sourceUrl: file.source_url })),
        sourceContext: context });
    } };
}

export function cmuTi64CatalogEntry(root = path.resolve('data/benchmark/cmu-ti64-meltpool-v1')): LpbfSourceCatalogEntry {
  return { datasetId: 'cmu-ti64-meltpool-v1', title: 'CMU Single/Multi-track Meltpool Dimensions', sourceRoot: root,
    loadDocument() {
      const manifest = readJson(root, 'manifest.json');
      if (manifest.schema_version !== 1 || manifest.dataset_id !== 'cmu-ti64-meltpool-v1' || manifest.material !== 'Ti-6Al-4V' || !Array.isArray(manifest.files)) {
        throw new Error('Source manifest identity mismatch');
      }
      return validateSourceDocument({ schemaVersion: 1, datasetId: manifest.dataset_id, materialId: 'ti6al4v', processScope: 'bare-plate',
        source: { url: manifest.doi ? `https://doi.org/${manifest.doi}` : '', citation: manifest.attribution, version: '1',
          terms: null, termsMissingReason: 'Public benchmark' },
        artifacts: manifest.files.map((file: any) => ({ relativePath: file.path, sha256: file.sha256, byteSize: file.bytes, sourceUrl: file.source_url })),
        sourceContext: { schema_version: 1, dataset_id: manifest.dataset_id, source_version: '1' } });
    } };
}

/** A locally transcribed Table 4 aggregate, kept separate from NIST's raw HDF5 catalog. */
export function nistOpticalTable4CatalogEntry(root = path.resolve('data/benchmark/nist-amb2022-03-optical')): LpbfSourceCatalogEntry {
  const datasetId = 'nist-amb2022-03-optical-table4-local-v1';
  const artifactSha256 = 'd1b36dfa2e01a3537093c481e249ce52df6b8879c1c67480ddb9aa10799133da';
  const artifactBytes = 4321;
  const resultsUrl = 'https://www.nist.gov/document/am-bench-amb2022-03-measurement-and-result-descriptions-v10';
  const methodsUrl = 'https://www.nist.gov/document/amb2022-03-measurement-and-challenge-descriptions-version-101';
  return { datasetId, title: 'NIST AMB2022-03 Table 4 · local aggregate transcription', sourceRoot: root,
    loadDocument() {
      const manifest = readJson(root, 'manifest.json');
      const file = manifest.files?.[0];
      if (manifest.schema_version !== 1 || manifest.dataset_id !== datasetId || manifest.version !== '1.1.0'
        || manifest.material !== 'IN718' || manifest.process_scope !== 'bare-plate'
        || manifest.artifact_kind !== 'local-transcription-of-published-aggregate-measurements'
        || !Array.isArray(manifest.files) || manifest.files.length !== 1
        || file?.path !== 'table4-aggregate-v2.json' || file.source_url !== resultsUrl
        || file.bytes !== artifactBytes || file.sha256 !== artifactSha256) {
        throw new Error('Optical transcription manifest identity mismatch');
      }
      const filename = path.join(artifactDirectory(root), file.path);
      const stat = lstatSync(filename);
      if (stat.isSymbolicLink() || !stat.isFile() || stat.size !== file.bytes || stat.size > 1024 * 1024) {
        throw new Error('Optical transcription artifact size mismatch');
      }
      const bytes = readFileSync(filename);
      if (createHash('sha256').update(bytes).digest('hex') !== file.sha256) {
        throw new Error('Optical transcription artifact hash mismatch');
      }
      const data = JSON.parse(bytes.toString('utf8'));
      const experiment = data.experiment;
      if (data.schemaVersion !== 1 || data.kind !== manifest.artifact_kind
        || data.transcriptionVersion !== manifest.version || data.material !== 'IN718'
        || data.benchmark !== 'AMB2022-03' || data.doi !== '10.18434/mds2-2718'
        || data.publishedResults !== resultsUrl || data.publishedMethods !== methodsUrl
        || data.measurement?.countPerCondition !== 6 || data.measurement?.unit !== 'um'
        || experiment?.processScope !== 'bare-plate' || experiment?.sample !== 'AMB2022-718-SH1-BP1'
        || experiment?.beamDiameterDefinition !== 'D4sigma' || experiment?.scanDirection !== '+X'
        || experiment?.trackLength_mm !== 10 || experiment?.powderLayerThickness_um !== null
        || experiment?.hatchSpacing_um !== null
        || experiment?.heatTreatment !== 'Residual-stress annealed in vacuum at 800 °C for 2 h before laser processing.'
        || experiment?.heatTreatmentEvidence?.sourceUrl !== methodsUrl
        || experiment?.heatTreatmentEvidence?.location !== 'Version 1.01, Section 2.1 (Plate preparation), PDF page 2'
        || experiment?.heatTreatmentMissingReason !== null
        || data.supersedes?.transcriptionVersion !== '1.0.0'
        || data.supersedes?.artifactPath !== 'table4-aggregate-v1.json'
        || data.supersedes?.artifactSha256 !== 'dcefd9c8c998e516eb81769cbe7b13014dfcb1c38e69c838a62475e79beac518'
        || !Array.isArray(data.cases) || data.cases.length !== 7
        || new Set(data.cases.map((item: any) => item.caseNumber)).size !== 7
        || data.cases.some((item: any) => typeof item.caseNumber !== 'string'
          || item.sampleId !== `AMB2022-718-SH1-BP1-L${item.caseNumber}`
          || ['laserPower_W', 'scanSpeed_mm_s', 'beamDiameterD4sigma_um', 'depthMean_um',
            'depthStdDev_um', 'widthMean_um', 'widthStdDev_um'].some(key =>
            typeof item[key] !== 'number' || !Number.isFinite(item[key]) || item[key] <= 0))) {
        throw new Error('Optical transcription content identity mismatch');
      }
      return validateSourceDocument({ schemaVersion: 1, datasetId, materialId: 'in718', processScope: 'bare-plate',
        source: { url: 'https://doi.org/10.18434/mds2-2718', citation: manifest.citation,
          version: manifest.version, terms: null,
          termsMissingReason: 'Reuse terms for this local transcription were not established from the cited NIST result and method PDFs.' },
        artifacts: [{ relativePath: file.path, sha256: file.sha256, byteSize: file.bytes, sourceUrl: resultsUrl }],
        sourceContext: { schema_version: 1, dataset_id: datasetId, source_version: manifest.version,
          transcription: { kind: data.kind, publisher_raw_data: false, publisher_pdf: false,
            note: data.transcriptionNote, published_results_location: data.publishedResultsLocation,
            checksum_authority: manifest.checksum_authority, results_url: resultsUrl, methods_url: methodsUrl },
          experiment: { machine: experiment.machine, process_scope: experiment.processScope,
            sample: experiment.sample, scan_direction: experiment.scanDirection,
            track_length_mm: experiment.trackLength_mm, substrate_and_chamber_temperature_C: experiment.substrateAndChamberTemperature_C,
            substrate_and_chamber_temperature_uncertainty_C: experiment.substrateAndChamberTemperatureUncertainty_C,
            powder_layer_thickness_um: null, hatch_spacing_um: null,
            heat_treatment: experiment.heatTreatment,
            heat_treatment_evidence: experiment.heatTreatmentEvidence,
            heat_treatment_missing_reason: experiment.heatTreatmentMissingReason },
          measurement: { quantity: data.measurement.quantity, method: data.measurement.method,
            unit_source: data.measurement.unit, temperature_conversion: null,
            temperature_conversion_missing_reason: 'Not applicable to optical cross-section geometry.',
            beam_diameter_definition: experiment.beamDiameterDefinition,
            repeat_group_rule: 'Six cross-sections per condition; only Table 4 aggregate means and standard deviations are archived.',
            uncertainty: data.measurement.uncertainty },
          split: 'unassigned', unresolved: ['Individual cross-section measurements and source images are not in this local transcription.',
            'Published standard deviation is not an experimental validation claim for this model.'] } });
    } };
}

/** NIST publisher workbook is a separate source from the local Table 4 transcription. */
export function nistOpticalOfficialWorkbookCatalogEntry(root = path.resolve('data/benchmark/nist-amb2022-03-optical/official')): LpbfSourceCatalogEntry {
  const datasetId = 'nist-amb2022-03-optical-xlsx-official-v1';
  const name = 'AMB2022-718-SH1-MeltPool_Cross-Section_Measurement_Results.xlsx';
  const sourceUrl = `https://data.nist.gov/od/ds/ark:/88434/mds2-2718/${name}`;
  const workbookSha = '2cfaac96aaca3dabb77b7029f842cdcc7e75c5a2cf3577d0734823246364a931';
  const sidecarSha = '770c0826e53e42c242110e69c032f2cbc74f6183048c43a530c5b62e746ae09b';
  return { datasetId, title: 'NIST AMB2022-03 optical sections · official workbook', sourceRoot: root,
    loadDocument() {
      const manifest = readJson(root, 'manifest.json');
      const files = manifest.files;
      if (manifest.schema_version !== 1 || manifest.dataset_id !== datasetId || manifest.version !== '1.0.0'
        || manifest.material !== 'IN718' || manifest.process_scope !== 'bare-plate'
        || manifest.artifact_kind !== 'publisher-optical-cross-section-measurements'
        || manifest.checksum_authority !== 'NIST-published SHA-256 sidecar for the publisher XLSX'
        || !Array.isArray(files) || files.length !== 2
        || files[0]?.path !== name || files[0]?.source_url !== sourceUrl
        || files[0]?.bytes !== 25811 || files[0]?.sha256 !== workbookSha
        || files[1]?.path !== `${name}.sha256` || files[1]?.source_url !== `${sourceUrl}.sha256`
        || files[1]?.bytes !== 64 || files[1]?.sha256 !== sidecarSha) {
        throw new Error('Official optical workbook manifest identity mismatch');
      }
      for (const file of files) {
        const filename = path.join(artifactDirectory(root), file.path);
        const stat = lstatSync(filename);
        if (stat.isSymbolicLink() || !stat.isFile() || stat.size !== file.bytes) {
          throw new Error('Official optical workbook artifact size mismatch');
        }
        if (createHash('sha256').update(readFileSync(filename)).digest('hex') !== file.sha256) {
          throw new Error('Official optical workbook artifact hash mismatch');
        }
      }
      if (readFileSync(path.join(root, `${name}.sha256`), 'utf8').trim() !== workbookSha) {
        throw new Error('Official optical workbook publisher checksum mismatch');
      }
      return validateSourceDocument({ schemaVersion: 1, datasetId, materialId: 'in718', processScope: 'bare-plate',
        source: { url: 'https://doi.org/10.18434/mds2-2718', citation: manifest.citation,
          version: manifest.version, terms: null,
          termsMissingReason: 'Reuse terms for this workbook were not established from the cited NIST data page.' },
        artifacts: files.map((file: any) => ({ relativePath: file.path, sha256: file.sha256,
          byteSize: file.bytes, sourceUrl: file.source_url })),
        sourceContext: { schema_version: 1, dataset_id: datasetId, source_version: manifest.version,
          publisher_artifact_kind: manifest.artifact_kind, checksum_authority: manifest.checksum_authority,
          experiment: { process_scope: 'bare-plate', sample: 'AMB2022-718-SH1-BP1',
            track_length_mm: 10, section_positions_mm: [4.9, 6.0],
            heat_treatment_missing_reason: 'Not established in this workbook.' },
          measurement: { quantity: 'optical cross-section melt-pool width and depth', unit_source: 'um',
            beam_diameter_definition: 'D4sigma', repeat_group_rule: 'Three tracks × two sections at 4.9 and 6.0 mm per case; six measurements.',
            temperature_conversion: null,
            temperature_conversion_missing_reason: 'Not applicable to optical cross-section geometry.' },
          split: 'unassigned', unresolved: ['Optical section operator is not implemented by the model.',
            'Publisher workbook measurements do not establish model validation.'] } });
  } };
}

/** NIST supplemental IN718 bare-plate single-track data; cataloged as measured
 * data, but the published groups are outside this application's conduction-model window.
 */
export function nistSupplementalIn718CatalogEntry(root = path.resolve('data/benchmark/nist-mds2-2923-in718/official')): LpbfSourceCatalogEntry {
  const datasetId = 'nist-mds2-2923-in718-supplement-v1';
  const manifestSha256 = '7e7f380d5902dc04385941a4222c8356619d747861694ca6d2d7517daef95b44';
  return { datasetId, title: 'NIST supplemental IN718 bare-plate tracks · mds2-2923', sourceRoot: root,
    loadDocument() {
      const manifestPath = path.join(artifactDirectory(root), 'manifest.json');
      const manifestStat = lstatSync(manifestPath);
      if (manifestStat.isSymbolicLink() || !manifestStat.isFile() || manifestStat.size > 1024 * 1024) {
        throw new Error('Invalid NIST supplemental IN718 manifest file');
      }
      const manifestBytes = readFileSync(manifestPath);
      if (createHash('sha256').update(manifestBytes).digest('hex') !== manifestSha256) {
        throw new Error('NIST supplemental IN718 manifest SHA-256 mismatch');
      }
      const manifest = JSON.parse(manifestBytes.toString('utf8'));
      const files = manifest.files;
      if (manifest.schema_version !== 1 || manifest.dataset_id !== datasetId || manifest.version !== '1.0.0'
        || manifest.material !== 'IN718' || manifest.process_scope !== 'bare-plate'
        || manifest.artifact_kind !== 'publisher-workbook-and-readme'
        || !Array.isArray(files) || files.length !== 2 || !Array.isArray(manifest.measurements)
        || manifest.measurements.length !== 6) {
        throw new Error('NIST supplemental IN718 manifest identity mismatch');
      }
      const expectedFiles = [
        { path: '2923_README.txt', sourceUrl: 'https://data.nist.gov/od/ds/mds2-2923/2923_README.txt',
          bytes: 8372, sha256: '8b8fc00ce62915af3e0c91c138dc4d033c031d7758161fb9da0e8702fa621c39' },
        { path: 'Master_TrackList_Measurements.xlsx', sourceUrl: 'https://data.nist.gov/od/ds/mds2-2923/Master_TrackList_Measurements.xlsx',
          bytes: 59141, sha256: '6cd32669f5c84cdb9e90890ba40ddc5548c85b0dbb95cf038f2f6fc69da67a52' },
      ];
      for (const [index, expected] of expectedFiles.entries()) {
        const file = files[index];
        if (file?.path !== expected.path || file?.source_url !== expected.sourceUrl
          || file?.bytes !== expected.bytes || file?.sha256 !== expected.sha256) {
          throw new Error('NIST supplemental IN718 artifact identity mismatch');
        }
        const filename = path.join(artifactDirectory(root), expected.path);
        const stat = lstatSync(filename);
        if (stat.isSymbolicLink() || !stat.isFile() || stat.size !== expected.bytes
          || createHash('sha256').update(readFileSync(filename)).digest('hex') !== expected.sha256) {
          throw new Error('NIST supplemental IN718 artifact integrity mismatch');
        }
      }
      const observations = manifest.measurements.map((row: any) => ({
        part: row.machine,
        caseAndLine: `${row.laserPower_W} W · ${row.scanSpeed_mm_s} mm/s · D4σ ${row.beamDiameter_um} µm`,
        measuredWidth_um: row.meanWidth_um,
        widthUncertainty_k2_um: row.expandedWidthUncertainty_k2_um,
        measuredDepth_um: row.meanDepth_um,
        depthUncertainty_k2_um: row.expandedDepthUncertainty_k2_um,
        observationCount: row.observationCount,
        imagePath: 'Master_TrackList_Measurements.xlsx#Summary',
      }));
      return validateSourceDocument({ schemaVersion: 1, datasetId, materialId: 'in718', processScope: 'bare-plate',
        source: { url: 'https://doi.org/10.18434/mds2-2923', citation: manifest.citation,
          version: manifest.version, terms: 'NIST Open License: https://www.nist.gov/open/license', termsMissingReason: null },
        artifacts: files.map((file: any) => ({ relativePath: file.path, sha256: file.sha256,
          byteSize: file.bytes, sourceUrl: file.source_url })),
        sourceContext: { schema_version: 1, dataset_id: datasetId, source_version: manifest.version,
          publisher_artifact_kind: manifest.artifact_kind,
          checksum_authority: 'Locally computed SHA-256 of the bytes downloaded from the NIST publication URLs; no publisher sidecar is supplied for these two files.',
          experiment: { process_scope: 'bare-plate', material_scope: 'IN718 rows extracted from a multi-alloy NIST workbook',
            surface_condition: '320 grit where recorded', machine: 'EOS M290 and NIST AMMT',
            track_length_mm: null, track_length_missing_reason: 'Not established for every supplemental group in the archived workbook.',
            heat_treatment_missing_reason: 'Not established in the publisher workbook.' },
          measurement: { quantity: 'optical cross-section melt-pool width and depth', unit_source: 'µm',
            beam_diameter_definition: 'D4σ; estimated for EOS M290 and measured for AMMT',
            repeat_group_rule: 'Use the six publisher Summary groups and their stated measurement counts and expanded uncertainties; row count is not assumed to equal independent builds.' },
          observations, split: 'unassigned', unresolved: [
            'All six group means have depth-to-spot-radius ratios above 3.0 using the reported spot diameters, outside the conduction-model window; these measurements are not eligible for validation of the present surface-conduction model.',
            'The EOS M290 spot diameter is estimated; AMMT spot diameter is measured. The archived workbook does not include full beam-profile artifacts.',
            'The publisher data are measured bare-plate geometry, not powder-bed or thermal-history validation.',
          ] } });
    } };
}

/** Original NIST case 0 cross-sections and publisher checksum sidecars.
 * This is a separate experimental source revision; catalog discovery does not hash
 * the 125 MB image set. Preview/import stream-verify every artifact byte.
 */
export function nistOpticalCase0MicrographsCatalogEntry(root = path.resolve('data/benchmark/nist-amb2022-03-optical/official')): LpbfSourceCatalogEntry {
  const datasetId = 'nist-amb2022-03-optical-case0-micrographs-v1';
  const manifestPath = 'single-track-case0/manifest.json';
  const manifestSha = 'c33ff22d370f75754d89eb7e05721a0bb21e3192f5563a6213116d098ca65148';
  const baseUrl = 'https://data.nist.gov/od/ds/ark:/88434/mds2-2718/Single_Track_Cross_Sections/';
  return { datasetId, title: 'NIST AMB2022-03 · case 0 original optical micrographs', sourceRoot: root,
    loadDocument() {
      const filename = path.join(artifactDirectory(root), manifestPath);
      const stat = lstatSync(filename);
      if (stat.isSymbolicLink() || !stat.isFile() || stat.size > 1024 * 1024) throw new Error('Invalid case 0 micrograph manifest');
      const manifestBytes = readFileSync(filename);
      if (createHash('sha256').update(manifestBytes).digest('hex') !== manifestSha) {
        throw new Error('NIST case 0 micrograph manifest identity mismatch');
      }
      const manifest = JSON.parse(manifestBytes.toString('utf8'));
      const expectedNames = [1, 2, 3].flatMap(line => ['P3', 'P4'].map(part =>
        `AMB2022-718-SH1-BP1-${part}-L0-${line}.tif`));
      const files = manifest.files;
      const conditions = manifest.processConditions;
      if (manifest.schemaVersion !== 1 || manifest.datasetId !== datasetId || manifest.publisherVersion !== '1.0.0'
        || manifest.material !== 'IN718' || manifest.processScope !== 'bare-plate-single-track'
        || manifest.evidenceClass !== 'experimental-measurements-and-original-micrographs'
        || manifest.licenseUrl !== 'https://www.nist.gov/open/license'
        || manifest.measurementMethod?.pixelScale_um_per_pixel !== 0.069
        || !Array.isArray(files) || files.length !== expectedNames.length
        || !Array.isArray(manifest.measurements) || manifest.measurements.length !== expectedNames.length
        || conditions?.laserPower_W !== 285 || conditions?.scanSpeed_mm_s !== 960
        || conditions?.beamDiameterD4sigma_um !== 67) {
        throw new Error('NIST case 0 micrograph manifest identity mismatch');
      }
      const observations = new Map(manifest.measurements.map((row: any) => [row.imagePath, row]));
      const artifacts: { relativePath: string; sha256: string; byteSize: number; sourceUrl: string }[] = [];
      for (const [index, file] of files.entries()) {
        const expectedName = expectedNames[index];
        const relativePath = `single-track-case0/${expectedName}`;
        const imageUrl = `${baseUrl}${expectedName}`;
        if (file?.path !== relativePath || file?.sourceUrl !== imageUrl
          || file?.publisherSha256Sidecar !== `${relativePath}.sha256`
          || !Number.isSafeInteger(file.bytes) || file.bytes <= 0
          || typeof file.sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(file.sha256)) {
          throw new Error('NIST case 0 micrograph file identity mismatch');
        }
        const imageFilename = path.join(artifactDirectory(root), relativePath);
        const imageStat = lstatSync(imageFilename);
        if (imageStat.isSymbolicLink() || !imageStat.isFile() || imageStat.size !== file.bytes) {
          throw new Error('NIST case 0 micrograph size mismatch');
        }
        const sidecarPath = `${relativePath}.sha256`;
        const sidecarFilename = path.join(artifactDirectory(root), sidecarPath);
        const sidecarStat = lstatSync(sidecarFilename);
        if (sidecarStat.isSymbolicLink() || !sidecarStat.isFile() || sidecarStat.size !== 64) {
          throw new Error('NIST case 0 publisher checksum sidecar size mismatch');
        }
        const sidecar = readFileSync(sidecarFilename);
        if (sidecar.toString('ascii') !== file.sha256) throw new Error('NIST case 0 publisher checksum mismatch');
        const observation: any = observations.get(relativePath);
        const part = expectedName.includes('-P3-') ? 'P3' : 'P4';
        const position = part === 'P3' ? 4.9 : 6.0;
        if (!observation || observation.sample !== 'AMB2022-718-SH1-BP1' || observation.part !== part
          || observation.position_mm !== position || observation.imagePath !== relativePath
          || observation.laserPower_W !== conditions.laserPower_W || observation.scanSpeed_mm_s !== conditions.scanSpeed_mm_s
          || observation.beamDiameterD4sigma_um !== conditions.beamDiameterD4sigma_um
          || !Number.isFinite(observation.measuredWidth_um) || !Number.isFinite(observation.measuredDepth_um)) {
          throw new Error('NIST case 0 measurement-to-image mapping mismatch');
        }
        artifacts.push({ relativePath, sha256: file.sha256, byteSize: file.bytes, sourceUrl: imageUrl });
        artifacts.push({ relativePath: sidecarPath, sha256: createHash('sha256').update(sidecar).digest('hex'),
          byteSize: sidecar.length, sourceUrl: `${imageUrl}.sha256` });
      }
      if (observations.size !== expectedNames.length) throw new Error('NIST case 0 has duplicate or unexpected image measurements');
      return validateSourceDocument({ schemaVersion: 1, datasetId, materialId: 'in718', processScope: 'bare-plate',
        source: { url: 'https://doi.org/10.18434/mds2-2718', citation: manifest.citation,
          version: manifest.publisherVersion, terms: `NIST Open License: ${manifest.licenseUrl}`, termsMissingReason: null },
        artifacts,
        sourceContext: { schema_version: 1, dataset_id: datasetId, source_version: manifest.publisherVersion,
          publisher_artifact_kind: 'original-optical-cross-section-micrographs-and-publisher-checksums',
          checksum_authority: 'NIST-published SHA-256 sidecar for each TIFF; image hashes are rechecked at preview and import.',
          experiment: { process_scope: 'bare-plate', sample: 'AMB2022-718-SH1-BP1', machine: 'NIST AMMT', scan_direction: '+X',
            laser_power_W: 285, scan_speed_mm_s: 960, beam_diameter_D4sigma_um: 67,
            beam_diameter_definition: 'D4sigma', track_length_mm: 10, section_positions_mm: [4.9, 6.0],
            heat_treatment: null, heat_treatment_missing_reason: 'Not established by the case 0 micrograph manifest.' },
          measurement: { quantity: 'optical cross-section melt-pool width and depth', unit_source: 'um',
            pixel_scale_um_per_pixel: 0.069,
            published_observation_operator: 'ImageJ bounding rectangle; top of rectangle corresponds to specimen surface.',
            beam_diameter_definition: 'D4sigma', repeat_group_rule: 'Three tracks measured on each of two sections; six rows from one specimen.',
            temperature_conversion: null, temperature_conversion_missing_reason: 'Not applicable to optical cross-section geometry.' },
          observations: manifest.measurements, split: 'unassigned',
          unresolved: ['The six rows are three tracks on each of two sections from one specimen, not six independent builds.',
            'The workbook and original images derive from the same microscopy campaign and are not independent sources.',
            'The LPBF solver does not implement the published optical image observation operator.',
            'Bare-plate measurements do not establish powder-bed model validity.'] } });
    } };
}

/**
 * A local screening-input archive, not publisher raw data or an experimental
 * benchmark. The thermal JSON is emitted by in625_lpbf_thermal_snapshot(); a
 * separate fixed density assumption is pinned to the supplier bulletin.
 */
export function in625BareplateScreeningCatalogEntry(root = path.resolve('data/benchmark/in625-bareplate-screening')): LpbfSourceCatalogEntry {
  const datasetId = 'in625-bareplate-screening-local-v1';
  const thermalPath = 'in625-thermal-snapshot-v1.json';
  const densityPath = 'density-assumption-v1.json';
  const thermalUrl = 'https://doi.org/10.1007/s11663-020-01808-w';
  const densityUrl = 'https://www.specialmetals.com/documents/technical-bulletins/inconel/inconel-alloy-625.pdf';
  const thermalSha = 'a35ab7258eee08139fdfb4a7571f3f8fa5b8b9e9074fabca381becab4dda340d';
  const densitySha = '135cb88f6c0398dc4df05b5c9e238b86fc98827732f5d5c20ac7172a14cfbc9e';
  const readPinnedArtifact = (file: any, expected: { path: string; url: string; bytes: number; sha256: string }) => {
    if (file?.path !== expected.path || file?.source_url !== expected.url
      || file?.bytes !== expected.bytes || file?.sha256 !== expected.sha256) {
      throw new Error('IN625 screening manifest artifact identity mismatch');
    }
    const filename = path.join(artifactDirectory(root), expected.path);
    const stat = lstatSync(filename);
    if (stat.isSymbolicLink() || !stat.isFile() || stat.size !== expected.bytes || stat.size > 1024 * 1024) {
      throw new Error('IN625 screening artifact size mismatch');
    }
    const bytes = readFileSync(filename);
    if (createHash('sha256').update(bytes).digest('hex') !== expected.sha256) {
      throw new Error('IN625 screening artifact hash mismatch');
    }
    return JSON.parse(bytes.toString('utf8'));
  };
  return { datasetId, title: 'IN625 bare-plate screening inputs · local derived snapshot', sourceRoot: root,
    loadDocument() {
      const manifest = readJson(root, 'manifest.json');
      const context = readJson(root, 'source-context.json');
      const files = manifest.files;
      if (manifest.schema_version !== 1 || manifest.dataset_id !== datasetId || manifest.version !== '1.0.0'
        || manifest.material !== 'IN625' || manifest.process_scope !== 'bare-plate-screening-inputs'
        || manifest.artifact_kind !== 'derived-local-screening-input-snapshot'
        || manifest.evidence_status !== 'unreviewed-source-archive'
        || !Array.isArray(files) || files.length !== 2
        || context.schema_version !== 1 || context.dataset_id !== datasetId || context.source_version !== manifest.version
        || context.provenance_class !== 'derived-local-transcription-of-literature-model-and-separate-supplier-assumption'
        || context.evidence_status !== 'unreviewed-source-archive'
        || context.experiment?.material !== 'IN625' || context.experiment?.experimental_dataset !== false
        || context.experiment?.experimental_validation !== false) {
        throw new Error('IN625 screening manifest/context identity mismatch');
      }
      const thermal = readPinnedArtifact(files[0], { path: thermalPath, url: thermalUrl, bytes: 1353, sha256: thermalSha });
      const density = readPinnedArtifact(files[1], { path: densityPath, url: densityUrl, bytes: 549, sha256: densitySha });
      if (thermal.schemaVersion !== 1 || thermal.materialId !== 'in625'
        || thermal.capability !== 'bounded-fusion-enthalpy-screening'
        || thermal.validationStatus !== 'unvalidated-literature-model-screening'
        || thermal.provenanceClass !== 'literature-constitutive-model' || thermal.source !== thermalUrl
        || thermal.materialRevisionSha256 !== 'f47b07e4c8288b8c7177001f069a254be3410bace43ad5ea2f73168ac4466f07'
        || density.schemaVersion !== 1 || density.kind !== 'fixed-supplier-bulletin-density-assumption'
        || density.material !== 'IN625' || density.density_kg_m3 !== 8440 || density.density_g_cm3 !== 8.44
        || density.source !== densityUrl || density.sourceLocator !== 'Special Metals, INCONEL alloy 625 technical bulletin (2013), Table 2, page 2'
        || density.validationStatus !== 'unvalidated-source-archive'
        || context.thermal_model?.artifact_path !== thermalPath
        || context.thermal_model?.material_revision_sha256 !== thermal.materialRevisionSha256
        || context.thermal_model?.artifact_is_raw_publisher_data !== false
        || context.density_assumption?.artifact_path !== densityPath || context.density_assumption?.density_kg_m3 !== 8440
        || context.density_assumption?.fixed !== true || context.density_assumption?.lot_matched !== false
        || context.density_assumption?.measured_for_this_model !== false
        || !Array.isArray(context.unresolved) || !context.unresolved.some((item: unknown) => typeof item === 'string' && /full-transient admission/i.test(item))) {
        throw new Error('IN625 screening artifact/context content identity mismatch');
      }
      return validateSourceDocument({ schemaVersion: 1, datasetId, materialId: 'in625', processScope: 'bare-plate',
        source: { url: thermalUrl, citation: manifest.citation, version: manifest.version, terms: null,
          termsMissingReason: 'Reuse terms for these locally derived screening inputs were not established from the cited literature and supplier bulletin.' },
        artifacts: files.map((file: any) => ({ relativePath: file.path, sha256: file.sha256,
          byteSize: file.bytes, sourceUrl: file.source_url })),
        sourceContext: context });
    } };
}

/**
 * NIST mds2-2525 time-resolved absorptance (Ti-6Al-4V spot/scan) and the
 * aluminium A-AMB2022-01 challenge tables. Values are measured for NIST's
 * experiment only; nothing here validates a model. `root` is the `official`
 * directory; the locally derived summary lives in the sibling `derived`
 * directory, so artifacts are addressed relative to their common parent.
 */
export function nistMds22525AbsorptanceCatalogEntry(root = path.resolve('data/benchmark/nist-mds2-2525-ti64-absorptance/official')): LpbfSourceCatalogEntry {
  const datasetId = 'nist-mds2-2525-ti64-absorptance-v1';
  const manifestSha256 = '6664470601b31f729458539d9243de397b59a6af614e84dbe955bd2f8ee00be0';
  const doiUrl = 'https://doi.org/10.18434/mds2-2525';
  const base = 'https://data.nist.gov/od/ds/ark:/88434/mds2-2525/';
  const baseShort = 'https://data.nist.gov/od/ds/mds2-2525/';
  const derivedPath = '../derived/ti64-spot-absorptance-summary-v1.json';
  const derivedSha256 = 'da814016f93f1c54742d9bdd9828780c94ee883d21d35cc44387ad6ca9d4389b';
  const derivedBytes = 13381;
  const expectedFiles = [
    { path: '2525_README_v200.txt', sourceUrl: `${base}2525_README_v200.txt`, bytes: 21907,
      sha256: '936f4c166b448f4b5a27d1e2b2465f9c2db1be073a7bffd54d45eb4259120a65', wayback: '20241217170746', kind: 'readme' },
    { path: 'Spot on Bare Metal_Calibrated Absorption Data.csv',
      sourceUrl: `${baseShort}Spot%20on%20Bare%20Metal_Calibrated%20Absorption%20Data.csv`, bytes: 6497288,
      sha256: '0e96b220852d762fde846e406cc44c6fc874cef22e7e41db7f4025dbcc9ca274', wayback: '20241217170645', kind: 'ti64-spot-absorptance-timeseries' },
    { path: 'Al_Spot_TDA_Results.csv', sourceUrl: `${base}Al_Spot_TDA_Results.csv`, bytes: 2292050,
      sha256: '3f0b6812f98535f5ffbb0e2fed31f084ad9a7f9cc393c04a43ed57f0bb14bf69', wayback: '20241217170821', kind: 'al-challenge-table' },
    { path: 'Al_Scan_TDA_v2_Results.csv', sourceUrl: `${base}Al_Scan_TDA_v2_Results.csv`, bytes: 2493685,
      sha256: '3af3478b463b867ed3c78ef6e60c75f9d613607b236933f3f9df08113884a6a8', wayback: '20241217170831', kind: 'al-challenge-table' },
    { path: 'Al_Spot_TDW_Results.csv', sourceUrl: `${base}Al_Spot_TDW_Results.csv`, bytes: 2169,
      sha256: '06b280222eab5f82eb9dcfb0689f20a5011c16e115548cd94ce120e5a97b4f5c', wayback: '20241217170826', kind: 'al-challenge-table' },
    { path: 'Al_Spot_AA_ASR_Results.csv', sourceUrl: `${base}Al_Spot_AA_ASR_Results.csv`, bytes: 242,
      sha256: '4429f08ff3f571ab871fdbaf072e0c67aaef346259a3f2ca8744927ad6419ffb', wayback: '20241217170715', kind: 'al-challenge-table' },
    { path: 'Al_Scan_AA_MWD_ASR_Results.csv', sourceUrl: `${base}Al_Scan_AA_MWD_ASR_Results.csv`, bytes: 364,
      sha256: 'd3732fcddaaee046105aa90eb82547ffd0fe61edb425fc1e8f019c6f73ed0b4d', wayback: '20241217170730', kind: 'al-challenge-table' },
    { path: 'NIST SRM 654b Ti64 data sheet.pdf', sourceUrl: `${baseShort}NIST%20SRM%20654b%20Ti64%20data%20sheet.pdf`, bytes: 67521,
      sha256: '57a8295d6db46e723cb3f0eb63844a98527dc8c61bedfa934dba549bffe13740', wayback: '20241217170629', kind: 'srm-datasheet' },
    { path: 'nerdm-record-mds2-2525.json', sourceUrl: 'https://data.nist.gov/rmm/records?@id=ark:/88434/mds2-2525', bytes: 39359,
      sha256: '8388c6a21a7e4432ee23bfca17a45d3cd160ddfaf194d9607e5961d2eff03695', wayback: null, kind: 'nerdm-record' },
  ];
  const expectedAbsent = [
    { path: 'Scan on Bare Metal_Calibrated Absorption Data.csv', bytes: 6657476,
      sha256: '1c64f24e84c274d9f9ae27fb09e79b86cda2fda5bee4b67da3567c8a59ca499d',
      sourceUrl: `${baseShort}Scan%20on%20Bare%20Metal_Calibrated%20Absorption%20Data.csv` },
    { path: 'Absorption_Uncertainty_Analysis.pdf', bytes: 388131,
      sha256: '98ead678e3a8f6696650302dbf29660f2a886a62ba677453dd130c222755e28d',
      sourceUrl: `${baseShort}Absorption_Uncertainty_Analysis.pdf` },
  ];
  /** Metadata-sized JSON only; the CSV artifacts are hashed separately without the 1 MiB guard. */
  const readSmallPinned = (directory: string, relative: string, bytes: number | null, sha256: string, label: string) => {
    const filename = path.join(artifactDirectory(directory), relative);
    const stat = lstatSync(filename);
    if (stat.isSymbolicLink() || !stat.isFile() || stat.size > 1024 * 1024 || (bytes !== null && stat.size !== bytes)) {
      throw new Error(`Invalid NIST mds2-2525 ${label} file`);
    }
    const content = readFileSync(filename);
    if (createHash('sha256').update(content).digest('hex') !== sha256) throw new Error(`NIST mds2-2525 ${label} SHA-256 mismatch`);
    return content;
  };
  return { datasetId, title: 'NIST mds2-2525 · Ti-6Al-4V time-resolved absorptance (measured, NIST experiment only)',
    sourceRoot: path.dirname(root),
    loadDocument() {
      const manifestBytes = readSmallPinned(root, 'manifest.json', null, manifestSha256, 'manifest');
      const manifest = JSON.parse(manifestBytes.toString('utf8'));
      const files = manifest.files;
      if (manifest.schema_version !== 1 || manifest.dataset_id !== datasetId || manifest.version !== '1.3.2'
        || manifest.readme_document_version !== '2.0.0' || manifest.material !== 'Ti-6Al-4V'
        || manifest.process_scope !== 'bare-plate'
        || manifest.artifact_kind !== 'publisher-calibrated-absorptance-and-challenge-tables'
        || manifest.doi !== '10.18434/mds2-2525' || manifest.license !== 'https://www.nist.gov/open/license'
        || typeof manifest.citation !== 'string' || !manifest.citation
        || !Array.isArray(files) || files.length !== expectedFiles.length
        || !Array.isArray(manifest.absent_files) || manifest.absent_files.length !== expectedAbsent.length
        || !Array.isArray(manifest.derived_tables) || manifest.derived_tables.length !== 1
        || !Array.isArray(manifest.not_archived_components?.components)
        || manifest.not_archived_components.components.length === 0
        || manifest.not_archived_components.components.some((item: any) => typeof item?.path !== 'string'
          || !/^[0-9a-f]{64}$/.test(item?.sha256 ?? '') || !Number.isInteger(item?.bytes))) {
        throw new Error('NIST mds2-2525 manifest identity mismatch');
      }
      for (const [index, expected] of expectedFiles.entries()) {
        const file = files[index];
        if (file?.path !== expected.path || file?.source_url !== expected.sourceUrl || file?.bytes !== expected.bytes
          || file?.sha256 !== expected.sha256 || file?.wayback_timestamp !== expected.wayback || file?.kind !== expected.kind) {
          throw new Error('NIST mds2-2525 artifact identity mismatch');
        }
        const filename = path.join(artifactDirectory(root), expected.path);
        const stat = lstatSync(filename);
        if (stat.isSymbolicLink() || !stat.isFile() || stat.size !== expected.bytes
          || createHash('sha256').update(readFileSync(filename)).digest('hex') !== expected.sha256) {
          throw new Error('NIST mds2-2525 artifact integrity mismatch');
        }
      }
      for (const [index, expected] of expectedAbsent.entries()) {
        const entry = manifest.absent_files[index];
        if (entry?.path !== expected.path || entry?.bytes !== expected.bytes || entry?.sha256 !== expected.sha256
          || entry?.source_url !== expected.sourceUrl || entry?.status !== 'unavailable' || typeof entry?.reason !== 'string') {
          throw new Error('NIST mds2-2525 absent-file identity mismatch');
        }
      }
      const derivedRef = manifest.derived_tables[0];
      if (derivedRef?.path !== derivedPath || derivedRef?.bytes !== derivedBytes || derivedRef?.sha256 !== derivedSha256) {
        throw new Error('NIST mds2-2525 derived summary identity mismatch');
      }
      const derived = JSON.parse(readSmallPinned(path.dirname(root), 'derived/ti64-spot-absorptance-summary-v1.json',
        derivedBytes, derivedSha256, 'derived summary').toString('utf8'));
      const spot = derived.ti64_spot;
      const al = derived.aluminium_challenge;
      if (derived.schemaVersion !== 1 || derived.datasetId !== datasetId || derived.evidence?.experimentalValidation !== false
        || derived.evidence?.modelAcceptance !== false || !Number.isFinite(spot?.pre_keyhole_mean_pct)
        || !Number.isFinite(spot?.keyhole_mean_pct) || !Array.isArray(al?.spot_average_absorption?.rows)
        || !Array.isArray(al?.scan_average_absorption?.rows) || !Array.isArray(derived.unavailable)
        || derived.unavailable.length !== expectedAbsent.length) {
        throw new Error('NIST mds2-2525 derived summary content mismatch');
      }
      const aluminiumReason = 'Aluminium (NIST SRM 1241c) challenge result; the application has no aluminium material counterpart.';
      const aluminium = (table: any, sourceFile: string, description: string, label: string, quantity: string, laserPower_W: number,
        n: number) => {
        const row = table.rows.find((item: any) => item.description === description);
        if (!row) throw new Error('NIST mds2-2525 aluminium table row missing');
        return { label, material: 'aluminium (NIST SRM 1241c)', quantity, laser_power_W: laserPower_W,
          value: row.value, unit: row.unit, std_dev: row.std_dev, std_dev_unit: row.std_dev_unit,
          n, n_source: 'NIST README v2.0.0 table description', derived_locally: false,
          measured: true, comparable_to_app_models: false, comparable_reason: aluminiumReason, source_file: sourceFile };
      };
      const spotAa = 'Al_Spot_AA_ASR_Results.csv';
      const scanAa = 'Al_Scan_AA_MWD_ASR_Results.csv';
      const ti64Common = { material: 'Ti-6Al-4V (NIST SRM 654b)', laser_power_W_median: spot.input_power_median_W,
        quantity: 'time-resolved relative absorptance, stationary beam', unit: '%', measured: true,
        source_file: 'Spot on Bare Metal_Calibrated Absorption Data.csv', derived_locally: true,
        comparable_to_app_models: false, window_definition: spot.window_definition };
      const observations = [
        { label: 'Ti-6Al-4V spot, pre-keyhole window (local analysis window, not NIST-published)', ...ti64Common,
          value: spot.pre_keyhole_mean_pct, std_dev: spot.pre_keyhole_std_pct, n: spot.pre_keyhole_n,
          window_ms: spot.pre_keyhole_window_ms,
          comparable_reason: 'Only an offline screening comparison with the constant flat-plate absorptivity exists '
            + '(docs/LPBF_NIST_2525_ABSORPTANCE_COMPARISON_2026-10-06.md); the thin coupon, 7 degree incidence and '
            + 'temperature dependence are not represented, so it is not a model acceptance.' },
        { label: 'Ti-6Al-4V spot, keyhole window (local analysis window, not NIST-published)', ...ti64Common,
          value: spot.keyhole_mean_pct, std_dev: spot.keyhole_std_pct, n: spot.keyhole_n,
          window_ms: spot.keyhole_window_ms,
          comparable_reason: 'Stationary beam on a thin polished coupon; the application does not solve keyhole geometry.' },
        aluminium(al.spot_average_absorption, spotAa, 'Average Absorption before keyhole',
          'Aluminium spot, average absorptance before keyhole (NIST-published)', 'average absorptance, 3 runs', 501, 3),
        aluminium(al.spot_average_absorption, spotAa, 'Average Absorption during keyhole',
          'Aluminium spot, average absorptance during keyhole (NIST-published)', 'average absorptance, 3 runs', 501, 3),
        aluminium(al.spot_average_absorption, spotAa, 'Solidification Rate',
          'Aluminium spot, solidification rate (NIST-published)', 'solidification rate', 501, 2),
        aluminium(al.scan_average_absorption, scanAa, 'Average Absorption before keyhole',
          'Aluminium scan, average absorptance before keyhole (NIST-published)', 'average absorptance, 3 runs', 473, 3),
        aluminium(al.scan_average_absorption, scanAa, 'Average Absorption during keyhole',
          'Aluminium scan, average absorptance during keyhole (NIST-published)', 'average absorptance, 3 runs', 473, 3),
        aluminium(al.scan_average_absorption, scanAa, 'Melt Pool Depth - Maximum',
          'Aluminium scan, maximum melt-pool depth (NIST-published)', 'maximum melt-pool depth from X-ray imaging', 473, 3),
        aluminium(al.scan_average_absorption, scanAa, 'Melt Pool Width - Maximum',
          'Aluminium scan, maximum melt-pool width (NIST-published)', 'maximum melt-pool width from X-ray imaging', 473, 3),
        aluminium(al.scan_average_absorption, scanAa, 'Solidification Rate',
          'Aluminium scan, solidification rate (NIST-published)', 'solidification rate', 473, 3),
      ];
      const artifacts = [
        ...files.map((file: any) => ({ relativePath: `official/${file.path}`, sha256: file.sha256,
          byteSize: file.bytes, sourceUrl: file.source_url })),
        { relativePath: 'derived/ti64-spot-absorptance-summary-v1.json', sha256: derivedSha256,
          byteSize: derivedBytes, sourceUrl: doiUrl },
      ];
      return validateSourceDocument({ schemaVersion: 1, datasetId, materialId: 'ti6al4v', processScope: 'bare-plate',
        source: { url: doiUrl, citation: manifest.citation, version: manifest.version,
          terms: 'NIST Open License: https://www.nist.gov/open/license', termsMissingReason: null },
        artifacts,
        sourceContext: { schema_version: 1, dataset_id: datasetId, source_version: manifest.version,
          publisher_artifact_kind: manifest.artifact_kind, checksum_authority: manifest.checksum_authority,
          acquisition: manifest.acquisition,
          locally_derived_artifacts: [{ path: 'derived/ti64-spot-absorptance-summary-v1.json', published_by_nist: false,
            note: 'Locally derived from the publisher CSV files; the sourceUrl of this artifact is the DOI landing page, not a NIST download.' },
          { path: 'official/nerdm-record-mds2-2525.json', published_by_nist: false,
            note: 'Content is the NIST NERDm record, but these bytes are a local re-serialisation (sorted keys, indent 1); the bytes served at its sourceUrl will not match. Its SHA-256 is locally authoritative only.' }],
          experiment: { process_scope: 'bare-plate', machine: 'APS 32-ID-B integrating-sphere and X-ray imaging apparatus',
            laser: manifest.experiment.laser, spot_diameter_1_over_e2_um: manifest.experiment.spot_diameter_1_over_e2_um,
            beam_waist_um: manifest.experiment.beam_waist_um, materials: manifest.experiment.materials,
            atmosphere: manifest.experiment.atmosphere, pulse_duration_ms: manifest.experiment.pulse_duration_ms,
            scan_case: manifest.experiment.scan_case, sample_thickness_um: 300, powder: false,
            heat_treatment_missing_reason: 'Not established in the NIST README.' },
          measurement: { quantity: 'time-resolved absolute laser absorptance (integrating sphere) and melt-pool width from X-ray imaging',
            method: manifest.experiment.absorptance_method, xray_imaging: manifest.experiment.xray_imaging,
            unit_source: 'W and %',
            uncertainty: 'The AbsAbsorptionUncertainty column is the publisher absolute expanded uncertainty in W; the uncertainty analysis PDF is not acquired.',
            beam_diameter_definition: '1/e^2 diameter 122.5 ± 3.0 µm at the sample surface, 2.8 mm below the beam waist (NIST README)',
            temperature_conversion: null,
            temperature_conversion_missing_reason: 'Not applicable: integrating-sphere power measurement, no camera or thermal signal.',
            repeat_group_rule: 'Aluminium before/during-keyhole absorptance averages are 3 runs with 1 standard deviation; the aluminium spot solidification rate is the average of 2 measurements; the aluminium scan maximum melt-pool depth/width and solidification rate are averages of 3 measurements (NIST README). The Ti-6Al-4V spot file is a single trace.' },
          observations, unavailable_files: derived.unavailable,
          not_archived_components: manifest.not_archived_components, split: 'unassigned',
          unresolved: [
            'The Al_* tables are aluminium (NIST SRM 1241c) challenge results and have no application material counterpart.',
            'The Ti-6Al-4V scan CSV and the absorption uncertainty PDF were not acquired (NIST download timed out; no Internet Archive copy with the official SHA-256); they are listed as unavailable with their official hashes.',
            'Absorptance was measured on a ~300 um thin polished bare coupon, not on a powder bed.',
            'The application does not solve keyhole geometry, so no model acceptance follows from these values; experimentalValidation stays false.',
            'The pre-keyhole and keyhole windows for the Ti-6Al-4V trace are local analysis choices, not NIST-published phase boundaries.',
          ] } });
    } };
}

/**
 * Locally derived signal-unit metrics from NIST mds2-2716 (AMB2022-03 IN718 staring-camera
 * thermography and pad scan strategy). The 550 MB raw HDF5 file is never committed; this entry
 * archives only the small derived table and the publisher NERDm record, while the derived manifest
 * pins the raw inputs by size and SHA-256. Values are raw camera signal in digital levels for NIST's
 * experiment only: no temperature conversion is executed and nothing here validates a model.
 * `root` is the `derived` directory; artifacts are addressed relative to its parent dataset folder.
 */
export function nistIn718ThermographyDerivedCatalogEntry(root = path.resolve('data/benchmark/nist-amb2022-03/derived')): LpbfSourceCatalogEntry {
  const datasetId = 'nist-mds2-2716-thermography-signal-v1';
  const doiUrl = 'https://doi.org/10.18434/mds2-2716';
  const nerdmUrl = 'https://data.nist.gov/rmm/records?@id=ark:/88434/mds2-2716';
  const manifestSha256 = 'ef3fb4b1dfc028d6f1a40ba0bb4f4ee565bf9895b8f1e289b1334f086480d7bc';
  const derivedName = 'thermography-signal-metrics-v1.json';
  const derivedSha256 = '7b34b3b304a95aab0dccd9481d8d944d066bfddb087bd05bd409a949b021d76a';
  const derivedBytes = 182588;
  const nerdmSha256 = '9e53e0f906763192087de331ad5eebaa29f98d9ee11ac4b1fa709ac0d9fa24c8';
  const nerdmBytes = 14033;
  const base = 'https://data.nist.gov/od/ds/ark:/88434/mds2-2716/';
  const expectedInputs = [
    { name: 'AMB2022-03-718-AMMT-StaringCamera_Signal.h5', bytes: 549979044,
      sha256: 'f6fe21ec911707f72e7efda2932c77eae2b75d84765848878fe5beb6b728cd43',
      sourceUrl: `${base}Thermography/AMB2022-03-718-AMMT-StaringCamera_Signal.h5` },
    { name: 'AMB2022-03-AMMT-718-Pad_XYPT.h5', bytes: 406992,
      sha256: '7b7004753e150bc26632e9ce356e0440429160fa92cbff8fc8559202fdce2103',
      sourceUrl: `${base}ScanStrategy/AMB2022-03-AMMT-718-Pad_XYPT.h5` },
    { name: 'README.txt', bytes: 12573,
      sha256: 'ba44076ed51b69c0e4ca80ff0e2568eed2dc6459e85c9ad83b85860bee5760f2',
      sourceUrl: 'https://data.nist.gov/od/ds/mds2-2716/2716_README.txt' },
  ];
  const datasetRoot = path.dirname(root);
  const readPinned = (relative: string, bytes: number | null, sha256: string, label: string) => {
    const filename = path.join(artifactDirectory(datasetRoot), relative);
    const stat = lstatSync(filename);
    if (stat.isSymbolicLink() || !stat.isFile() || stat.size > 1024 * 1024 || (bytes !== null && stat.size !== bytes)) {
      throw new Error(`Invalid NIST mds2-2716 ${label} file`);
    }
    const content = readFileSync(filename);
    if (createHash('sha256').update(content).digest('hex') !== sha256) throw new Error(`NIST mds2-2716 ${label} SHA-256 mismatch`);
    return content;
  };
  return { datasetId, title: 'NIST mds2-2716 · IN718 staring-camera signal metrics (raw DL, derived locally, no temperature)',
    sourceRoot: datasetRoot,
    loadDocument() {
      const derivedDir = path.basename(root);
      const manifest = JSON.parse(readPinned(`${derivedDir}/manifest.json`, null, manifestSha256, 'derived manifest').toString('utf8'));
      if (manifest.schemaVersion !== 1 || manifest.datasetId !== datasetId || manifest.sourceDatasetId !== 'nist-mds2-2716'
        || manifest.derived?.path !== derivedName || manifest.derived?.bytes !== derivedBytes || manifest.derived?.sha256 !== derivedSha256
        || manifest.sourceRecord?.path !== '../official/nerdm-record-mds2-2716.json' || manifest.sourceRecord?.bytes !== nerdmBytes
        || manifest.sourceRecord?.sha256 !== nerdmSha256 || manifest.evidence?.experimentalValidation !== false
        || manifest.evidence?.opticalOperatorMatched !== false || manifest.evidence?.temperatureConversion !== null
        || !Array.isArray(manifest.inputs) || manifest.inputs.length !== expectedInputs.length) {
        throw new Error('NIST mds2-2716 derived manifest identity mismatch');
      }
      const sourceManifest = readJson(datasetRoot, 'manifest.json');
      if (sourceManifest.dataset_id !== 'nist-mds2-2716' || !Array.isArray(sourceManifest.files)) {
        throw new Error('NIST mds2-2716 source manifest identity mismatch');
      }
      for (const [index, expected] of expectedInputs.entries()) {
        const input = manifest.inputs[index];
        const archived = sourceManifest.files.filter((file: any) => path.posix.basename(String(file?.path ?? '')) === expected.name);
        if (input?.name !== expected.name || input?.bytes !== expected.bytes || input?.sha256 !== expected.sha256
          || input?.source_url !== expected.sourceUrl || archived.length !== 1
          || archived[0].bytes !== expected.bytes || archived[0].sha256 !== expected.sha256) {
          throw new Error('NIST mds2-2716 input pin mismatch');
        }
      }
      const derived = JSON.parse(readPinned(`${derivedDir}/${derivedName}`, derivedBytes, derivedSha256, 'derived table').toString('utf8'));
      readPinned('official/nerdm-record-mds2-2716.json', nerdmBytes, nerdmSha256, 'NERDm record');
      if (derived.schemaVersion !== 1 || derived.datasetId !== datasetId || derived.evidence?.experimentalValidation !== false
        || derived.evidence?.opticalOperatorMatched !== false || derived.evidence?.modelAcceptance !== false
        || derived.evidence?.temperatureConversion !== null || !Array.isArray(derived.lines) || derived.lines.length !== 21
        || !Array.isArray(derived.cases) || derived.cases.length !== 7 || !Array.isArray(derived.unavailable)
        || derived.unavailable.some((item: any) => item?.status !== 'unavailable' || typeof item?.reason !== 'string' || !item.reason)) {
        throw new Error('NIST mds2-2716 derived table content mismatch');
      }
      return validateSourceDocument({ schemaVersion: 1, datasetId, materialId: 'in718', processScope: 'bare-plate',
        source: { url: doiUrl, citation: derived.source.citation, version: derived.source.nerdmVersion,
          terms: 'NIST Open License: https://www.nist.gov/open/license', termsMissingReason: null },
        artifacts: [
          { relativePath: `${derivedDir}/${derivedName}`, sha256: derivedSha256, byteSize: derivedBytes, sourceUrl: doiUrl },
          { relativePath: 'official/nerdm-record-mds2-2716.json', sha256: nerdmSha256, byteSize: nerdmBytes, sourceUrl: nerdmUrl },
        ],
        sourceContext: { schema_version: 1, dataset_id: datasetId, source_version: derived.source.nerdmVersion,
          publisher_artifact_kind: 'locally-derived-signal-metrics-from-raw-thermography',
          headline: derived.headline,
          raw_inputs: manifest.inputs.map((input: any) => ({ ...input, committed: false })),
          raw_storage: manifest.rawStorage,
          locally_derived_artifacts: [{ path: `${derivedDir}/${derivedName}`, published_by_nist: false,
            tool: manifest.tool, runtime: manifest.runtime,
            note: 'Derived locally from the hash-pinned NIST HDF5 files; the sourceUrl of this artifact is the DOI landing page, not a NIST download.' },
          { path: 'official/nerdm-record-mds2-2716.json', published_by_nist: false,
            note: 'Content is the NIST NERDm record (ResultData[0] of the RMM query), re-serialised locally (sorted keys, indent 1); the bytes served at its sourceUrl will not match. Its SHA-256 is locally authoritative only.' }],
          experiment: { material: 'IN718', process_scope: 'bare-plate', powder_present: false,
            machine: 'NIST Additive Manufacturing Metrology Testbed (AMMT)',
            heat_treatment: null, heat_treatment_missing_reason: 'Not recorded in the thermography files.' },
          measurement: { quantity: 'Raw staring-camera signal (FASTCAM Mini AX200, 30000 frames/s) reduced to time above signal thresholds, signal-decay times, saturated-region length and inferred pixel pitch',
            unit_source: 'digital levels (DL); frames of 1/30000 s', unit_missing_reason: null,
            temperature_conversion: null,
            temperature_conversion_missing_reason: derived.evidence.temperatureConversionMissingReason,
            beam_diameter_definition: 'D4s (literal HDF5 spot_size_measure)', beam_diameter_missing_reason: null,
            censoring: 'Signals at 4095 DL are saturated (upper-censored); values below 100 DL were stored as 0 by NIST (lower-censored, not zero temperature).',
            repeat_group_rule: 'Line_0_Z is the baseline case; Line_X_Y_Z is case X.Y; Z = 1..3 are repeats, aggregated together and never split.' },
          checks: derived.checks, unavailable_quantities: derived.unavailable,
          split: 'unassigned', thermal_validation_ready: false,
          unresolved: [
            'Pixel pitch (about 21.3 µm) and the camera-axis to scan-direction mapping are inferred from hot-spot speed against the commanded speed (README ±2.5 % k=1), not from a published spatial calibration.',
            'Emissivity is not published and the stored ThermalCal Model string is malformed; no temperature, cooling rate or time above melting is derived.',
            'The Celsius/Kelvin convention of the calibration regression cannot be determined from the file.',
            'The melt-pool region saturates at 4095 DL in every laser-on frame, so peak signal is censored.',
            'The camera trigger offset for single lines is not recorded; laser-on is defined as the first frame with a saturated pixel.',
            'Pad camera videos (re-heating, revisit intervals) are not analysed in v1; only the commanded XYPT track table is derived.',
          ] } });
    } };
}
