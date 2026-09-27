/** Read-only AMB2022-03 optical comparison against an exact local archive binding. */
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { lstatSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { artifactDirectory, LpbfArtifactStore } from './lpbfArtifactStore';
import { LpbfRunArchiveError, LpbfRunArchiveService } from './lpbfRunArchiveService';
import { runArtifacts } from './lpbfRunImport';
import { LpbfSourceRepository } from './lpbfSourceRepository';
import { getHostPython } from './pythonRuntime';

const DATASET_ID = 'nist-amb2022-03-optical-table4-local-v1';
const PUBLISHER_ID = 'nist-mds2-2718';
const TABLE_SHA256 = 'd1b36dfa2e01a3537093c481e249ce52df6b8879c1c67480ddb9aa10799133da';
const TABLE_BYTES = 4321;
const TABLE_PATH = 'table4-aggregate-v2.json';
const RESULTS_URL = 'https://www.nist.gov/document/am-bench-amb2022-03-measurement-and-result-descriptions-v10';
const METHODS_URL = 'https://www.nist.gov/document/amb2022-03-measurement-and-challenge-descriptions-version-101';
const CASES = new Set(['0', '1.1', '1.2', '2.1', '2.2', '3.1', '3.2']);

function unavailable(caseNumber: string, reasons: string[]) {
  return { schemaVersion: 1, benchmark: 'AMB2022-03-TMPG', caseNumber,
    status: 'unavailable' as const, validationStatus: 'unvalidated' as const,
    reference: { doi: '10.18434/mds2-2718', results: RESULTS_URL,
      resultsLocator: 'Table 4, CHAL-AMB2022-03-TMPG', methods: METHODS_URL,
      measurement: 'six optical cross-section depth/width measurements per condition',
      archiveKind: 'local transcription of published aggregate means and standard deviations' },
    sourceBinding: null, reasons, errors: null };
}

function pythonCompare(file: string, payload: unknown): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const python = getHostPython();
    const child = spawn(python.cmd, [...python.prefix, '-u', file], {
      cwd: path.resolve(), windowsHide: true, shell: false, stdio: 'pipe',
    });
    let stdout = '', stderr = '', finished = false;
    const fail = (error: Error) => { if (!finished) { finished = true; clearTimeout(timer); reject(error); } };
    const timer = setTimeout(() => { child.kill(); fail(new Error('NIST comparison timed out')); }, 15000);
    child.stdout.on('data', chunk => {
      stdout += chunk.toString();
      if (stdout.length > 1024 * 1024) { child.kill(); fail(new Error('NIST comparison output exceeds limit')); }
    });
    child.stderr.on('data', chunk => { stderr = (stderr + chunk.toString()).slice(-2048); });
    child.on('error', fail);
    child.on('close', code => {
      if (finished) return;
      if (code !== 0) { fail(new Error(`NIST comparison process failed: ${stderr}`)); return; }
      try { const report = JSON.parse(stdout); finished = true; clearTimeout(timer); resolve(report); }
      catch { fail(new Error('Invalid NIST comparison output')); }
    });
    child.stdin.on('error', fail);
    child.stdin.end(JSON.stringify(payload));
  });
}

export class LpbfNistComparisonService {
  private readonly runs: LpbfRunArchiveService;
  constructor(
    private readonly runRoot = path.resolve(process.env.METALLIKSA_LPBF_RUN_ROOT || '.lpbf-runs'),
    private readonly sourceRoot = path.resolve(process.env.METALLIKSA_LPBF_SOURCE_ROOT || '.lpbf-sources'),
    private readonly pythonFile = path.resolve('python/lpbf_nist_in718_comparison.py'),
  ) { this.runs = new LpbfRunArchiveService(runRoot, sourceRoot); }

