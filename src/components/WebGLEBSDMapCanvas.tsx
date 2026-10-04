import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  createGLProgram,
  EBSD_VORONOI_VERTEX_SHADER,
  EBSD_VORONOI_FRAGMENT_SHADER,
} from "../render/webglShaderEngine";
import { useVisibleAnimationFrame } from "../hooks/useVisibleAnimationFrame";
import {
  Maximize2,
  Sliders,
  Layers,
  Compass,
  Sparkles,
  Zap,
  RotateCcw,
  Activity,
  Eye,
} from "lucide-react";

interface WebGLEBSDMapCanvasProps {
  grainSizeUm?: number;
  elongation?: number;
  mode?: "ipf" | "schmid" | "kam" | "twin" | "band_contrast";
  width?: number;
  height?: number;
  onModeChange?: (mode: "ipf" | "schmid" | "kam" | "twin" | "band_contrast") => void;
}

export const WebGLEBSDMapCanvas: React.FC<WebGLEBSDMapCanvasProps> = ({
  grainSizeUm = 12.5,
  elongation = 1.15,
  mode = "ipf",
  height = 360,
  onModeChange,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const glRef = useRef<WebGLRenderingContext | null>(null);
  const programRef = useRef<WebGLProgram | null>(null);
  const quadBufferRef = useRef<WebGLBuffer | null>(null);

  const [activeShaderMode, setActiveShaderMode] = useState<
    "ipf" | "schmid" | "kam" | "twin" | "band_contrast"
  >(mode);

  const [grainScale, setGrainScale] = useState<number>(36.0);
  const [hoverPixel, setHoverPixel] = useState<{ x: number; y: number } | null>(null);

  // Sync mode prop
  useEffect(() => {
    setActiveShaderMode(mode);
  }, [mode]);

  // Map grain size (um) to GPU Voronoi frequency scale
  useEffect(() => {
    // Smaller um -> higher frequency (more grains)
    const scale = Math.max(12.0, Math.min(90.0, (250 / Math.max(grainSizeUm, 2.0))));
    setGrainScale(scale);
  }, [grainSizeUm]);

  // Initialize WebGL
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const gl = canvas.getContext("webgl", {
      antialias: true,
      preserveDrawingBuffer: false,
      powerPreference: "high-performance",
    });

    if (!gl) {
      console.error("WebGL context creation failed for EBSD Map");
      return;
    }

    glRef.current = gl;
    const program = createGLProgram(gl, EBSD_VORONOI_VERTEX_SHADER, EBSD_VORONOI_FRAGMENT_SHADER);
    if (!program) return;
    programRef.current = program;

    // Full-screen Quad [-1..1]
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
    quadBufferRef.current = quadBuf;

    return () => {
      if (program) gl.deleteProgram(program);
    };
  }, []);

  // Render Frame
  const renderFrame = useCallback(() => {
    const gl = glRef.current;
    const program = programRef.current;
    const canvas = canvasRef.current;
    const quadBuf = quadBufferRef.current;

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

    // Uniform mapping
    const uResolution = gl.getUniformLocation(program, "u_resolution");
    const uGrainScale = gl.getUniformLocation(program, "u_grainScale");
    const uAspectRatio = gl.getUniformLocation(program, "u_aspectRatio");
    const uElongation = gl.getUniformLocation(program, "u_elongation");
    const uMode = gl.getUniformLocation(program, "u_mode");
    const uTime = gl.getUniformLocation(program, "u_time");

    gl.uniform2f(uResolution, canvas.width, canvas.height);
    gl.uniform1f(uGrainScale, grainScale);
    gl.uniform1f(uAspectRatio, canvas.width / canvas.height);
    gl.uniform1f(uElongation, elongation);

    let modeInt = 0;
    if (activeShaderMode === "ipf") modeInt = 0;
    else if (activeShaderMode === "schmid") modeInt = 1;
    else if (activeShaderMode === "kam") modeInt = 2;
    else if (activeShaderMode === "twin") modeInt = 3;
    else if (activeShaderMode === "band_contrast") modeInt = 4;

    gl.uniform1i(uMode, modeInt);
    gl.uniform1f(uTime, performance.now() * 0.001);

    const aPosition = gl.getAttribLocation(program, "a_position");
    gl.enableVertexAttribArray(aPosition);
    gl.bindBuffer(gl.ARRAY_BUFFER, quadBuf);
    gl.vertexAttribPointer(aPosition, 2, gl.FLOAT, false, 0, 0);

    gl.drawArrays(gl.TRIANGLES, 0, 6);
  }, [grainScale, elongation, activeShaderMode]);

  useVisibleAnimationFrame(renderFrame);

  const handleModeSelect = (m: "ipf" | "schmid" | "kam" | "twin" | "band_contrast") => {
    setActiveShaderMode(m);
    onModeChange?.(m);
  };

  return (
    <div id="webgl-ebsd-container" className="relative w-full rounded-2xl overflow-hidden border border-slate-800 bg-[#050811] shadow-2xl select-none">
      {/* Top Header Controls Overlay */}
      <div className="absolute top-3 left-3 right-3 z-10 flex flex-wrap items-center justify-between gap-2 pointer-events-none">
        <div className="flex items-center gap-2 bg-slate-950/80 backdrop-blur-md px-3 py-1.5 rounded-xl border border-slate-700/60 shadow-lg pointer-events-auto">
          <Zap className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
          <span className="text-[11px] font-mono font-bold text-cyan-300">
            EBSD GPU Shader (60 FPS)
          </span>
          <span className="text-[10px] text-slate-400 font-mono">
            d={grainSizeUm.toFixed(1)} µm | AR={elongation.toFixed(2)}
          </span>
        </div>

        {/* Shader Mode Switcher Buttons */}
        <div className="flex items-center gap-1 bg-slate-950/90 backdrop-blur-md p-1 rounded-xl border border-slate-800 pointer-events-auto">
          <button
            onClick={() => handleModeSelect("ipf")}
            className={`px-2 py-1 rounded-lg text-[10px] font-mono font-semibold transition-all cursor-pointer ${
              activeShaderMode === "ipf"
                ? "bg-gradient-to-r from-red-600 to-blue-600 text-white shadow-md"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            IPF-Z Orientation
          </button>
          <button
            onClick={() => handleModeSelect("schmid")}
            className={`px-2 py-1 rounded-lg text-[10px] font-mono font-semibold transition-all cursor-pointer ${
              activeShaderMode === "schmid"
                ? "bg-gradient-to-r from-blue-600 to-red-600 text-white shadow-md"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Schmid Factor
          </button>
          <button
            onClick={() => handleModeSelect("kam")}
            className={`px-2 py-1 rounded-lg text-[10px] font-mono font-semibold transition-all cursor-pointer ${
              activeShaderMode === "kam"
                ? "bg-gradient-to-r from-emerald-600 to-rose-600 text-white shadow-md"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            KAM / Dislocations
          </button>
          <button
            onClick={() => handleModeSelect("twin")}
            className={`px-2 py-1 rounded-lg text-[10px] font-mono font-semibold transition-all cursor-pointer ${
              activeShaderMode === "twin"
                ? "bg-amber-600 text-white shadow-md"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Σ3 Twins
          </button>
        </div>
      </div>

      {/* Main WebGL Canvas */}
      <canvas
        ref={canvasRef}
        style={{ height: `${height}px`, width: "100%" }}
        className="block cursor-crosshair"
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          setHoverPixel({ x: e.clientX - rect.left, y: e.clientY - rect.top });
        }}
        onMouseLeave={() => setHoverPixel(null)}
      />

      {/* Bottom Color Legend Overlay */}
      <div className="absolute bottom-3 left-3 z-10 pointer-events-none bg-slate-950/85 backdrop-blur-md px-3 py-1.5 rounded-xl border border-slate-800 text-[10px] font-mono text-slate-300 flex items-center gap-3">
        {activeShaderMode === "ipf" && (
          <>
            <span className="text-slate-400">IPF-Z Triangle:</span>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-red-600" />
              <span>[001]</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-600" />
              <span>[111]</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-600" />
              <span>[101]</span>
            </div>
          </>
        )}
        {activeShaderMode === "schmid" && (
          <>
            <span className="text-slate-400">Schmid (m):</span>
            <span>0.35 (Low)</span>
            <div className="w-16 h-2 rounded bg-gradient-to-r from-blue-600 via-yellow-500 to-red-600" />
            <span>0.50 (Max)</span>
          </>
        )}
        {activeShaderMode === "kam" && (
          <>
            <span className="text-slate-400">KAM Local Misorientation:</span>
            <span>0° (Annealed)</span>
            <div className="w-16 h-2 rounded bg-gradient-to-r from-emerald-500 to-rose-600" />
            <span>5° (High Dislocation)</span>
          </>
        )}
        {activeShaderMode === "twin" && (
          <>
            <span className="text-slate-400">Boundary Type:</span>
            <span className="text-rose-400 font-bold">■ Σ3 Coherent Annealing Twin</span>
            <span className="text-slate-400">■ Random HAGB</span>
          </>
        )}
      </div>

      {/* Micron Scale Bar */}
      <div className="absolute bottom-3 right-3 z-10 pointer-events-none bg-slate-950/85 backdrop-blur-md px-3 py-1.5 rounded-xl border border-slate-800 text-[10px] font-mono text-slate-300 flex flex-col items-center">
        <div className="w-16 h-1 bg-white mb-1 rounded-full shadow-md" />
        <span>50 µm</span>
      </div>
    </div>
  );
};
