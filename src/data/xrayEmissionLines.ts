// Characteristic X-ray emission line energies used for EDS peak identification.
//
// Every energy below is copied, in electron volts and as printed, from the
// X-Ray Data Booklet (Center for X-ray Optics and Advanced Light Source,
// Lawrence Berkeley National Laboratory), Table 1-2 "Photon energies, in
// electron volts, of principal K-, L-, and M-shell emission lines". The booklet
// attributes the values to J. A. Bearden, "X-Ray Wavelengths", Rev. Mod. Phys.
// 39, 78 (1967). The PDF was downloaded and read for this file; see
// XRAY_EMISSION_LINES_SOURCE.
//
// Naming: "Ka" is the booklet's K-alpha-1 energy. K-alpha-1 and K-alpha-2 are
// not resolved by an EDS detector (a few to tens of eV apart), so the tabulated
// K-alpha-1 value stands for the unresolved K-alpha doublet. "La" is L-alpha-1,
// "Lb" is L-beta-1, "Kb" is K-beta-1 and "Ma" is M-alpha-1. For the 3d metals
// (Ti-Zn) the booklet prints identical L-alpha-1 and L-alpha-2 values.
//
// Only a subset of elements is listed (those common in metallurgical EDS). An
// element that is absent here is simply not offered as a candidate; the peak
// table never claims an element is absent from the sample.

export const XRAY_EMISSION_LINES_SOURCE = {
  title: "X-Ray Data Booklet, Table 1-2: Photon energies, in electron volts, of principal K-, L-, and M-shell emission lines",
  publisher: "Center for X-ray Optics and Advanced Light Source, Lawrence Berkeley National Laboratory",
  originalReference: "J. A. Bearden, Rev. Mod. Phys. 39, 78 (1967)",
  url: "https://xdb.lbl.gov/Section1/Table_1-2.pdf",
  retrievedOn: "2026-10-04",
  fileBytes: 104531,
  fileSha256: "7f7d412c1fc1b9ddaa5729b2987d597e58ef0ba435491d502deeb44de6868d81",
} as const;

export type EmissionLineName = "Ka" | "Kb" | "La" | "Lb" | "Ma";

export interface EmissionLine {
  element: string;
  atomicNumber: number;
  line: EmissionLineName;
  /** Photon energy in eV exactly as printed in the booklet. */
  energyEv: number;
}

interface ElementLineRecord {
  z: number;
  Ka?: number;
  Kb?: number;
  La?: number;
  Lb?: number;
  Ma?: number;
}

const ELEMENT_LINES: Record<string, ElementLineRecord> = {
  B: { z: 5, Ka: 183.3 },
  C: { z: 6, Ka: 277 },
  N: { z: 7, Ka: 392.4 },
  O: { z: 8, Ka: 524.9 },
  Mg: { z: 12, Ka: 1253.60, Kb: 1302.2 },
  Al: { z: 13, Ka: 1486.70, Kb: 1557.45 },
  Si: { z: 14, Ka: 1739.98, Kb: 1835.94 },
  P: { z: 15, Ka: 2013.7, Kb: 2139.1 },
  S: { z: 16, Ka: 2307.84, Kb: 2464.04 },
  Ti: { z: 22, Ka: 4510.84, Kb: 4931.81, La: 452.2, Lb: 458.4 },
  V: { z: 23, Ka: 4952.20, Kb: 5427.29, La: 511.3, Lb: 519.2 },
  Cr: { z: 24, Ka: 5414.72, Kb: 5946.71, La: 572.8, Lb: 582.8 },
  Mn: { z: 25, Ka: 5898.75, Kb: 6490.45, La: 637.4, Lb: 648.8 },
  Fe: { z: 26, Ka: 6403.84, Kb: 7057.98, La: 705.0, Lb: 718.5 },
  Co: { z: 27, Ka: 6930.32, Kb: 7649.43, La: 776.2, Lb: 791.4 },
  Ni: { z: 28, Ka: 7478.15, Kb: 8264.66, La: 851.5, Lb: 868.8 },
  Cu: { z: 29, Ka: 8047.78, Kb: 8905.29, La: 929.7, Lb: 949.8 },
  Zn: { z: 30, Ka: 8638.86, Kb: 9572.0, La: 1011.7, Lb: 1034.7 },
  Y: { z: 39, Ka: 14958.4, Kb: 16737.8, La: 1922.56, Lb: 1995.84 },
  Zr: { z: 40, Ka: 15775.1, Kb: 17667.8, La: 2042.36, Lb: 2124.4 },
  Nb: { z: 41, Ka: 16615.1, Kb: 18622.5, La: 2165.89, Lb: 2257.4 },
  Mo: { z: 42, Ka: 17479.34, Kb: 19608.3, La: 2293.16, Lb: 2394.81 },
  // K lines of Hf-Re (55-69 keV) are far outside any SEM-EDS range and are not listed.
  Hf: { z: 72, La: 7899.0, Lb: 9022.7, Ma: 1644.6 },
  Ta: { z: 73, La: 8146.1, Lb: 9343.1, Ma: 1710 },
  W: { z: 74, La: 8397.6, Lb: 9672.35, Ma: 1775.4 },
  Re: { z: 75, La: 8652.5, Lb: 10010.0, Ma: 1842.5 },
};

const LINE_ORDER: EmissionLineName[] = ["Ka", "Kb", "La", "Lb", "Ma"];

/** Flat list of every tabulated line, ordered by atomic number and then K, L, M. */
export const XRAY_EMISSION_LINES: readonly EmissionLine[] = Object.entries(ELEMENT_LINES)
  .sort((a, b) => a[1].z - b[1].z)
  .flatMap(([element, record]) =>
    LINE_ORDER.flatMap((line): EmissionLine[] => {
      const energyEv = record[line];
      return energyEv === undefined ? [] : [{ element, atomicNumber: record.z, line, energyEv }];
    }),
  );

export const XRAY_EMISSION_LINE_ELEMENTS: readonly string[] = Object.keys(ELEMENT_LINES);

export function lineLabel(line: Pick<EmissionLine, "element" | "line">): string {
  return `${line.element} ${line.line}`;
}

export function findEmissionLine(element: string, line: EmissionLineName): EmissionLine | undefined {
  return XRAY_EMISSION_LINES.find(entry => entry.element === element && entry.line === line);
}
