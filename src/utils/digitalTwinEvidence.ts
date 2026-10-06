import type { DigitalTwinReportedClaims, SampleDigitalTwin } from "../types/digitalTwin";

/** Keep source declarations in JSON exports while effective scope remains not assessed.
 * Repeated hydration/export must never replace the backup with downgraded UI values.
 */
function preserveReportedClaims(twin: Partial<SampleDigitalTwin>): DigitalTwinReportedClaims | undefined {
  if (twin.evidence?.reportedClaims) return structuredClone(twin.evidence.reportedClaims);
  if (twin.currentStatus === undefined && twin.certification === undefined && twin.mechanical?.mmpdsStatisticalBasis === undefined) return undefined;
  return structuredClone({
    verification: "unverified" as const,
    currentStatus: twin.currentStatus,
    certification: twin.certification,
    mmpdsStatisticalBasis: twin.mechanical?.mmpdsStatisticalBasis,
  });
}

/** Missing physical quantities are null; zero must remain a real supplied value. */
export function createUnresolvedDigitalTwin(base: Partial<SampleDigitalTwin> = {}): SampleDigitalTwin {
  const date = new Date().toISOString().split("T")[0];
  const id = globalThis.crypto.randomUUID();
  const empty: SampleDigitalTwin = {
    id: `twin-${id}`, serialNumber: `TWIN-${id.slice(0, 8)}`, sampleName: "New material specimen",
    materialCategory: "Unresolved", standardDesignation: "Unresolved", creationDate: date, lastUpdated: date,
    leadMetallurgist: "Unassigned", organization: "Unassigned", currentStatus: "R&D Prototype", attachments: [],
    evidence: { kind: "unresolved", note: "Empty specimen record. No measurements, simulations or qualification evidence supplied.", qualification: "not-assessed" },
    chemistry: { baseElement: "Unresolved", nominalComposition: {} },
    thermodynamics: { calphadSystemId: "Unresolved", liquidusTemperatureC: null, solidusTemperatureC: null, freezingRangeC: null, stablePhasesAtRoomTemp: [], scheilSolidification: { eutecticFractionPct: null, hotTearingIndexKou: null, microsegregationSeverity: "Unresolved" } },
    processHistory: { manufacturingRoute: "Unresolved", currentCondition: "Unresolved", thermalCycles: [] },
    microstructure: { primaryCrystalStructure: "Unresolved", astmGrainSizeNumber: null, meanGrainDiameterUm: null, porosityPct: null, phasesDetected: [], ebsdTexture: { preferredOrientation: "Unresolved", misorientationAngleMeanDeg: null, lowAngleBoundaryPct: null, highAngleBoundaryPct: null, kosselSchmidFactorMean: null }, xrdVerification: { primaryPeaks: [], residualStressSin2PsiMpa: null, crystalliteSizeNm: null }, edsPurityPurityPct: null },
    mechanical: { yieldStrengthMpa: null, ultimateTensileStrengthMpa: null, elongationPct: null, reductionOfAreaPct: null, hardness: { value: null, scale: "Unresolved" }, mmpdsStatisticalBasis: { basisLevel: "Not assessed", sampleCountN: 0, cpkReliability: null } },
    electrochemistry: { corrosionRateMpy: null, openCircuitPotentialEcorrV: null, polarizationResistanceRpOhmCm2: null, eisImpedanceModuleOhm: null, passivationQuality: "Unresolved" },
    extremeService: { operatingMaxTempC: null, thermalConductivityW_mK: null, thermalDiffusivityMm2_s: null, oxidationResistanceCategory: "Unresolved" },
    certification: { applicableStandards: [], aerospaceFlightReadinessScorePct: null, qualificationAuditStatus: "Not assessed", complianceRiskLevel: "Unresolved", nonDestructiveTestResults: { ultrasonicInspection: "Pending", xrayRadiography: "Pending", surfaceDyePenetrant: "Pending" } },
  };
  return {
    ...empty, ...base, id: empty.id, serialNumber: empty.serialNumber,
    evidence: { ...empty.evidence!, kind: Object.keys(base).length ? "user-supplied" : "unresolved", note: Object.keys(base).length ? "User-supplied record; source and measurement conditions require review. Original declared claims are preserved as unverified reportedClaims in exports." : empty.evidence!.note, reportedClaims: preserveReportedClaims(base) },
    currentStatus: "R&D Prototype", certification: { ...empty.certification, applicableStandards: base.certification?.applicableStandards ?? [] },
    mechanical: { ...(base.mechanical ?? empty.mechanical), mmpdsStatisticalBasis: empty.mechanical.mmpdsStatisticalBasis },
  };
}

export function labelTwinEvidence(twin: SampleDigitalTwin, demoIds: readonly string[]): SampleDigitalTwin {
  const demo = twin.evidence?.kind === "demo" || demoIds.includes(twin.id);
  return {
    ...twin,
    evidence: { kind: demo ? "demo" : twin.evidence?.kind ?? "user-supplied", qualification: "not-assessed", note: demo ? "Synthetic demonstration record. Values illustrate the interface and are not measured or validated evidence." : twin.evidence?.note ?? "Legacy or imported record. Source, measurement conditions and qualification have not been verified. Original declared claims are preserved as unverified reportedClaims in exports.", reportedClaims: preserveReportedClaims(twin) },
    currentStatus: "R&D Prototype",
    certification: { ...twin.certification, aerospaceFlightReadinessScorePct: null, qualificationAuditStatus: "Not assessed", complianceRiskLevel: "Unresolved", nonDestructiveTestResults: { ultrasonicInspection: "Pending", xrayRadiography: "Pending", surfaceDyePenetrant: "Pending" }, blockchainHashCertificate: undefined },
    // A synthetic record has no coupon population: derived statistics (Cpk, N) are scrubbed, not shown.
    mechanical: { ...twin.mechanical, mmpdsStatisticalBasis: { ...twin.mechanical.mmpdsStatisticalBasis, basisLevel: "Not assessed", ...(demo ? { sampleCountN: null, cpkReliability: null } : {}) } },
  };
}

/**
 * Apply a composition edit. Values derived from the old composition (Schaeffler / carbon
 * equivalent, liquidus / solidus / freezing range, stable phases, Scheil indices) no longer
 * describe the record, so they are cleared rather than left stale; nothing here recomputes them.
 */
export function withEditedComposition(twin: SampleDigitalTwin, composition: Record<string, number>): SampleDigitalTwin {
  return {
    ...twin,
    chemistry: { ...twin.chemistry, nominalComposition: composition, schaefflerCoordinates: undefined, carbonEquivalent: undefined },
    thermodynamics: {
      ...twin.thermodynamics,
      liquidusTemperatureC: null, solidusTemperatureC: null, freezingRangeC: null, stablePhasesAtRoomTemp: [],
      scheilSolidification: { eutecticFractionPct: null, hotTearingIndexKou: null, microsegregationSeverity: "Unresolved" },
    },
  };
}

/** Full-content download link for an attachment; never truncates the stored data. */
export function attachmentDownloadHref(data: string): string {
  if (data.startsWith("data:")) return data;
  return `data:application/octet-stream;charset=utf-8,${encodeURIComponent(data)}`;
}
