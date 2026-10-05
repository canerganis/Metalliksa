// EDS background estimation, peak search and line candidate listing.
//
// Pure functions, no React. Everything here is a spectrum-processing aid: it lists
// which tabulated X-ray lines lie close to a detected maximum. It does NOT identify
// elements with a probability or a score, and it does NOT quantify composition
// (no ZAF/PhiRhoZ correction, no standards, no k-ratios).

import {
  XRAY_EMISSION_LINES,
  lineLabel,
  type EmissionLine,
  type EmissionLineName,
} from "../data/xrayEmissionLines";

/** One channel of an imported spectrum. The energy axis must be uniformly spaced. */
export interface EdsChannel {
  energyKeV: number;
  counts: number;
}

export interface EdsPeakIdOptions {
  /**
   * Detector energy resolution as FWHM in eV, applied as one constant over the whole
   * spectrum. Real detectors are narrower at low energy and wider at high energy, and the
   * value is usually quoted at Mn K-alpha (5.9 keV). Set it from the instrument; the default
   * of 130 eV is a typical Mn K-alpha figure for a silicon drift detector, not a measurement.
   */
  fwhmEv?: number;
  /**
   * Largest SNIP clipping half-window in channels. Default: ceil(1.5 * FWHM in channels).
   * A Gaussian peak is negligible beyond about +/-1.27 FWHM (+/-3 sigma), so a half-window of
   * 1.5 FWHM is the smallest simple choice that lets the clipping reach the base of a peak.
   */
  snipIterations?: number;
  /**
   * Minimum net/sqrt(background) at the peak maximum. Default 3: net counts of at least three
   * Poisson standard deviations of the local background. Lowering it admits statistically
   * insignificant maxima and is only meaningful for noise-free (synthetic) spectra.
   */
  minSignificance?: number;
  /**
   * Counting noise per channel used in the significance ratio instead of sqrt(background).
   * Only for spectra whose noise is known not to be Poisson, for example 0.29 (= sqrt(1/12), the
   * rounding error) for a noise-free synthetic spectrum rounded to integer counts. Leave unset
   * for measured spectra.
   */
  noiseSigmaCounts?: number;
  /**
   * Maxima below this energy are not reported. Default 0.1 keV: below it the zero-energy
   * electronic noise peak dominates real detectors and the lightest line in the line table
   * (B K-alpha, 183 eV) is above it.
   */
  minEnergyKeV?: number;
  /** Candidate window half-width is max(this, FWHM/2) in eV. Default 50. */
  minMatchWindowEv?: number;
  /**
   * Known-overlap partner lines within this many FWHM of a candidate line are listed as
   * partners. Default 1.5: closer lines than that leave overlapping peak tails.
   */
  partnerFwhmFactor?: number;
}

export interface PeakLineRef {
  element: string;
  line: EmissionLineName;
  label: string;
  energyKeV: number;
  /** Peak energy minus tabulated line energy, in eV. */
  deltaEv: number;
}

export interface DetectedEdsPeak {
  energyKeV: number;
  channel: number;
  /** Smoothed net counts (counts minus SNIP background) at the maximum. */
  netCounts: number;
  /** SNIP background (of the smoothed spectrum) at the maximum. */
  backgroundCounts: number;
  /** netCounts / sqrt(max(backgroundCounts, 1)) (or / noiseSigmaCounts when that option is set). */
  significance: number;
  /**
   * Net counts at the maximum minus the higher of the lowest net values found within one SNIP
   * half-window on either side. It removes the locally constant offset that SNIP leaves on noisy
   * data, so a maximum has to stand out from its own surroundings, not only from zero.
   */
  prominenceCounts: number;
  /** Every tabulated line inside the match window, closest first. */
  candidates: PeakLineRef[];
  /** Known-overlap partner lines near a candidate that are outside the window. */
  overlapPartners: PeakLineRef[];
  overlap: boolean;
  overlapNote?: string;
  /** Raw (unsmoothed) counts at the maximum channel. */
  grossCountsAtMax: number;
  netArea: EdsNetArea;
}

export interface EdsNetArea {
  fromKeV: number;
  toKeV: number;
  /** Sum of (counts - SNIP background) over +/-1 FWHM around the peak. */
  netCounts: number;
  /** sqrt(sum of gross counts in the window): counting statistics only, ignores background-model error. */
  countingSigma: number;
}

