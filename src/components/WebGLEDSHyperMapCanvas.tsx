import React, { useEffect, useRef, useState, useCallback } from "react";
import { useVisibleAnimationFrame } from "../hooks/useVisibleAnimationFrame";
import {
  createGLProgram,
  EDS_MAP_VERTEX_SHADER,
  EDS_MAP_FRAGMENT_SHADER,
} from "../render/webglShaderEngine";
import { Zap, Sliders, Eye, Layers, Palette, Sparkles, RotateCcw } from "lucide-react";

interface WebGLEDSHyperMapCanvasProps {
  height?: number;
  activeElements?: string[]; // e.g. ["Ni", "Cr", "Ti", "Nb", "Al"]
  gamma?: number;
  contrast?: number;
  brightness?: number;
}

export const WebGLEDSHyperMapCanvas: React.FC<WebGLEDSHyperMapCanvasProps> = ({
  height = 360,
  activeElements = ["Ni", "Cr", "Ti", "Nb", "Al"],
  gamma = 1.0,
  contrast = 1.0,
  brightness = 0.0,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const glRef = useRef<WebGLRenderingContext | null>(null);
  const programRef = useRef<WebGLProgram | null>(null);
  const quadBufRef = useRef<WebGLBuffer | null>(null);

  // Channel Bitmask: Ni=1, Cr=2, Ti=4, Nb=8, Al=16, Fe=32
  const [enabledChannels, setEnabledChannels] = useState<{ [el: string]: boolean }>({
    Ni: true,
    Cr: true,
    Ti: true,
    Nb: true,
    Al: true,
  });

  const [localGamma, setLocalGamma] = useState<number>(gamma);
  const [localContrast, setLocalContrast] = useState<number>(contrast);
  const [showControls, setShowControls] = useState<boolean>(false);

  // Sync props
  useEffect(() => {
    setLocalGamma(gamma);
    setLocalContrast(contrast);
  }, [gamma, contrast]);

  // Compute Bitmask
  const activeBitmask = React.useMemo(() => {
    let mask = 0;
    if (enabledChannels["Ni"]) mask |= 1;
    if (enabledChannels["Cr"]) mask |= 2;
    if (enabledChannels["Ti"]) mask |= 4;
    if (enabledChannels["Nb"]) mask |= 8;
    if (enabledChannels["Al"]) mask |= 16;
    return mask;
  }, [enabledChannels]);

  // Initialize WebGL
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const gl = canvas.getContext("webgl", {
      antialias: true,
      powerPreference: "high-performance",
    });

    if (!gl) return;
    glRef.current = gl;

    const program = createGLProgram(gl, EDS_MAP_VERTEX_SHADER, EDS_MAP_FRAGMENT_SHADER);
    if (!program) return;
    programRef.current = program;

    const quadVertices = new Float32Array([
      -1, -1,
       1, -1,
      -1,  1,
      -1,  1,
       1, -1,
       1,  1,
    ]);

    const quadBuf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, quadBuf);
    gl.bufferData(gl.ARRAY_BUFFER, quadVertices, gl.STATIC_DRAW);
    quadBufRef.current = quadBuf;

    return () => {
      if (program) gl.deleteProgram(program);
    };
  }, []);

  // Render Frame
  const renderFrame = useCallback(() => {
    const gl = glRef.current;
    const program = programRef.current;
    const canvas = canvasRef.current;
    const quadBuf = quadBufRef.current;

    if (!gl || !program || !canvas || !quadBuf) return;

    const dpr = window.devicePixelRatio || 1;
    const displayWidth = Math.round(canvas.clientWidth * dpr);
    const displayHeight = Math.round(canvas.clientHeight * dpr);

    if (canvas.width !== displayWidth || canvas.height !== displayHeight) {
      canvas.width = displayWidth;
      canvas.height = displayHeight;
    }

    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.useProgram(program);

    const uResolution = gl.getUniformLocation(program, "u_resolution");
    const uGamma = gl.getUniformLocation(program, "u_gamma");
    const uContrast = gl.getUniformLocation(program, "u_contrast");
    const uBrightness = gl.getUniformLocation(program, "u_brightness");
    const uMask = gl.getUniformLocation(program, "u_activeElementMask");

    gl.uniform2f(uResolution, canvas.width, canvas.height);
    gl.uniform1f(uGamma, localGamma);
    gl.uniform1f(uContrast, localContrast);
    gl.uniform1f(uBrightness, brightness);
    gl.uniform1i(uMask, activeBitmask);

    const aPosition = gl.getAttribLocation(program, "a_position");
    gl.enableVertexAttribArray(aPosition);
    gl.bindBuffer(gl.ARRAY_BUFFER, quadBuf);
    gl.vertexAttribPointer(aPosition, 2, gl.FLOAT, false, 0, 0);

    gl.drawArrays(gl.TRIANGLES, 0, 6);
  }, [localGamma, localContrast, brightness, activeBitmask]);

  useVisibleAnimationFrame(renderFrame);

  const toggleElement = (el: string) => {
    setEnabledChannels((prev) => ({
      ...prev,
      [el]: !prev[el],
    }));
  };

  return (
    <div id="webgl-eds-map-container" className="relative w-full rounded-2xl overflow-hidden border border-slate-800 bg-[#050811] shadow-2xl select-none">
      {/* Top Header Controls */}
      <div className="absolute top-3 left-3 right-3 z-10 flex flex-wrap items-center justify-between gap-2 pointer-events-none">
        <div className="flex items-center gap-2 bg-slate-950/80 backdrop-blur-md px-3 py-1.5 rounded-xl border border-slate-700/60 shadow-lg pointer-events-auto">
          <Zap className="w-3.5 h-3.5 text-violet-400 animate-pulse" />
          <span className="text-[11px] font-mono font-bold text-violet-300">
            Multi-Spectral EDS WebGL Blend (GPU)
          </span>
        </div>

        {/* Elemental Channel Selector Pills */}
        <div className="flex items-center gap-1 bg-slate-950/90 backdrop-blur-md p-1 rounded-xl border border-slate-800 pointer-events-auto">
          <button
            onClick={() => toggleElement("Ni")}
            className={`px-2 py-1 rounded-lg text-[10px] font-mono font-bold transition-all cursor-pointer ${
              enabledChannels["Ni"] ? "bg-blue-600 text-white shadow-md" : "text-slate-500 bg-slate-900"
            }`}
          >
            Ni-Kα (Blue)
          </button>
          <button
            onClick={() => toggleElement("Cr")}
            className={`px-2 py-1 rounded-lg text-[10px] font-mono font-bold transition-all cursor-pointer ${
              enabledChannels["Cr"] ? "bg-emerald-600 text-white shadow-md" : "text-slate-500 bg-slate-900"
            }`}
          >
            Cr-Kα (Green)
          </button>
          <button
            onClick={() => toggleElement("Ti")}
            className={`px-2 py-1 rounded-lg text-[10px] font-mono font-bold transition-all cursor-pointer ${
              enabledChannels["Ti"] ? "bg-amber-500 text-white shadow-md" : "text-slate-500 bg-slate-900"
            }`}
          >
            Ti-Kα (Yellow)
          </button>
          <button
            onClick={() => toggleElement("Nb")}
            className={`px-2 py-1 rounded-lg text-[10px] font-mono font-bold transition-all cursor-pointer ${
              enabledChannels["Nb"] ? "bg-fuchsia-600 text-white shadow-md" : "text-slate-500 bg-slate-900"
            }`}
          >
            Nb-Lα (Magenta)
          </button>
          <button
            onClick={() => toggleElement("Al")}
            className={`px-2 py-1 rounded-lg text-[10px] font-mono font-bold transition-all cursor-pointer ${
              enabledChannels["Al"] ? "bg-cyan-500 text-white shadow-md" : "text-slate-500 bg-slate-900"
            }`}
          >
            Al-Kα (Cyan)
          </button>
          <button
            onClick={() => setShowControls(!showControls)}
            title="Shader Adjustment Sliders"
            className="p-1 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 transition cursor-pointer"
          >
            <Sliders className="w-3.5 h-3.5 text-sky-400" />
          </button>
        </div>
      </div>

      {/* Main WebGL Canvas */}
      <canvas
        ref={canvasRef}
        style={{ height: `${height}px`, width: "100%" }}
        className="block cursor-crosshair"
      />

      {/* Shader Dynamic Contrast & Gamma Adjuster Popup */}
      {showControls && (
        <div className="absolute top-14 right-3 z-20 bg-slate-950/95 border border-slate-700/80 rounded-xl p-3 shadow-2xl space-y-2 text-xs font-mono backdrop-blur-md w-56">
          <div className="flex justify-between items-center text-slate-300">
            <span>GPU Gamma ({localGamma.toFixed(2)})</span>
            <input aria-label="GPU Gamma"
              type="range"
              min="0.4"
              max="2.5"
              step="0.05"
              value={localGamma}
              onChange={(e) => setLocalGamma(parseFloat(e.target.value))}
              className="w-24 accent-sky-500"
            />
          </div>
          <div className="flex justify-between items-center text-slate-300">
            <span>Contrast ({localContrast.toFixed(2)})</span>
            <input aria-label="Contrast"
              type="range"
              min="0.5"
              max="2.0"
              step="0.05"
              value={localContrast}
              onChange={(e) => setLocalContrast(parseFloat(e.target.value))}
              className="w-24 accent-sky-500"
            />
          </div>
        </div>
      )}

      {/* Micron Scale Bar */}
      <div className="absolute bottom-3 right-3 z-10 pointer-events-none bg-slate-950/85 backdrop-blur-md px-3 py-1.5 rounded-xl border border-slate-800 text-[10px] font-mono text-slate-300 flex flex-col items-center">
        <div className="w-16 h-1 bg-white mb-1 rounded-full shadow-md" />
        <span>25 µm</span>
      </div>
    </div>
  );
};
