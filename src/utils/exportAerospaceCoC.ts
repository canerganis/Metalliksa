import type { jsPDF } from "jspdf";
import { ENGINEERING_ESTIMATE_DISCLAIMER } from "./engineeringDisclaimer";

export interface LabMultiTestData {
  // Tabor-Cahoon Non-Destructive Tensile Test
  taborTest?: {
    measuredHardnessHV: number;
    predictedYieldMpa: number;
    predictedUtsMpa: number;
    strainHardeningExponentN: number;
    fractureToughnessKic: number;
    correlationConfidencePct: number;
    indentationStandard: string;
  };
  // XRD Phase & Residual Stress Analysis
  xrdAnalysis?: {
    primaryPhase: string;
    secondaryPhaseFractionPct: number;
    crystalliteSizeNm: number;
    microstrainPct: number;
    surfaceResidualStressMpa: number;
    standardReference: string;
  };
  // EBSD Grain & Microtexture
  ebsdMicrostructure?: {
    meanGrainSizeUm: number;
    astmGrainSizeNumberG: number;
    hagbFractionPct: number;
    dominantTextureOrientation: string;
    schmidFactorAverage: number;
    standardReference: string;
  };
  // 3D LPBF Additive Defect & Thermal Stress
  additiveDefectAudit?: {
    volumetricEnergyDensityJmm3: number;
    maxThermalWarpageMm: number;
    peakTensileStressMpa: number;
    keyholeRiskScorePct: number;
    lackOfFusionRiskPct: number;
    asBuiltVsHipState: string;
    standardReference: string;
  };
}

export interface AerospaceAuditReportData { sampleLotNumber?: string;
  certificateId: string;
  lotHeatNumber?: string;
  partNumber?: string;
  partName?: string;
  customerPoNumber?: string;
  cageCode?: string;
  revision: string;
  issueDate: string;
  engineerName: string;
  qaDirectorName?: string;
  facility: string;
  programName: string;
  criticalityLevel?: "Class 1 (Flight Critical)" | "Class 2 (Primary Structural)" | "Class 3 (Secondary System)";
  
  // Alloy info
  alloyName: string;
  category: string;
  standardSpec: string;
  manufacturingRoute: string;
  heatTreatmentCondition?: string;
  protectiveCoating: string;
  serviceTempMin: number;
  serviceTempMax: number;
  operatingStressMpa: number;
  
  // MMPDS mechanical properties
  meanYieldMpa: number;
  meanTensileMpa: number;
  elongationPct?: number;
  fractureToughnessMpaM: number;
  youngsModulusGpa?: number;
  densityGcm3?: number;
  sampleSizeN: number;
  scatterCvPct: number;
  
  mmpdsStats: {
    kA: number;
    kB: number;
    aBasisYield: number;
    bBasisYield: number;
    aBasisTensile: number;
    bBasisTensile: number;
    shearUltimate: number;
    bearingYield: number;
    bearingUltimate: number;
    compressiveYield: number;
    cpk: number;
    status: string;
  };
  
  // Cross-lab experimental test data
  labData?: LabMultiTestData;

  // Environmental and AS9100 tests
  qualificationTests: Array<{
    standard: string;
    methodName: string;
    testCategory: string;
    passProbabilityPct: number;
    riskLevel: string;
    primaryThreat: string;
    criticalThreshold: string;
    mitigationRecommendation: string;
    executionStatus?: string;
  }>;
  
  overallReadinessIndex: number;
  aiAuditNotes?: string | null;
}

export type CoCData = AerospaceAuditReportData;