export interface EdsPeakIdResult {
  peaks: DetectedEdsPeak[];
  /** SNIP background per input channel (equals the counts for excluded leading/trailing zero channels). */
  background: number[];
  parameters: {
    fwhmEv: number;
    channelWidthEv: number;
    snipIterations: number;
    minSignificance: number;
    noiseSigmaCounts?: number;
    minEnergyKeV: number;
    matchWindowEv: number;
    smoothing: string;
  };
}

export const NET_AREA_LABEL = "Relative intensities, not composition; no ZAF/standards";
export const SMOOTHING_DESCRIPTION =
  "peak signal: 5-channel filter, weights 1-2-3-2-1; SNIP input: Gaussian, sigma = FWHM/4 channels; both renormalised at the range ends";

interface KnownOverlapGroup {
  name: string;
  members: ReadonlyArray<readonly [string, EmissionLineName]>;
}

/**
 * Line groups that are routinely confused in EDS because their energies fall within
 * about one detector FWHM of each other. The groups are fixed by the line table energies.
 */
export const KNOWN_OVERLAP_GROUPS: readonly KnownOverlapGroup[] = [
  { name: "S Ka / Mo La / Nb Lb", members: [["S", "Ka"], ["Mo", "La"], ["Nb", "Lb"]] },
  { name: "Ti Kb / V Ka", members: [["Ti", "Kb"], ["V", "Ka"]] },
  { name: "V Kb / Cr Ka", members: [["V", "Kb"], ["Cr", "Ka"]] },
  { name: "Cr Kb / Mn Ka", members: [["Cr", "Kb"], ["Mn", "Ka"]] },
  { name: "Mn Kb / Fe Ka", members: [["Mn", "Kb"], ["Fe", "Ka"]] },
  { name: "Fe Kb / Co Ka", members: [["Fe", "Kb"], ["Co", "Ka"]] },
  { name: "Co Kb / Ni Ka", members: [["Co", "Kb"], ["Ni", "Ka"]] },
  { name: "W Ma / Ta Ma / Si Ka", members: [["W", "Ma"], ["Ta", "Ma"], ["Si", "Ka"]] },
];

// SNIP takes minima, so on noisy low-count data it sits below the true continuum. Smoothing its input
// with a Gaussian of sigma = FWHM/4 (about 0.6 of a peak's own sigma, so peaks are still clipped as
// peaks) lowers that bias; the peak signal itself is only lightly smoothed (5 channels).
const BG_SMOOTH_FWHM_DIVISOR = 4;

/**
 * Accepted detector FWHM range in eV. Energy-dispersive detectors resolve roughly 120-180 eV at Mn K-alpha; the
 * range is a sanity bound against typos and runaway kernels, not a property of any detector.
 */
export const FWHM_LIMITS_EV = { min: 20, max: 1000 } as const;

const DEFAULTS = {
  fwhmEv: 130,
  minSignificance: 3,
  minEnergyKeV: 0.1,
  minMatchWindowEv: 50,
  partnerFwhmFactor: 1.5,
  snipHalfWindowFwhm: 1.5,
} as const;

/**
 * SNIP background (Ryan et al. 1988; Morhac et al. 1997).
 *
 * The counts are compressed with the LLS transform v = ln(ln(sqrt(y + 1) + 1) + 1) so
 * that weak and strong features are clipped on a comparable scale. The window then
 * decreases from `iterations` channels to 1: for each window p every channel becomes
 * min(v[i], (v[i - p] + v[i + p]) / 2). The result is transformed back and never exceeds
 * the input. Channels closer than p to either end are not clipped by window p.
 */
export function estimateBackgroundSNIP(counts: ArrayLike<number>, iterations: number): number[] {
  const n = counts.length;
  if (!Number.isInteger(iterations) || iterations < 1) {
    throw new Error("SNIP iterations must be a positive integer.");
  }
  let v = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    const y = counts[i];
    if (!Number.isFinite(y)) throw new Error("SNIP input counts must be finite.");
    v[i] = Math.log(Math.log(Math.sqrt(Math.max(0, y) + 1) + 1) + 1);
  }
  for (let p = iterations; p >= 1; p--) {
    if (2 * p >= n) continue;
    const next = Float64Array.from(v);
    for (let i = p; i < n - p; i++) {
      const average = (v[i - p] + v[i + p]) / 2;
      if (average < next[i]) next[i] = average;
    }
    v = next;
  }
  const out: number[] = new Array(n);
  for (let i = 0; i < n; i++) {
    const inverse = (Math.exp(Math.exp(v[i]) - 1) - 1) ** 2 - 1;
    out[i] = Math.min(Math.max(0, inverse), Math.max(0, counts[i]));
  }
  return out;
}

