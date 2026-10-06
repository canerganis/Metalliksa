/**
 * Parser for the CMU Ti-6Al-4V melt-pool measurement CSVs (DOI 10.1184/R1/25696293.v1, CC BY 4.0).
 * Columns are located by header name, never by position.
 *
 * Scope: only MTMeasurements.csv carries a power column (the actual STMeasurements.csv has none, contrary to the
 * dataset README), and MT describes multi-track, powder-entrained cross sections. This module therefore serves MT
 * rows labelled as multi-track; it never calls them single-track and never copies MT power onto ST rows.
 */
export interface CmuMeasurementRow {
  slice: number | null; orientation: number | null; power_W: number | null; velocity_mms: number | null;
  width_um: number | null; depth_um: number | null; cap_um: number | null;
}

export const CMU_MT_SCOPE = {
  trackScope: 'multi-track-powder-entrained',
  file: 'raw/MTMeasurements.csv',
  rationale: 'STMeasurements.csv has no power column, so a power-matched comparison needs the multi-track file.',
  unresolved: ['beam profile/diameter for this CSV', 'layer thickness', 'powder lot', 'thermal boundary conditions'],
} as const;

const COLUMNS: Record<keyof CmuMeasurementRow, string> = {
  slice: 'Slice', orientation: 'Orientation (degrees)', power_W: 'Power (W)', velocity_mms: 'Velocity (mm/s)',
  width_um: 'Width (um)', depth_um: 'Depth (um)', cap_um: 'Cap (um)',
};

export function parseCmuMeasurementsCsv(csv: string): CmuMeasurementRow[] {
  const lines = csv.replace(/^\uFEFF/, '').split(/\r?\n/).filter(line => line.trim() !== '');
  if (!lines.length) throw new Error('Empty CMU measurement table');
  const header = lines[0].split(',').map(h => h.trim());
  const index = {} as Record<keyof CmuMeasurementRow, number>;
  for (const key of Object.keys(COLUMNS) as (keyof CmuMeasurementRow)[]) {
    index[key] = header.indexOf(COLUMNS[key]);
    if (index[key] < 0) throw new Error(`CMU measurement table lacks required column "${COLUMNS[key]}"`);
  }
  return lines.slice(1).map((line, i) => {
    const parts = line.split(',');
    const value = (key: keyof CmuMeasurementRow): number | null => {
      const raw = (parts[index[key]] ?? '').trim();
      const n = Number(raw);
      if (raw === '' || !Number.isFinite(n)) throw new Error(`CMU measurement row ${i + 2}: non-numeric ${COLUMNS[key]}`);
      return n === -1 ? null : n; // -1 is the dataset's documented missing-value sentinel.
    };
    return { slice: value('slice'), orientation: value('orientation'), power_W: value('power_W'), velocity_mms: value('velocity_mms'),
      width_um: value('width_um'), depth_um: value('depth_um'), cap_um: value('cap_um') };
  });
}
