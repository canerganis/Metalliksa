// Canvas drawing of the Pourbaix E-pH map (domains, water lines, test points, probe). A pure function of
// the scene so that a recording 2D context can test it (tests/pourbaix-canvas.test.ts); the Studio only
// builds the scene. Nothing here decides a thermodynamic category: domains and states come from the port.

import { CATEGORY_STYLE, clipPolygon, polygonArea, polygonCentroid } from "./pourbaixThermodynamics";
import type {
  PourbaixDomain,
  PourbaixPointState,
  PourbaixWithheldRegion,
  SpeciesCoefficients,
  StabilityCategory,
  WaterStabilityLines,
} from "../types/pourbaix";

export const ZONE_LABEL: Record<StabilityCategory, string> = {
  "Immunity": "IMMUNITY",
  "Corrosion (acid)": "ACID CORROSION",
  "Corrosion (alkaline)": "ALKALINE CORROSION",
  "Passivation (thermodynamic, film-forming)": "PASSIVATION (THERMODYNAMIC)",
  "Transpassive": "TRANSPASSIVE",
};

/** Smallest view-clipped polygon area (px^2) that gets a zone label. */
export const ZONE_LABEL_MIN_AREA_PX2 = 3000;

export interface CanvasTestPoint {
  id: string;
  name: string;
  stageName?: string;
  pH: number;
  /** Potential vs SHE (input potential plus the reference-electrode offset). */
  she: number;
  /** Category of the point in the drawn map (null while there is no map); colours the marker. */
  category: StabilityCategory | null;
}

export interface PourbaixScene {
  width: number;
  height: number;
  viewBounds: { minPH: number; maxPH: number; minE: number; maxE: number };
  /** E(displayed reference) = E(SHE) - refOffset. */
  refOffset: number;
  domains: PourbaixDomain[];
  coeffs: SpeciesCoefficients[] | null;
  waterLines: WaterStabilityLines;
  nernstSlope: number;
  temperature_C: number;
  log10Activity: number;
  probePH: number;
  probePotential_SHE: number;
  probedState: PourbaixPointState | null;
  showExperimentalOverlay: boolean;
  showTrajectoryPath: boolean;
  showPointLabels: boolean;
  points: CanvasTestPoint[];
  selectedPointId: string | null;
  /** Regions where a withheld candidate species would be stable (hatched; the map is not valid there). */
  withheldRegions?: PourbaixWithheldRegion[];
  /** True when the probe lies in a withheld-data region (the readout says so). */
  probeInWithheldRegion?: boolean;
}

/** Hatch colour and spacing of the withheld-data regions (strokes only: the domain fills keep their alpha). */
export const WITHHELD_HATCH = { color: "rgba(226, 232, 240, 0.55)", spacingPx: 9 };

export const MARKER_FALLBACK_COLOR = "#38bdf8";