const SMOOTH_WEIGHTS = [1, 2, 3, 2, 1];

function smooth(values: readonly number[]): number[] {
  const n = values.length;
  const out = new Array<number>(n);
  for (let i = 0; i < n; i++) {
    let sum = 0;
    let weight = 0;
    for (let k = -2; k <= 2; k++) {
      const j = i + k;
      if (j < 0 || j >= n) continue;
      const w = SMOOTH_WEIGHTS[k + 2];
      sum += w * values[j];
      weight += w;
    }
    out[i] = sum / weight;
  }
  return out;
}

/** Gaussian smoothing with edge renormalisation; sigma in channels. */
function gaussianSmooth(values: readonly number[], sigma: number): number[] {
  const half = Math.ceil(3 * sigma);
  const weights: number[] = [];
  for (let k = -half; k <= half; k++) weights.push(Math.exp(-(k * k) / (2 * sigma * sigma)));
  const n = values.length;
  return values.map((_, i) => {
    let sum = 0;
    let weight = 0;
    for (let k = -half; k <= half; k++) {
      const j = i + k;
      if (j < 0 || j >= n) continue;
      sum += weights[k + half] * values[j];
      weight += weights[k + half];
    }
    return sum / weight;
  });
}

function sameValue(a: number, b: number): boolean {
  return Math.abs(a - b) <= 1e-9 * Math.max(1, Math.abs(a), Math.abs(b));
}

function lineRef(line: EmissionLine, peakEv: number): PeakLineRef {
  return {
    element: line.element,
    line: line.line,
    label: lineLabel(line),
    energyKeV: line.energyEv / 1000,
    deltaEv: peakEv - line.energyEv,
  };
}

/**
 * Lines inside the match window around a peak energy plus known-overlap partners.
 * Exported separately so overlap flagging can be tested without a spectrum.
 */
export function listPeakCandidates(
  peakEnergyKeV: number,
  fwhmEv: number,
  options: Pick<EdsPeakIdOptions, "minMatchWindowEv" | "partnerFwhmFactor"> = {},
): { candidates: PeakLineRef[]; overlapPartners: PeakLineRef[]; overlap: boolean; overlapNote?: string } {
  const peakEv = peakEnergyKeV * 1000;
  const windowEv = Math.max(options.minMatchWindowEv ?? DEFAULTS.minMatchWindowEv, fwhmEv / 2);
  const partnerEv = (options.partnerFwhmFactor ?? DEFAULTS.partnerFwhmFactor) * fwhmEv;

  const inWindow = XRAY_EMISSION_LINES.filter(line => Math.abs(peakEv - line.energyEv) <= windowEv);
  const candidates = inWindow
    .map(line => lineRef(line, peakEv))
    .sort((a, b) => Math.abs(a.deltaEv) - Math.abs(b.deltaEv));

  const candidateKeys = new Set(inWindow.map(line => `${line.element} ${line.line}`));
  const partnerMap = new Map<string, PeakLineRef>();
  const groupNames = new Set<string>();
  for (const candidate of inWindow) {
    for (const group of KNOWN_OVERLAP_GROUPS) {
      if (!group.members.some(([element, line]) => element === candidate.element && line === candidate.line)) continue;
      groupNames.add(group.name);
      for (const [element, name] of group.members) {
        const key = `${element} ${name}`;
        if (candidateKeys.has(key) || partnerMap.has(key)) continue;
        const member = XRAY_EMISSION_LINES.find(line => line.element === element && line.line === name);
        if (member && Math.abs(member.energyEv - candidate.energyEv) <= partnerEv) {
          partnerMap.set(key, lineRef(member, peakEv));
        }
      }
    }
  }
  const overlapPartners = [...partnerMap.values()].sort((a, b) => Math.abs(a.deltaEv) - Math.abs(b.deltaEv));
  const elements = new Set(candidates.map(candidate => candidate.element));
  const overlap = elements.size > 1 || overlapPartners.length > 0;

  let overlapNote: string | undefined;
  if (overlap) {
    const parts: string[] = [];
    if (elements.size > 1) {
      parts.push(`Lines of ${elements.size} elements lie within +/-${windowEv.toFixed(0)} eV of this peak (${candidates.map(c => c.label).join(", ")}); the peak alone cannot separate them.`);
    }
    if (overlapPartners.length > 0) {
      parts.push(`Known overlapping lines within ${(partnerEv).toFixed(0)} eV of a candidate: ${overlapPartners.map(p => `${p.label} (${Math.abs(p.deltaEv).toFixed(0)} eV ${p.deltaEv < 0 ? "above" : "below"} the peak)`).join(", ")}.`);
    }
    if (groupNames.size > 0) parts.push(`Known overlap group: ${[...groupNames].join("; ")}.`);
    parts.push("Check a second line of each element before accepting one.");
    overlapNote = parts.join(" ");
  }
  return { candidates, overlapPartners, overlap, overlapNote };
}

