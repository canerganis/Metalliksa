import React, { useState, useCallback } from 'react';
import { pythonComputationService } from '../services/pythonComputationService';

const SAMPLE_STL_CUBE = `solid tensile_coupon
  facet normal 0.0 0.0 1.0
    outer loop
      vertex 0.0 0.0 20.0
      vertex 20.0 0.0 20.0
      vertex 20.0 20.0 20.0
    endloop
  endfacet
  facet normal 0.0 0.0 1.0
    outer loop
      vertex 0.0 0.0 20.0
      vertex 20.0 20.0 20.0
      vertex 0.0 20.0 20.0
    endloop
  endfacet
  facet normal 0.0 0.0 -1.0
    outer loop
      vertex 0.0 0.0 0.0
      vertex 20.0 20.0 0.0
      vertex 20.0 0.0 0.0
    endloop
  endfacet
  facet normal 0.0 0.0 -1.0
    outer loop
      vertex 0.0 0.0 0.0
      vertex 0.0 20.0 0.0
      vertex 20.0 20.0 0.0
    endloop
  endfacet
endsolid tensile_coupon
`;

export const LpbfDefectTwinLab: React.FC = () => {
  const [stlContent, setStlContent] = useState(SAMPLE_STL_CUBE);
  const [resolution, setResolution] = useState(32);
  const [keyholePoresCount, setKeyholePoresCount] = useState(5);
  const [lofPoresCount, setLofPoresCount] = useState(3);
  const [selectedZLayer, setSelectedZLayer] = useState(10);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleVoxelize = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    // Generate physical defects based on current LPBF process criteria
    const simulatedDefects = [];
    for (let i = 0; i < keyholePoresCount; i++) {
      simulatedDefects.push({
        x: 4.0 + (i * 2.5),
        y: 6.0 + (i * 1.8),
        z: 5.0 + (i * 2.2),
        type: "keyhole",
        diameter_um: 40.0 + (i * 8.0)
      });
    }
    for (let j = 0; j < lofPoresCount; j++) {
      simulatedDefects.push({
        x: 12.0 - (j * 2.0),
        y: 14.0 - (j * 1.5),
        z: 8.0 + (j * 3.0),
        type: "lof",
        diameter_um: 70.0 + (j * 15.0)
      });
    }

    try {
      const res = await pythonComputationService.voxelizeSTLDefects({
        stlContent,
        resolution,
        defects: simulatedDefects
      });
      setResult(res);
      if (res.bounds?.max?.[2]) {
        setSelectedZLayer(Math.round(res.bounds.max[2] / 2));
      }
    } catch (err: any) {
      setError(err.message || 'Voxelization failed');
    } finally {
      setIsLoading(false);
    }
  }, [stlContent, resolution, keyholePoresCount, lofPoresCount]);

  return (
    <div className="flex flex-col h-full bg-gray-900 text-gray-200">
      <div className="flex items-center justify-between p-4 bg-gray-800 border-b border-gray-700">
        <div>
          <h2 className="text-lg font-bold text-white">Part-Level Spatial Defect Digital Twin</h2>
          <p className="text-sm text-gray-400">Phase 14: CAD/STL Voxelization, 3D Defect Mapping & Relative Density (%99.X)</p>
        </div>
        <button
          onClick={handleVoxelize}
          disabled={isLoading}
          className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded font-medium disabled:opacity-50"
        >
          {isLoading ? 'Voxelizing CAD Mesh...' : 'Map 3D Defect Twin'}
        </button>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Sol Panel: STL Girişi ve Ayarlar */}
        <div className="w-84 p-4 border-r border-gray-700 overflow-y-auto space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-300 uppercase mb-1">STL Geometry (ASCII / Base64)</label>
            <textarea aria-label="STL Geometry (ASCII / Base64)"
              rows={6}
              value={stlContent}
              onChange={e => setStlContent(e.target.value)}
              className="w-full bg-gray-950 font-mono text-[11px] p-2 rounded border border-gray-700 text-gray-200 focus:outline-none focus:border-purple-500"
            />
          </div>

          <div className="space-y-3 pt-2 border-t border-gray-800">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">Voxel Grid Resolution</h3>
            <div className="grid grid-cols-3 gap-2">
              {[16, 32, 64].map(res => (
                <button
                  key={res}
                  type="button"
                  onClick={() => setResolution(res)}
                  className={`py-1.5 text-xs rounded border ${resolution === res ? 'bg-purple-600 border-purple-500 text-white font-bold' : 'bg-gray-800 border-gray-700 text-gray-400'}`}
                >
                  {res}³ voxels
                </button>
              ))}
            </div>

            <label className="block text-xs">
              <span className="text-gray-400">Keyhole Pore Count (King Criterion)</span>
              <input
                type="range" min={0} max={25} step={1}
                value={keyholePoresCount} onChange={e => setKeyholePoresCount(Number(e.target.value))}
                className="w-full mt-1"
              />
              <div className="text-right font-mono text-red-400 text-xs">{keyholePoresCount} pores</div>
            </label>

            <label className="block text-xs">
              <span className="text-gray-400">Lack-of-Fusion Pores (Tang Criterion)</span>
              <input
                type="range" min={0} max={15} step={1}
                value={lofPoresCount} onChange={e => setLofPoresCount(Number(e.target.value))}
                className="w-full mt-1"
              />
              <div className="text-right font-mono text-amber-400 text-xs">{lofPoresCount} pores</div>
            </label>
          </div>

          <div className="p-3 rounded bg-purple-950/30 border border-purple-800 text-[11px] text-purple-300">
            <strong>Akenine-Möller Algorithm:</strong> Computes exact 3D Triangle-Box bounding volume to determine part infill without voxel leakage.
          </div>
        </div>

        {/* Sağ Panel: 3B Görselleştirme & Yoğunluk */}
        <div className="flex-1 p-6 overflow-y-auto bg-gray-950">
          {error && (
            <div className="mb-4 p-4 bg-red-900/40 border border-red-700 text-red-200 rounded text-sm">
              {error}
            </div>
          )}

          {!result && !isLoading && !error && (
            <div className="flex h-full items-center justify-center text-gray-500 text-sm">
              Load STL mesh and click 'Map 3D Defect Twin' to project spatial pores and calculate relative density.
            </div>
          )}

          {result && (
            <div className="space-y-6">
              {/* Metrik Kartları */}
              <div className="grid grid-cols-4 gap-4">
                <div className="p-3 bg-gray-800 border border-gray-700 rounded flex flex-col items-center">
                  <span className="text-xs text-gray-400 mb-1">Relative Density</span>
                  <span className="text-xl font-mono font-bold text-emerald-400">
                    {result.relative_density_pct.toFixed(3)} %
                  </span>
                </div>
                <div className="p-3 bg-gray-800 border border-gray-700 rounded flex flex-col items-center">
                  <span className="text-xs text-gray-400 mb-1">Part Volume</span>
                  <span className="text-lg font-mono font-bold text-white">
                    {result.part_volume_mm3.toFixed(1)} mm³
                  </span>
                </div>
                <div className="p-3 bg-gray-800 border border-gray-700 rounded flex flex-col items-center">
                  <span className="text-xs text-gray-400 mb-1">Total Pores</span>
                  <span className="text-lg font-mono font-bold text-purple-400">
                    {result.total_defects_count}
                  </span>
                </div>
                <div className="p-3 bg-gray-800 border border-gray-700 rounded flex flex-col items-center">
                  <span className="text-xs text-gray-400 mb-1">Bounding Box</span>
                  <span className="text-xs font-mono font-bold text-gray-300">
                    {result.bounds.dimensions_mm.join(' × ')} mm
                  </span>
                </div>
              </div>

              {/* 3B İzometrik Voksel & Kusur Görselleştirici */}
              <div className="bg-gray-800 border border-gray-700 rounded p-4">
                <div className="flex justify-between items-center mb-3">
                  <h3 className="text-sm font-semibold text-white">3D Spatial Defect Map (Isometric View)</h3>
                  <div className="flex items-center gap-4 text-xs">
                    <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block"/> Keyhole (Spherical)</span>
                    <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-amber-400 inline-block"/> Lack of Fusion (Planar)</span>
                  </div>
                </div>

                <div className="relative w-full h-80 bg-gray-950 rounded border border-gray-800 overflow-hidden flex items-center justify-center">
                  <svg viewBox="0 0 500 300" className="w-full h-full">
                    {/* Bounding Grid Box (Isometric) */}
                    <polygon points="250,50 400,120 250,190 100,120" fill="none" stroke="#374151" strokeWidth="1" strokeDasharray="3 3" />
                    <polygon points="100,120 250,190 250,260 100,190" fill="none" stroke="#374151" strokeWidth="1" strokeDasharray="3 3" />
                    <polygon points="250,190 400,120 400,190 250,260" fill="none" stroke="#374151" strokeWidth="1" strokeDasharray="3 3" />

                    {/* Surface Sample Voxels (Wireframe) */}
                    {result.sample_surface_voxels?.map((v: any, i: number) => {
                      const isoX = 250 + (v.x - v.y) * 5.0;
                      const isoY = 160 + (v.x + v.y) * 2.5 - (v.z * 3.5);
                      return (
                        <circle key={i} cx={isoX} cy={isoY} r={1.5} fill="#4b5563" opacity={0.6} />
                      );
                    })}

                    {/* Defect Markers Projected in 3D */}
                    {result.defects?.map((d: any, idx: number) => {
                      const isoX = 250 + (d.x - d.y) * 5.0;
                      const isoY = 160 + (d.x + d.y) * 2.5 - (d.z * 3.5);
                      const isKeyhole = d.type === 'keyhole';
                      return (
                        <g key={idx}>
                          <circle
                            cx={isoX}
                            cy={isoY}
                            r={Math.max(4, d.diameter_um / 12)}
                            fill={isKeyhole ? '#ef4444' : '#f59e0b'}
                            opacity={0.85}
                            stroke="#ffffff"
                            strokeWidth={1}
                          />
                          <text x={isoX + 6} y={isoY + 3} fill="#9ca3af" fontSize="9" fontFamily="monospace">
                            {d.diameter_um}µm
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                </div>
              </div>

              {/* Kusur Listesi */}
              <div className="bg-gray-800 border border-gray-700 rounded p-4">
                <h3 className="text-sm font-semibold text-white mb-2">Detected Spatial Defect Coordinates</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left text-gray-300">
                    <thead className="bg-gray-900 text-gray-400 uppercase">
                      <tr>
                        <th className="p-2">Defect ID</th>
                        <th className="p-2">Mechanism</th>
                        <th className="p-2">Coordinates (X, Y, Z)</th>
                        <th className="p-2">Diameter</th>
                        <th className="p-2">Pore Volume</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-700">
                      {result.defects.map((df: any, index: number) => (
                        <tr key={index} className="hover:bg-gray-750">
                          <td className="p-2 font-mono">#{index + 1}</td>
                          <td className="p-2">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${df.type === 'keyhole' ? 'bg-red-950 text-red-300 border border-red-800' : 'bg-amber-950 text-amber-300 border border-amber-800'}`}>
                              {df.type.toUpperCase()}
                            </span>
                          </td>
                          <td className="p-2 font-mono">({df.x}, {df.y}, {df.z}) mm</td>
                          <td className="p-2 font-mono font-bold text-white">{df.diameter_um} µm</td>
                          <td className="p-2 font-mono text-gray-400">{df.volume_mm3.toExponential(3)} mm³</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
