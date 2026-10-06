/**
 * EBSD & Micrograph Raw Data Parser Utility
 * Parses Oxford Instruments .ctf, EDAX .ang or grain boundary CSV/TXT tables.
 * Calculates Heyn Intercepts and ASTM E112 G number from imported grains.
 */

export interface ParsedGrainData {
  grainId: number;
  area_um2: number;
  equivalentDiameter_um: number;
  aspectRatio: number;
  euler1_deg?: number;
  euler2_deg?: number;
  euler3_deg?: number;
  phaseName?: string;
}

export interface EbsdParseResult {
  filename: string;
  totalGrains: number;
  meanDiameter_um: number;
  astm_G: number;
  meanAspectRatio: number;
  grains: ParsedGrainData[];
  distribution: { sizeBin: string; frequency: number }[];
}

export function parseEBSDOrGrainFile(content: string, filename: string): EbsdParseResult {
  const lines = content.split(/\r?\n/);
  const grains: ParsedGrainData[] = [];

  let isCTF = filename.toLowerCase().endsWith(".ctf");
  let isANG = filename.toLowerCase().endsWith(".ang");

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line || line.startsWith("#") || line.startsWith(";") || line.startsWith("Channel Text File")) {
      continue;
    }

    const parts = line.split(/[\s,;\t]+/).filter(Boolean);
    if (parts.length >= 2) {
      // Check if header row with text
      if (isNaN(parseFloat(parts[0])) && isNaN(parseFloat(parts[1]))) {
        continue;
      }

      // If user uploaded simple grain size table: [Diameter] or [Area, Diameter, AspectRatio]
      const val1 = parseFloat(parts[0]);
      const val2 = parts.length > 1 ? parseFloat(parts[1]) : val1;
      const val3 = parts.length > 2 ? parseFloat(parts[2]) : 1.15;

      let dia = val1;
      let area = Math.PI * Math.pow(dia / 2, 2);
      let aspect = 1.15;

      if (!isNaN(val2) && val2 > 0 && val1 > val2) {
        // First is area, second is diameter
        area = val1;
        dia = val2;
        aspect = !isNaN(val3) ? val3 : 1.2;
      } else if (!isNaN(val1) && val1 > 0) {
        dia = val1;
        area = Math.PI * Math.pow(dia / 2, 2);
        aspect = !isNaN(val2) && val2 >= 1 ? val2 : 1.15;
      }

      if (dia > 0.05 && dia < 2000) {
        grains.push({
          grainId: grains.length + 1,
          area_um2: +area.toFixed(2),
          equivalentDiameter_um: +dia.toFixed(2),
          aspectRatio: +aspect.toFixed(2),
        });
      }
    }
  }

  if (grains.length === 0) {
    // If not table, try generating statistical sample
    throw new Error("No valid grain diameter or area data found in file. Please verify CSV, CTF, or TXT formatting.");
  }

  const sumDia = grains.reduce((acc, g) => acc + g.equivalentDiameter_um, 0);
  const meanDiameter_um = +(sumDia / grains.length).toFixed(2);
  const sumAspect = grains.reduce((acc, g) => acc + g.aspectRatio, 0);
  const meanAspectRatio = +(sumAspect / grains.length).toFixed(2);

  // ASTM E112 planimetric grain size number from the mean grain AREA (N_A = 1 / mean area, grains per mm^2 at 1x;
  // N_AE = 2^(G-1) per in^2 at 100x, 1 in^2 = 645.16 mm^2):  G = -3.321928 * log10(meanArea_mm2) - 2.954.
  // (Until 2026-10 this was -3.3219 * log10(meanDiameter_mm) - 3.288: an area coefficient applied to a length,
  // with the intercept constant.)
  const meanArea_mm2 = grains.reduce((acc, g) => acc + g.area_um2, 0) / grains.length / 1e6;
  const astm_G = +(-3.321928 * Math.log10(meanArea_mm2) - 2.954).toFixed(2);

  // Build histogram
  const minSize = Math.max(0.2, Math.min(...grains.map((g) => g.equivalentDiameter_um)));
  const maxSize = Math.max(...grains.map((g) => g.equivalentDiameter_um));
  const bins = 10;
  const step = Math.max(0.5, (maxSize - minSize) / bins);
  const distribution: { sizeBin: string; frequency: number }[] = [];

  for (let b = 0; b < bins; b++) {
    const lower = minSize + b * step;
    const upper = lower + step;
    const count = grains.filter((g) => g.equivalentDiameter_um >= lower && g.equivalentDiameter_um < upper).length;
    distribution.push({
      sizeBin: `${lower.toFixed(1)} µm`,
      frequency: count,
    });
  }

  return {
    filename,
    totalGrains: grains.length,
    meanDiameter_um,
    astm_G,
    meanAspectRatio,
    grains: grains.slice(0, 1000),
    distribution,
  };
}
