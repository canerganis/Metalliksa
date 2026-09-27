export interface RunSourceLink {
  datasetId: string;
  revision: number;
  documentSha256: string;
}

export interface RunCapture {
  schemaVersion: 1;
  jobId: string;
  resultJson: string;
  inputJson: string;
  materialJson: string;
  contractStatus: 'core-v1-bound' | 'legacy-unbound' | 'gpu-pilot-v1-bound' | 'gpu-pilot-v2-warp-bound';
  runKind?: RunKind;
}

export type RunKind = 'analytical-screening' | 'build-screening' | 'transient-thermal' | 'bounded-material-screening' | 'gpu-thermal-pilot' | 'legacy-unspecified';

export interface RunDocument {
  schemaVersion: 1;
  runId: string;
  capture: RunCapture;
  sources: RunSourceLink[];
}

export type RunSourceBindingStatus = 'exact-revision-bound' | 'legacy-unlinked';

export interface RunRecord {
  document: RunDocument;
  documentSha256: string;
  createdAt: string;
  evidenceStatus: 'unvalidated-model';
  sourceBindingStatus: RunSourceBindingStatus;
  runKind: RunKind;
}

export type NistOpticalCaseNumber = '0' | '1.1' | '1.2' | '2.1' | '2.2' | '3.1' | '3.2';

export interface NistOpticalError {
  signed_um: number;
  absolute_um: number;
  measuredMean_um: number;
  publishedStdDev_um: number;
  model_um: number;
}

export interface NistOpticalReport {
  schemaVersion: 1;
  benchmark: 'AMB2022-03-TMPG';
  caseNumber: NistOpticalCaseNumber;
  status: 'unavailable' | 'comparable-screening';
  validationStatus: 'unvalidated';
  reference: {
    doi: '10.18434/mds2-2718';
    results: string;
    resultsLocator: string;
    methods: string;
    measurement: string;
    archiveKind: string;
  };
  sourceBinding: (RunSourceLink & { sourceDatasetId: 'nist-mds2-2718'; artifactSha256: string }) | null;
  reasons: string[];
  errors: { width: NistOpticalError; depth: NistOpticalError } | null;
}
