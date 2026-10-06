export interface SlicerRequestInputs {
  preset: string;
  material: string;
  laserPower_W: number;
  scanSpeed_mms: number;
  layerThickness_um: number;
  hatchSpacing_um: number;
  recoatTimePerLayer_s: number;
  hatchStrategy: string;
  customTriangles: number[][][] | null;
  cadAssetName: string;
  triangleCountNative: number | undefined;
}

/** Exact body sent to /api/python/stl-slicer-build-time (unchanged from the inline original). */
export function buildSlicerPayload(i: SlicerRequestInputs) {
  return {
    preset: i.preset,
    material: i.material,
    laserPower_W: i.laserPower_W,
    scanSpeed_mms: i.scanSpeed_mms,
    layerThickness_um: i.layerThickness_um,
    hatchSpacing_um: i.hatchSpacing_um,
    recoatTimePerLayer_s: i.recoatTimePerLayer_s,
    hatchStrategy: i.hatchStrategy,
    customTriangles: i.customTriangles,
    cadAssetName: i.cadAssetName,
    triangleCountNative: i.triangleCountNative,
  };
}

/** Signature of every payload field; the triangle array is represented by the geometry identity it derives from. */
export function slicerRequestSignature(i: Omit<SlicerRequestInputs, "customTriangles"> & { geometryId: string | null }): string {
  const { geometryId, ...rest } = i;
  const { customTriangles: _ignored, ...fields } = buildSlicerPayload({ ...rest, customTriangles: null });
  return JSON.stringify([fields, geometryId]);
}