function assertUniformAxis(channels: readonly EdsChannel[]): number {
  const n = channels.length;
  if (n < 16) throw new Error("At least 16 channels are required for peak search.");
  const step = (channels[n - 1].energyKeV - channels[0].energyKeV) / (n - 1);
  if (!(step > 0) || !Number.isFinite(step)) throw new Error("Spectrum energy axis must be strictly increasing.");
  for (let i = 0; i < n; i++) {
    if (!Number.isFinite(channels[i].energyKeV) || !Number.isFinite(channels[i].counts)) {
      throw new Error("Spectrum channels must be finite.");
    }
    if (i > 0 && Math.abs(channels[i].energyKeV - channels[i - 1].energyKeV - step) > 1e-6 * step + 1e-12) {
      throw new Error("Peak search needs a uniformly spaced energy axis; the imported energy axis is not uniform.");
    }
  }
  return step;
}

/**
 * Background-subtracted peak search with candidate line listing.
 *
 * 1. Leading/trailing zero-count channels (below the detector's low-energy cutoff or above the
 *    beam energy) are excluded from the analysis range.
 * 2. Counts are smoothed with a 5-channel 1-2-3-2-1 filter (the peak signal). The SNIP background is
 *    estimated on a Gaussian-smoothed copy (sigma = FWHM/4 channels); net = peak signal - background.
 * 3. A maximum is a channel (or a run of equal channels, reported once at the run centre) that is
 *    >= every net value within +/-FWHM/2 and strictly above the values just outside the run.
 *    It must have net > 0, net / sqrt(max(background, 1)) >= minSignificance and a prominence
 *    (see DetectedEdsPeak) of at least the same size in sqrt(background) units. A background of
 *    zero is replaced by one count only so the square root is defined. Maxima within the SNIP
 *    half-window of either end of the analysed range are not reported.
 * 4. Every tabulated line within max(50 eV, FWHM/2) of the maximum is listed as a candidate.
 */
