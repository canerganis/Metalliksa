import React, { useRef, useEffect, useState, useMemo } from "react";
import { area as d3Area, axisBottom as d3AxisBottom, axisLeft as d3AxisLeft, axisRight as d3AxisRight, bisector as d3Bisector, curveMonotoneX as d3CurveMonotoneX, line as d3Line, max as d3Max, min as d3Min, pointer as d3Pointer, scaleLinear as d3ScaleLinear, select as d3Select } from "d3";
import type { ScaleLinear } from "d3";
import {
  TrendingUp,
  Activity,
  Layers,
  Sparkles,
  Download,
  Info,
  Maximize2,
  Minimize2,
  Sliders,
  ChevronRight,
  Flame,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { SimulationTimePoint, ThermalStage, MaterialThermalProfile } from "../types/thermalKinetic";

export type ChartDisplayMode = "grain-zener" | "dual-temp" | "growth-rate" | "hall-petch";

export interface EnrichedSimulationTimePoint extends SimulationTimePoint { [key: string]: any;
  growthRate_um_per_min: number;
}

interface GrainEvolutionD3ChartProps {
  timePoints: SimulationTimePoint[];
  stages: ThermalStage[];
  material: MaterialThermalProfile;
  totalTime_min: number;
  playbackTime_min: number;
  initialGrainSize_um: number;
  onSeekTime?: (time_min: number) => void;
}

export const GrainEvolutionD3Chart: React.FC<GrainEvolutionD3ChartProps> = ({
  timePoints,
  stages,
  material,
  totalTime_min,
  playbackTime_min,
  initialGrainSize_um,
  onSeekTime,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);

  const [displayMode, setDisplayMode] = useState<ChartDisplayMode>("grain-zener");
  const [hoveredPoint, setHoveredPoint] = useState<EnrichedSimulationTimePoint | null>(null);
  const [hoveredPos, setHoveredPos] = useState<{ x: number; y: number } | null>(null);
  const [isHovered, setIsHovered] = useState<boolean>(false);
  const [dimensions, setDimensions] = useState<{ width: number; height: number }>({
    width: 680,
    height: 320,
  });

  // Calculate stage cumulative start and end times for stage boundary bands
  const stageIntervals = useMemo(() => {
    let accumulated = 0;
    return stages.map((st, idx) => {
      const start = accumulated;
      accumulated += st.duration_min;
      return {
        stage: st,
        index: idx,
        startTime_min: start,
        endTime_min: accumulated,
      };
    });
  }, [stages]);

  // Derived growth rates: dD/dt (um/min)
  const enrichedTimePoints: EnrichedSimulationTimePoint[] = useMemo(() => {
    if (!timePoints || timePoints.length === 0) return [];
    return timePoints.map((pt, i, arr) => {
      let growthRate = 0;
      if (i > 0) {
        const prev = arr[i - 1];
        const dt = pt.time_min - prev.time_min;
        if (dt > 0.0001) {
          growthRate = Math.max(0, (pt.grainSize_um - prev.grainSize_um) / dt);
        }
      }
      return {
        ...pt,
        growthRate_um_per_min: parseFloat(growthRate.toFixed(4)),
      };
    });
  }, [timePoints]);

  // Metrics summary
  const summaryMetrics = useMemo(() => {
    if (!enrichedTimePoints || enrichedTimePoints.length === 0) {
      return {
        initialD: initialGrainSize_um,
        finalD: initialGrainSize_um,
        maxD: initialGrainSize_um,
        coarseningRatio: 1.0,
        maxGrowthRate: 0,
        finalASTM_G: 8.0,
        deltaYield_MPa: 0,
      };
    }

    const finalPt = enrichedTimePoints[enrichedTimePoints.length - 1];
    const firstPt = enrichedTimePoints[0];
    const maxD = Math.max(...enrichedTimePoints.map((p) => p.grainSize_um));
    const maxRate = Math.max(...enrichedTimePoints.map((p) => p.growthRate_um_per_min || 0));
    const coarseningRatio = parseFloat((finalPt.grainSize_um / Math.max(0.1, initialGrainSize_um)).toFixed(2));
    const deltaYield = finalPt.yieldStrength_MPa - firstPt.yieldStrength_MPa;

    return {
      initialD: initialGrainSize_um,
      finalD: finalPt.grainSize_um,
      maxD: parseFloat(maxD.toFixed(2)),
      coarseningRatio,
      maxGrowthRate: parseFloat(maxRate.toFixed(3)),
      finalASTM_G: finalPt.astmGrainSizeNumber_G,
      deltaYield_MPa: deltaYield,
    };
  }, [enrichedTimePoints, initialGrainSize_um]);

  // ResizeObserver for fluid responsive D3 rendering
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0) {
          setDimensions({
            width: Math.max(320, Math.floor(entry.contentRect.width)),
            height: 320,
          });
        }
      }
    });

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Main D3 Rendering Engine
  useEffect(() => {
    if (!svgRef.current || enrichedTimePoints.length === 0) return;

    const svg = d3Select(svgRef.current);
    svg.selectAll("*").remove();

    const { width, height } = dimensions;
    const margin = { top: 28, right: 55, bottom: 42, left: 55 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    if (innerWidth <= 0 || innerHeight <= 0) return;

    const g = svg
      .attr("width", width)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // X Scale (Time in minutes)
    const maxX = Math.max(1, totalTime_min);
    const xScale = d3ScaleLinear().domain([0, maxX]).range([0, innerWidth]);

    // Primary Y Scale (Left Axis) - Depends on Mode
    let yPrimaryScale: ScaleLinear<number, number>;
    let ySecondaryScale: ScaleLinear<number, number> | null = null;

    if (displayMode === "grain-zener") {
      const maxVal = Math.max(
        30,
        d3Max(enrichedTimePoints, (d: EnrichedSimulationTimePoint) => Math.max(d.grainSize_um, Math.min(250, d.zenerLimit_um))) ?? 30
      );
      yPrimaryScale = d3ScaleLinear()
        .domain([0, maxVal * 1.1])
        .nice()
        .range([innerHeight, 0]);

      // Secondary axis for ASTM G Number
      ySecondaryScale = d3ScaleLinear().domain([14, 0]).range([innerHeight, 0]);
    } else if (displayMode === "dual-temp") {
      const maxGrain = Math.max(30, d3Max(enrichedTimePoints, (d: EnrichedSimulationTimePoint) => d.grainSize_um) ?? 30);
      yPrimaryScale = d3ScaleLinear()
        .domain([0, maxGrain * 1.15])
        .nice()
        .range([innerHeight, 0]);

      const maxTemp = Math.max(1000, d3Max(enrichedTimePoints, (d: EnrichedSimulationTimePoint) => d.temperature_C) ?? 1000);
      ySecondaryScale = d3ScaleLinear()
        .domain([0, maxTemp * 1.1])
        .nice()
        .range([innerHeight, 0]);
    } else if (displayMode === "growth-rate") {
      const maxRate = Math.max(0.05, d3Max(enrichedTimePoints, (d: EnrichedSimulationTimePoint) => d.growthRate_um_per_min) ?? 0.05);
      yPrimaryScale = d3ScaleLinear()
        .domain([0, maxRate * 1.2])
        .nice()
        .range([innerHeight, 0]);

      const maxGrain = Math.max(30, d3Max(enrichedTimePoints, (d: EnrichedSimulationTimePoint) => d.grainSize_um) ?? 30);
      ySecondaryScale = d3ScaleLinear()
        .domain([0, maxGrain * 1.15])
        .nice()
        .range([innerHeight, 0]);
    } else {
      // Hall-Petch Mode
      const minYield = Math.max(0, ((d3Min(enrichedTimePoints, (d: EnrichedSimulationTimePoint) => d.yieldStrength_MPa) ?? 300) as number) * 0.85);
      const maxYield = ((d3Max(enrichedTimePoints, (d: EnrichedSimulationTimePoint) => d.yieldStrength_MPa) ?? 1200) as number) * 1.1;
      yPrimaryScale = d3ScaleLinear()
        .domain([minYield, maxYield])
        .nice()
        .range([innerHeight, 0]);

      const maxGrain = Math.max(30, d3Max(enrichedTimePoints, (d: EnrichedSimulationTimePoint) => d.grainSize_um) ?? 30);
      ySecondaryScale = d3ScaleLinear()
        .domain([0, maxGrain * 1.15])
        .nice()
        .range([innerHeight, 0]);
    }

    // --- DEFINITIONS (Gradients & Glow Filters) ---
    const defs = svg.append("defs");

    // Emerald Area Gradient for Grain Size
    const grainAreaGrad = defs
      .append("linearGradient")
      .attr("id", "d3GrainAreaGrad")
      .attr("x1", "0%")
      .attr("y1", "0%")
      .attr("x2", "0%")
      .attr("y2", "100%");
    grainAreaGrad.append("stop").attr("offset", "0%").attr("stop-color", "#10b981").attr("stop-opacity", 0.35);
    grainAreaGrad.append("stop").attr("offset", "100%").attr("stop-color", "#10b981").attr("stop-opacity", 0.02);

    // Amber Area Gradient for Temperature
    const tempAreaGrad = defs
      .append("linearGradient")
      .attr("id", "d3TempAreaGrad")
      .attr("x1", "0%")
      .attr("y1", "0%")
      .attr("x2", "0%")
      .attr("y2", "100%");
    tempAreaGrad.append("stop").attr("offset", "0%").attr("stop-color", "#f59e0b").attr("stop-opacity", 0.25);
    tempAreaGrad.append("stop").attr("offset", "100%").attr("stop-color", "#f59e0b").attr("stop-opacity", 0.01);

    // Cyan Area Gradient for Growth Rate
    const rateAreaGrad = defs
      .append("linearGradient")
      .attr("id", "d3RateAreaGrad")
      .attr("x1", "0%")
      .attr("y1", "0%")
      .attr("x2", "0%")
      .attr("y2", "100%");
    rateAreaGrad.append("stop").attr("offset", "0%").attr("stop-color", "#06b6d4").attr("stop-opacity", 0.35);
    rateAreaGrad.append("stop").attr("offset", "100%").attr("stop-color", "#06b6d4").attr("stop-opacity", 0.02);

    // --- 1. STAGE BACKGROUND BANDS & BOUNDARY DIVIDERS ---
    const stageBandsG = g.append("g").attr("class", "stage-bands");

    stageIntervals.forEach((si) => {
      const x0 = xScale(si.startTime_min);
      const x1 = xScale(si.endTime_min);
      const bandWidth = Math.max(0, x1 - x0);

      // Color coding per stage type
      let fillColor = "rgba(255, 255, 255, 0.015)";
      let typeLabel = "RAMP";
      if (si.stage.type === "soak") {
        fillColor = "rgba(244, 63, 94, 0.04)";
        typeLabel = "SOAK";
      } else if (si.stage.type === "quench") {
        fillColor = "rgba(6, 182, 212, 0.04)";
        typeLabel = "QUENCH";
      }

      stageBandsG
        .append("rect")
        .attr("x", x0)
        .attr("y", 0)
        .attr("width", bandWidth)
        .attr("height", innerHeight)
        .attr("fill", fillColor);

      // Stage vertical boundary line
      if (si.startTime_min > 0) {
        stageBandsG
          .append("line")
          .attr("x1", x0)
          .attr("y1", 0)
          .attr("x2", x0)
          .attr("y2", innerHeight)
          .attr("stroke", "#162032")
          .attr("stroke-dasharray", "3,3")
          .attr("stroke-width", 1);
      }

      // Stage Name Tag on top
      if (bandWidth > 35) {
        stageBandsG
          .append("text")
          .attr("x", x0 + bandWidth / 2)
          .attr("y", 12)
          .attr("text-anchor", "middle")
          .attr("fill", "#64748b")
          .attr("font-size", "8.5px")
          .attr("font-family", "monospace")
          .attr("font-weight", "600")
          .text(`S${si.index + 1}: ${typeLabel}`);
      }
    });

    // --- 2. GRID LINES ---
    const gridG = g.append("g").attr("class", "grid-lines");

    // Horizontal grid
    const yTicks = yPrimaryScale.ticks(5);
    yTicks.forEach((tickVal) => {
      const yPos = yPrimaryScale(tickVal);
      gridG
        .append("line")
        .attr("x1", 0)
        .attr("y1", yPos)
        .attr("x2", innerWidth)
        .attr("y2", yPos)
        .attr("stroke", "#162032")
        .attr("stroke-width", 1);
    });

    // --- 3. CURVE RENDERINGS BASED ON ACTIVE DISPLAY MODE ---

    // A. Grain Size Area & Line
    const grainAreaGenerator = d3Area<SimulationTimePoint>()
      .x((d) => xScale(d.time_min))
      .y0(innerHeight)
      .y1((d) => (displayMode === "grain-zener" || displayMode === "dual-temp" ? yPrimaryScale(d.grainSize_um) : (ySecondaryScale ? ySecondaryScale(d.grainSize_um) : innerHeight)))
      .curve(d3CurveMonotoneX);

    const grainLineGenerator = d3Line<SimulationTimePoint>()
      .x((d) => xScale(d.time_min))
      .y((d) => (displayMode === "grain-zener" || displayMode === "dual-temp" ? yPrimaryScale(d.grainSize_um) : (ySecondaryScale ? ySecondaryScale(d.grainSize_um) : innerHeight)))
      .curve(d3CurveMonotoneX);

    if (displayMode === "grain-zener" || displayMode === "dual-temp") {
      // Area under grain curve
      g.append("path")
        .datum(enrichedTimePoints)
        .attr("fill", "url(#d3GrainAreaGrad)")
        .attr("d", grainAreaGenerator);

      // Primary Grain Line
      g.append("path")
        .datum(enrichedTimePoints)
        .attr("fill", "none")
        .attr("stroke", "#10b981")
        .attr("stroke-width", 2.5)
        .attr("d", grainLineGenerator);
    }

    // B. Zener Pinning Limit Curve (Mode: grain-zener)
    if (displayMode === "grain-zener") {
      const zenerLineGenerator = d3Line<SimulationTimePoint>()
        .x((d) => xScale(d.time_min))
        .y((d) => yPrimaryScale(Math.min(yPrimaryScale.domain()[1], d.zenerLimit_um)))
        .curve(d3CurveMonotoneX);

      g.append("path")
        .datum(enrichedTimePoints)
        .attr("fill", "none")
        .attr("stroke", "#f43f5e")
        .attr("stroke-width", 1.8)
        .attr("stroke-dasharray", "4,3")
        .attr("d", zenerLineGenerator);
    }

    // C. Temperature Curve (Mode: dual-temp)
    if (displayMode === "dual-temp" && ySecondaryScale) {
      const tempAreaGenerator = d3Area<SimulationTimePoint>()
        .x((d) => xScale(d.time_min))
        .y0(innerHeight)
        .y1((d) => ySecondaryScale!(d.temperature_C))
        .curve(d3CurveMonotoneX);

      const tempLineGenerator = d3Line<SimulationTimePoint>()
        .x((d) => xScale(d.time_min))
        .y((d) => ySecondaryScale!(d.temperature_C))
        .curve(d3CurveMonotoneX);

      g.append("path")
        .datum(enrichedTimePoints)
        .attr("fill", "url(#d3TempAreaGrad)")
        .attr("d", tempAreaGenerator);

      g.append("path")
        .datum(enrichedTimePoints)
        .attr("fill", "none")
        .attr("stroke", "#f59e0b")
        .attr("stroke-width", 2)
        .attr("d", tempLineGenerator);

      // Solvus temperature horizontal reference line
      if (material.solvusTemp_C <= ySecondaryScale.domain()[1]) {
        const solvusY = ySecondaryScale(material.solvusTemp_C);
        g.append("line")
          .attr("x1", 0)
          .attr("y1", solvusY)
          .attr("x2", innerWidth)
          .attr("y2", solvusY)
          .attr("stroke", "#f43f5e")
          .attr("stroke-dasharray", "2,2")
          .attr("stroke-width", 1);

        g.append("text")
          .attr("x", innerWidth - 6)
          .attr("y", solvusY - 4)
          .attr("text-anchor", "end")
          .attr("fill", "#f43f5e")
          .attr("font-size", "8.5px")
          .attr("font-family", "monospace")
          .text(`T_solvus: ${material.solvusTemp_C}°C`);
      }
    }

    // D. Growth Velocity Curve (Mode: growth-rate)
    if (displayMode === "growth-rate") {
      const rateAreaGenerator = d3Area<any>()
        .x((d) => xScale(d.time_min))
        .y0(innerHeight)
        .y1((d) => yPrimaryScale(d.growthRate_um_per_min || 0))
        .curve(d3CurveMonotoneX);

      const rateLineGenerator = d3Line<any>()
        .x((d) => xScale(d.time_min))
        .y((d) => yPrimaryScale(d.growthRate_um_per_min || 0))
        .curve(d3CurveMonotoneX);

      g.append("path")
        .datum(enrichedTimePoints)
        .attr("fill", "url(#d3RateAreaGrad)")
        .attr("d", rateAreaGenerator);

      g.append("path")
        .datum(enrichedTimePoints)
        .attr("fill", "none")
        .attr("stroke", "#06b6d4")
        .attr("stroke-width", 2.2)
        .attr("d", rateLineGenerator);

      // Secondary Grain curve in background
      if (ySecondaryScale) {
        g.append("path")
          .datum(enrichedTimePoints)
          .attr("fill", "none")
          .attr("stroke", "#10b981")
          .attr("stroke-width", 1.5)
          .attr("stroke-dasharray", "3,2")
          .attr("opacity", 0.65)
          .attr("d", grainLineGenerator);
      }
    }

    // E. Hall-Petch Yield Strength Curve (Mode: hall-petch)
    if (displayMode === "hall-petch") {
      const hpLineGenerator = d3Line<SimulationTimePoint>()
        .x((d) => xScale(d.time_min))
        .y((d) => yPrimaryScale(d.yieldStrength_MPa))
        .curve(d3CurveMonotoneX);

      g.append("path")
        .datum(enrichedTimePoints)
        .attr("fill", "none")
        .attr("stroke", "#a855f7")
        .attr("stroke-width", 2.2)
        .attr("d", hpLineGenerator);

      if (ySecondaryScale) {
        g.append("path")
          .datum(enrichedTimePoints)
          .attr("fill", "none")
          .attr("stroke", "#10b981")
          .attr("stroke-width", 1.5)
          .attr("stroke-dasharray", "3,2")
          .attr("opacity", 0.65)
          .attr("d", grainLineGenerator);
      }
    }

    // --- 4. AXES RENDERING ---
    const xAxis = d3AxisBottom(xScale)
      .ticks(Math.min(8, Math.floor(innerWidth / 75)))
      .tickFormat((d) => `${(Number(d) / 60).toFixed(1)}h`);

    const yAxisLeft = d3AxisLeft(yPrimaryScale)
      .ticks(5)
      .tickFormat((d) => `${d}`);

    // X Axis
    g.append("g")
      .attr("class", "x-axis")
      .attr("transform", `translate(0,${innerHeight})`)
      .call(xAxis)
      .selectAll("text")
      .attr("fill", "#64748b")
      .attr("font-family", "monospace")
      .attr("font-size", "9px");

    // X Axis Label
    g.append("text")
      .attr("x", innerWidth / 2)
      .attr("y", innerHeight + 34)
      .attr("text-anchor", "middle")
      .attr("fill", "#64748b")
      .attr("font-family", "monospace")
      .attr("font-size", "10px")
      .attr("font-weight", "bold")
      .text(`Thermal Cycle Process Time (Hours / Min) ➔`);

    // Left Y Axis
    g.append("g")
      .attr("class", "y-axis-left")
      .call(yAxisLeft)
      .selectAll("text")
      .attr("fill", () => {
        if (displayMode === "grain-zener" || displayMode === "dual-temp") return "#10b981";
        if (displayMode === "growth-rate") return "#06b6d4";
        return "#c084fc";
      })
      .attr("font-family", "monospace")
      .attr("font-size", "9px");

    // Left Y Axis Label
    let leftAxisLabel = "Mean Grain Size D (µm)";
    let leftAxisColor = "#10b981";
    if (displayMode === "growth-rate") {
      leftAxisLabel = "Growth Rate dD/dt (µm/min)";
      leftAxisColor = "#06b6d4";
    } else if (displayMode === "hall-petch") {
      leftAxisLabel = "Yield Strength σ_y (MPa)";
      leftAxisColor = "#c084fc";
    }

    g.append("text")
      .attr("transform", "rotate(-90)")
      .attr("x", -innerHeight / 2)
      .attr("y", -38)
      .attr("text-anchor", "middle")
      .attr("fill", leftAxisColor)
      .attr("font-family", "monospace")
      .attr("font-size", "10px")
      .attr("font-weight", "bold")
      .text(leftAxisLabel);

    // Right Y Axis (If applicable)
    if (ySecondaryScale) {
      let yAxisRight = d3AxisRight(ySecondaryScale).ticks(5);
      let rightAxisLabel = "";
      let rightAxisColor = "#64748b";

      if (displayMode === "grain-zener") {
        rightAxisLabel = "ASTM E112 G Number";
        rightAxisColor = "#c084fc";
      } else if (displayMode === "dual-temp") {
        rightAxisLabel = "Temperature T (°C)";
        rightAxisColor = "#f59e0b";
      } else {
        rightAxisLabel = "Grain Size D (µm)";
        rightAxisColor = "#10b981";
      }

      g.append("g")
        .attr("class", "y-axis-right")
        .attr("transform", `translate(${innerWidth},0)`)
        .call(yAxisRight)
        .selectAll("text")
        .attr("fill", rightAxisColor)
        .attr("font-family", "monospace")
        .attr("font-size", "9px");

      g.append("text")
        .attr("transform", "rotate(90)")
        .attr("x", innerHeight / 2)
        .attr("y", -innerWidth - 38)
        .attr("text-anchor", "middle")
        .attr("fill", rightAxisColor)
        .attr("font-family", "monospace")
        .attr("font-size", "10px")
        .attr("font-weight", "bold")
        .text(rightAxisLabel);
    }

    // Style axis domain & tick lines to dark slate
    g.selectAll(".domain").attr("stroke", "#162032");
    g.selectAll(".tick line").attr("stroke", "#162032");

    // --- 5. PLAYHEAD INDICATOR (Current Simulation Playback Time) ---
    const clampedPlayTime = Math.max(0, Math.min(playbackTime_min, totalTime_min));
    const playX = xScale(clampedPlayTime);

    const playheadG = g.append("g").attr("class", "playhead-indicator");

    playheadG
      .append("line")
      .attr("x1", playX)
      .attr("y1", 0)
      .attr("x2", playX)
      .attr("y2", innerHeight)
      .attr("stroke", "#38bdf8")
      .attr("stroke-width", 1.8)
      .attr("stroke-dasharray", "3,3");

    playheadG
      .append("circle")
      .attr("cx", playX)
      .attr("cy", 0)
      .attr("r", 4)
      .attr("fill", "#38bdf8")
      .attr("stroke", "#050810")
      .attr("stroke-width", 1.5);

    // --- 6. INTERACTIVE OVERLAY FOR HOVER CROSSHAIR & TIME SEEKING ---
    const overlay = g
      .append("rect")
      .attr("class", "interactive-overlay")
      .attr("width", innerWidth)
      .attr("height", innerHeight)
      .attr("fill", "transparent")
      .attr("cursor", "crosshair");

    // D3 Bisector
    const bisectTime = d3Bisector<SimulationTimePoint, number>((d) => d.time_min).left;

    const crosshairG = g.append("g").attr("class", "crosshair-group").style("display", "none");

    const crosshairLine = crosshairG
      .append("line")
      .attr("y1", 0)
      .attr("y2", innerHeight)
      .attr("stroke", "#f59e0b")
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "2,2");

    const crosshairDotGrain = crosshairG
      .append("circle")
      .attr("r", 5)
      .attr("fill", "#10b981")
      .attr("stroke", "#ffffff")
      .attr("stroke-width", 2);

    const crosshairDotSecondary = crosshairG
      .append("circle")
      .attr("r", 4.5)
      .attr("fill", displayMode === "dual-temp" ? "#f59e0b" : "#f43f5e")
      .attr("stroke", "#ffffff")
      .attr("stroke-width", 1.5);

    overlay
      .on("pointerenter", () => {
        crosshairG.style("display", null);
        setIsHovered(true);
      })
      .on("pointerleave", () => {
        crosshairG.style("display", "none");
        setIsHovered(false);
        setHoveredPoint(null);
      })
      .on("pointermove", function (event: MouseEvent) {
        const [mx, my] = d3Pointer(event);
        const tVal = xScale.invert(mx);
        const idx = bisectTime(enrichedTimePoints, tVal, 1);
        const d0 = enrichedTimePoints[idx - 1];
        const d1 = enrichedTimePoints[idx];
        let d = d0;
        if (d1 && d0) {
          d = tVal - d0.time_min > d1.time_min - tVal ? d1 : d0;
        } else if (d1) {
          d = d1;
        }

        if (!d) return;

        setHoveredPoint(d);
        const ptX = xScale(d.time_min);
        crosshairLine.attr("x1", ptX).attr("x2", ptX);

        if (displayMode === "grain-zener" || displayMode === "dual-temp") {
          const gY = yPrimaryScale(d.grainSize_um);
          crosshairDotGrain.attr("cx", ptX).attr("cy", gY).style("display", null);
        } else if (displayMode === "growth-rate") {
          const rY = yPrimaryScale(d.growthRate_um_per_min || 0);
          crosshairDotGrain.attr("cx", ptX).attr("cy", rY).style("display", null);
        } else {
          const hpY = yPrimaryScale(d.yieldStrength_MPa);
          crosshairDotGrain.attr("cx", ptX).attr("cy", hpY).style("display", null);
        }

        if (displayMode === "grain-zener") {
          const zY = yPrimaryScale(Math.min(yPrimaryScale.domain()[1], d.zenerLimit_um));
          crosshairDotSecondary.attr("cx", ptX).attr("cy", zY).style("display", null);
        } else if (displayMode === "dual-temp" && ySecondaryScale) {
          const tY = ySecondaryScale(d.temperature_C);
          crosshairDotSecondary.attr("cx", ptX).attr("cy", tY).style("display", null);
        } else {
          crosshairDotSecondary.style("display", "none");
        }

        // Compute tooltip screen position
        setHoveredPos({
          x: ptX + margin.left,
          y: my + margin.top,
        });
      })
      .on("click", function (event: MouseEvent) {
        const [mx] = d3Pointer(event);
        const tVal = Math.max(0, Math.min(totalTime_min, xScale.invert(mx)));
        if (onSeekTime) {
          onSeekTime(parseFloat(tVal.toFixed(1)));
        }
      });
  }, [dimensions, enrichedTimePoints, displayMode, totalTime_min, playbackTime_min, material, stageIntervals, onSeekTime]);

  const handleExportSVG = () => {
    if (!svgRef.current) return;
    const svgEl = svgRef.current;
    const serializer = new XMLSerializer();
    const source = serializer.serializeToString(svgEl);
    const blob = new Blob([source], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `GrainSizeEvolution_D3_${material.id}.svg`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="bg-[#090e18] p-5 rounded-2xl border border-[#162032] space-y-4">
      {/* Header & Mode Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#162032] pb-3">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider flex items-center gap-2">
            <span>D3.js Predicted Grain Size Evolution</span>
            <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-mono border border-emerald-500/40 font-normal">
              Kinetic Path
            </span>
          </h3>
        </div>

        {/* View Mode Tabs */}
        <div className="flex items-center gap-1 bg-[#050810] p-1 rounded-xl border border-[#162032] overflow-x-auto">
          <button
            type="button"
            onClick={() => setDisplayMode("grain-zener")}
            className={`px-2.5 py-1 rounded-lg text-[10px] font-mono font-bold transition whitespace-nowrap ${
              displayMode === "grain-zener"
                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-[0_0_8px_rgba(16,185,129,0.2)]"
                : "text-slate-400 hover:text-white border border-transparent"
            }`}
          >
            Grain D(t) & Zener
          </button>
          <button
            type="button"
            onClick={() => setDisplayMode("dual-temp")}
            className={`px-2.5 py-1 rounded-lg text-[10px] font-mono font-bold transition whitespace-nowrap ${
              displayMode === "dual-temp"
                ? "bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-[0_0_8px_rgba(245,158,11,0.2)]"
                : "text-slate-400 hover:text-white border border-transparent"
            }`}
          >
            Dual Axis (D & T)
          </button>
          <button
            type="button"
            onClick={() => setDisplayMode("growth-rate")}
            className={`px-2.5 py-1 rounded-lg text-[10px] font-mono font-bold transition whitespace-nowrap ${
              displayMode === "growth-rate"
                ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-[0_0_8px_rgba(6,182,212,0.2)]"
                : "text-slate-400 hover:text-white border border-transparent"
            }`}
          >
            Growth Rate (dD/dt)
          </button>
          <button
            type="button"
            onClick={() => setDisplayMode("hall-petch")}
            className={`px-2.5 py-1 rounded-lg text-[10px] font-mono font-bold transition whitespace-nowrap ${
              displayMode === "hall-petch"
                ? "bg-purple-500/20 text-purple-300 border border-purple-500/40 shadow-[0_0_8px_rgba(168,85,247,0.2)]"
                : "text-slate-400 hover:text-white border border-transparent"
            }`}
          >
            Hall-Petch (σ_y)
          </button>
        </div>
      </div>

      {/* Statistical Summary Micro-Cards Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 font-mono text-xs">
        <div className="p-2.5 bg-[#050810] rounded-xl border border-[#162032]">
          <span className="text-[9px] text-slate-400 uppercase block font-semibold">Initial Grain (D₀)</span>
          <span className="text-slate-200 font-bold text-sm block mt-0.5">{summaryMetrics.initialD} µm</span>
          <span className="text-[9px] text-slate-500">G = {enrichedTimePoints[0]?.astmGrainSizeNumber_G || 8.5}</span>
        </div>

        <div className="p-2.5 bg-[#050810] rounded-xl border border-[#162032]">
          <span className="text-[9px] text-slate-400 uppercase block font-semibold">Final Grain (D_f)</span>
          <span className="text-emerald-400 font-extrabold text-sm block mt-0.5">{summaryMetrics.finalD} µm</span>
          <span className="text-[9px] text-emerald-500 font-bold">ASTM G = {summaryMetrics.finalASTM_G}</span>
        </div>

        <div className="p-2.5 bg-[#050810] rounded-xl border border-[#162032]">
          <span className="text-[9px] text-slate-400 uppercase block font-semibold">Coarsening Factor</span>
          <span className="text-amber-400 font-extrabold text-sm block mt-0.5">{summaryMetrics.coarseningRatio}x</span>
          <span className="text-[9px] text-slate-500">ΔD = +{(summaryMetrics.finalD - summaryMetrics.initialD).toFixed(1)} µm</span>
        </div>

        <div className="p-2.5 bg-[#050810] rounded-xl border border-[#162032]">
          <span className="text-[9px] text-slate-400 uppercase block font-semibold">Peak Growth Rate</span>
          <span className="text-cyan-400 font-bold text-sm block mt-0.5">{summaryMetrics.maxGrowthRate} µm/min</span>
          <span className="text-[9px] text-slate-500">Max Kinetics Spike</span>
        </div>

        <div className="p-2.5 bg-[#050810] rounded-xl border border-[#162032]">
          <span className="text-[9px] text-slate-400 uppercase block font-semibold">Hall-Petch Shift</span>
          <span className={`font-bold text-sm block mt-0.5 ${summaryMetrics.deltaYield_MPa >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
            {summaryMetrics.deltaYield_MPa >= 0 ? `+${summaryMetrics.deltaYield_MPa}` : summaryMetrics.deltaYield_MPa} MPa
          </span>
          <span className="text-[9px] text-slate-500">Net Yield Strength</span>
        </div>
      </div>

      {/* D3 Canvas Container with Tooltip Overlay */}
      <div
        ref={containerRef}
        className="relative w-full bg-[#050810] rounded-xl border border-[#162032] p-1 overflow-hidden select-none"
      >
        <svg ref={svgRef} className="w-full h-[320px] block" />

        {/* Floating Custom Tooltip */}
        {isHovered && hoveredPoint && hoveredPos && (
          <div
            ref={tooltipRef}
            className="absolute pointer-events-none z-30 p-3 rounded-xl bg-[#090e18]/95 backdrop-blur border border-[#1e2d46] shadow-[0_4px_20px_rgba(0,0,0,0.6)] font-mono text-xs text-white space-y-1.5 min-w-[210px] transition-transform duration-75"
            style={{
              left: `${Math.min(dimensions.width - 230, Math.max(10, hoveredPos.x + 15))}px`,
              top: `${Math.min(dimensions.height - 180, Math.max(10, hoveredPos.y - 40))}px`,
            }}
          >
            <div className="flex items-center justify-between border-b border-[#162032] pb-1.5">
              <span className="text-[10px] text-slate-400">
                t = <strong>{(hoveredPoint.time_min / 60).toFixed(2)}h</strong> ({hoveredPoint.time_min.toFixed(0)} min)
              </span>
              <span className="text-[9px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 font-bold border border-amber-500/40">
                S{hoveredPoint.stageIndex + 1}
              </span>
            </div>

            <div className="text-[11px] font-bold text-slate-200 truncate">{hoveredPoint.stageName}</div>

            <div className="space-y-1 pt-1 text-[11px]">
              <div className="flex justify-between">
                <span className="text-slate-400">Temperature:</span>
                <span className="text-amber-400 font-bold">{hoveredPoint.temperature_C}°C</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Grain Diameter (D):</span>
                <span className="text-emerald-400 font-bold">{hoveredPoint.grainSize_um} µm</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">ASTM Number (G):</span>
                <span className="text-purple-300 font-bold">G = {hoveredPoint.astmGrainSizeNumber_G}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Zener Pinning Limit:</span>
                <span className="text-rose-400 font-bold">{hoveredPoint.zenerLimit_um} µm</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Yield Strength (σ_y):</span>
                <span className="text-cyan-400 font-bold">{hoveredPoint.yieldStrength_MPa} MPa</span>
              </div>
            </div>

            <div className="text-[9px] text-slate-500 pt-1 border-t border-[#162032] text-center">
              Click anywhere to seek simulation playhead
            </div>
          </div>
        )}
      </div>

      {/* Legend & Interactive Hints Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1 text-xs font-mono">
        <div className="flex flex-wrap items-center gap-4 text-[11px]">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-1 bg-emerald-400 rounded-full inline-block"></span>
            <span className="text-emerald-300">Mean Grain Size D(t)</span>
          </div>
          {displayMode === "grain-zener" && (
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 border-t-2 border-dashed border-rose-400 inline-block"></span>
              <span className="text-rose-300">Zener Pinning Boundary (D_z)</span>
            </div>
          )}
          {displayMode === "dual-temp" && (
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-1 bg-amber-400 rounded-full inline-block"></span>
              <span className="text-amber-300">Furnace Temp T(t)</span>
            </div>
          )}
          {displayMode === "growth-rate" && (
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-1 bg-cyan-400 rounded-full inline-block"></span>
              <span className="text-cyan-300">Instantaneous Growth Velocity (dD/dt)</span>
            </div>
          )}
          {displayMode === "hall-petch" && (
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-1 bg-purple-400 rounded-full inline-block"></span>
              <span className="text-purple-300">Hall-Petch Strength (σ_y)</span>
            </div>
          )}
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 border-t border-dashed border-sky-400 inline-block"></span>
            <span className="text-sky-300">Active Playhead</span>
          </div>
        </div>

        {/* D3 SVG Export Button */}
        <button
          type="button"
          onClick={handleExportSVG}
          className="px-2.5 py-1 bg-[#050810] hover:bg-white/10 border border-[#1e2d46] text-slate-300 hover:text-white rounded-lg transition flex items-center gap-1.5 text-[10px]"
          title="Download D3 Vector Graphic SVG"
        >
          <Download className="w-3 h-3 text-emerald-400" />
          <span>Export D3 SVG Chart</span>
        </button>
      </div>
    </div>
  );
};

