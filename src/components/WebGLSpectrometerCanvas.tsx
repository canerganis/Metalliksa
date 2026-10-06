import React, { useEffect, useRef, useState, useMemo, useCallback } from "react";
import {
  createGLProgram,
  SPECTROMETER_VERTEX_SHADER,
  SPECTROMETER_FRAGMENT_SHADER,
} from "../render/webglShaderEngine";
import { useVisibleAnimationFrame } from "../hooks/useVisibleAnimationFrame";
import { Zap, Maximize2, RotateCcw, Crosshair, Sparkles } from "lucide-react";

export interface SpectrumDataPoint {
  x: number; // e.g. Energy (keV) or 2-Theta (deg) or Frequency (Hz)
  y: number; // e.g. Counts or Intensity or Impedance
}

export interface PeakAnnotation {
  x: number;
  label: string;
  intensity: number;
  color?: string;
}

interface WebGLSpectrometerCanvasProps {
  data: SpectrumDataPoint[];
  backgroundOverlays?: { name: string; color: string; points: SpectrumDataPoint[] }[];
  xLabel?: string;
  yLabel?: string;
  xUnit?: string;
  yUnit?: string;
  lineColor?: [number, number, number, number]; // [r, g, b, a]
  fillColor?: [number, number, number, number];
  annotations?: PeakAnnotation[];
  height?: number;
  enableGlow?: boolean;
}