  async compare(runId: string, caseNumber: string) {
    if (!/^[a-f0-9]{32}$/.test(runId)) throw new LpbfRunArchiveError(400, 'Invalid run id.');
    if (typeof caseNumber !== 'string' || !CASES.has(caseNumber)) {
      throw new LpbfRunArchiveError(400, 'Select a published Table 4 case number.');
    }
    const record = this.runs.get(runId);
    const result = JSON.parse(record.document.capture.resultJson);
    if (record.runKind === 'gpu-thermal-pilot') {
      return unavailable(caseNumber, ['GPU thermal-pilot archives are separate parity evidence and are not eligible for CPU-core NIST optical comparison.']);
    }
    if (record.runKind === 'analytical-screening') {
      return unavailable(caseNumber, ['Analytical screening has no transient thermal evolution and is not eligible for NIST optical comparison.']);
    }
    if (record.runKind === 'build-screening' || result.settings?.jobType === 'build-job') {
      return unavailable(caseNumber, ['Build-job screening captures are not eligible for NIST optical comparison.']);
    }
    if (record.runKind === 'bounded-material-screening') {
      return unavailable(caseNumber, ['The bounded IN625 bare-plate field model has no matched IN718 Table 4 comparison contract.']);
    }
    if (record.document.capture.contractStatus !== 'core-v1-bound') {
      return unavailable(caseNumber, ['Archived run has no executed core contract; legacy runs cannot be compared to optical Table 4.']);
    }
    const links = record.document.sources.filter(link => link.datasetId === DATASET_ID);
    if (links.length !== 1) {
      return unavailable(caseNumber, ['Archived run is not bound to exactly one local AMB2022-03 Table 4 source revision.']);
    }
    const link = links[0];
    let revision;
    try {
      artifactDirectory(this.sourceRoot);
      const filename = path.join(this.sourceRoot, 'metadata.sqlite');
      if (lstatSync(filename).isSymbolicLink()) throw new Error('Source metadata link');
      const repository = new LpbfSourceRepository(filename, { readOnly: true });
      try { revision = repository.revision(link.datasetId, link.revision); }
      finally { repository.close(); }
    } catch {
      return unavailable(caseNumber, ['Exact archived Table 4 source revision is unavailable or failed metadata integrity verification.']);
    }
    if (!revision || revision.documentSha256 !== link.documentSha256) {
      return unavailable(caseNumber, ['Run source revision or document SHA-256 differs from the archived Table 4 record.']);
    }
    const document = revision.document;
    const artifact = document.artifacts[0];
    if (document.datasetId !== DATASET_ID || document.materialId !== 'in718'
      || document.processScope !== 'bare-plate' || document.source.url !== 'https://doi.org/10.18434/mds2-2718'
      || document.artifacts.length !== 1 || artifact?.relativePath !== TABLE_PATH
      || artifact.sha256 !== TABLE_SHA256 || artifact.byteSize !== TABLE_BYTES
      || artifact.sourceUrl !== RESULTS_URL) {
      return unavailable(caseNumber, ['Archived Table 4 source identity or fixed transcription artifact differs from the reviewed local revision.']);
    }
    let table4Json: string;
    try {
      const sourceStore = new LpbfArtifactStore(path.join(this.sourceRoot, 'artifacts'), { readOnly: true });
      const verified = await sourceStore.verify(artifact);
      const bytes = readFileSync(verified.path);
      if (bytes.length !== TABLE_BYTES || createHash('sha256').update(bytes).digest('hex') !== TABLE_SHA256) {
        throw new Error('Table 4 bytes changed after verification');
      }
      table4Json = bytes.toString('utf8');
    } catch {
      return unavailable(caseNumber, ['Archived Table 4 transcription bytes are missing or fail the fixed SHA-256 check.']);
    }
    let archivedArtifacts: ReturnType<typeof runArtifacts>;
    try {
      const runStore = new LpbfArtifactStore(path.join(this.runRoot, 'artifacts'), { readOnly: true });
      archivedArtifacts = runArtifacts(record.document);
      for (const artifactRef of archivedArtifacts) await runStore.verify(artifactRef);
    } catch {
      return unavailable(caseNumber, ['Archived run output artifact bytes are missing or failed integrity verification.']);
    }
    const beamEvidence = result.measuredBeamProfileEvidence;
    if (beamEvidence?.profileArtifactVerified === true
      && !archivedArtifacts.some(ref => ref.sha256 === beamEvidence.profileSha256)) {
      return unavailable(caseNumber, ['Claimed measured beam profile SHA-256 is not present in verified run artifacts.']);
    }
    const sourceBinding = { datasetId: DATASET_ID, sourceDatasetId: PUBLISHER_ID,
      artifactSha256: TABLE_SHA256, revision: link.revision, documentSha256: link.documentSha256 };
    try {
      // Keep the archived JSON number lexemes intact: JavaScript round-tripping 285.0
      // into 285 changes the Python-canonical material and Table 4 content hashes.
      const report = await pythonCompare(this.pythonFile, { resultJson: record.document.capture.resultJson,
        table4Json, sourceBinding,
        expectedSourceBinding: sourceBinding, caseNumber });
      if (!report || typeof report !== 'object' || (report as any).schemaVersion !== 1
        || !['unavailable', 'comparable-screening'].includes((report as any).status)
        || (report as any).caseNumber !== caseNumber) throw new Error('Invalid NIST report schema');
      return report;
    } catch {
      return unavailable(caseNumber, ['Optical comparison gate could not execute or returned an invalid report.']);
    }
  }
}