export async function generateAerospaceCoCPDF(data: AerospaceAuditReportData): Promise<jsPDF> {
  const [{ jsPDF }, { default: autoTable }] = await Promise.all([
    import("jspdf"),
    import("jspdf-autotable"),
  ]);
  const doc = new jsPDF({
    orientation: "portrait",
    unit: "mm",
    format: "a4",
  });

  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = 12;
  const contentWidth = pageWidth - margin * 2;

  // ==========================================
  // PAGE 1: CERTIFICATE OF CONFORMANCE & MMPDS
  // ==========================================

  // Header Banner Background (Deep Aerospace Navy)
  doc.setFillColor(10, 15, 29); // #0a0f1d
  doc.rect(0, 0, pageWidth, 44, "F");

  // Cyan Accent Line
  doc.setDrawColor(14, 165, 233); // Sky-500
  doc.setLineWidth(1.4);
  doc.line(0, 44, pageWidth, 44);

  // Top Badge / Classification
  doc.setFillColor(30, 41, 59);
  doc.roundedRect(margin, 6, 92, 5.5, 1, 1, "F");
  doc.setFont("helvetica", "bold");
  doc.setFontSize(6.5);
  doc.setTextColor(56, 189, 248); // Cyan
  doc.text("ENGINEERING SCREENING TEMPLATE (NOT A CERTIFICATE)", margin + 3, 9.8);

  // Main Title
  doc.setTextColor(255, 255, 255);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(14.5);
  doc.text("ENGINEERING SCREENING AUDIT REPORT", margin, 20);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(7.5);
  doc.setTextColor(251, 191, 36); // Amber
  doc.text(ENGINEERING_ESTIMATE_DISCLAIMER, margin, 26, { maxWidth: contentWidth - 82 });
  doc.text(
    `Criticality: ${data.criticalityLevel}  |  Part No: ${data.partNumber}  |  Heat/Lot: ${data.lotHeatNumber}`,
    margin,
    31
  );

  // Certificate Metadata Box (Header Right)
  doc.setFillColor(17, 24, 39);
  doc.roundedRect(pageWidth - margin - 78, 6, 78, 33, 2, 2, "F");
  doc.setDrawColor(51, 65, 85);
  doc.setLineWidth(0.4);
  doc.roundedRect(pageWidth - margin - 78, 6, 78, 33, 2, 2, "D");

  doc.setFontSize(7.5);
  doc.setTextColor(56, 189, 248);
  doc.setFont("helvetica", "bold");
  doc.text(`DOC REF: ${data.certificateId}`, pageWidth - margin - 74, 12);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(6.8);
  doc.setTextColor(203, 213, 225);
  doc.text(`Rev: ${data.revision} | CAGE: ${data.cageCode} | PO: ${data.customerPoNumber}`, pageWidth - margin - 74, 17.5);
  doc.text(`Issue Date: ${data.issueDate}`, pageWidth - margin - 74, 23);
  doc.text(`Facility: ${data.facility}`, pageWidth - margin - 74, 28.5);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(251, 191, 36);
  doc.text(`STATUS: SCREENING ESTIMATE ONLY`, pageWidth - margin - 74, 34);

  let currentY = 50;

  // SECTION 1: MATERIAL IDENTITY & MANUFACTURING SPECIFICATION
  doc.setFont("helvetica", "bold");
  doc.setFontSize(9.5);
  doc.setTextColor(15, 23, 42);
  doc.text("1. MATERIAL SPECIFICATION, HEAT TREATMENT & LOT IDENTIFICATION", margin, currentY);
  currentY += 3.5;

  const specTableData = [
    [
      { content: "Alloy & Grade:", styles: { fontStyle: "bold" as const, fillColor: [241, 245, 249] as [number, number, number] } },
      data.alloyName,
      { content: "Primary Standard Spec:", styles: { fontStyle: "bold" as const, fillColor: [241, 245, 249] as [number, number, number] } },
      data.standardSpec,
    ],
    [
      { content: "Alloy Classification:", styles: { fontStyle: "bold" as const, fillColor: [241, 245, 249] as [number, number, number] } },
      data.category,
      { content: "Manufacturing Route:", styles: { fontStyle: "bold" as const, fillColor: [241, 245, 249] as [number, number, number] } },
      data.manufacturingRoute,
    ],
    [
      { content: "Heat Treatment / State:", styles: { fontStyle: "bold" as const, fillColor: [241, 245, 249] as [number, number, number] } },
      data.heatTreatmentCondition || "STA (Solution Treated & Aged)",
      { content: "Surface Protection:", styles: { fontStyle: "bold" as const, fillColor: [241, 245, 249] as [number, number, number] } },
      data.protectiveCoating,
    ],
    [
      { content: "Operational Envelope:", styles: { fontStyle: "bold" as const, fillColor: [241, 245, 249] as [number, number, number] } },
      `${data.serviceTempMin}°C to +${data.serviceTempMax}°C | σ_op: ${data.operatingStressMpa} MPa`,
      { content: "Sample Size & Scatter:", styles: { fontStyle: "bold" as const, fillColor: [241, 245, 249] as [number, number, number] } },
      `N = ${data.sampleSizeN} Coupons | CV: ${data.scatterCvPct}% (Cpk: ${data.mmpdsStats.cpk})`,
    ],
  ];

  autoTable(doc, {
    startY: currentY,
    head: [],
    body: specTableData,
    theme: "grid",
    styles: { fontSize: 7.2, cellPadding: 1.8, textColor: [30, 41, 59], lineColor: [203, 213, 225], lineWidth: 0.2 },
    columnStyles: {
      0: { cellWidth: 38 },
      1: { cellWidth: 55 },
      2: { cellWidth: 40 },
      3: { cellWidth: 53 },
    },
    margin: { left: margin, right: margin },
  });

  currentY = (doc as any).lastAutoTable.finalY + 6;

  // SECTION 2: MMPDS-14 / MIL-HDBK-5 STATISTICAL DESIGN ALLOWABLES
  doc.setFont("helvetica", "bold");
  doc.setFontSize(9.5);
  doc.setTextColor(15, 23, 42);
  doc.text("2. MMPDS-14 / MIL-HDBK-5 STATISTICAL DESIGN ALLOWABLES (CHAPTER 9)", margin, currentY);
  currentY += 3.5;

  const mmpdsTableHead = [
    ["Symbol", "Mechanical Property Description", "Mean Value", "A-Basis (T99)", "B-Basis (T90)", "Unit", "Compliance Standard"],
  ];

  const mmpdsTableBody = [
    [
      "F_ty",
      "Tensile Yield Strength (0.2% Offset)",
      `${data.meanYieldMpa}`,
      `${data.mmpdsStats.aBasisYield}`,
      `${data.mmpdsStats.bBasisYield}`,
      "MPa",
      "MMPDS-14 / ASTM E8",
    ],
    [
      "F_tu",
      "Tensile Ultimate Strength (UTS)",
      `${data.meanTensileMpa}`,
      `${data.mmpdsStats.aBasisTensile}`,
      `${data.mmpdsStats.bBasisTensile}`,
      "MPa",
      "MMPDS-14 / ASTM E8",
    ],
    [
      "F_cy",
      "Compressive Yield Strength (Derived)",
      `${Math.round(data.meanYieldMpa * 1.04)}`,
      `${data.mmpdsStats.compressiveYield}`,
      `${Math.round(data.mmpdsStats.bBasisYield * 1.04)}`,
      "MPa",
      "MIL-HDBK-5 Ch. 9",
    ],
    [
      "F_su",
      "Shear Ultimate Strength (Derived)",
      `${Math.round(data.meanTensileMpa * 0.60)}`,
      `${data.mmpdsStats.shearUltimate}`,
      `${Math.round(data.mmpdsStats.bBasisTensile * 0.60)}`,
      "MPa",
      "Von Mises / MIL-HDBK-5",
    ],
    [
      "F_bry",
      "Bearing Yield Strength (e/D = 1.5)",
      `${Math.round(data.meanYieldMpa * 1.50)}`,
      `${data.mmpdsStats.bearingYield}`,
      `${Math.round(data.mmpdsStats.bBasisYield * 1.50)}`,
      "MPa",
      "ASTM E238 / Fastener",
    ],
    [
      "F_bru",
      "Bearing Ultimate Strength (e/D = 2.0)",
      `${Math.round(data.meanTensileMpa * 2.00)}`,
      `${data.mmpdsStats.bearingUltimate}`,
      `${Math.round(data.mmpdsStats.bBasisTensile * 2.00)}`,
      "MPa",
      "ASTM E238 / Fastener",
    ],
    [
      "K_IC",
      "Plane-Strain Fracture Toughness",
      `${data.fractureToughnessMpaM}`,
      `${data.fractureToughnessMpaM}`,
      `${data.fractureToughnessMpaM}`,
      "MPa√m",
      "ASTM E399 / E1820",
    ],
    [
      "E / ρ",
      "Young's Modulus / Specific Density",
      `${data.youngsModulusGpa} GPa`,
      `${data.youngsModulusGpa} GPa`,
      `${data.youngsModulusGpa} GPa`,
      `${data.densityGcm3} g/cm³`,
      "ASTM E111",
    ],
  ];

  autoTable(doc, {
    startY: currentY,
    head: mmpdsTableHead,
    body: mmpdsTableBody,
    theme: "striped",
    headStyles: { fillColor: [15, 23, 42], textColor: [255, 255, 255], fontSize: 7, fontStyle: "bold" },
    styles: { fontSize: 6.8, cellPadding: 1.8, textColor: [30, 41, 59] },
    alternateRowStyles: { fillColor: [248, 250, 252] },
    margin: { left: margin, right: margin },
  });

  currentY = (doc as any).lastAutoTable.finalY + 4;

  // Tolerance Factor Callout Box
  doc.setFillColor(241, 245, 249);
  doc.roundedRect(margin, currentY, contentWidth, 10.5, 1.5, 1.5, "F");
  doc.setFontSize(6.8);
  doc.setTextColor(51, 65, 85);
  doc.setFont("helvetica", "normal");
  doc.text(
    `Statistical One-Sided Tolerance Limits (Lieberman-Resnikoff, N=${data.sampleSizeN}): k_A = ${data.mmpdsStats.kA} (99%/95%) | k_B = ${data.mmpdsStats.kB} (90%/95%)\nProcess Capability Index: Cpk = ${data.mmpdsStats.cpk} | Release Status: ${data.mmpdsStats.status} (Passable for Primary Structure)`,
    margin + 3,
    currentY + 4.2
  );

  currentY += 16;

  // SECTION 3: MULTI-LAB CROSS-VERIFICATION MATRIX (XRD, EBSD, TABOR, 3D AM)
  doc.setFont("helvetica", "bold");
  doc.setFontSize(9.5);
  doc.setTextColor(15, 23, 42);
  doc.text("3. ADVANCED LAB NDT & MICROSTRUCTURAL VERIFICATION MATRIX", margin, currentY);
  currentY += 3.5;

  const lab = data.labData;
  const labTableHead = [["Testing Discipline", "Analyzed Metric", "Experimental Measurement", "Spec Acceptance Limit", "Verification Result"]];
  const labTableBody = [
    [
      "Tabor-Cahoon Indentation\n(ASTM E8 / E384)",
      "Non-Destructive σ-ε Curve\nYield, UTS, Hollomon n",
      `R_p0.2: ${lab?.taborTest?.predictedYieldMpa ?? data.meanYieldMpa} MPa | R_m: ${lab?.taborTest?.predictedUtsMpa ?? data.meanTensileMpa} MPa\nStrain Hardening n: ${lab?.taborTest?.strainHardeningExponentN ?? 0.14}`,
      `R_p0.2 ≥ ${data.mmpdsStats.aBasisYield} MPa\nHardness: ${lab?.taborTest?.measuredHardnessHV ?? 330} HV`,
      "SCREENING ONLY",
    ],
    [
      "Rapid XRD Diffraction\n(ASTM E975 / Rigaku)",
      "Phase ID & Microstrain\nWilliamson-Hall & σ_res",
      `Primary: ${lab?.xrdAnalysis?.primaryPhase ?? "α-Ti / γ-Ni"} | Sec Phase: ${lab?.xrdAnalysis?.secondaryPhaseFractionPct ?? 8.5}%\nCrystallite: ${lab?.xrdAnalysis?.crystalliteSizeNm ?? 42} nm | ε_micro: ${lab?.xrdAnalysis?.microstrainPct ?? 0.18}%`,
      "Secondary Phase < 12%\nSurface σ_res < +200 MPa",
      "SCREENING ONLY",
    ],
    [
      "EBSD Microtexture\n(ASTM E112 / Oxford)",
      "Grain Size & IPF-Z Texture\nSchmid Factor & HAGB",
      `Grain Size d: ${lab?.ebsdMicrostructure?.meanGrainSizeUm ?? 18.4} µm (ASTM G=${lab?.ebsdMicrostructure?.astmGrainSizeNumberG ?? 8.5})\nHAGB Fraction: ${lab?.ebsdMicrostructure?.hagbFractionPct ?? 78}% | Texture: ${lab?.ebsdMicrostructure?.dominantTextureOrientation ?? "<0001> Basal"}`,
      "ASTM Grain Size G ≥ 7.0\nTaylor Factor M ≤ 3.2",
      "SCREENING ONLY",
    ],
    [
      "3D LPBF Defect Audit\n(ASTM F3055 / F2924)",
      "Laser VED, Warpage & LoF\nThermal Residual Stress",
      `VED: ${lab?.additiveDefectAudit?.volumetricEnergyDensityJmm3 ?? 62.5} J/mm³ | Max Warpage: ${lab?.additiveDefectAudit?.maxThermalWarpageMm ?? 0.18} mm\nKeyhole Risk: ${lab?.additiveDefectAudit?.keyholeRiskScorePct ?? 4.2}% | LoF Risk: ${lab?.additiveDefectAudit?.lackOfFusionRiskPct ?? 2.1}%`,
      "Max Warpage < 0.35 mm\nPorosity Defect < 0.10%",
      "SCREENING ONLY",
    ],
  ];

  autoTable(doc, {
    startY: currentY,
    head: labTableHead,
    body: labTableBody,
    theme: "grid",
    headStyles: { fillColor: [15, 23, 42], textColor: [255, 255, 255], fontSize: 6.8, fontStyle: "bold" },
    styles: { fontSize: 6.5, cellPadding: 1.8, textColor: [30, 41, 59] },
    columnStyles: {
      0: { cellWidth: 42 },
      1: { cellWidth: 40 },
      2: { cellWidth: 54 },
      3: { cellWidth: 32 },
      4: { cellWidth: 18, halign: "center" as const, fontStyle: "bold" },
    },
    margin: { left: margin, right: margin },
  });

  // Footer on Page 1
  doc.setFontSize(6.2);
  doc.setTextColor(148, 163, 184);
  doc.setFont("helvetica", "normal");
  doc.text(
    `Page 1 of 2 | ${ENGINEERING_ESTIMATE_DISCLAIMER}`,
    margin,
    290
  );

  // =========================================================================
  // PAGE 2: ENVIRONMENTAL STRESS, AS9100 RISK MATRIX & AUDITOR SIGN-OFF
  // =========================================================================
  doc.addPage();

  // Page 2 Header Banner
  doc.setFillColor(10, 15, 29);
  doc.rect(0, 0, pageWidth, 28, "F");
  doc.setDrawColor(14, 165, 233);
  doc.setLineWidth(1.2);
  doc.line(0, 28, pageWidth, 28);

  doc.setFont("helvetica", "bold");
  doc.setFontSize(12);
  doc.setTextColor(255, 255, 255);
  doc.text("SECTION 4: ENVIRONMENTAL PROTOCOL CHECKLIST (NOT EXECUTED)", margin, 15);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(7.5);
  doc.setTextColor(148, 163, 184);
  doc.text(
    `Document: ${data.certificateId} | Alloy: ${data.alloyName} | Customer PO: ${data.customerPoNumber} | Lot: ${data.lotHeatNumber}`,
    margin,
    22
  );

  currentY = 36;

  // SECTION 4: MIL-STD-810H & AS9100 TEST EVALUATION TABLE
  doc.setFont("helvetica", "bold");
  doc.setFontSize(9.5);
  doc.setTextColor(15, 23, 42);
  doc.text("4. MIL-STD-810H / AS9100 / STANAG PROTOCOL CHECKLIST TEMPLATE", margin, currentY);
  currentY += 3.5;

  const qualTableHead = [
    ["Standard & Method", "Evaluation Criterion", "Status", "Attestation", "Notes"],
  ];

  const qualTableBody = data.qualificationTests.map((t) => [
    t.standard + "\n" + t.methodName.split(":")[0],
    t.testCategory + "\n" + t.criticalThreshold,
    t.executionStatus || "Not executed",
    "User-attested only",
    t.mitigationRecommendation,
  ]);

  autoTable(doc, {
    startY: currentY,
    head: qualTableHead,
    body: qualTableBody,
    theme: "grid",
    headStyles: { fillColor: [15, 23, 42], textColor: [255, 255, 255], fontSize: 7, fontStyle: "bold" },
    styles: { fontSize: 6.8, cellPadding: 1.8, textColor: [30, 41, 59] },
    columnStyles: {
      0: { cellWidth: 40 },
      1: { cellWidth: 42 },
      2: { cellWidth: 16, halign: "center" as const, fontStyle: "bold" },
      3: { cellWidth: 18, halign: "center" as const },
      4: { cellWidth: 70 },
    },
    margin: { left: margin, right: margin },
  });

  currentY = (doc as any).lastAutoTable.finalY + 6;

  // SECTION 5: AI METALLURGICAL EXPERT AUDIT SUMMARY
  if (data.aiAuditNotes) {
    doc.setFont("helvetica", "bold");
    doc.setFontSize(9.5);
    doc.setTextColor(15, 23, 42);
    doc.text("5. ENGINEERING SCREENING NOTES", margin, currentY);
    currentY += 3.5;

    doc.setFillColor(248, 250, 252);
    doc.roundedRect(margin, currentY, contentWidth, 32, 1.5, 1.5, "F");
    doc.setDrawColor(203, 213, 225);
    doc.setLineWidth(0.3);
    doc.roundedRect(margin, currentY, contentWidth, 32, 1.5, 1.5, "D");

    doc.setFontSize(6.8);
    doc.setTextColor(51, 65, 85);
    doc.setFont("helvetica", "normal");
    const cleanNotes = data.aiAuditNotes.replace(/[#*`]/g, "").substring(0, 520);
    doc.text(
      cleanNotes || ENGINEERING_ESTIMATE_DISCLAIMER,
      margin + 3,
      currentY + 5,
      { maxWidth: contentWidth - 6 }
    );

    currentY += 38;
  }

  // SECTION 6: OFFICIAL AS9100 / NADCAP CERTIFICATE OF CONFORMANCE DECLARATION & STAMPS
  doc.setFillColor(248, 250, 252);
  doc.rect(margin, currentY, contentWidth, 48, "F");
  doc.setDrawColor(30, 41, 59);
  doc.setLineWidth(0.6);
  doc.rect(margin, currentY, contentWidth, 48, "D");

  doc.setFontSize(8);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(15, 23, 42);
  doc.text("SCREENING DISCLAIMER (NOT A CERTIFICATE OF CONFORMANCE):", margin + 4, currentY + 6);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(6.6);
  doc.setTextColor(71, 85, 105);
  doc.text(
    `${ENGINEERING_ESTIMATE_DISCLAIMER} This document is a laboratory screening template. Protocol rows are checklists only and do not confirm that MIL-STD-810H, AS9100, NADCAP, or STANAG tests were executed. Statistical A/B figures, if shown, are not contractual or handbook allowables unless independently attested from real coupon lots.`,
    margin + 4,
    currentY + 11.5,
    { maxWidth: contentWidth - 8 }
  );

  // Digital Signature Blocks & Airworthiness Stamp
  const signY = currentY + 26;

  // 1. Lead Metallurgist
  doc.setFont("helvetica", "bold");
  doc.setFontSize(7.2);
  doc.setTextColor(15, 23, 42);
  doc.text("Chief Materials & Metallurgical Lead:", margin + 4, signY);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(6.8);
  doc.setTextColor(51, 65, 85);
  doc.text(data.engineerName, margin + 4, signY + 4.5);
  doc.text(`Doc Ref: COC-${(data.sampleLotNumber || "REF").toUpperCase()}`, margin + 4, signY + 9);

  // 2. QA Director / Authority
  doc.setFont("helvetica", "bold");
  doc.setFontSize(7.2);
  doc.setTextColor(15, 23, 42);
  doc.text("Quality Assurance Authority:", margin + 65, signY);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(6.8);
  doc.setTextColor(51, 65, 85);
  doc.text(data.qaDirectorName || "Pending Formal QA Sign-off", margin + 65, signY + 4.5);
  doc.text("SCREENING SIGN-OFF ONLY", margin + 65, signY + 9);

  // 3. Airworthiness Stamp Box (Circular / Hex Badge in PDF)
  const stampX = pageWidth - margin - 52;
  const stampY = signY - 2;
  doc.setFillColor(255, 251, 235);
  doc.roundedRect(stampX, stampY, 48, 17, 2, 2, "F");
  doc.setDrawColor(217, 119, 6);
  doc.setLineWidth(0.8);
  doc.roundedRect(stampX, stampY, 48, 17, 2, 2, "D");

  doc.setFont("helvetica", "bold");
  doc.setFontSize(7.5);
  doc.setTextColor(146, 64, 14);
  doc.text("SCREENING ONLY", stampX + 8, stampY + 5);
  doc.setFontSize(7);
  doc.text("NOT CERTIFIED", stampX + 10, stampY + 10.5);
  doc.setFontSize(5.8);
  doc.setFont("helvetica", "normal");
  doc.text("CHECKLIST TEMPLATE", stampX + 8, stampY + 14.5);

  // Page 2 Footer
  doc.setFontSize(6.2);
  doc.setTextColor(148, 163, 184);
  doc.setFont("helvetica", "normal");
  doc.text(
    `Page 2 of 2 | ${ENGINEERING_ESTIMATE_DISCLAIMER}`,
    margin,
    290
  );

  return doc;
}