export function findEdsPeaks(channels: readonly EdsChannel[], options: EdsPeakIdOptions = {}): EdsPeakIdResult {
  const stepKeV = assertUniformAxis(channels);
  const channelWidthEv = stepKeV * 1000;
  const fwhmEv = options.fwhmEv ?? DEFAULTS.fwhmEv;
  if (!Number.isFinite(fwhmEv) || fwhmEv < FWHM_LIMITS_EV.min || fwhmEv > FWHM_LIMITS_EV.max) {
    throw new Error(`Detector FWHM must be between ${FWHM_LIMITS_EV.min} and ${FWHM_LIMITS_EV.max} eV.`);
  }
  const fwhmChannels = fwhmEv / channelWidthEv;
  // The SNIP window, smoothing kernel and peak window all scale with FWHM in channels; they must fit the spectrum.
  if (!Number.isFinite(fwhmChannels) || fwhmChannels > channels.length / 4) {
    throw new Error(`An FWHM of ${fwhmEv} eV spans ${fwhmChannels.toFixed(1)} channels, more than a quarter of the ` +
      `${channels.length}-channel spectrum; peak search is not possible at this resolution.`);
  }
  if (options.snipIterations !== undefined &&
      !(Number.isInteger(options.snipIterations) && options.snipIterations >= 1 && options.snipIterations <= channels.length)) {
    throw new Error("snipIterations must be an integer between 1 and the number of channels.");
  }
  const minSignificance = options.minSignificance ?? DEFAULTS.minSignificance;
  const minEnergyKeV = options.minEnergyKeV ?? DEFAULTS.minEnergyKeV;
  const snipIterations = options.snipIterations ?? Math.max(1, Math.ceil(DEFAULTS.snipHalfWindowFwhm * fwhmChannels));
  const matchWindowEv = Math.max(options.minMatchWindowEv ?? DEFAULTS.minMatchWindowEv, fwhmEv / 2);
  const parameters = {
    fwhmEv, channelWidthEv, snipIterations, minSignificance, noiseSigmaCounts: options.noiseSigmaCounts,
    minEnergyKeV, matchWindowEv,
    smoothing: SMOOTHING_DESCRIPTION,
  };

  const n = channels.length;
  const counts = channels.map(channel => Math.max(0, channel.counts));
  let lo = 0;
  while (lo < n && counts[lo] === 0) lo++;
  let hi = n - 1;
  while (hi > lo && counts[hi] === 0) hi--;
  const background: number[] = counts.slice();
  if (hi - lo + 1 < 16) return { peaks: [], background, parameters };

  const slice = counts.slice(lo, hi + 1);
  const smoothed = smooth(slice);
  const bgSlice = estimateBackgroundSNIP(gaussianSmooth(slice, fwhmChannels / BG_SMOOTH_FWHM_DIVISOR), snipIterations);
  for (let i = 0; i < bgSlice.length; i++) background[lo + i] = bgSlice[i];
  const net = smoothed.map((value, i) => value - bgSlice[i]);

  const halfWindow = Math.max(1, Math.round(fwhmChannels / 2));
  const isWindowMax = (i: number): boolean => {
    const from = Math.max(0, i - halfWindow);
    const to = Math.min(net.length - 1, i + halfWindow);
    for (let j = from; j <= to; j++) if (net[j] > net[i] && !sameValue(net[j], net[i])) return false;
    return true;
  };

  const peaks: DetectedEdsPeak[] = [];
  let i = 1;
  while (i < net.length - 1) {
    if (!isWindowMax(i)) { i++; continue; }
    let runEnd = i;
    while (runEnd + 1 < net.length && sameValue(net[runEnd + 1], net[i]) && isWindowMax(runEnd + 1)) runEnd++;
    const runStart = i;
    i = runEnd + 1;
    // SNIP clipping windows are truncated within snipIterations channels of either end of the analysed
    // range, so the background is not reliable there and no maximum is reported.
    if (runStart < snipIterations || runEnd > net.length - 1 - snipIterations) continue;
    if (!(net[runStart - 1] < net[runStart] && !sameValue(net[runStart - 1], net[runStart]))) continue;
    if (!(net[runEnd + 1] < net[runEnd] && !sameValue(net[runEnd + 1], net[runEnd]))) continue;

    const centre = Math.floor((runStart + runEnd) / 2);
    const peakEnergyKeV = (channels[lo + runStart].energyKeV + channels[lo + runEnd].energyKeV) / 2;
    if (peakEnergyKeV < minEnergyKeV) continue;
    const netCounts = net[centre];
    if (!(netCounts > 0)) continue;
    const backgroundCounts = bgSlice[centre];
    const noise = options.noiseSigmaCounts ?? Math.sqrt(Math.max(backgroundCounts, 1));
    const significance = netCounts / noise;
    if (significance < minSignificance) continue;
    let leftMin = Infinity;
    for (let k = runStart - snipIterations; k <= runStart; k++) leftMin = Math.min(leftMin, net[k]);
    let rightMin = Infinity;
    for (let k = runEnd; k <= runEnd + snipIterations; k++) rightMin = Math.min(rightMin, net[k]);
    const prominenceCounts = netCounts - Math.max(leftMin, rightMin);
    if (prominenceCounts / noise < minSignificance) continue;

    const matched = listPeakCandidates(peakEnergyKeV, fwhmEv, options);
    const fromKeV = peakEnergyKeV - fwhmEv / 1000;
    const toKeV = peakEnergyKeV + fwhmEv / 1000;
    let areaNet = 0;
    let areaGross = 0;
    for (let k = 0; k < n; k++) {
      const e = channels[k].energyKeV;
      if (e < fromKeV || e > toKeV) continue;
      areaNet += counts[k] - background[k];
      areaGross += counts[k];
    }
    peaks.push({
      energyKeV: peakEnergyKeV,
      channel: lo + centre,
      netCounts,
      backgroundCounts,
      significance,
      prominenceCounts,
      candidates: matched.candidates,
      overlapPartners: matched.overlapPartners,
      overlap: matched.overlap,
      overlapNote: matched.overlapNote,
      grossCountsAtMax: counts[lo + centre],
      netArea: { fromKeV, toKeV, netCounts: areaNet, countingSigma: Math.sqrt(areaGross) },
    });
  }
  return { peaks, background, parameters };
}
