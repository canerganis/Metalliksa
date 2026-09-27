type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
export interface LpbfSourceDocument {
  schemaVersion: 1;
  datasetId: string;
  materialId: 'ti6al4v' | 'ss316l' | 'alsi10mg' | 'in718' | 'in625';
  processScope: 'bare-plate' | 'powder-bed' | 'unknown' | 'material-characterization';
  source: { url: string; citation: string; version: string; terms: string | null; termsMissingReason: string | null };
  artifacts: { relativePath: string; sha256: string; byteSize: number; sourceUrl: string }[];
  sourceContext: { [key: string]: Json } | null;
}
export interface LpbfSourceRevision {
  revision: number;
  createdAt: string;
  document: LpbfSourceDocument;
  documentSha256: string;
  evidenceStatus: 'unreviewed-source-archive';
  artifactIntegrity: 'not-verified';
}
