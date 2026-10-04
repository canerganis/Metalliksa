import React, { useState, useRef, useEffect } from 'react';
import { Layers, Activity, Grid3X3, Flame } from 'lucide-react';

export const ToolpathThermalMapLab: React.FC = () => {
  const [alloy, setAlloy] = useState('IN718');
  const [power, setPower] = useState(250);
  const [speed, setSpeed] = useState(1000);
  const [strategy, setStrategy] = useState('chessboard');
  const [hatch, setHatch] = useState(100);
  const [angle, setAngle] = useState(45);
  const [island, setIsland] = useState(5.0);
  
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/python/lpbf-toolpath-thermal-map", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alloy, power_W: power, speed_mms: speed, strategy, hatch_um: hatch, angle_deg: angle, island_size_mm: island })
      });
      const data = await response.json();
      setResult(data);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  useEffect(() => {
    if (!result || !result.tracks || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Geometry bounds (0 to 10mm mapped to 0 to 600px)
    const scale = 600 / 10.0;
    
    // Find min and max temperature for color mapping
    const temps = result.tracks.map((t: any) => t.t_max);
    const minT = Math.min(...temps);
    const maxT = Math.max(...temps);
    
    // Draw background
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    const getColor = (t: number) => {
      // Normalize between 0 and 1
      const norm = maxT === minT ? 0.5 : (t - minT) / (maxT - minT);
      // Map to blue -> yellow -> red
      const r = Math.floor(255 * norm);
      const g = Math.floor(255 * (1 - Math.abs(norm - 0.5) * 2));
      const b = Math.floor(255 * (1 - norm));
      return `rgb(${r},${g},${b})`;
    };

    // Draw tracks
    result.tracks.forEach((track: any) => {
      ctx.beginPath();
      ctx.moveTo(track.x1 * scale, 600 - track.y1 * scale); // Flip Y
      ctx.lineTo(track.x2 * scale, 600 - track.y2 * scale);
      ctx.strokeStyle = getColor(track.t_max);
      ctx.lineWidth = 2;
      ctx.stroke();
    });
    
  }, [result]);

  return (
    <div className="flex flex-col gap-6 p-6 max-w-6xl mx-auto h-full overflow-y-auto bg-gray-900">
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
        <h2 className="text-2xl font-bold text-white mb-2 flex items-center gap-3">
          <Grid3X3 className="text-blue-400 w-8 h-8" />
          Toolpath Thermal Map (Phases 12 & 17)
        </h2>
        <p className="text-slate-400 mb-6">
          Generates a 2D layer toolpath based on the selected scan strategy (Chessboard / Stripe) and calculates multi-track thermal accumulation.
          Tracks are colored by their maximum temperature (T_max).
        </p>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
            <label className="block text-xs text-slate-400 mb-1">Alloy</label>
            <select aria-label="Alloy" value={alloy} onChange={(e) => setAlloy(e.target.value)} className="w-full bg-slate-900 text-sm text-white border border-slate-700 rounded p-1">
              <option value="IN718">IN718</option>
              <option value="Ti6Al4V">Ti-6Al-4V</option>
              <option value="AlSi10Mg">AlSi10Mg</option>
              <option value="316L SS">316L SS</option>
            </select>
          </div>
          
          <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
            <label className="block text-xs text-slate-400 mb-1">Strategy</label>
            <select aria-label="Strategy" value={strategy} onChange={(e) => setStrategy(e.target.value)} className="w-full bg-slate-900 text-sm text-white border border-slate-700 rounded p-1">
              <option value="chessboard">Chessboard</option>
              <option value="stripe">Stripe</option>
            </select>
          </div>
          
          <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
            <label className="block text-xs text-slate-400 mb-1">Hatch (µm): {hatch}</label>
            <input aria-label="Hatch" type="range" min="50" max="200" value={hatch} onChange={(e) => setHatch(Number(e.target.value))} className="w-full" />
          </div>

          <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
            <label className="block text-xs text-slate-400 mb-1">Angle (Degrees): {angle}</label>
            <input aria-label="Angle" type="range" min="0" max="180" value={angle} onChange={(e) => setAngle(Number(e.target.value))} className="w-full" />
          </div>
        </div>

        <button 
          onClick={handleGenerate}
          disabled={loading}
          className="w-full py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold rounded-lg shadow-lg flex items-center justify-center gap-2"
        >
          {loading ? <Activity className="animate-spin w-5 h-5" /> : <Flame className="w-5 h-5" />}
          {loading ? 'Thermal simulation running...' : 'Calculate Toolpath and Thermal Accumulation'}
        </button>
      </div>

      <div className="flex justify-center bg-slate-950 p-4 border border-slate-800 rounded-xl">
        <canvas ref={canvasRef} width={600} height={600} className="rounded border border-slate-800 shadow-2xl bg-black" />
      </div>
      
      {result && result.tracks && (
        <div className="text-center text-slate-400 text-sm">
          Generated Track Count: <span className="font-bold text-white">{result.total_tracks}</span> |
          Maximum Temperature: <span className="font-bold text-red-400">{Math.max(...result.tracks.map((t: any) => t.t_max)).toFixed(0)} K</span>
        </div>
      )}
    </div>
  );
};
