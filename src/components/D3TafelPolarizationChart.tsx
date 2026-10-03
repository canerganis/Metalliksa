import React, { useEffect, useRef, useState, useMemo } from "react";
import { axisBottom as d3AxisBottom, axisLeft as d3AxisLeft, curveMonotoneX as d3CurveMonotoneX, extent as d3Extent, line as d3Line, pointer as d3Pointer, scaleLinear as d3ScaleLinear, select as d3Select, zoom as d3Zoom, zoomIdentity as d3ZoomIdentity } from "d3";
import type { ScaleLinear, ZoomBehavior } from "d3";
import {
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Crosshair,
  Download,
  Activity,
  Cpu,
  Layers,
  Sparkles,
  Info,
  Maximize2,
} from "lucide-react";
import { TafelDataset, TafelFitResult } from "../types/tafel";

export interface D3TafelPolarizationChartProps {
  dataset: TafelDataset;
  fitResult: TafelFitResult;
  onRangesChange?: (cathodic: [number, number], anodic: [number, number]) => void;
  onManualTune?: (ecorr: number, logIcorr: number) => void;
  onTriggerPythonRecalculate?: () => void;
  isPythonCalculating?: boolean;
  initialOrientation?: "evans" | "potentiodynamic";
  height?: number;
}

interface HoverState {
  visible: boolean;
  x: number;
  y: number;
  potential: number;
  logI: number;
  linearI_uA: number;
  overpotential_mV: number;
  isAnodic: boolean;
}