export function drawPourbaixScene(ctx: CanvasRenderingContext2D, s: PourbaixScene): void {
  const { width, height, refOffset, waterLines, nernstSlope } = s;
  const { minPH, maxPH, minE, maxE } = s.viewBounds;
  const phToX = (ph: number) => ((ph - minPH) / (maxPH - minPH)) * width;
  const eToY = (eShe: number) => {
    const eDisp = eShe - refOffset;
    return height - ((eDisp - minE) / (maxE - minE)) * height;
  };

  // 1. Background
  ctx.fillStyle = "#050b14";
  ctx.fillRect(0, 0, width, height);

  // 2. Exact domain polygons (each species domain is a convex polygon; no per-pixel rule)
  for (const d of s.domains) {
    const style = CATEGORY_STYLE[d.category];
    ctx.beginPath();
    d.polygon.forEach(([ph, e], i) => (i === 0 ? ctx.moveTo(phToX(ph), eToY(e)) : ctx.lineTo(phToX(ph), eToY(e))));
    ctx.closePath();
    ctx.globalAlpha = style.alpha;
    ctx.fillStyle = style.color;
    ctx.fill();
  }
  ctx.globalAlpha = 1.0;

  // 2b. Withheld-data regions: diagonal hatch clipped to each region polygon, dashed outline
  for (const r of s.withheldRegions ?? []) {
    ctx.save();
    ctx.beginPath();
    r.polygon.forEach(([ph, e], i) => (i === 0 ? ctx.moveTo(phToX(ph), eToY(e)) : ctx.lineTo(phToX(ph), eToY(e))));
    ctx.closePath();
    ctx.clip();
    ctx.strokeStyle = WITHHELD_HATCH.color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let x = -height; x < width; x += WITHHELD_HATCH.spacingPx) {
      ctx.moveTo(x, height);
      ctx.lineTo(x + height, 0);
    }
    ctx.stroke();
    ctx.restore();
    ctx.strokeStyle = WITHHELD_HATCH.color;
    ctx.setLineDash([4, 3]);
    ctx.beginPath();
    r.polygon.forEach(([ph, e], i) => (i === 0 ? ctx.moveTo(phToX(ph), eToY(e)) : ctx.lineTo(phToX(ph), eToY(e))));
    ctx.closePath();
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // 3. Grid lines and axis labels (the E axis shows the displayed reference scale)
  ctx.strokeStyle = "#162235";
  ctx.lineWidth = 1;
  ctx.setLineDash([3, 3]);
  for (let ph = Math.ceil(minPH); ph <= maxPH; ph += 2) {
    const x = phToX(ph);
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
    ctx.fillStyle = "#64748b";
    ctx.font = "10px monospace";
    ctx.fillText(`pH ${ph}`, x + 4, height - 8);
  }
  for (let e = Math.ceil(minE * 2) / 2; e <= maxE; e += 0.5) {
    const y = height - ((e - minE) / (maxE - minE)) * height;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
    ctx.fillStyle = "#64748b";
    ctx.font = "10px monospace";
    ctx.fillText(`${e > 0 ? "+" : ""}${e.toFixed(1)}V`, 8, y - 4);
  }
  ctx.setLineDash([]);

  // 3b. Domain outlines (the exact boundaries)
  ctx.strokeStyle = "rgba(226, 232, 240, 0.55)";
  ctx.lineWidth = 1;
  for (const d of s.domains) {
    ctx.beginPath();
    d.polygon.forEach(([ph, e], i) => (i === 0 ? ctx.moveTo(phToX(ph), eToY(e)) : ctx.lineTo(phToX(ph), eToY(e))));
    ctx.closePath();
    ctx.stroke();
  }

  // 4. Water stability lines (a: HER, b: OER)
  ctx.strokeStyle = "#38bdf8";
  ctx.lineWidth = 2.0;
  ctx.setLineDash([6, 4]);
  ctx.beginPath();
  ctx.moveTo(phToX(minPH), eToY(waterLines.herLine.e_at_ph0 + waterLines.herLine.slope * minPH));
  ctx.lineTo(phToX(maxPH), eToY(waterLines.herLine.e_at_ph0 + waterLines.herLine.slope * maxPH));
  ctx.stroke();
  ctx.strokeStyle = "#f43f5e";
  ctx.beginPath();
  ctx.moveTo(phToX(minPH), eToY(waterLines.oerLine.e_at_ph0 + waterLines.oerLine.slope * minPH));
  ctx.lineTo(phToX(maxPH), eToY(waterLines.oerLine.e_at_ph0 + waterLines.oerLine.slope * maxPH));
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = "#38bdf8";
  ctx.font = "bold 11px monospace";
  ctx.fillText(
    `(a) H₂/H⁺: E = -${nernstSlope.toFixed(3)}·pH`,
    phToX(2) + 6,
    eToY(waterLines.herLine.e_at_ph0 + waterLines.herLine.slope * 2) - 6
  );
  ctx.fillStyle = "#f43f5e";
  ctx.fillText(
    `(b) O₂/H₂O: E = ${waterLines.oerLine.e_at_ph0.toFixed(2)} - ${nernstSlope.toFixed(3)}·pH`,
    phToX(2) + 6,
    eToY(waterLines.oerLine.e_at_ph0 + waterLines.oerLine.slope * 2) - 6
  );

  // 5. Zone labels at the centroid of each (view-clipped) domain polygon
  const pxPerPhE = (width / (maxPH - minPH)) * (height / (maxE - minE));
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  for (const d of s.domains) {
    let poly = d.polygon;
    poly = clipPolygon(poly, -1, 0, minPH); // pH >= minPH
    poly = clipPolygon(poly, 1, 0, -maxPH); // pH <= maxPH
    poly = clipPolygon(poly, 0, -1, minE + refOffset); // E >= view minimum (SHE)
    poly = clipPolygon(poly, 0, 1, -(maxE + refOffset)); // E <= view maximum (SHE)
    if (poly.length < 3 || polygonArea(poly) * pxPerPhE < ZONE_LABEL_MIN_AREA_PX2) continue;
    const [cph, ce] = polygonCentroid(poly);
    const style = CATEGORY_STYLE[d.category];
    const sp = s.coeffs?.find((c) => c.id === d.speciesId);
    ctx.fillStyle = style.color;
    ctx.font = "bold 12px monospace";
    ctx.fillText(`${d.formula}${sp?.phase === "s" ? " (s)" : ""}`, phToX(cph), eToY(ce) - 7);
    ctx.font = "9px monospace";
    ctx.fillText(ZONE_LABEL[d.category], phToX(cph), eToY(ce) + 7);
  }
  ctx.textAlign = "start";
  ctx.textBaseline = "alphabetic";

  // 6. Test points and trajectory (marker colour = category of the point in the drawn map)
  if (s.showExperimentalOverlay && s.points.length > 0) {
    const coords = s.points.map((pt) => ({ ...pt, x: phToX(pt.pH), y: eToY(pt.she) }));

    if (s.showTrajectoryPath && coords.length > 1) {
      ctx.strokeStyle = "rgba(255, 255, 255, 0.65)";
      ctx.lineWidth = 2.5;
      ctx.setLineDash([6, 3]);
      ctx.beginPath();
      ctx.moveTo(coords[0].x, coords[0].y);
      for (let i = 1; i < coords.length; i++) ctx.lineTo(coords[i].x, coords[i].y);
      ctx.stroke();
      ctx.setLineDash([]);
      for (let i = 0; i < coords.length - 1; i++) {
        const from = coords[i];
        const to = coords[i + 1];
        const angle = Math.atan2(to.y - from.y, to.x - from.x);
        ctx.save();
        ctx.translate((from.x + to.x) / 2, (from.y + to.y) / 2);
        ctx.rotate(angle);
        ctx.fillStyle = "#38bdf8";
        ctx.beginPath();
        ctx.moveTo(6, 0);
        ctx.lineTo(-4, -4);
        ctx.lineTo(-4, 4);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
      }
    }

    coords.forEach((pt, idx) => {
      const isSelected = pt.id === s.selectedPointId;
      const markerColor = pt.category ? CATEGORY_STYLE[pt.category].color : MARKER_FALLBACK_COLOR;
      if (isSelected) {
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 16, 0, Math.PI * 2);
        ctx.fillStyle = `${markerColor}30`;
        ctx.fill();
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 22, 0, Math.PI * 2);
        ctx.strokeStyle = markerColor;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([3, 3]);
        ctx.stroke();
        ctx.setLineDash([]);
      }
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, isSelected ? 10 : 8, 0, Math.PI * 2);
      ctx.fillStyle = markerColor;
      ctx.fill();
      ctx.lineWidth = isSelected ? 3 : 2;
      ctx.strokeStyle = "#ffffff";
      ctx.stroke();

      ctx.fillStyle = "#0f172a";
      ctx.font = "bold 9px monospace";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(`${idx + 1}`, pt.x, pt.y);
      ctx.textAlign = "start";
      ctx.textBaseline = "alphabetic";

      if (s.showPointLabels) {
        ctx.font = isSelected ? "bold 11px monospace" : "10px monospace";
        const labelText = pt.stageName || pt.name || `Pt #${idx + 1}`;
        const lx = pt.x + 12;
        const ly = pt.y - 8;
        const textWidth = ctx.measureText(labelText).width;
        ctx.fillStyle = "rgba(10, 16, 28, 0.85)";
        ctx.strokeStyle = markerColor;
        ctx.lineWidth = 1;
        ctx.fillRect(lx - 4, ly - 11, textWidth + 8, 15);
        ctx.strokeRect(lx - 4, ly - 11, textWidth + 8, 15);
        ctx.fillStyle = "#f8fafc";
        ctx.fillText(labelText, lx, ly);
      }
    });
  }

  // 7. Crosshair probe and its readout box
  const probeX = phToX(s.probePH);
  const probeY = eToY(s.probePotential_SHE);
  const probeColor = s.probedState ? CATEGORY_STYLE[s.probedState.category].color : "#94a3b8";
  ctx.strokeStyle = "rgba(255, 255, 255, 0.4)";
  ctx.lineWidth = 1;
  ctx.setLineDash([2, 2]);
  ctx.beginPath();
  ctx.moveTo(probeX, 0);
  ctx.lineTo(probeX, height);
  ctx.moveTo(0, probeY);
  ctx.lineTo(width, probeY);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.beginPath();
  ctx.arc(probeX, probeY, 7, 0, Math.PI * 2);
  ctx.fillStyle = probeColor;
  ctx.fill();
  ctx.lineWidth = 2.5;
  ctx.strokeStyle = "#ffffff";
  ctx.stroke();

  const boxW = 270;
  ctx.fillStyle = "#0c1524";
  ctx.strokeStyle = probeColor;
  ctx.lineWidth = 1.5;
  const boxX = Math.min(width - boxW - 10, Math.max(10, probeX + 12));
  const boxH = s.probeInWithheldRegion ? 64 : 50;
  const boxY = Math.min(height - boxH - 10, Math.max(20, probeY - 45));
  ctx.fillRect(boxX, boxY, boxW, boxH);
  ctx.strokeRect(boxX, boxY, boxW, boxH);
  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 10px monospace";
  ctx.fillText(`pH: ${s.probePH.toFixed(2)} | E: ${(s.probePotential_SHE - refOffset).toFixed(3)}V`, boxX + 6, boxY + 16);
  ctx.fillStyle = probeColor;
  ctx.fillText(s.probedState ? s.probedState.category : "No verified data", boxX + 6, boxY + 30);
  ctx.fillStyle = "#94a3b8";
  ctx.font = "9px monospace";
  ctx.fillText(
    `${s.probedState ? s.probedState.formula + " | " : ""}${s.temperature_C}°C data only | a(M) = 10^${s.log10Activity}`,
    boxX + 6,
    boxY + 42
  );
  if (s.probeInWithheldRegion) {
    ctx.fillStyle = "#fbbf24";
    ctx.fillText("withheld-data region: map not valid here", boxX + 6, boxY + 56);
  }
}
