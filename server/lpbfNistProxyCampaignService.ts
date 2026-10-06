/** Immutable thermal-proxy campaigns. This path never computes optical residuals. */
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { lstatSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { artifactDirectory, LpbfArtifactStore } from './lpbfArtifactStore';
import { LpbfRunArchiveError } from './lpbfRunArchiveService';
import { LpbfRunRepository, type ProxyCampaignRecord, type RunRecord } from './lpbfRunRepository';
import { runArtifacts } from './lpbfRunImport';
import { LpbfSourceRepository } from './lpbfSourceRepository';
import { deriveProxyCampaignRunBinding, proxyCampaignEligibilityFailure, rederiveProxyCampaignSections,
  validateArchivedProxySections } from './lpbfProxyCampaignBinding';
import { resolvePythonRoot } from './pythonRoot';
import { getHostPython } from './pythonRuntime';

const DATASET_ID = 'nist-amb2022-03-optical-table4-local-v1';
const PUBLISHER_ID = 'nist-mds2-2718';
const TABLE_SHA256 = 'd1b36dfa2e01a3537093c481e249ce52df6b8879c1c67480ddb9aa10799133da';
const TABLE_BYTES = 4321;
const TABLE_PATH = 'table4-aggregate-v2.json';
const RESULTS_URL = 'https://www.nist.gov/document/am-bench-amb2022-03-measurement-and-result-descriptions-v10';
const SECTION_DISTANCES = [4.9, 6.0];
const sha = (value: string | Buffer) => createHash('sha256').update(value).digest('hex');
const unavailable = (reasons: string[]) => ({ schemaVersion: 1, kind: 'lpbf-nist-amb2022-03-proxy-campaign-validation',
  campaignId: null, status: 'unavailable', validationStatus: 'unvalidated', experimentalValidation: false,
  numericalConvergenceStatus: 'not-evaluated', comparisonResiduals: null, observationCount: null, reasons });

function validatePython(campaign: unknown, source: unknown, expectedBeamDiameterUm: number): Promise<any> {
  return new Promise((resolve, reject) => {
    const python = getHostPython();
    const code = `import json,sys; sys.path.insert(0,${JSON.stringify(resolvePythonRoot())}); from lpbf_nist_proxy_campaign import validate_proxy_campaign; q=json.load(sys.stdin); print(json.dumps(validate_proxy_campaign(q["campaign"], q["source"], q["expectedBeamDiameterUm"]), allow_nan=False))`;
    const child = spawn(python.cmd, [...python.prefix, '-c', code], { cwd: path.resolve(), windowsHide: true, shell: false, stdio: 'pipe' });
    let stdout = '', stderr = '', done = false;
    const fail = (error: Error) => { if (!done) { done = true; clearTimeout(timer); reject(error); } };
    const timer = setTimeout(() => { child.kill(); fail(new Error('Proxy campaign validation timed out')); }, 15000);
    child.stdout.on('data', chunk => { stdout += chunk.toString(); if (stdout.length > 1024 * 1024) { child.kill(); fail(new Error('Proxy validation output too large')); } });
    child.stderr.on('data', chunk => { stderr = (stderr + chunk.toString()).slice(-2048); });
    child.on('error', fail);
    child.on('close', code => {
      if (done) return;
      if (code !== 0) { fail(new Error(`Proxy validation failed: ${stderr}`)); return; }
      try { const result = JSON.parse(stdout); done = true; clearTimeout(timer); resolve(result); }
      catch { fail(new Error('Invalid proxy validation response')); }
    });
    child.stdin.on('error', fail);
    child.stdin.end(JSON.stringify({ campaign, source, expectedBeamDiameterUm }));
  });
}

function exactCase(table: any, caseNumber: string) {
  if (!Array.isArray(table?.cases)) return null;
  const matches = table.cases.filter((item: any) => item?.caseNumber === caseNumber);
  return matches.length === 1 ? matches[0] : null;
}

export class LpbfNistProxyCampaignService {
  constructor(private readonly runRoot = path.resolve(process.env.METALLIKSA_LPBF_RUN_ROOT || '.lpbf-runs'),
    private readonly sourceRoot = path.resolve(process.env.METALLIKSA_LPBF_SOURCE_ROOT || '.lpbf-sources'),
    private readonly sectionReader: (result: unknown, bytes: Buffer) => Promise<any> = rederiveProxyCampaignSections) {}

  async list(): Promise<ProxyCampaignRecord[]> {
    const runDb = path.join(this.runRoot, 'runs.sqlite');
    let stat;
    try { stat = lstatSync(runDb); }
    catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return []; throw error; }
    if (stat.isSymbolicLink() || !stat.isFile()) throw new Error('Run metadata is not a regular file');
    artifactDirectory(this.runRoot);
    const repository = new LpbfRunRepository(runDb, { readOnly: true });
    try {
      const campaigns = [...repository.allProxyCampaigns()];
      for (const campaign of campaigns) {
        for (const track of campaign.document.tracks) {
          const identity = track.runIdentity, run = repository.get(identity.runId);
          if (!run || run.documentSha256 !== identity.runDocumentSha256
            || !run.document.sources.some(link => link.datasetId === campaign.document.sourceBinding?.datasetId
              && link.revision === campaign.document.sourceBinding?.revision
              && link.documentSha256 === campaign.document.sourceBinding?.documentSha256)) {
            throw new Error('Stored campaign run/source reference integrity failed');
          }
        }
      }
      return campaigns.sort((left, right) => right.createdAt.localeCompare(left.createdAt));
    } finally { repository.close(); }
  }

  private async build(runIds: unknown, caseNumber: unknown) {
    if (!Array.isArray(runIds) || runIds.length !== 3 || runIds.some(id => typeof id !== 'string' || !/^[a-f0-9]{32}$/.test(id))
      || new Set(runIds).size !== 3 || typeof caseNumber !== 'string') {
      throw new LpbfRunArchiveError(400, 'Provide exactly three distinct archived run IDs and a Table 4 case number.');
    }
    if (caseNumber !== '0') {
      return { campaign: null, validation: unavailable([
        'Proxy campaign v2 currently supports Table 4 case 0 only; other cases are unavailable.',
      ]) };
    }
    let runs: LpbfRunRepository | null = null, sources: LpbfSourceRepository | null = null;
    try {
      artifactDirectory(this.runRoot);
      const runDb = path.join(this.runRoot, 'runs.sqlite');
      if (lstatSync(runDb).isSymbolicLink()) throw new Error('Run metadata link');
      runs = new LpbfRunRepository(runDb, { readOnly: true });
      const records = runIds.map(id => runs!.get(id)).filter(Boolean) as RunRecord[];
      if (records.length !== 3) return { campaign: null, validation: unavailable(['One or more selected archived runs are missing.']) };
      const runStore = new LpbfArtifactStore(path.join(this.runRoot, 'artifacts'), { readOnly: true });
      for (const record of records) {
        for (const artifactRef of runArtifacts(record.document)) await runStore.verify(artifactRef);
      }

      const links = records.map(record => record.document.sources.filter(link => link.datasetId === DATASET_ID));
      if (links.some(value => value.length !== 1) || links.some(value => value[0].revision !== links[0][0].revision
        || value[0].documentSha256 !== links[0][0].documentSha256)) {
        return { campaign: null, validation: unavailable(['All three runs must bind the same exact local Table 4 source revision.']) };
      }
      const link = links[0][0];
      const sourceDb = path.join(this.sourceRoot, 'metadata.sqlite');
      if (lstatSync(sourceDb).isSymbolicLink()) throw new Error('Source metadata link');
      sources = new LpbfSourceRepository(sourceDb, { readOnly: true });
      const revision = sources.revision(DATASET_ID, link.revision);
      const artifact = revision?.document.artifacts[0];
      if (!revision || revision.documentSha256 !== link.documentSha256 || revision.document.datasetId !== DATASET_ID
        || revision.document.materialId !== 'in718' || revision.document.processScope !== 'bare-plate'
        || revision.document.source.url !== 'https://doi.org/10.18434/mds2-2718' || revision.document.artifacts.length !== 1
        || artifact?.relativePath !== TABLE_PATH || artifact.sha256 !== TABLE_SHA256 || artifact.byteSize !== TABLE_BYTES
        || artifact.sourceUrl !== RESULTS_URL) {
        return { campaign: null, validation: unavailable(['The exact archived Table 4 source identity does not match the reviewed local transcription.']) };
      }
      const verified = await new LpbfArtifactStore(path.join(this.sourceRoot, 'artifacts'), { readOnly: true }).verify(artifact);
      const bytes = readFileSync(verified.path);
      if (bytes.length !== TABLE_BYTES || sha(bytes) !== TABLE_SHA256) return { campaign: null, validation: unavailable(['Table 4 source artifact bytes failed exact SHA-256 verification.']) };
      const sourceBinding = { datasetId: DATASET_ID, revision: link.revision, documentSha256: link.documentSha256,
        artifactPath: artifact.relativePath, artifactSha256: artifact.sha256, artifactSizeBytes: artifact.byteSize, caseNumber };
      const table = JSON.parse(bytes.toString('utf8')), row = exactCase(table, caseNumber);
      if (!row) return { campaign: null, validation: unavailable(['Selected Table 4 case is absent or ambiguous in the verified source.']) };

      const gpuPilot = records.find(record => record.runKind === 'gpu-thermal-pilot');
      if (gpuPilot) {
        return { campaign: null, validation: unavailable([
          `Archived GPU pilot ${gpuPilot.document.runId} is separate from CPU-core proxy eligibility.`,
        ]) };
      }
      const eligibilityFailure = proxyCampaignEligibilityFailure(records, {
        beamDiameter_um: row.beamDiameterD4sigma_um,
        power_W: row.laserPower_W,
        speed_mm_s: row.scanSpeed_mm_s,
      });
      if (eligibilityFailure) return { campaign: null, validation: unavailable([eligibilityFailure]) };

      const tracks = [];
      let sharedRunIdentity: any = null;
      for (let index = 0; index < records.length; index++) {
        const record = records[index], result = JSON.parse(record.document.capture.resultJson);
        const settings = result.settings || {};
        if (record.runKind === 'gpu-thermal-pilot') {
          return { campaign: null, validation: unavailable([`Archived GPU pilot ${record.document.runId} is separate from CPU-core proxy eligibility.`]) };
        }
        if (record.runKind !== 'transient-thermal' || record.document.capture.contractStatus !== 'core-v1-bound'
          || result.coreContract?.modelId !== 'stationary-enthalpy-conduction-v1'
          || result.coreContract?.actualBackend !== 'numpy-reference' || result.effectiveMode !== 'standard'
          || result.material?.materialId !== 'in718' || settings.surfaceMode !== 'bare-plate' || settings.tracks !== 1
          || settings.layers !== 1 || settings.trackLength_um !== 10000 || settings.scanAngle_deg !== 0
          || settings.power_W !== row.laserPower_W || settings.speed_mm_s !== row.scanSpeed_mm_s
          || settings.beamDiameter_um !== row.beamDiameterD4sigma_um
          || !Number.isFinite(settings.preheat_C) || settings.preheat_C < 22.5 || settings.preheat_C > 24.5
          || !Number.isFinite(settings.speed_mm_s) || settings.speed_mm_s <= 0
          || !Array.isArray(result.scanPath) || result.scanPath.length !== 1
          || JSON.stringify(result.scanPath[0]?.start) !== JSON.stringify([-0.005, 0])
          || JSON.stringify(result.scanPath[0]?.end) !== JSON.stringify([0.005, 0])
          || result.scanPath[0]?.start_s !== 0 || !Number.isFinite(result.scanPath[0]?.end_s)
          || Math.abs(result.scanPath[0]?.end_s - 10 / settings.speed_mm_s) > 1e-12
          || !Array.isArray(result.barePlateSectionObservations)) {
          return { campaign: null, validation: unavailable([`Archived run ${record.document.runId} is not a matching, core-bound IN718 bare-plate thermal track for Table 4 case ${caseNumber}.`]) };
        }
        const sectionFailure = await validateArchivedProxySections(result,
          new LpbfArtifactStore(path.join(this.runRoot, 'artifacts'), { readOnly: true }), this.sectionReader);
        if (sectionFailure) return { campaign: null, validation: unavailable([`Archived run ${record.document.runId}: ${sectionFailure}`]) };
        const run = deriveProxyCampaignRunBinding(record, sourceBinding);
        if (!run) return { campaign: null, validation: unavailable([`Archived run ${record.document.runId} lacks both finite 4.9/6.0 mm thermal-proxy sections.`]) };
        const identity = run.runIdentity;
        const physicalIdentity = JSON.stringify({ inputSha256: identity.inputSha256, materialSha256: identity.materialSha256,
          materialRevisionSha256: identity.materialRevisionSha256, materialId: identity.materialId, coreContract: identity.coreContract });
        if (sharedRunIdentity !== null && sharedRunIdentity !== physicalIdentity) {
          return { campaign: null, validation: unavailable(['The three computational runs do not share one exact input, material revision and executed core identity.']) };
        }
        sharedRunIdentity = physicalIdentity;
        tracks.push({ simulatedTrackId: `sim-${record.document.runId}`, experimentalTrackId: null,
          replicateKind: 'independent-computational-run', runIdentity: run.runIdentity, observations: run.observations });
      }
      const schemaVersion = 2;
      const campaignId = sha(JSON.stringify({ schemaVersion, runIds, caseNumber, revision: link.revision, doc: link.documentSha256 })).slice(0, 32);
      const beamInputDeclaration = { status: 'published-source-declared', definition: 'D4sigma',
        value_um: row.beamDiameterD4sigma_um, mappingStatus: 'conditional-ideal-Gaussian',
        measuredProfileMatched: false, sourceBinding };
      const campaign = { schemaVersion, kind: 'lpbf-nist-amb2022-03-proxy-campaign', campaignId,
        benchmark: 'AMB2022-03-TMPG', caseNumber, sourceBinding,
        beamInputDeclaration,
        claimBoundary: { resultKind: 'thermal-proxy-screening', validationStatus: 'unvalidated', experimentalValidation: false, opticalOperatorMatched: false },
        samplingPlan: { coordinateFrame: 'scan-start-relative', scanDirection: '+X', sectionPositions_mm: SECTION_DISTANCES,
          expectedTrackCount: 3, expectedObservationCount: 6,
          replicateSemantics: 'reproducibility-evidence-not-independent-replicates' },
        tracks: tracks.map(track => ({ ...track, replicateKind: 'reproducibility-execution' })) };
      const validation = await validatePython(campaign, sourceBinding, row.beamDiameterD4sigma_um);
      if (validation?.status !== 'proxy-screening-only' || validation.comparisonResiduals !== null
        || validation.experimentalValidation !== false || validation.validationStatus !== 'unvalidated') {
        return { campaign: null, validation: unavailable(Array.isArray(validation?.reasons) ? validation.reasons : ['Python proxy validator returned an invalid result.']) };
      }
      return { campaign, validation };
    } catch (error) {
      if (error instanceof LpbfRunArchiveError) throw error;
      return { campaign: null, validation: unavailable(['Archived run or source integrity could not be verified.']) };
    } finally { runs?.close(); sources?.close(); }
  }

  async preview(runIds: unknown, caseNumber: unknown) {
    const built = await this.build(runIds, caseNumber);
    if (!built.campaign) return built;
    return { ...built, previewSha256: sha(JSON.stringify(built.campaign)) };
  }

  async create(runIds: unknown, caseNumber: unknown, previewSha256: unknown) {
    const built = await this.build(runIds, caseNumber);
    if (!built.campaign) return built;
    if (typeof previewSha256 !== 'string' || previewSha256 !== sha(JSON.stringify(built.campaign))) {
      throw new LpbfRunArchiveError(409, 'Campaign preview changed; preview the archived runs again.');
    }
    const repository = new LpbfRunRepository(path.join(this.runRoot, 'runs.sqlite'));
    try { return { ...built, record: repository.saveProxyCampaign(built.campaign) }; }
    finally { repository.close(); }
  }
}