export const D3TafelPolarizationChart: React.FC<D3TafelPolarizationChartProps> = ({
  dataset,
  fitResult,
  onRangesChange,
  onManualTune,
  onTriggerPythonRecalculate,
  isPythonCalculating = false,
  initialOrientation = "evans",
  height = 480,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const zoomBehaviorRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null);

  // Display toggles
  const [orientation, setOrientation] = useState<"evans" | "potentiodynamic">(initialOrientation);
  const [showTangents, setShowTangents] = useState(true);
  const [showButlerVolmer, setShowButlerVolmer] = useState(true);
  const [showRawDots, setShowRawDots] = useState(false);
  const [showDomainShading, setShowDomainShading] = useState(true);
  const [showCrosshairs, setShowCrosshairs] = useState(true);
  const [hoverState, setHoverState] = useState<HoverState | null>(null);

  // Dimensions
  const [dimensions, setDimensions] = useState({ width: 800, height });

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0) {
          setDimensions({
            width: Math.max(450, entry.contentRect.width),
            height,
          });
        }
      }
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, [height]);

  // Derived Plot Margins
  const margin = { top: 36, right: 36, bottom: 54, left: 68 };
  const innerWidth = Math.max(100, dimensions.width - margin.left - margin.right);
  const innerHeight = Math.max(100, dimensions.height - margin.top - margin.bottom);

  // Prepare Points
  const rawPoints = useMemo(() => {
    return dataset.points.map((p) => ({
      potential: p.potential,
      logI: p.logCurrentDensity,
      currentDensity_uA_cm2: p.currentDensity_uA_cm2,
    }));
  }, [dataset]);

  // Main D3 Rendering Effect
  useEffect(() => {
    if (!svgRef.current || rawPoints.length === 0) return;

    const svg = d3Select(svgRef.current);
    svg.selectAll("*").remove(); // Clear previous render

    // Color definitions
    const colors = {
      bg: "#040711",
      grid: "#121b2d",
      axis: "#64748b",
      axisText: "#94a3b8",
      curve: "#f8fafc",
      ecorr: "#10b981", // Emerald
      icorr: "#38bdf8", // Sky Blue
      anodic: "#38bdf8", // Sky Blue
      cathodic: "#f59e0b", // Amber
      bv: "#34d399", // Mint / Emerald
      zoneAnodic: "rgba(56, 189, 248, 0.05)",
      zoneCathodic: "rgba(245, 158, 11, 0.05)",
    };

    // SVG Defs
    const defs = svg.append("defs");

    // Clip path for main chart area
    defs
      .append("clipPath")
      .attr("id", "d3-tafel-clip")
      .append("rect")
      .attr("width", innerWidth)
      .attr("height", innerHeight);

    // Filter for glowing highlight badge
    const filter = defs.append("filter").attr("id", "ecorr-glow").attr("x", "-20%").attr("y", "-20%").attr("width", "140%").attr("height", "140%");
    filter.append("feGaussianBlur").attr("stdDeviation", "3").attr("result", "blur");
    filter.append("feMerge").selectAll("feMergeNode").data(["blur", "SourceGraphic"]).enter().append("feMergeNode").attr("in", (d) => d);

    // Compute Base Domain Extents
    const potentialExtent = d3Extent(rawPoints, (d: { potential: number }) => d.potential) as [number, number];
    const logIExtent = d3Extent(rawPoints, (d: { logI: number }) => d.logI) as [number, number];

    // Ensure Ecorr and Icorr fit within domain with margin
    const eMin = Math.min(potentialExtent[0] ?? -1.0, fitResult.eCorr - 0.25);
    const eMax = Math.max(potentialExtent[1] ?? 0.5, fitResult.eCorr + 0.25);
    const ePad = (eMax - eMin) * 0.06;

    const logIMin = Math.min(logIExtent[0] ?? -4.0, fitResult.logIcorr - 1.2);
    const logIMax = Math.max(logIExtent[1] ?? 4.0, fitResult.logIcorr + 1.5);
    const logIPad = (logIMax - logIMin) * 0.06;

    // Base Scales according to orientation
    let xScaleBase: ScaleLinear<number, number>;
    let yScaleBase: ScaleLinear<number, number>;

    if (orientation === "evans") {
      // Evans Diagram: X = Log(i), Y = Potential E
      xScaleBase = d3ScaleLinear().domain([logIMin - logIPad, logIMax + logIPad]).range([0, innerWidth]);
      yScaleBase = d3ScaleLinear().domain([eMin - ePad, eMax + ePad]).range([innerHeight, 0]);
    } else {
      // Potentiodynamic Curve: X = Potential E, Y = Log(i)
      xScaleBase = d3ScaleLinear().domain([eMin - ePad, eMax + ePad]).range([0, innerWidth]);
      yScaleBase = d3ScaleLinear().domain([logIMin - logIPad, logIMax + logIPad]).range([innerHeight, 0]);
    }

    let currentXScale = xScaleBase;
    let currentYScale = yScaleBase;

    // Main Canvas Group
    const g = svg.append("g").attr("transform", `translate(${margin.left}, ${margin.top})`);

    // Background Canvas
    g.append("rect")
      .attr("width", innerWidth)
      .attr("height", innerHeight)
      .attr("fill", colors.bg)
      .attr("rx", 6);

    // Zoomable Content Layer (clipped)
    const contentG = g.append("g").attr("clip-path", "url(#d3-tafel-clip)");

    // Domain Shading Group (Behind curves)
    const shadingG = contentG.append("g").attr("class", "shading-layer");

    // Gridlines Group
    const gridXG = contentG.append("g").attr("class", "grid-x");
    const gridYG = contentG.append("g").attr("class", "grid-y");

    // Tangent Lines Group
    const tangentsG = contentG.append("g").attr("class", "tangents-layer");

    // Butler-Volmer Group
    const bvG = contentG.append("g").attr("class", "bv-layer");

    // Primary Experimental Curve Group
    const curveG = contentG.append("g").attr("class", "curve-layer");

    // Raw Dots Group
    const dotsG = contentG.append("g").attr("class", "dots-layer");

    // Ecorr / Icorr Highlight Layer
    const highlightG = contentG.append("g").attr("class", "highlight-layer");

    // Axes Groups (drawn outside clipped area so labels are never cut off)
    const xAxisG = g.append("g").attr("transform", `translate(0, ${innerHeight})`).attr("class", "x-axis");
    const yAxisG = g.append("g").attr("class", "y-axis");

    // Axis Labels
    const xAxisLabel = g
      .append("text")
      .attr("x", innerWidth / 2)
      .attr("y", innerHeight + 42)
      .attr("text-anchor", "middle")
      .attr("fill", colors.axisText)
      .attr("font-size", "12px")
      .attr("font-family", "monospace")
      .attr("font-weight", "600");

    const yAxisLabel = g
      .append("text")
      .attr("transform", "rotate(-90)")
      .attr("x", -innerHeight / 2)
      .attr("y", -50)
      .attr("text-anchor", "middle")
      .attr("fill", colors.axisText)
      .attr("font-size", "12px")
      .attr("font-family", "monospace")
      .attr("font-weight", "600");

    if (orientation === "evans") {
      xAxisLabel.text("Log Current Density log₁₀(i, µA/cm²)");
      yAxisLabel.text(`Potential E (V vs ${dataset.metadata.referenceElectrode})`);
    } else {
      xAxisLabel.text(`Potential E (V vs ${dataset.metadata.referenceElectrode})`);
      yAxisLabel.text("Log Current Density log₁₀(i, µA/cm²)");
    }

    // Generator Functions for Lines
    const getXCoord = (pt: { potential: number; logI: number }, sx = currentXScale) => {
      return orientation === "evans" ? sx(pt.logI) : sx(pt.potential);
    };

    const getYCoord = (pt: { potential: number; logI: number }, sy = currentYScale) => {
      return orientation === "evans" ? sy(pt.potential) : sy(pt.logI);
    };

    // Line generator for experimental points
    const expLineGenerator = d3Line<{ potential: number; logI: number }>()
      .x((d) => getXCoord(d, currentXScale))
      .y((d) => getYCoord(d, currentYScale))
      .curve(d3CurveMonotoneX);

    // Render Function (Called on initial draw and every zoom/pan event)
    const render = () => {
      // 1. Render Axes
      const xAxis = d3AxisBottom(currentXScale)
        .ticks(Math.max(5, Math.floor(innerWidth / 90)))
        .tickFormat((d) => {
          const val = typeof d === "number" ? d : Number(d);
          return orientation === "evans"
            ? `${val.toFixed(1)}`
            : `${val >= 0 ? "+" : ""}${val.toFixed(2)}V`;
        });

      const yAxis = d3AxisLeft(currentYScale)
        .ticks(Math.max(5, Math.floor(innerHeight / 60)))
        .tickFormat((d) => {
          const val = typeof d === "number" ? d : Number(d);
          return orientation === "evans"
            ? `${val >= 0 ? "+" : ""}${val.toFixed(2)}V`
            : `${val.toFixed(1)}`;
        });

      xAxisG.call(xAxis);
      yAxisG.call(yAxis);

      // Style axes
      xAxisG.select(".domain").attr("stroke", colors.grid).attr("stroke-width", 1.5);
      yAxisG.select(".domain").attr("stroke", colors.grid).attr("stroke-width", 1.5);
      xAxisG.selectAll(".tick line").attr("stroke", colors.grid);
      yAxisG.selectAll(".tick line").attr("stroke", colors.grid);
      xAxisG.selectAll(".tick text").attr("fill", colors.axisText).attr("font-size", "10px").attr("font-family", "monospace");
      yAxisG.selectAll(".tick text").attr("fill", colors.axisText).attr("font-size", "10px").attr("font-family", "monospace");

      // 2. Render Grid
      const xTicks = currentXScale.ticks(Math.max(5, Math.floor(innerWidth / 90)));
      const yTicks = currentYScale.ticks(Math.max(5, Math.floor(innerHeight / 60)));

      gridXG
        .selectAll("line")
        .data(xTicks)
        .join("line")
        .attr("x1", (d) => currentXScale(d))
        .attr("x2", (d) => currentXScale(d))
        .attr("y1", 0)
        .attr("y2", innerHeight)
        .attr("stroke", colors.grid)
        .attr("stroke-dasharray", "3,3")
        .attr("stroke-width", 1);

      gridYG
        .selectAll("line")
        .data(yTicks)
        .join("line")
        .attr("x1", 0)
        .attr("x2", innerWidth)
        .attr("y1", (d) => currentYScale(d))
        .attr("y2", (d) => currentYScale(d))
        .attr("stroke", colors.grid)
        .attr("stroke-dasharray", "3,3")
        .attr("stroke-width", 1);

      // 3. Render Domain Shading (Cathodic reduction zone vs Anodic oxidation zone)
      shadingG.selectAll("*").remove();
      if (showDomainShading) {
        if (orientation === "evans") {
          const ecorrY = currentYScale(fitResult.eCorr);
          // Anodic Zone: above Ecorr (lower Y value)
          shadingG
            .append("rect")
            .attr("x", 0)
            .attr("y", 0)
            .attr("width", innerWidth)
            .attr("height", Math.max(0, ecorrY))
            .attr("fill", colors.zoneAnodic);

          // Cathodic Zone: below Ecorr (higher Y value)
          shadingG
            .append("rect")
            .attr("x", 0)
            .attr("y", Math.max(0, ecorrY))
            .attr("width", innerWidth)
            .attr("height", Math.max(0, innerHeight - ecorrY))
            .attr("fill", colors.zoneCathodic);
        } else {
          const ecorrX = currentXScale(fitResult.eCorr);
          // Cathodic Zone: left of Ecorr
          shadingG
            .append("rect")
            .attr("x", 0)
            .attr("y", 0)
            .attr("width", Math.max(0, ecorrX))
            .attr("height", innerHeight)
            .attr("fill", colors.zoneCathodic);

          // Anodic Zone: right of Ecorr
          shadingG
            .append("rect")
            .attr("x", Math.max(0, ecorrX))
            .attr("y", 0)
            .attr("width", Math.max(0, innerWidth - ecorrX))
            .attr("height", innerHeight)
            .attr("fill", colors.zoneAnodic);
        }
      }

      // 4. Render Tangents
      tangentsG.selectAll("*").remove();
      if (showTangents && fitResult.tangentLines && fitResult.tangentLines.length > 0) {
        const anodicPts = fitResult.tangentLines
          .filter((t) => t.logI_anodic !== null && t.logI_anodic !== undefined)
          .map((t) => ({ potential: t.potential, logI: t.logI_anodic! }));

        const cathodicPts = fitResult.tangentLines
          .filter((t) => t.logI_cathodic !== null && t.logI_cathodic !== undefined)
          .map((t) => ({ potential: t.potential, logI: t.logI_cathodic! }));

        if (anodicPts.length >= 2) {
          const anodicLineGen = d3Line<{ potential: number; logI: number }>()
            .x((d) => getXCoord(d, currentXScale))
            .y((d) => getYCoord(d, currentYScale));

          tangentsG
            .append("path")
            .datum(anodicPts)
            .attr("fill", "none")
            .attr("stroke", colors.anodic)
            .attr("stroke-width", 2.2)
            .attr("stroke-dasharray", "6,4")
            .attr("d", anodicLineGen);
        }

        if (cathodicPts.length >= 2) {
          const cathodicLineGen = d3Line<{ potential: number; logI: number }>()
            .x((d) => getXCoord(d, currentXScale))
            .y((d) => getYCoord(d, currentYScale));

          tangentsG
            .append("path")
            .datum(cathodicPts)
            .attr("fill", "none")
            .attr("stroke", colors.cathodic)
            .attr("stroke-width", 2.2)
            .attr("stroke-dasharray", "6,4")
            .attr("d", cathodicLineGen);
        }
      }

      // 5. Render Butler-Volmer Curve
      bvG.selectAll("*").remove();
      if (showButlerVolmer && fitResult.syntheticButlerVolmer && fitResult.syntheticButlerVolmer.length > 0) {
        const bvPts = fitResult.syntheticButlerVolmer.map((b) => ({
          potential: b.potential,
          logI: b.logI_model,
        }));

        const bvLineGen = d3Line<{ potential: number; logI: number }>()
          .x((d) => getXCoord(d, currentXScale))
          .y((d) => getYCoord(d, currentYScale))
          .curve(d3CurveMonotoneX);

        bvG
          .append("path")
          .datum(bvPts)
          .attr("fill", "none")
          .attr("stroke", colors.bv)
          .attr("stroke-width", 1.8)
          .attr("stroke-dasharray", "3,3")
          .attr("opacity", 0.85)
          .attr("d", bvLineGen);
      }

      // 6. Render Primary Experimental Curve
      curveG.selectAll("*").remove();
      curveG
        .append("path")
        .datum(rawPoints)
        .attr("fill", "none")
        .attr("stroke", colors.curve)
        .attr("stroke-width", 2.5)
        .attr("stroke-linecap", "round")
        .attr("stroke-linejoin", "round")
        .attr("d", expLineGenerator);

      // 7. Render Raw Data Dots if toggled
      dotsG.selectAll("*").remove();
      if (showRawDots) {
        dotsG
          .selectAll("circle")
          .data(rawPoints)
          .join("circle")
          .attr("cx", (d: any) => getXCoord(d, currentXScale))
          .attr("cy", (d: any) => getYCoord(d, currentYScale))
          .attr("r", 2.2)
          .attr("fill", colors.curve)
          .attr("opacity", 0.7);
      }

      // 8. Render Ecorr & Icorr Highlight Guides & Marker Point
      highlightG.selectAll("*").remove();

      const intersectX =
        orientation === "evans"
          ? currentXScale(fitResult.logIcorr)
          : currentXScale(fitResult.eCorr);

      const intersectY =
        orientation === "evans"
          ? currentYScale(fitResult.eCorr)
          : currentYScale(fitResult.logIcorr);

      // Guidelines
      if (orientation === "evans") {
        // Horizontal guideline to Y-axis for Ecorr
        highlightG
          .append("line")
          .attr("x1", 0)
          .attr("x2", innerWidth)
          .attr("y1", intersectY)
          .attr("y2", intersectY)
          .attr("stroke", colors.ecorr)
          .attr("stroke-width", 1.8)
          .attr("stroke-dasharray", "4,4")
          .attr("opacity", 0.9);

        // Vertical guideline to X-axis for log(Icorr)
        highlightG
          .append("line")
          .attr("x1", intersectX)
          .attr("x2", intersectX)
          .attr("y1", 0)
          .attr("y2", innerHeight)
          .attr("stroke", colors.icorr)
          .attr("stroke-width", 1.8)
          .attr("stroke-dasharray", "4,4")
          .attr("opacity", 0.9);

        // Ecorr badge on Y-axis edge
        highlightG
          .append("rect")
          .attr("x", 4)
          .attr("y", intersectY - 10)
          .attr("width", 96)
          .attr("height", 20)
          .attr("rx", 4)
          .attr("fill", "rgba(16, 185, 129, 0.9)")
          .attr("stroke", "#10b981")
          .attr("stroke-width", 1);

        highlightG
          .append("text")
          .attr("x", 8)
          .attr("y", intersectY + 4)
          .attr("fill", "#ffffff")
          .attr("font-size", "10px")
          .attr("font-weight", "bold")
          .attr("font-family", "monospace")
          .text(`E_corr: ${fitResult.eCorr}V`);

        // Icorr badge on X-axis edge
        highlightG
          .append("rect")
          .attr("x", intersectX - 44)
          .attr("y", innerHeight - 24)
          .attr("width", 88)
          .attr("height", 20)
          .attr("rx", 4)
          .attr("fill", "rgba(56, 189, 248, 0.9)")
          .attr("stroke", "#38bdf8")
          .attr("stroke-width", 1);

        highlightG
          .append("text")
          .attr("x", intersectX)
          .attr("y", innerHeight - 10)
          .attr("text-anchor", "middle")
          .attr("fill", "#040711")
          .attr("font-size", "10px")
          .attr("font-weight", "bold")
          .attr("font-family", "monospace")
          .text(`${fitResult.iCorr_uA_cm2} µA/cm²`);
      } else {
        // Potentiodynamic Mode guidelines
        highlightG
          .append("line")
          .attr("x1", intersectX)
          .attr("x2", intersectX)
          .attr("y1", 0)
          .attr("y2", innerHeight)
          .attr("stroke", colors.ecorr)
          .attr("stroke-width", 1.8)
          .attr("stroke-dasharray", "4,4")
          .attr("opacity", 0.9);

        highlightG
          .append("line")
          .attr("x1", 0)
          .attr("x2", innerWidth)
          .attr("y1", intersectY)
          .attr("y2", intersectY)
          .attr("stroke", colors.icorr)
          .attr("stroke-width", 1.8)
          .attr("stroke-dasharray", "4,4")
          .attr("opacity", 0.9);
      }

      // Outer animated pulsating halo circle at the intersection
      highlightG
        .append("circle")
        .attr("cx", intersectX)
        .attr("cy", intersectY)
        .attr("r", 14)
        .attr("fill", "rgba(16, 185, 129, 0.15)")
        .attr("stroke", colors.ecorr)
        .attr("stroke-width", 1.5)
        .attr("opacity", 0.85);

      // Middle accent ring
      highlightG
        .append("circle")
        .attr("cx", intersectX)
        .attr("cy", intersectY)
        .attr("r", 8)
        .attr("fill", "rgba(56, 189, 248, 0.35)")
        .attr("stroke", "#ffffff")
        .attr("stroke-width", 1.5);

      // Core intersection bead
      highlightG
        .append("circle")
        .attr("cx", intersectX)
        .attr("cy", intersectY)
        .attr("r", 3.5)
        .attr("fill", "#ffffff");

      // Floating callout badge anchored near the intersection
      const calloutWidth = 190;
      const calloutHeight = 58;
      // Position callout intelligently to avoid clipping against boundaries
      let calloutX = intersectX + 18;
      let calloutY = intersectY - 68;

      if (calloutX + calloutWidth > innerWidth) {
        calloutX = intersectX - calloutWidth - 18;
      }
      if (calloutY < 10) {
        calloutY = intersectY + 20;
      }

      const calloutG = highlightG
        .append("g")
        .attr("class", "ecorr-callout")
        .attr("transform", `translate(${calloutX}, ${calloutY})`);

      // Leader pointer line from callout to target
      highlightG
        .append("line")
        .attr("x1", intersectX)
        .attr("y1", intersectY)
        .attr(
          "x2",
          calloutX > intersectX ? calloutX : calloutX + calloutWidth
        )
        .attr("y2", calloutY + calloutHeight / 2)
        .attr("stroke", colors.ecorr)
        .attr("stroke-width", 1.2)
        .attr("stroke-dasharray", "2,2");

      // Callout card box
      calloutG
        .append("rect")
        .attr("width", calloutWidth)
        .attr("height", calloutHeight)
        .attr("rx", 6)
        .attr("fill", "#09101d")
        .attr("stroke", "#10b981")
        .attr("stroke-width", 1.5)
        .attr("filter", "url(#ecorr-glow)");

      // Callout Header
      calloutG
        .append("text")
        .attr("x", 8)
        .attr("y", 16)
        .attr("fill", "#34d399")
        .attr("font-size", "10px")
        .attr("font-weight", "800")
        .attr("font-family", "monospace")
        .text(
          fitResult.isPythonEngine
            ? "PYTHON 3.10 ASTM G102 FIT"
            : "EXTRAPOLATED TAFEL FIT"
        );

      // Callout Line 1: Ecorr
      calloutG
        .append("text")
        .attr("x", 8)
        .attr("y", 32)
        .attr("fill", "#e2e8f0")
        .attr("font-size", "11px")
        .attr("font-family", "monospace")
        .text(`E_corr = `)
        .append("tspan")
        .attr("fill", "#34d399")
        .attr("font-weight", "bold")
        .text(`${fitResult.eCorr} V`);

      // Callout Line 2: Icorr & CR
      calloutG
        .append("text")
        .attr("x", 8)
        .attr("y", 48)
        .attr("fill", "#e2e8f0")
        .attr("font-size", "11px")
        .attr("font-family", "monospace")
        .text(`i_corr = `)
        .append("tspan")
        .attr("fill", "#38bdf8")
        .attr("font-weight", "bold")
        .text(`${fitResult.iCorr_uA_cm2} µA/cm²`)
        .append("tspan")
        .attr("fill", "#94a3b8")
        .text(` (${fitResult.corrosionRateMmYr} mm/yr)`);
    };

    // Initial draw
    render();

    // 9. D3 Zoom & Pan Setup
    const zoom = d3Zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.6, 25])
      .extent([
        [0, 0],
        [innerWidth, innerHeight],
      ])
      .on("zoom", (event) => {
        currentXScale = event.transform.rescaleX(xScaleBase);
        currentYScale = event.transform.rescaleY(yScaleBase);
        render();
      });

    zoomBehaviorRef.current = zoom;

    // Overlay transparent rectangle to capture hover and zoom interactions
    const overlay = g
      .append("rect")
      .attr("class", "zoom-overlay")
      .attr("width", innerWidth)
      .attr("height", innerHeight)
      .attr("fill", "transparent")
      .attr("cursor", "crosshair");

    svg.call(zoom as any);

    // 10. Interactive Crosshairs & Inspection Tooltip on Mouse Move
    const crosshairLineX = contentG
      .append("line")
      .attr("stroke", "#94a3b8")
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "2,2")
      .attr("opacity", 0)
      .attr("pointer-events", "none");

    const crosshairLineY = contentG
      .append("line")
      .attr("stroke", "#94a3b8")
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "2,2")
      .attr("opacity", 0)
      .attr("pointer-events", "none");

    overlay
      .on("mousemove", (event) => {
        if (!showCrosshairs) return;

        const [mouseX, mouseY] = d3Pointer(event, g.node());
        if (mouseX < 0 || mouseX > innerWidth || mouseY < 0 || mouseY > innerHeight) {
          setHoverState(null);
          crosshairLineX.attr("opacity", 0);
          crosshairLineY.attr("opacity", 0);
          return;
        }

        crosshairLineX
          .attr("x1", mouseX)
          .attr("x2", mouseX)
          .attr("y1", 0)
          .attr("y2", innerHeight)
          .attr("opacity", 0.7);

        crosshairLineY
          .attr("x1", 0)
          .attr("x2", innerWidth)
          .attr("y1", mouseY)
          .attr("y2", mouseY)
          .attr("opacity", 0.7);

        // Calculate inverted coordinates
        let inspectedPotential = 0;
        let inspectedLogI = 0;

        if (orientation === "evans") {
          inspectedLogI = currentXScale.invert(mouseX);
          inspectedPotential = currentYScale.invert(mouseY);
        } else {
          inspectedPotential = currentXScale.invert(mouseX);
          inspectedLogI = currentYScale.invert(mouseY);
        }

        const linearI = Math.pow(10, inspectedLogI);
        const overpotential_mV = (inspectedPotential - fitResult.eCorr) * 1000;
        const isAnodic = inspectedPotential > fitResult.eCorr;

        setHoverState({
          visible: true,
          x: mouseX + margin.left,
          y: mouseY + margin.top,
          potential: inspectedPotential,
          logI: inspectedLogI,
          linearI_uA: linearI,
          overpotential_mV,
          isAnodic,
        });
      })
      .on("mouseleave", () => {
        setHoverState(null);
        crosshairLineX.attr("opacity", 0);
        crosshairLineY.attr("opacity", 0);
      });

    // Double click to reset zoom
    overlay.on("dblclick", () => {
      svg.transition().duration(500).call(zoom.transform as any, d3ZoomIdentity);
    });

  }, [
    rawPoints,
    dimensions,
    orientation,
    showTangents,
    showButlerVolmer,
    showRawDots,
    showDomainShading,
    showCrosshairs,
    fitResult,
    dataset.metadata.referenceElectrode,
    innerWidth,
    innerHeight,
  ]);

  // Zoom Button Handlers
  const handleZoomIn = () => {
    if (!svgRef.current || !zoomBehaviorRef.current) return;
    d3Select(svgRef.current).transition().duration(300).call(zoomBehaviorRef.current.scaleBy as any, 1.35);
  };

  const handleZoomOut = () => {
    if (!svgRef.current || !zoomBehaviorRef.current) return;
    d3Select(svgRef.current).transition().duration(300).call(zoomBehaviorRef.current.scaleBy as any, 0.75);
  };

  const handleResetZoom = () => {
    if (!svgRef.current || !zoomBehaviorRef.current) return;
    d3Select(svgRef.current).transition().duration(400).call(zoomBehaviorRef.current.transform as any, d3ZoomIdentity);
  };

  // Center specifically on Ecorr / Icorr
  const handleCenterOnEcorr = () => {
    if (!svgRef.current || !zoomBehaviorRef.current) return;
    d3Select(svgRef.current).transition().duration(500).call(zoomBehaviorRef.current.transform as any, d3ZoomIdentity);
  };

  // Export SVG handler
  const handleExportSVG = () => {
    if (!svgRef.current) return;
    const serializer = new XMLSerializer();
    const source = serializer.serializeToString(svgRef.current);
    const blob = new Blob([source], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `Tafel_${dataset.name.replace(/\s+/g, "_")}_D3_Chart.svg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div
      ref={containerRef}
      className="w-full bg-[#050810] rounded-2xl border border-[#162032] p-4 flex flex-col space-y-3 relative overflow-hidden shadow-2xl"
    >
      {/* Top Header & Interactive Toolbar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-[#162032] pb-3">
        {/* Title & Coordinates Info */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-500/15 border border-emerald-500/40 flex items-center justify-center text-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.3)]">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="text-sm font-bold text-white font-mono flex items-center gap-1.5">
                <span>Interactive D3.js Tafel Evans Visualizer</span>
              </h4>
              {fitResult.isPythonEngine && (
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-sky-500/20 text-sky-300 border border-sky-500/40 flex items-center gap-1">
                  <Cpu className="w-3 h-3 text-sky-400" />
                  Python {fitResult.pythonVersion || "3.10"}
                </span>
              )}
            </div>
            <p className="text-[11px] text-slate-400 font-mono flex items-center gap-2 mt-0.5">
              <span>
                Highlighted <strong className="text-emerald-400">E_corr: {fitResult.eCorr} V</strong>
              </span>
              <span>•</span>
              <span>
                <strong className="text-sky-400">i_corr: {fitResult.iCorr_uA_cm2} µA/cm²</strong>
              </span>
              <span>•</span>
              <span>
                CR: <strong className="text-amber-300">{fitResult.corrosionRateMmYr} mm/yr</strong>
              </span>
            </p>
          </div>
        </div>

        {/* View Controls & Action Toggles */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {/* Orientation Flip */}
          <button
            type="button"
            onClick={() => setOrientation(orientation === "evans" ? "potentiodynamic" : "evans")}
            className="px-2.5 py-1.5 rounded-lg bg-[#090e18] hover:bg-[#121c2e] border border-[#1b2a44] text-[11px] font-mono text-slate-300 transition-colors flex items-center gap-1"
            title="Switch between Evans (E vs log i) and Potentiodynamic (log i vs E)"
          >
            <Layers className="w-3.5 h-3.5 text-sky-400" />
            <span>{orientation === "evans" ? "Evans (E vs log i)" : "Scan (log i vs E)"}</span>
          </button>

          {/* Tangents Toggle */}
          <button
            type="button"
            onClick={() => setShowTangents(!showTangents)}
            className={`px-2 py-1.5 rounded-lg border text-[11px] font-mono transition-colors ${
              showTangents
                ? "bg-sky-500/20 text-sky-300 border-sky-500/40"
                : "bg-[#090e18] text-slate-400 border-[#1b2a44] hover:text-slate-200"
            }`}
            title="Toggle Anodic and Cathodic linear Tafel slopes"
          >
            Tangents
          </button>

          {/* Butler-Volmer Toggle */}
          <button
            type="button"
            onClick={() => setShowButlerVolmer(!showButlerVolmer)}
            className={`px-2 py-1.5 rounded-lg border text-[11px] font-mono transition-colors ${
              showButlerVolmer
                ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
                : "bg-[#090e18] text-slate-400 border-[#1b2a44] hover:text-slate-200"
            }`}
            title="Toggle Butler-Volmer synthetic kinetic curve"
          >
            B-V Fit
          </button>

          {/* Raw Dots */}
          <button
            type="button"
            onClick={() => setShowRawDots(!showRawDots)}
            className={`px-2 py-1.5 rounded-lg border text-[11px] font-mono transition-colors ${
              showRawDots
                ? "bg-purple-500/20 text-purple-300 border-purple-500/40"
                : "bg-[#090e18] text-slate-400 border-[#1b2a44] hover:text-slate-200"
            }`}
            title="Toggle individual measured data points"
          >
            Points
          </button>

          {/* Zone Shading */}
          <button
            type="button"
            onClick={() => setShowDomainShading(!showDomainShading)}
            className={`px-2 py-1.5 rounded-lg border text-[11px] font-mono transition-colors ${
              showDomainShading
                ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                : "bg-[#090e18] text-slate-400 border-[#1b2a44] hover:text-slate-200"
            }`}
            title="Toggle Anodic/Cathodic domain background tinting"
          >
            Zones
          </button>

          {/* Python Recompute Button */}
          {onTriggerPythonRecalculate && (
            <button
              type="button"
              onClick={onTriggerPythonRecalculate}
              disabled={isPythonCalculating}
              className="px-2.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-[11px] font-mono font-bold flex items-center gap-1.5 transition shadow-[0_0_10px_rgba(16,185,129,0.3)]"
              title="Re-run Python 3.10 least-squares Tafel solver"
            >
              <Sparkles className={`w-3.5 h-3.5 ${isPythonCalculating ? "animate-spin" : ""}`} />
              <span>{isPythonCalculating ? "Python..." : "Recalc (Py)"}</span>
            </button>
          )}

          {/* D3 Zoom Controls */}
          <div className="flex items-center gap-1 pl-1 border-l border-[#1b2a44]">
            <button
              type="button"
              onClick={handleZoomIn}
              className="p-1.5 rounded bg-[#090e18] hover:bg-[#121c2e] border border-[#1b2a44] text-slate-300 hover:text-white"
              title="Zoom in (+)"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={handleZoomOut}
              className="p-1.5 rounded bg-[#090e18] hover:bg-[#121c2e] border border-[#1b2a44] text-slate-300 hover:text-white"
              title="Zoom out (-)"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={handleResetZoom}
              className="p-1.5 rounded bg-[#090e18] hover:bg-[#121c2e] border border-[#1b2a44] text-slate-300 hover:text-white"
              title="Reset view (Fit all)"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={handleCenterOnEcorr}
              className="p-1.5 rounded bg-[#090e18] hover:bg-[#121c2e] border border-[#1b2a44] text-emerald-400 hover:text-emerald-300"
              title="Focus on Ecorr / Icorr intersection point"
            >
              <Crosshair className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={handleExportSVG}
              className="p-1.5 rounded bg-[#090e18] hover:bg-[#121c2e] border border-[#1b2a44] text-slate-300 hover:text-white"
              title="Export Publication SVG"
            >
              <Download className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Main SVG Visualization Canvas Container */}
      <div className="relative w-full h-[460px] select-none rounded-xl overflow-hidden border border-[#162032] bg-[#040711]">
        <svg
          ref={svgRef}
          width={dimensions.width}
          height={dimensions.height}
          className="w-full h-full block"
        />

        {/* Live Hover Inspection Tooltip Overlay HUD */}
        {hoverState && hoverState.visible && (
          <div
            className="absolute pointer-events-none z-30 bg-[#09101d]/95 backdrop-blur border border-sky-500/40 rounded-xl p-2.5 shadow-2xl text-[11px] font-mono text-slate-200"
            style={{
              left: Math.min(dimensions.width - 230, Math.max(10, hoverState.x + 15)),
              top: Math.min(dimensions.height - 130, Math.max(10, hoverState.y - 45)),
            }}
          >
            <div className="flex items-center justify-between gap-3 border-b border-[#1b2a44] pb-1.5 mb-1.5">
              <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                Cursor Probe
              </span>
              <span
                className={`px-1.5 py-0.2 rounded text-[9px] font-bold ${
                  hoverState.isAnodic
                    ? "bg-sky-500/20 text-sky-300 border border-sky-500/40"
                    : "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                }`}
              >
                {hoverState.isAnodic ? "Anodic Oxidation" : "Cathodic Reduction"}
              </span>
            </div>
            <div className="space-y-1">
              <div className="flex justify-between gap-3">
                <span className="text-slate-400">Potential E:</span>
                <span className="text-white font-bold">{hoverState.potential.toFixed(4)} V</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-slate-400">Current Density:</span>
                <span className="text-sky-300 font-bold">
                  {hoverState.linearI_uA < 1000
                    ? `${hoverState.linearI_uA.toFixed(3)} µA/cm²`
                    : `${(hoverState.linearI_uA / 1000).toFixed(3)} mA/cm²`}
                </span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-slate-400">log₁₀(i):</span>
                <span className="text-amber-300">{hoverState.logI.toFixed(3)}</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-slate-400">Overpotential η:</span>
                <span
                  className={
                    hoverState.overpotential_mV >= 0 ? "text-sky-300" : "text-amber-300"
                  }
                >
                  {hoverState.overpotential_mV >= 0 ? "+" : ""}
                  {hoverState.overpotential_mV.toFixed(1)} mV
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Legend Banner Pill at Bottom Left */}
        <div className="absolute bottom-3 left-4 pointer-events-none bg-[#09101d]/90 backdrop-blur border border-[#1b2a44] rounded-lg px-3 py-1.5 flex items-center gap-4 text-[10px] font-mono text-slate-300 shadow-lg">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-0.5 bg-white inline-block"></span>
            <span>Experimental Scan</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-0.5 bg-sky-400 inline-block border-b border-dashed border-sky-400"></span>
            <span>Anodic Tangent (β_a = {fitResult.betaA_mV_dec} mV)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-0.5 bg-amber-400 inline-block border-b border-dashed border-amber-400"></span>
            <span>Cathodic Tangent (β_c = {fitResult.betaC_mV_dec} mV)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block shadow-[0_0_6px_#10b981]"></span>
            <span className="text-emerald-300 font-bold">Intersection (E_corr, i_corr)</span>
          </div>
        </div>

        {/* Zoom Instructions Pill at Top Right */}
        <div className="absolute top-3 right-4 pointer-events-none bg-[#09101d]/85 backdrop-blur border border-[#1b2a44] rounded-md px-2.5 py-1 text-[10px] font-mono text-slate-400 flex items-center gap-2">
          <span>Scroll to Zoom</span>
          <span>•</span>
          <span>Drag to Pan</span>
          <span>•</span>
          <span>Dbl-Click to Reset</span>
        </div>
      </div>

      {/* Numerical Metrics Summary Bar Below Chart */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-2 text-xs font-mono">
        <div className="bg-[#090e18] p-2.5 rounded-xl border border-emerald-500/30">
          <span className="text-[10px] text-slate-400 block">Corrosion Potential</span>
          <span className="text-emerald-300 font-extrabold text-sm">{fitResult.eCorr} V</span>
          <span className="text-[10px] text-slate-500 block">vs {dataset.metadata.referenceElectrode}</span>
        </div>

        <div className="bg-[#090e18] p-2.5 rounded-xl border border-sky-500/30">
          <span className="text-[10px] text-slate-400 block">Corrosion Current i_corr</span>
          <span className="text-sky-300 font-extrabold text-sm">{fitResult.iCorr_uA_cm2} µA/cm²</span>
          <span className="text-[10px] text-slate-500 block">log₁₀(i) = {fitResult.logIcorr}</span>
        </div>

        <div className="bg-[#090e18] p-2.5 rounded-xl border border-amber-500/30">
          <span className="text-[10px] text-slate-400 block">Annual Corrosion Rate</span>
          <span className="text-amber-300 font-extrabold text-sm">{fitResult.corrosionRateMmYr} mm/yr</span>
          <span className="text-[10px] text-slate-500 block">{fitResult.corrosionRateMpy} mpy</span>
        </div>

        <div className="bg-[#090e18] p-2.5 rounded-xl border border-[#162032]">
          <span className="text-[10px] text-slate-400 block">Polarization Resistance</span>
          <span className="text-purple-300 font-extrabold text-sm">
            {fitResult.rp_ohm_cm2.toLocaleString()} Ω·cm²
          </span>
          <span className="text-[10px] text-slate-500 block">B = {fitResult.sternGearyB_V.toFixed(3)} V</span>
        </div>

        <div className="bg-[#090e18] p-2.5 rounded-xl border border-[#162032]">
          <span className="text-[10px] text-slate-400 block">Tafel Slopes (β_a / β_c)</span>
          <span className="text-white font-bold text-xs">
            {fitResult.betaA_mV_dec} / {fitResult.betaC_mV_dec}
          </span>
          <span className="text-[10px] text-slate-500 block">mV/decade (ASTM G59)</span>
        </div>

        <div className="bg-[#090e18] p-2.5 rounded-xl border border-[#162032]">
          <span className="text-[10px] text-slate-400 block">ASTM G102 Severity</span>
          <span
            className={`font-bold text-xs block truncate ${
              fitResult.severity === "Immune / Highly Resistant"
                ? "text-emerald-300"
                : fitResult.severity === "Passivated / Good"
                ? "text-sky-300"
                : fitResult.severity === "Moderate (Caution)"
                ? "text-amber-300"
                : "text-rose-400"
            }`}
          >
            {fitResult.severity}
          </span>
          <span className="text-[10px] text-slate-500 block truncate">
            {fitResult.isPythonEngine ? "Python Verified" : "Client Engine"}
          </span>
        </div>
      </div>
    </div>
  );
};
