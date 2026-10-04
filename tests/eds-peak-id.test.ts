import assert from 'node:assert/strict';
import test from 'node:test';
import { parseRawEDSFile } from '../src/utils/edsParser';
import {
  KNOWN_OVERLAP_GROUPS,
  NET_AREA_LABEL,
  estimateBackgroundSNIP,
  findEdsPeaks,
  listPeakCandidates,
  type DetectedEdsPeak,
  type EdsChannel,
} from '../src/utils/edsPeakId';
import {
  XRAY_EMISSION_LINES,
  XRAY_EMISSION_LINES_SOURCE,
  findEmissionLine,
} from '../src/data/xrayEmissionLines';

// ---------------------------------------------------------------------------------------------
// Synthetic spectrum generators. Nothing here is measured data.
// ---------------------------------------------------------------------------------------------

const E1_LINES: Array<[string, number, number]> = [
  ['Fe Ka', 6.404, 6800], ['Fe Kb', 7.058, 900], ['Cr Ka', 5.415, 2600], ['Cr Kb', 5.947, 350],
  ['Ni Ka', 7.478, 1100], ['Ni Kb', 8.265, 150], ['Mo La', 2.293, 300], ['Si Ka', 1.740, 120],
  ['Fe La', 0.705, 900],
];

function mulberry32(seed: number): () => number {
  let state = seed;
  return () => {
    state = (state + 0x6D2B79F5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Counts of the 316L-like generator; optional Gaussian noise with variance equal to the counts. */
function e1Counts(withLines: boolean, noiseSeed?: number): number[] {
  const n = 2048;
  const dE = 10;
  const fwhm = 0.130;
  const sig = fwhm / 2.355;
  const random = noiseSeed === undefined ? undefined : mulberry32(noiseSeed);
  const counts: number[] = [];
  for (let i = 0; i < n; i++) {
    const e = (i * dE) / 1000;
    let c = e > 0.2 ? 400 * (15 - e) / e * (1 - Math.exp(-e / 0.8)) : 0;
    if (withLines) {
      for (const [, energy, area] of E1_LINES) {
        c += area / (sig * Math.sqrt(2 * Math.PI)) * 0.01 * Math.exp(-((e - energy) ** 2) / (2 * sig * sig));
      }
    }
    if (random) {
      const gauss = Math.sqrt(-2 * Math.log(1 - random())) * Math.cos(2 * Math.PI * random());
      c += Math.sqrt(Math.max(c, 0)) * gauss;
    }
    counts.push(Math.max(0, Math.round(c)));
  }
  return counts;
}

function emsaText(counts: number[], title: string): string {
  return [
    '#FORMAT : EMSA/MAS Spectral Data File', '#VERSION : 1.0', `#TITLE : ${title}`,
    `#NPOINTS : ${counts.length}`, '#NCOLUMNS : 1', '#XUNITS : eV', '#YUNITS : counts',
    '#XPERCHAN : 10', '#OFFSET : 0', '#BEAMKV : 15', '#LIVETIME : 60', '#SPECTRUM :',
    ...counts.map(String), '#ENDOFDATA :',
  ].join('\n');
}

function channelsFromEmsa(counts: number[], title: string): EdsChannel[] {
  const parsed = parseRawEDSFile(emsaText(counts, title), 'synthetic.emsa');
  return parsed.points.map(point => ({ energyKeV: point.energyKeV, counts: point.counts }));
}

function hasCandidate(peaks: DetectedEdsPeak[], label: string, toleranceEv = 20): boolean {
  return peaks.some(peak => peak.candidates.some(c => c.label === label && Math.abs(c.deltaEv) <= toleranceEv));
}

/** Noise-free spectra are rounded to integers: the rounding error has sigma = sqrt(1/12) counts. */
const ROUNDING_SIGMA = Math.sqrt(1 / 12);

// ---------------------------------------------------------------------------------------------
// E1: synthetic 316L-like EMSA spectrum
// ---------------------------------------------------------------------------------------------

test('E1 (default 3-sigma gate): strong 316L lines are found, nothing below 0.3 keV, weak lines are not claimed', () => {
  const channels = channelsFromEmsa(e1Counts(true), 'synthetic 316L');
  const { peaks, parameters } = findEdsPeaks(channels);

  assert.equal(parameters.minSignificance, 3);
  assert.equal(parameters.fwhmEv, 130);
  assert.ok(hasCandidate(peaks, 'Fe Ka'), 'Fe Ka');
  assert.ok(hasCandidate(peaks, 'Cr Ka'), 'Cr Ka');
  assert.ok(hasCandidate(peaks, 'Ni Ka'), 'Ni Ka');
  assert.equal(peaks.filter(peak => peak.energyKeV < 0.3).length, 0, 'no peak below 0.3 keV');

  // The generator's weak lines carry only 120-900 counts of net area under a continuum of several
  // thousand counts per channel at low energy. With Poisson noise they would be indistinguishable
  // from the background, and the default 3 sqrt(background) gate correctly does not report them.
  // Measured at these defaults: Fe Kb net/sqrt(bg) = 2.99, Cr Kb, Mo La, Si Ka, Fe La lower still.
  for (const label of ['Cr Kb', 'Mo La', 'Si Ka', 'Fe La', 'Ni Kb']) {
    assert.equal(hasCandidate(peaks, label), false, `${label} must not pass the default gate`);
  }
  for (const peak of peaks) {
    assert.ok(peak.significance >= 3);
    assert.ok(Math.abs(peak.netCounts) > 0 && peak.backgroundCounts > 0);
  }
});

test('E1 (noise-free input, noise = rounding error): all seven required lines plus Ni Kb and Fe La are found within 20 eV', () => {
  const channels = channelsFromEmsa(e1Counts(true), 'synthetic 316L');
  const { peaks } = findEdsPeaks(channels, { noiseSigmaCounts: ROUNDING_SIGMA });

  for (const label of ['Fe Ka', 'Cr Ka', 'Ni Ka', 'Fe Kb', 'Cr Kb', 'Mo La', 'Si Ka', 'Ni Kb', 'Fe La']) {
    assert.ok(hasCandidate(peaks, label), `${label} found within 20 eV`);
  }
  assert.equal(peaks.filter(peak => peak.energyKeV < 0.3).length, 0, 'no peak below 0.3 keV');
  assert.equal(peaks.length, 9, 'exactly the nine generated lines and nothing else');
  for (const peak of peaks) {
    assert.ok(peak.candidates.length > 0);
    assert.ok(!('confidence' in peak));
  }
});

test('E1: every reported peak carries the required fields and no confidence value', () => {
  const channels = channelsFromEmsa(e1Counts(true), 'synthetic 316L');
  const { peaks } = findEdsPeaks(channels, { noiseSigmaCounts: ROUNDING_SIGMA });
  const peak = peaks.find(p => hasCandidate([p], 'Fe Ka'))!;
  assert.ok(peak);
  assert.equal(peak.channel, Math.round(peak.energyKeV * 100));
  assert.ok(peak.netCounts > 400 && peak.backgroundCounts > 400);
  assert.ok(peak.significance > 0);
  assert.equal(typeof peak.overlap, 'boolean');
  assert.equal(JSON.stringify(peak).toLowerCase().includes('confidence'), false);
  assert.ok(peak.netArea.netCounts > 0 && peak.netArea.countingSigma > 0);
  assert.match(NET_AREA_LABEL, /not composition/);
  assert.match(NET_AREA_LABEL, /no ZAF\/standards/);
});

// ---------------------------------------------------------------------------------------------
// E2: flat-topped maximum
// ---------------------------------------------------------------------------------------------

function plateauSpectrum(width: number, centreChannel: number): EdsChannel[] {
  const counts = new Array<number>(2048).fill(400);
  const ramp = [20, 60, 120, 190];
  const start = centreChannel - Math.floor(width / 2);
  for (let k = 0; k < width; k++) counts[start + k] += 250;
  for (let k = 0; k < ramp.length; k++) {
    counts[start - 1 - k] += ramp[ramp.length - 1 - k];
    counts[start + width + k] += ramp[ramp.length - 1 - k];
  }
  return counts.map((value, i) => ({ energyKeV: (i * 10) / 1000, counts: value }));
}

test('E2: a Ni Ka maximum with a flat plateau of equal counts is reported exactly once', () => {
  for (const width of [3, 4, 5, 6, 7, 9]) {
    const channels = plateauSpectrum(width, 748);
    const plateau = channels.slice(748 - Math.floor(width / 2), 748 - Math.floor(width / 2) + width);
    assert.ok(plateau.every(point => point.counts === 650), 'input plateau of equal integer counts');
    const { peaks } = findEdsPeaks(channels);
    assert.equal(peaks.length, 1, `plateau width ${width}`);
    const candidate = peaks[0].candidates.find(c => c.label === 'Ni Ka');
    assert.ok(candidate && Math.abs(candidate.deltaEv) <= 20, `plateau width ${width}: Ni Ka within 20 eV`);
    assert.ok(Math.abs(peaks[0].channel - 748) <= 2, `plateau width ${width}: located at the plateau centre`);
  }
});

// ---------------------------------------------------------------------------------------------
// E3: overlap flags
// ---------------------------------------------------------------------------------------------

function gaussianSpectrum(energyKeV: number, area: number): EdsChannel[] {
  const sig = 0.130 / 2.355;
  return Array.from({ length: 2048 }, (_, i) => {
    const e = (i * 10) / 1000;
    const continuum = e > 0.2 ? 400 * (15 - e) / e * (1 - Math.exp(-e / 0.8)) : 0;
    const peak = area / (sig * Math.sqrt(2 * Math.PI)) * 0.01 * Math.exp(-((e - energyKeV) ** 2) / (2 * sig * sig));
    return { energyKeV: e, counts: Math.max(0, Math.round(continuum + peak)) };
  });
}

test('E3: a peak at 2.30 keV lists S Ka, Mo La and Nb Lb and carries an overlap flag', () => {
  const { peaks } = findEdsPeaks(gaussianSpectrum(2.30, 60000));
  assert.equal(peaks.length, 1);
  const labels = peaks[0].candidates.map(c => c.label);
  for (const expected of ['S Ka', 'Mo La', 'Nb Lb']) assert.ok(labels.includes(expected), expected);
  assert.equal(peaks[0].overlap, true);
  assert.match(peaks[0].overlapNote ?? '', /S Ka \/ Mo La \/ Nb Lb/);
});

test('E3: a peak at the Ni Ka energy lists Ni Ka and flags the Co Kb partner; a peak at Co Kb flags Ni Ka', () => {
  const ni = findEdsPeaks(gaussianSpectrum(7.478, 60000)).peaks;
  assert.equal(ni.length, 1);
  assert.deepEqual(ni[0].candidates.map(c => c.label), ['Ni Ka']);
  assert.deepEqual(ni[0].overlapPartners.map(c => c.label), ['Co Kb']);
  assert.equal(ni[0].overlap, true);
  assert.match(ni[0].overlapNote ?? '', /Co Kb/);
  assert.match(ni[0].overlapNote ?? '', /Co Kb \/ Ni Ka/);

  const co = findEdsPeaks(gaussianSpectrum(7.649, 60000)).peaks;
  assert.equal(co.length, 1);
  assert.deepEqual(co[0].candidates.map(c => c.label), ['Co Kb']);
  assert.deepEqual(co[0].overlapPartners.map(c => c.label), ['Ni Ka']);
  assert.equal(co[0].overlap, true);
});

test('every known overlap group member lists the other members as candidates or partners', () => {
  for (const group of KNOWN_OVERLAP_GROUPS) {
    for (const [element, name] of group.members) {
      const line = findEmissionLine(element, name)!;
      assert.ok(line, `${element} ${name} is in the line table`);
      const listed = listPeakCandidates(line.energyEv / 1000, 130);
      const labels = new Set([...listed.candidates, ...listed.overlapPartners].map(c => c.label));
      for (const [otherElement, otherName] of group.members) {
        assert.ok(labels.has(`${otherElement} ${otherName}`), `${group.name}: ${element} ${name} should list ${otherElement} ${otherName}`);
      }
      assert.equal(listed.overlap, true);
    }
  }
});

test('an isolated line is not flagged as an overlap', () => {
  const listed = listPeakCandidates(8.047, 130); // Cu Ka (8047.78 eV): nothing else within 195 eV in the table
  assert.deepEqual(listed.candidates.map(c => c.label), ['Cu Ka']);
  assert.equal(listed.overlap, false);
  assert.equal(listed.overlapNote, undefined);
});

// ---------------------------------------------------------------------------------------------
// E4: pure continuum
// ---------------------------------------------------------------------------------------------

test('E4: a pure bremsstrahlung-like continuum has no peaks (noise-free)', () => {
  const channels = channelsFromEmsa(e1Counts(false), 'continuum only');
  assert.equal(findEdsPeaks(channels).peaks.length, 0);
  assert.equal(findEdsPeaks(channels, { noiseSigmaCounts: ROUNDING_SIGMA }).peaks.length, 0);
});

test('E4: a seeded noisy continuum has no peaks for 40 seeds at the default gate (regression pin of measured behaviour)', () => {
  let total = 0;
  for (let seed = 1; seed <= 40; seed++) {
    const channels = channelsFromEmsa(e1Counts(false, seed), 'noisy continuum');
    total += findEdsPeaks(channels).peaks.length;
  }
  assert.equal(total, 0);
});

test('seeded noisy 316L-like spectra: the strong lines are found in every seed', () => {
  for (let seed = 1; seed <= 10; seed++) {
    const { peaks } = findEdsPeaks(channelsFromEmsa(e1Counts(true, seed), 'noisy 316L'));
    // Noise moves a maximum by a few channels, so only the 65 eV candidate window is required here.
    assert.ok(hasCandidate(peaks, 'Fe Ka', 65), `seed ${seed} Fe Ka`);
    assert.ok(hasCandidate(peaks, 'Ni Ka', 65), `seed ${seed} Ni Ka`);
    assert.equal(peaks.filter(peak => peak.energyKeV < 0.3).length, 0);
  }
});

// ---------------------------------------------------------------------------------------------
// SNIP and input validation
// ---------------------------------------------------------------------------------------------

test('SNIP leaves a flat spectrum unchanged, never exceeds the counts, and clips a peak', () => {
  const flat = new Array(200).fill(500);
  for (const value of estimateBackgroundSNIP(flat, 20)) assert.ok(Math.abs(value - 500) < 1e-6);

  const withPeak = flat.slice();
  for (let i = 90; i <= 110; i++) withPeak[i] += Math.round(2000 * Math.exp(-((i - 100) ** 2) / (2 * 4 ** 2)));
  const bg = estimateBackgroundSNIP(withPeak, 20);
  assert.ok(bg.every((value, i) => value <= withPeak[i] + 1e-9));
  assert.ok(bg[100] < 520, `background under the peak top is ${bg[100]}`);
  assert.throws(() => estimateBackgroundSNIP(flat, 0), /positive integer/);
});

test('peak search rejects a non-uniform energy axis and an invalid FWHM', () => {
  const channels: EdsChannel[] = Array.from({ length: 64 }, (_, i) => ({ energyKeV: i * 0.01 + (i === 30 ? 0.004 : 0), counts: 100 }));
  assert.throws(() => findEdsPeaks(channels), /uniformly spaced/);
  const ok: EdsChannel[] = Array.from({ length: 64 }, (_, i) => ({ energyKeV: i * 0.01, counts: 100 }));
  assert.throws(() => findEdsPeaks(ok, { fwhmEv: 0 }), /FWHM/);
});

// ---------------------------------------------------------------------------------------------
// E6: line-table energies. The expected values below are typed from the printed X-Ray Data
// Booklet Table 1-2 (https://xdb.lbl.gov/Section1/Table_1-2.pdf, pages 1-4), not generated from the data module.
// ---------------------------------------------------------------------------------------------

test('E6: line table energies match the printed booklet values (eV)', () => {
  const printed: Array<[string, 'Ka' | 'Kb' | 'La' | 'Lb' | 'Ma', number]> = [
    ['Fe', 'Ka', 6403.84], ['Cr', 'Ka', 5414.72], ['Ni', 'Ka', 7478.15], ['Si', 'Ka', 1739.98],
    ['Mo', 'La', 2293.16], // the booklet prints 2,293.16 (not 2,293.19)
    ['S', 'Ka', 2307.84], ['Co', 'Kb', 7649.43], ['W', 'Ma', 1775.4], ['Ti', 'Kb', 4931.81], ['V', 'Ka', 4952.20],
    ['Fe', 'La', 705.0], ['C', 'Ka', 277],
  ];
  for (const [element, name, energy] of printed) {
    assert.equal(findEmissionLine(element, name)?.energyEv, energy, `${element} ${name}`);
  }
});

test('line table has the required elements and a cited source with a sha256', () => {
  const elements = new Set(XRAY_EMISSION_LINES.map(line => line.element));
  for (const element of ['B', 'C', 'N', 'O', 'Mg', 'Al', 'Si', 'P', 'S', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn', 'Y', 'Zr', 'Nb', 'Mo', 'Hf', 'Ta', 'W', 'Re']) {
    assert.ok(elements.has(element), element);
  }
  for (const element of ['Hf', 'Ta', 'W', 'Re']) assert.ok(findEmissionLine(element, 'Ma'), `${element} Ma`);
  assert.match(XRAY_EMISSION_LINES_SOURCE.url, /^https:\/\/xdb\.lbl\.gov\/Section1\/Table_1-2\.pdf$/);
  assert.match(XRAY_EMISSION_LINES_SOURCE.fileSha256, /^[a-f0-9]{64}$/);
  assert.match(XRAY_EMISSION_LINES_SOURCE.title, /Table 1-2/);
});