export const WebGLSpectrometerCanvas: React.FC<WebGLSpectrometerCanvasProps> = ({
  data,
  backgroundOverlays = [],
  xLabel = "Energy / 2-Theta",
  yLabel = "Intensity / Counts",
  xUnit = "keV",
  yUnit = "CPS",
  lineColor = [0.22, 0.74, 0.97, 1.0], // #38bdf8
  fillColor = [0.22, 0.74, 0.97, 0.25],
  annotations = [],
  height = 360,
  enableGlow = true,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const glRef = useRef<WebGLRenderingContext | null>(null);
  const programRef = useRef<WebGLProgram | null>(null);
  const buffersRef = useRef<{
    mainAreaBuffer: WebGLBuffer | null;
    mainLineBuffer: WebGLBuffer | null;
    peakBuffers: { name: string; color: [number, number, number, number]; buffer: WebGLBuffer | null; count: number }[];
    pointCount: number;
  }>({
    mainAreaBuffer: null,
    mainLineBuffer: null,
    peakBuffers: [],
    pointCount: 0,
  });

  // Pan and Zoom State
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [zoom, setZoom] = useState<{ x: number; y: number }>({ x: 1, y: 1 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [hoverPos, setHoverPos] = useState<{ xVal: number; yVal: number; screenX: number; screenY: number } | null>(null);

  // Compute Data Bounds
  const { minX, maxX, minY, maxY } = useMemo(() => {
    if (!data || data.length === 0) return { minX: 0, maxX: 10, minY: 0, maxY: 1000 };
    let minXVal = Infinity;
    let maxXVal = -Infinity;
    let minYVal = 0;
    let maxYVal = -Infinity;

    for (let i = 0; i < data.length; i++) {
      const pt = data[i];
      if (pt.x < minXVal) minXVal = pt.x;
      if (pt.x > maxXVal) maxXVal = pt.x;
      if (pt.y > maxYVal) maxYVal = pt.y;
    }
    if (maxYVal <= 0) maxYVal = 100;
    // Add 8% headroom
    maxYVal *= 1.08;

    return { minX: minXVal, maxX: maxXVal, minY: minYVal, maxY: maxYVal };
  }, [data]);

  // Initialize WebGL Context & Program
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const gl = canvas.getContext("webgl", {
      antialias: true,
      alpha: true,
      preserveDrawingBuffer: false,
      powerPreference: "high-performance",
    });

    if (!gl) {
      console.error("WebGL not supported for spectrometer canvas.");
      return;
    }

    glRef.current = gl;
    const program = createGLProgram(gl, SPECTROMETER_VERTEX_SHADER, SPECTROMETER_FRAGMENT_SHADER);
    if (!program) return;
    programRef.current = program;

    // Enable alpha blending for smooth area fills
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    return () => {
      if (program) gl.deleteProgram(program);
    };
  }, []);

  // Upload Spectrum Data to GPU Buffers
  useEffect(() => {
    const gl = glRef.current;
    if (!gl || !data || data.length === 0) return;

    const rangeX = maxX - minX || 1;
    const rangeY = maxY - minY || 1;

    // 1. Main Line Vertices: [x_norm, y_norm, ...]
    const lineVertices = new Float32Array(data.length * 2);
    for (let i = 0; i < data.length; i++) {
      lineVertices[i * 2] = (data[i].x - minX) / rangeX;
      lineVertices[i * 2 + 1] = (data[i].y - minY) / rangeY;
    }

    // 2. Main Area Triangle Strip Vertices: [x_norm, y_norm, x_norm, 0, ...]
    const areaVertices = new Float32Array(data.length * 4);
    for (let i = 0; i < data.length; i++) {
      const normX = (data[i].x - minX) / rangeX;
      const normY = (data[i].y - minY) / rangeY;
      areaVertices[i * 4] = normX;
      areaVertices[i * 4 + 1] = normY;
      areaVertices[i * 4 + 2] = normX;
      areaVertices[i * 4 + 3] = 0.0; // Baseline
    }

    // Create / Update Buffers
    const lineBuf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, lineBuf);
    gl.bufferData(gl.ARRAY_BUFFER, lineVertices, gl.STATIC_DRAW);

    const areaBuf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, areaBuf);
    gl.bufferData(gl.ARRAY_BUFFER, areaVertices, gl.STATIC_DRAW);

    // 3. Background overlay buffers
    const peakBufs = backgroundOverlays.map((peak) => {
      const pLineVertices = new Float32Array(peak.points.length * 2);
      for (let i = 0; i < peak.points.length; i++) {
        pLineVertices[i * 2] = (peak.points[i].x - minX) / rangeX;
        pLineVertices[i * 2 + 1] = (peak.points[i].y - minY) / rangeY;
      }
      const pBuf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, pBuf);
      gl.bufferData(gl.ARRAY_BUFFER, pLineVertices, gl.STATIC_DRAW);

      // Parse peak hex color or fallback
      const color: [number, number, number, number] = [0.65, 0.35, 0.95, 0.9];
      return {
        name: peak.name,
        color,
        buffer: pBuf,
        count: peak.points.length,
      };
    });

    buffersRef.current = {
      mainLineBuffer: lineBuf,
      mainAreaBuffer: areaBuf,
      peakBuffers: peakBufs,
      pointCount: data.length,
    };
  }, [data, backgroundOverlays, minX, maxX, minY, maxY]);

  // Render Frame onto Canvas via WebGL
  const renderFrame = useCallback(() => {
    const gl = glRef.current;
    const program = programRef.current;
    const buffers = buffersRef.current;
    const canvas = canvasRef.current;

    if (!gl || !program || !canvas || buffers.pointCount === 0) return;

    // Resize canvas resolution to device pixel ratio for razor-sharp retina lines
    const dpr = window.devicePixelRatio || 1;
    const displayWidth = Math.round(canvas.clientWidth * dpr);
    const displayHeight = Math.round(canvas.clientHeight * dpr);

    if (canvas.width !== displayWidth || canvas.height !== displayHeight) {
      canvas.width = displayWidth;
      canvas.height = displayHeight;
    }

    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(0.03, 0.05, 0.09, 1.0); // #080d16
    gl.clear(gl.COLOR_BUFFER_BIT);

    gl.useProgram(program);

    // Uniforms
    const uResolution = gl.getUniformLocation(program, "u_resolution");
    const uPan = gl.getUniformLocation(program, "u_pan");
    const uZoom = gl.getUniformLocation(program, "u_zoom");
    const uLineColor = gl.getUniformLocation(program, "u_lineColor");
    const uFillColor = gl.getUniformLocation(program, "u_fillColor");
    const uIsFill = gl.getUniformLocation(program, "u_isFill");
    const uGlow = gl.getUniformLocation(program, "u_glowIntensity");

    gl.uniform2f(uResolution, canvas.width, canvas.height);
    gl.uniform2f(uPan, pan.x, pan.y);
    gl.uniform2f(uZoom, zoom.x, zoom.y);
    gl.uniform4fv(uLineColor, new Float32Array(lineColor));
    gl.uniform4fv(uFillColor, new Float32Array(fillColor));
    gl.uniform1f(uGlow, enableGlow ? 1.0 : 0.0);

    const aPosition = gl.getAttribLocation(program, "a_position");
    gl.enableVertexAttribArray(aPosition);

    // 1. Draw Area Gradient Fill
    if (buffers.mainAreaBuffer) {
      gl.bindBuffer(gl.ARRAY_BUFFER, buffers.mainAreaBuffer);
      gl.vertexAttribPointer(aPosition, 2, gl.FLOAT, false, 0, 0);
      gl.uniform1f(uIsFill, 1.0);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, buffers.pointCount * 2);
    }

    // 2. Draw Main Spectrum Stroke
    if (buffers.mainLineBuffer) {
      gl.bindBuffer(gl.ARRAY_BUFFER, buffers.mainLineBuffer);
      gl.vertexAttribPointer(aPosition, 2, gl.FLOAT, false, 0, 0);
      gl.uniform1f(uIsFill, 0.0);
      gl.drawArrays(gl.LINE_STRIP, 0, buffers.pointCount);
    }

    // 3. Draw Deconvolution Sub-Peaks
    for (const p of buffers.peakBuffers) {
      if (p.buffer) {
        gl.bindBuffer(gl.ARRAY_BUFFER, p.buffer);
        gl.vertexAttribPointer(aPosition, 2, gl.FLOAT, false, 0, 0);
        gl.uniform4fv(uLineColor, new Float32Array(p.color));
        gl.uniform1f(uIsFill, 0.0);
        gl.drawArrays(gl.LINE_STRIP, 0, p.count);
      }
    }
  }, [pan, zoom, lineColor, fillColor, enableGlow]);

  // Request Animation Frame on Pan/Zoom change
  useVisibleAnimationFrame(renderFrame);

  // Mouse Interaction: Pan & Zoom
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX, y: e.clientY });
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const clientY = e.clientY - rect.top;

    if (isDragging) {
      const dx = (e.clientX - dragStart.x) / (rect.width * zoom.x);
      const dy = (e.clientY - dragStart.y) / (rect.height * zoom.y);
      setPan((prev) => ({
        x: Math.max(-0.5, Math.min(1.5, prev.x - dx)),
        y: Math.max(-0.5, Math.min(1.5, prev.y + dy)),
      }));
      setDragStart({ x: e.clientX, y: e.clientY });
    }

    // Normalized coordinates
    const normX = clientX / rect.width;
    const currentX = (normX / zoom.x + pan.x) * (maxX - minX) + minX;

    // Find nearest point
    let nearestY = 0;
    if (data.length > 0) {
      let closestDist = Infinity;
      for (let i = 0; i < data.length; i++) {
        const dist = Math.abs(data[i].x - currentX);
        if (dist < closestDist) {
          closestDist = dist;
          nearestY = data[i].y;
        }
      }
    }

    setHoverPos({
      xVal: currentX,
      yVal: nearestY,
      screenX: clientX,
      screenY: clientY,
    });
  };

  const handleMouseUp = () => setIsDragging(false);
  const handleMouseLeave = () => {
    setIsDragging(false);
    setHoverPos(null);
  };

  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
    setZoom((prev) => ({
      x: Math.max(0.5, Math.min(25.0, prev.x * zoomFactor)),
      y: Math.max(0.5, Math.min(25.0, prev.y * (e.shiftKey ? zoomFactor : 1.0))),
    }));
  };

  const resetView = () => {
    setPan({ x: 0, y: 0 });
    setZoom({ x: 1, y: 1 });
  };

  return (
    <div id="webgl-spectrometer-container" className="relative w-full rounded-2xl overflow-hidden border border-slate-800 bg-[#080d16] select-none">
      {/* Top Overlay Badge & Quick Toolbar */}
      <div className="absolute top-3 left-3 right-3 z-10 flex items-center justify-between pointer-events-none">
        <div className="flex items-center gap-2 bg-slate-900/80 backdrop-blur-md px-3 py-1 rounded-xl border border-slate-700/60 shadow-lg pointer-events-auto">
          <Zap className="w-3.5 h-3.5 text-sky-400 animate-pulse" />
          <span className="text-[11px] font-mono font-bold text-sky-300">
            WebGL Shader Core
          </span>
          <span className="text-[10px] text-slate-400 font-mono">
            {data.length.toLocaleString()} pts
          </span>
        </div>

        <div className="flex items-center gap-1.5 pointer-events-auto">
          <button
            onClick={resetView}
            title="Reset View"
            className="p-1.5 bg-slate-900/80 hover:bg-slate-800 text-slate-300 rounded-lg border border-slate-700/60 text-xs transition-all shadow-md cursor-pointer flex items-center gap-1"
          >
            <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-[10px] font-mono">1:1</span>
          </button>
        </div>
      </div>

      {/* Main WebGL Canvas */}
      <canvas
        ref={canvasRef}
        style={{ height: `${height}px`, width: "100%" }}
        className="cursor-crosshair block"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
        onWheel={handleWheel}
      />

      {/* Axis Labels */}
      <div className="absolute bottom-2 left-4 text-[10px] font-mono text-slate-400 pointer-events-none">
        {minX.toFixed(1)} {xUnit}
      </div>
      <div className="absolute bottom-2 right-4 text-[10px] font-mono text-slate-400 pointer-events-none">
        {maxX.toFixed(1)} {xUnit}
      </div>
      <div className="absolute bottom-2 left-1/2 -translate-x-1/2 text-[10px] font-mono font-bold text-slate-400 pointer-events-none">
        {xLabel} ({xUnit})
      </div>

      {/* Peak Annotations Overlaid on Canvas */}
      {annotations.map((ann, idx) => {
        const normX = (ann.x - minX) / (maxX - minX);
        const screenXPercent = ((normX - pan.x) * zoom.x) * 100;
        if (screenXPercent < -5 || screenXPercent > 105) return null;

        return (
          <div
            key={idx}
            className="absolute top-10 -translate-x-1/2 pointer-events-none flex flex-col items-center z-10"
            style={{ left: `${screenXPercent}%` }}
          >
            <div className="px-1.5 py-0.5 rounded bg-slate-900/90 border border-sky-500/40 text-[9px] font-mono font-bold text-sky-300 shadow-md whitespace-nowrap">
              {ann.label} ({ann.x.toFixed(2)})
            </div>
            <div className="w-px h-6 bg-sky-400/40 mt-0.5" />
          </div>
        );
      })}

      {/* Interactive Hover Crosshair & Tooltip */}
      {hoverPos && (
        <div
          className="absolute pointer-events-none z-20"
          style={{ left: `${hoverPos.screenX}px`, top: `${hoverPos.screenY}px` }}
        >
          {/* Vertical Guideline */}
          <div className="absolute top-[-200px] bottom-[-200px] left-0 w-px bg-sky-400/50 border-r border-sky-300/30" />
          {/* Tooltip Card */}
          <div className="absolute left-3 top-[-35px] bg-slate-900/95 border border-sky-500/60 rounded-xl px-2.5 py-1.5 shadow-2xl text-[10px] font-mono text-white whitespace-nowrap backdrop-blur-md">
            <div>
              <span className="text-slate-400">{xLabel}: </span>
              <span className="text-sky-300 font-bold">{hoverPos.xVal.toFixed(3)} {xUnit}</span>
            </div>
            <div>
              <span className="text-slate-400">{yLabel}: </span>
              <span className="text-emerald-400 font-bold">{hoverPos.yVal.toFixed(1)} {yUnit}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
