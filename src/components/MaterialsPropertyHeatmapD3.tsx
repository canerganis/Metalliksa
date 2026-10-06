import React, { useRef, useEffect, useState, useMemo } from "react";
import { axisBottom as d3AxisBottom, axisLeft as d3AxisLeft, interpolateInferno as d3InterpolateInferno, interpolatePlasma as d3InterpolatePlasma, interpolateRdYlGn as d3InterpolateRdYlGn, interpolateTurbo as d3InterpolateTurbo, interpolateViridis as d3InterpolateViridis, interpolateYlGnBu as d3InterpolateYlGnBu, max as d3Max, mean as d3Mean, median as d3Median, min as d3Min, pointer as d3Pointer, scaleBand as d3ScaleBand, scaleDiverging as d3ScaleDiverging, scaleLinear as d3ScaleLinear, scaleSequential as d3ScaleSequential, select as d3Select } from "d3";
import {
  Grid,
  Sparkles,
  Sliders,
  Maximize2,
  Minimize2,
  TrendingUp,
  Download,
  Info,
  Layers,
  Filter,
  Flame,
  ChevronRight,
  BarChart3,
  Search,
} from "lucide-react";
import { MaterialSpec } from "../types";

export type HeatmapMode = "alloy-elements" | "element-property-binned" | "property-correlation";
export type ColorPaletteKey = "viridis" | "plasma" | "turbo" | "emerald" | "amber-flame";

interface MaterialsPropertyHeatmapD3Props {
  materials: MaterialSpec[];
  selectedMaterial: MaterialSpec;
  onSelectMaterial: (mat: MaterialSpec) => void;
  categories: string[];
  activeCategory: string;
  onSelectCategory?: (category: string) => void;
}

// Major metallurgical alloying elements to track
const ALLOYING_ELEMENTS = [
  "C", "Cr", "Ni", "Mo", "Ti", "Al", "Cu", "V", "Mn", "Si", "Mg", "W", "Co", "Nb", "Zr", "Fe"
];

// Properties available for analysis
export const HEATMAP_PROPERTIES = [
  { key: "yieldStrength", label: "Yield Strength (σy)", unit: "MPa", shortLabel: "σy (MPa)" },
  { key: "tensileStrength", label: "Tensile Strength (UTS)", unit: "MPa", shortLabel: "UTS (MPa)" },
  { key: "youngsModulus", label: "Young's Modulus (E)", unit: "GPa", shortLabel: "E (GPa)" },
  { key: "density", label: "Density (ρ)", unit: "g/cm³", shortLabel: "ρ (g/cm³)" },
  { key: "specificStrength", label: "Specific Strength (σy/ρ)", unit: "kN·m/kg", shortLabel: "σy/ρ" },
  { key: "elongation", label: "Elongation (A5)", unit: "%", shortLabel: "A5 (%)" },
  { key: "thermalConductivity", label: "Thermal Conductivity", unit: "W/(m·K)", shortLabel: "k (W/m·K)" },
] as const;

export const MaterialsPropertyHeatmapD3: React.FC<MaterialsPropertyHeatmapD3Props> = ({
  materials,
  selectedMaterial,
  onSelectMaterial,
  categories,
  activeCategory,
  onSelectCategory,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  const [heatmapMode, setHeatmapMode] = useState<HeatmapMode>("alloy-elements");
  const [selectedPropertyKey, setSelectedPropertyKey] = useState<string>("yieldStrength");
  const [selectedElement, setSelectedElement] = useState<string>("Cr");
  const [colorPalette, setColorPalette] = useState<ColorPaletteKey>("viridis");
  const [sortBy, setSortBy] = useState<"property" | "element" | "name" | "category">("property");
  const [sortAsc, setSortAsc] = useState<boolean>(false);
  const [searchAlloy, setSearchAlloy] = useState<string>("");

  const [hoveredCell, setHoveredCell] = useState<{
    xLabel: string;
    yLabel: string;
    value: number | string;
    unit?: string;
    material?: MaterialSpec;
    extraInfo?: string;
    xPos: number;
    yPos: number;
  } | null>(null);

  const [dimensions, setDimensions] = useState<{ width: number; height: number }>({
    width: 800,
    height: 480,
  });

  // Extract numerical composition value (handles range objects or numbers)
  const getElementWt = (mat: MaterialSpec, element: string): number => {
    const val = mat.composition[element];
    if (val === undefined || val === null) return 0;
    if (typeof val === "number") return val;
    if (typeof val === "object") {
      const min = (val as any).min ?? 0;
      const max = (val as any).max ?? min;
      return (min + max) / 2;
    }
    return 0;
  };

  const getPropertyValue = (mat: MaterialSpec, propKey: string): number => {
    if (propKey === "specificStrength") {
      return mat.density > 0 ? parseFloat((mat.yieldStrength / mat.density).toFixed(1)) : 0;
    }
    if (propKey === "thermalConductivity") {
      return mat.thermalConductivity ?? 0;
    }
    const val = (mat as any)[propKey];
    return typeof val === "number" ? val : 0;
  };

  // Filter materials based on search query
  const displayedMaterials = useMemo(() => {
    return materials
      .filter((mat) => {
        if (!searchAlloy.trim()) return true;
        const q = searchAlloy.toLowerCase();
        return (
          mat.name.toLowerCase().includes(q) ||
          mat.category.toLowerCase().includes(q) ||
          mat.standard.toLowerCase().includes(q)
        );
      })
      .sort((a, b) => {
        let diff = 0;
        if (sortBy === "property") {
          diff = getPropertyValue(b, selectedPropertyKey) - getPropertyValue(a, selectedPropertyKey);
        } else if (sortBy === "element") {
          diff = getElementWt(b, selectedElement) - getElementWt(a, selectedElement);
        } else if (sortBy === "category") {
          diff = a.category.localeCompare(b.category) || a.name.localeCompare(b.name);
        } else {
          diff = a.name.localeCompare(b.name);
        }
        return sortAsc ? -diff : diff;
      });
  }, [materials, searchAlloy, sortBy, sortAsc, selectedPropertyKey, selectedElement]);

  // List of active alloying elements that actually appear in the displayed materials
  const activeElements = useMemo(() => {
    const counts: Record<string, number> = {};
    ALLOYING_ELEMENTS.forEach((elem) => {
      counts[elem] = displayedMaterials.reduce((acc, mat) => acc + (getElementWt(mat, elem) > 0 ? 1 : 0), 0);
    });
    // Return all standard elements with those occurring most placed first
    return ALLOYING_ELEMENTS.filter((elem) => counts[elem] > 0 || elem === "C" || elem === "Cr" || elem === "Ni" || elem === "Ti" || elem === "Al");
  }, [displayedMaterials]);

  // Statistical summary of property across displayed alloys
  const statsSummary = useMemo(() => {
    if (displayedMaterials.length === 0) return null;
    const values = displayedMaterials.map((m) => getPropertyValue(m, selectedPropertyKey)).filter((v) => v > 0);
    if (values.length === 0) return null;

    const min = d3Min(values) ?? 0;
    const max = d3Max(values) ?? 0;
    const mean = d3Mean(values) ?? 0;
    const median = d3Median(values) ?? 0;
    const currentProp = HEATMAP_PROPERTIES.find((p) => p.key === selectedPropertyKey);

    return {
      min,
      max,
      mean: Math.round(mean),
      median: Math.round(median),
      count: displayedMaterials.length,
      unit: currentProp?.unit || "",
      label: currentProp?.label || "",
    };
  }, [displayedMaterials, selectedPropertyKey]);

  // Correlation Matrix Data Computation (Pearson r between Elements and Properties)
  const correlationData = useMemo(() => {
    if (heatmapMode !== "property-correlation") return null;

    const targetProps = HEATMAP_PROPERTIES.filter((p) => p.key !== "thermalConductivity");
    const matrix: Array<{
      element: string;
      propertyKey: string;
      propertyLabel: string;
      r: number;
      sampleCount: number;
    }> = [];

    activeElements.forEach((elem) => {
      targetProps.forEach((prop) => {
        const pairs = displayedMaterials
          .map((m) => ({
            elemWt: getElementWt(m, elem),
            propVal: getPropertyValue(m, prop.key),
          }))
          .filter((p) => p.propVal > 0);

        if (pairs.length < 3) {
          matrix.push({
            element: elem,
            propertyKey: prop.key,
            propertyLabel: prop.shortLabel,
            r: 0,
            sampleCount: pairs.length,
          });
          return;
        }

        const meanX = d3Mean(pairs, (d: { elemWt: number; propVal: number }) => d.elemWt) ?? 0;
        const meanY = d3Mean(pairs, (d: { elemWt: number; propVal: number }) => d.propVal) ?? 0;

        let num = 0;
        let denX = 0;
        let denY = 0;

        pairs.forEach((d) => {
          const dx = d.elemWt - meanX;
          const dy = d.propVal - meanY;
          num += dx * dy;
          denX += dx * dx;
          denY += dy * dy;
        });

        const r = denX * denY > 0 ? num / Math.sqrt(denX * denY) : 0;
        matrix.push({
          element: elem,
          propertyKey: prop.key,
          propertyLabel: prop.shortLabel,
          r: parseFloat(r.toFixed(3)),
          sampleCount: pairs.length,
        });
      });
    });

    return matrix;
  }, [heatmapMode, displayedMaterials, activeElements]);

  // Element vs Property Binned Distribution (2D Binning)
  const binnedDistributionData = useMemo(() => {
    if (heatmapMode !== "element-property-binned") return null;

    // Filter materials with selected element > 0 or all
    const validMats = displayedMaterials.filter((m) => getPropertyValue(m, selectedPropertyKey) > 0);
    const propValues: number[] = validMats.map((m) => getPropertyValue(m, selectedPropertyKey));
    const elemValues: number[] = validMats.map((m) => getElementWt(m, selectedElement));

    const maxElem = Math.max(1, (d3Max(elemValues) as number | undefined) ?? 10);
    const maxProp = Math.max(10, (d3Max(propValues) as number | undefined) ?? 1000);
    const minProp = (d3Min(propValues) as number | undefined) ?? 0;

    // Create 8 bins for element wt% and 8 bins for property value
    const numBinsX = 8;
    const numBinsY = 8;
    const elemStep = maxElem / numBinsX;
    const propStep = (maxProp - minProp) / numBinsY;

    const bins: Array<{
      binX: number;
      binY: number;
      elemRange: [number, number];
      propRange: [number, number];
      materials: MaterialSpec[];
      count: number;
    }> = [];

    for (let bx = 0; bx < numBinsX; bx++) {
      const minX = bx * elemStep;
      const maxX = (bx + 1) * elemStep;
      for (let by = 0; by < numBinsY; by++) {
        const minY = minProp + by * propStep;
        const maxY = minProp + (by + 1) * propStep;

        const matching = validMats.filter((m) => {
          const eVal = getElementWt(m, selectedElement);
          const pVal = getPropertyValue(m, selectedPropertyKey);
          const inX = bx === numBinsX - 1 ? eVal >= minX && eVal <= maxX : eVal >= minX && eVal < maxX;
          const inY = by === numBinsY - 1 ? pVal >= minY && pVal <= maxY : pVal >= minY && pVal < maxY;
          return inX && inY;
        });

        bins.push({
          binX: bx,
          binY: by,
          elemRange: [parseFloat(minX.toFixed(2)), parseFloat(maxX.toFixed(2))],
          propRange: [Math.round(minY), Math.round(maxY)],
          materials: matching,
          count: matching.length,
        });
      }
    }

    return {
      bins,
      maxElem,
      minProp,
      maxProp,
      numBinsX,
      numBinsY,
      elemStep,
      propStep,
    };
  }, [heatmapMode, displayedMaterials, selectedElement, selectedPropertyKey]);

  // Color interpolators
  const getColorScale = (minVal: number, maxVal: number, diverging = false) => {
    if (diverging) {
      // Diverging for correlation: -1 (Rose/Crimson) -> 0 (Dark Slate) -> +1 (Emerald/Cyan)
      return d3ScaleDiverging<string>()
        .domain([-1, 0, 1])
        .interpolator(d3InterpolateRdYlGn);
    }

    if (colorPalette === "viridis") {
      return d3ScaleSequential(d3InterpolateViridis).domain([minVal, maxVal]);
    }
    if (colorPalette === "plasma") {
      return d3ScaleSequential(d3InterpolatePlasma).domain([minVal, maxVal]);
    }
    if (colorPalette === "turbo") {
      return d3ScaleSequential(d3InterpolateTurbo).domain([minVal, maxVal]);
    }
    if (colorPalette === "emerald") {
      return d3ScaleSequential(d3InterpolateYlGnBu).domain([minVal, maxVal]);
    }
    return d3ScaleSequential(d3InterpolateInferno).domain([minVal, maxVal]);
  };

  // ResizeObserver for fluid responsive D3 rendering
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0) {
          const w = Math.max(360, Math.floor(entry.contentRect.width));
          // Calculate dynamic height based on item count and mode
          let h = 480;
          if (heatmapMode === "alloy-elements") {
            h = Math.max(380, Math.min(850, displayedMaterials.length * 24 + 110));
          } else if (heatmapMode === "property-correlation") {
            h = Math.max(360, activeElements.length * 28 + 120);
          } else {
            h = 420;
          }
          setDimensions({ width: w, height: h });
        }
      }
    });

    observer.observe(el);
    return () => observer.disconnect();
  }, [displayedMaterials.length, heatmapMode, activeElements.length]);

  // Main D3 Rendering Engine
  useEffect(() => {
    if (!svgRef.current || displayedMaterials.length === 0) return;

    const svg = d3Select(svgRef.current);
    svg.selectAll("*").remove();

    const { width, height } = dimensions;

    // --- MODE 1: ALLOY VS ALLOYING ELEMENT COMPOSITION MATRIX ---
    if (heatmapMode === "alloy-elements") {
      const margin = { top: 60, right: 90, bottom: 25, left: Math.min(220, Math.max(140, Math.floor(width * 0.28))) };
      const innerWidth = width - margin.left - margin.right;
      const innerHeight = height - margin.top - margin.bottom;

      if (innerWidth <= 0 || innerHeight <= 0) return;

      const g = svg
        .attr("width", width)
        .attr("height", height)
        .append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);

      const xElements = activeElements;
      const yMaterials = displayedMaterials;

      const xScale = d3ScaleBand().domain(xElements).range([0, innerWidth]).padding(0.08);
      const yScale = d3ScaleBand().domain(yMaterials.map((m) => m.id)).range([0, innerHeight]).padding(0.08);

      // Max composition across cells (excluding matrix balance like Fe > 80% to keep contrast vibrant)
      const allCompValues: number[] = yMaterials.flatMap((m) =>
        xElements.map((el) => {
          const v = getElementWt(m, el);
          return el === "Fe" || el === "Ti" || el === "Ni" || el === "Al" || el === "Cu" ? Math.min(25, v) : v;
        })
      );
      const maxComp = Math.max(5, (d3Max(allCompValues) as number | undefined) ?? 15);
      const colorScale = getColorScale(0, maxComp);

      // X Axis (Element symbols on top)
      const xAxisG = g.append("g").attr("class", "x-axis");
      xElements.forEach((elem) => {
        const xPos = (xScale(elem) ?? 0) + xScale.bandwidth() / 2;
        xAxisG
          .append("text")
          .attr("x", xPos)
          .attr("y", -14)
          .attr("text-anchor", "middle")
          .attr("fill", elem === selectedElement ? "#38bdf8" : "#94a3b8")
          .attr("font-family", "monospace")
          .attr("font-size", "11px")
          .attr("font-weight", elem === selectedElement ? "bold" : "600")
          .attr("cursor", "pointer")
          .text(elem)
          .on("click", () => setSelectedElement(elem));
      });

      // Axis Title
      xAxisG
        .append("text")
        .attr("x", innerWidth / 2)
        .attr("y", -38)
        .attr("text-anchor", "middle")
        .attr("fill", "#38bdf8")
        .attr("font-family", "monospace")
        .attr("font-size", "10px")
        .attr("font-weight", "bold")
        .text("▲ Alloying Element Additions (% wt concentration) — Click element to focus");

      // Right Axis (Target Property Value column)
      const propColG = g.append("g").attr("class", "prop-column").attr("transform", `translate(${innerWidth + 12}, 0)`);
      const currentPropDef = HEATMAP_PROPERTIES.find((p) => p.key === selectedPropertyKey);

      propColG
        .append("text")
        .attr("x", 0)
        .attr("y", -14)
        .attr("text-anchor", "start")
        .attr("fill", "#10b981")
        .attr("font-family", "monospace")
        .attr("font-size", "10px")
        .attr("font-weight", "bold")
        .text(currentPropDef?.shortLabel || "Value");

      // Y Axis Rows (Materials)
      const yAxisG = g.append("g").attr("class", "y-axis");
      yMaterials.forEach((mat) => {
        const yPos = (yScale(mat.id) ?? 0) + yScale.bandwidth() / 2;
        const isSelected = selectedMaterial.id === mat.id;

        // Label text
        const textLabel = yAxisG
          .append("text")
          .attr("x", -10)
          .attr("y", yPos + 3.5)
          .attr("text-anchor", "end")
          .attr("fill", isSelected ? "#38bdf8" : "#cbd5e1")
          .attr("font-family", "monospace")
          .attr("font-size", "10px")
          .attr("font-weight", isSelected ? "bold" : "normal")
          .attr("cursor", "pointer")
          .text(mat.name.length > 22 ? mat.name.substring(0, 20) + "…" : mat.name)
          .on("click", () => onSelectMaterial(mat));

        // Category dot marker
        yAxisG
          .append("circle")
          .attr("cx", -Math.min(margin.left - 15, 135))
          .attr("cy", yPos)
          .attr("r", 2.5)
          .attr("fill", isSelected ? "#38bdf8" : "#475569");

        // Render Property Column Pill
        const propVal = getPropertyValue(mat, selectedPropertyKey);
        propColG
          .append("text")
          .attr("x", 0)
          .attr("y", yPos + 3.5)
          .attr("fill", isSelected ? "#38bdf8" : "#34d399")
          .attr("font-family", "monospace")
          .attr("font-size", "9.5px")
          .attr("font-weight", "600")
          .text(`${propVal}`);
      });

      // Heatmap Grid Cells
      const cellsG = g.append("g").attr("class", "heatmap-cells");

      yMaterials.forEach((mat) => {
        const isSelected = selectedMaterial.id === mat.id;
        const y0 = yScale(mat.id) ?? 0;
        const rowHeight = yScale.bandwidth();

        // Row background selection highlight
        if (isSelected) {
          cellsG
            .append("rect")
            .attr("x", -margin.left + 5)
            .attr("y", y0 - 1)
            .attr("width", innerWidth + margin.left + margin.right - 10)
            .attr("height", rowHeight + 2)
            .attr("fill", "rgba(56, 189, 248, 0.08)")
            .attr("stroke", "rgba(56, 189, 248, 0.35)")
            .attr("stroke-width", 1)
            .attr("rx", 4)
            .attr("pointer-events", "none");
        }

        xElements.forEach((elem) => {
          const x0 = xScale(elem) ?? 0;
          const colWidth = xScale.bandwidth();
          const wt = getElementWt(mat, elem);

          const cellColor = wt > 0 ? colorScale(wt) : "#0c1322";
          const cellStroke = wt > 0 ? "rgba(255,255,255,0.06)" : "#162032";

          const rect = cellsG
            .append("rect")
            .attr("x", x0)
            .attr("y", y0)
            .attr("width", colWidth)
            .attr("height", rowHeight)
            .attr("fill", cellColor)
            .attr("stroke", cellStroke)
            .attr("stroke-width", 0.75)
            .attr("rx", 3)
            .attr("cursor", "pointer")
            .on("click", () => {
              onSelectMaterial(mat);
              setSelectedElement(elem);
            })
            .on("pointerenter", function (event: MouseEvent) {
              d3Select(this).attr("stroke", "#ffffff").attr("stroke-width", 1.5);
              const [mx, my] = d3Pointer(event, svgRef.current);
              setHoveredCell({
                xLabel: `${elem} Content`,
                yLabel: mat.name,
                value: wt > 0 ? `${wt}% wt` : "None (< 0.01%)",
                unit: "% wt",
                material: mat,
                extraInfo: `${currentPropDef?.label}: ${getPropertyValue(mat, selectedPropertyKey)} ${currentPropDef?.unit}`,
                xPos: mx,
                yPos: my,
              });
            })
            .on("pointerleave", function () {
              d3Select(this).attr("stroke", cellStroke).attr("stroke-width", 0.75);
              setHoveredCell(null);
            });

          // Text label if cell is wide enough
          if (colWidth > 28 && rowHeight > 14 && wt > 0) {
            cellsG
              .append("text")
              .attr("x", x0 + colWidth / 2)
              .attr("y", y0 + rowHeight / 2 + 3)
              .attr("text-anchor", "middle")
              .attr("fill", wt > maxComp * 0.55 ? "#000000" : "#ffffff")
              .attr("font-family", "monospace")
              .attr("font-size", colWidth > 40 ? "8.5px" : "7.5px")
              .attr("font-weight", "600")
              .attr("pointer-events", "none")
              .text(wt >= 1 ? wt.toFixed(1) : wt.toFixed(2));
          }
        });
      });
    }

    // --- MODE 2: ELEMENT CONCENTRATION VS PROPERTY 2D BINNED HEATMAP ---
    else if (heatmapMode === "element-property-binned" && binnedDistributionData) {
      const margin = { top: 50, right: 60, bottom: 55, left: 75 };
      const innerWidth = width - margin.left - margin.right;
      const innerHeight = height - margin.top - margin.bottom;

      if (innerWidth <= 0 || innerHeight <= 0) return;

      const g = svg
        .attr("width", width)
        .attr("height", height)
        .append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);

      const { bins, maxElem, minProp, maxProp, numBinsX, numBinsY, elemStep, propStep } = binnedDistributionData;

      const xScale = d3ScaleLinear().domain([0, maxElem]).range([0, innerWidth]);
      const yScale = d3ScaleLinear().domain([minProp, maxProp]).range([innerHeight, 0]);

      const maxBinCount = Math.max(1, (d3Max(bins, (b: { count: number }) => b.count) as number | undefined) ?? 1);
      const colorScale = getColorScale(0, maxBinCount);

      // Grid Cells
      const cellWidth = innerWidth / numBinsX;
      const cellHeight = innerHeight / numBinsY;

      bins.forEach((b) => {
        const x0 = b.binX * cellWidth;
        const y0 = innerHeight - (b.binY + 1) * cellHeight;

        const cellColor = b.count > 0 ? colorScale(b.count) : "#0c1322";
        const hasSelectedMat = b.materials.some((m) => m.id === selectedMaterial.id);

        const rect = g
          .append("rect")
          .attr("x", x0 + 1)
          .attr("y", y0 + 1)
          .attr("width", cellWidth - 2)
          .attr("height", cellHeight - 2)
          .attr("fill", cellColor)
          .attr("stroke", hasSelectedMat ? "#38bdf8" : b.count > 0 ? "rgba(255,255,255,0.1)" : "#162032")
          .attr("stroke-width", hasSelectedMat ? 2 : 1)
          .attr("rx", 4)
          .attr("cursor", b.count > 0 ? "pointer" : "default")
          .on("click", () => {
            if (b.materials.length > 0) {
              onSelectMaterial(b.materials[0]);
            }
          })
          .on("pointerenter", function (event: MouseEvent) {
            if (b.count === 0) return;
            d3Select(this).attr("stroke", "#ffffff").attr("stroke-width", 2);
            const [mx, my] = d3Pointer(event, svgRef.current);
            const propDef = HEATMAP_PROPERTIES.find((p) => p.key === selectedPropertyKey);
            setHoveredCell({
              xLabel: `${selectedElement}: ${b.elemRange[0]}–${b.elemRange[1]}% wt`,
              yLabel: `${propDef?.label}: ${b.propRange[0]}–${b.propRange[1]} ${propDef?.unit}`,
              value: `${b.count} Alloy${b.count > 1 ? "s" : ""}`,
              extraInfo: b.materials.map((m) => m.name).slice(0, 3).join(", ") + (b.materials.length > 3 ? "..." : ""),
              xPos: mx,
              yPos: my,
            });
          })
          .on("pointerleave", function () {
            d3Select(this).attr("stroke", hasSelectedMat ? "#38bdf8" : b.count > 0 ? "rgba(255,255,255,0.1)" : "#162032").attr("stroke-width", hasSelectedMat ? 2 : 1);
            setHoveredCell(null);
          });

        if (b.count > 0) {
          g.append("text")
            .attr("x", x0 + cellWidth / 2)
            .attr("y", y0 + cellHeight / 2 + 4)
            .attr("text-anchor", "middle")
            .attr("fill", b.count > maxBinCount * 0.5 ? "#000000" : "#ffffff")
            .attr("font-family", "monospace")
            .attr("font-size", "11px")
            .attr("font-weight", "bold")
            .attr("pointer-events", "none")
            .text(b.count);
        }
      });

      // Scatter Points of Individual Alloys overlay
      displayedMaterials.forEach((mat) => {
        const eVal = getElementWt(mat, selectedElement);
        const pVal = getPropertyValue(mat, selectedPropertyKey);
        if (pVal <= 0) return;

        const cx = xScale(eVal);
        const cy = yScale(pVal);
        const isSelected = selectedMaterial.id === mat.id;

        g.append("circle")
          .attr("cx", cx)
          .attr("cy", cy)
          .attr("r", isSelected ? 6 : 3)
          .attr("fill", isSelected ? "#38bdf8" : "rgba(255, 255, 255, 0.7)")
          .attr("stroke", isSelected ? "#ffffff" : "#050810")
          .attr("stroke-width", isSelected ? 2 : 1)
          .attr("cursor", "pointer")
          .on("click", () => onSelectMaterial(mat));
      });

      // X Axis
      const xAxis = d3AxisBottom(xScale).ticks(6).tickFormat((d) => `${d}%`);
      g.append("g")
        .attr("transform", `translate(0, ${innerHeight})`)
        .call(xAxis)
        .selectAll("text")
        .attr("fill", "#64748b")
        .attr("font-family", "monospace")
        .attr("font-size", "10px");

      // X Axis Title
      g.append("text")
        .attr("x", innerWidth / 2)
        .attr("y", innerHeight + 42)
        .attr("text-anchor", "middle")
        .attr("fill", "#38bdf8")
        .attr("font-family", "monospace")
        .attr("font-size", "11px")
        .attr("font-weight", "bold")
        .text(`[${selectedElement}] Alloying Element Concentration (% wt)`);

      // Y Axis
      const yAxis = d3AxisLeft(yScale).ticks(6).tickFormat((d) => `${d}`);
      g.append("g")
        .call(yAxis)
        .selectAll("text")
        .attr("fill", "#10b981")
        .attr("font-family", "monospace")
        .attr("font-size", "10px");

      // Y Axis Title
      const propDef = HEATMAP_PROPERTIES.find((p) => p.key === selectedPropertyKey);
      g.append("text")
        .attr("transform", "rotate(-90)")
        .attr("x", -innerHeight / 2)
        .attr("y", -52)
        .attr("text-anchor", "middle")
        .attr("fill", "#10b981")
        .attr("font-family", "monospace")
        .attr("font-size", "11px")
        .attr("font-weight", "bold")
        .text(`${propDef?.label || "Property"} (${propDef?.unit || ""})`);

      g.selectAll(".domain, .tick line").attr("stroke", "#162032");
    }

    // --- MODE 3: ALLOYING ELEMENT VS MECHANICAL PROPERTIES CORRELATION HEATMAP ---
    else if (heatmapMode === "property-correlation" && correlationData) {
      const margin = { top: 65, right: 60, bottom: 35, left: 60 };
      const innerWidth = width - margin.left - margin.right;
      const innerHeight = height - margin.top - margin.bottom;

      if (innerWidth <= 0 || innerHeight <= 0) return;

      const g = svg
        .attr("width", width)
        .attr("height", height)
        .append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);

      const xProps = HEATMAP_PROPERTIES.filter((p) => p.key !== "thermalConductivity");
      const yElements = activeElements;

      const xScale = d3ScaleBand().domain(xProps.map((p) => p.key)).range([0, innerWidth]).padding(0.08);
      const yScale = d3ScaleBand().domain(yElements).range([0, innerHeight]).padding(0.08);

      const colorDiverging = getColorScale(-1, 1, true);

      // X Axis (Properties on top)
      const xAxisG = g.append("g").attr("class", "x-axis");
      xProps.forEach((prop) => {
        const xPos = (xScale(prop.key) ?? 0) + xScale.bandwidth() / 2;
        xAxisG
          .append("text")
          .attr("x", xPos)
          .attr("y", -14)
          .attr("text-anchor", "middle")
          .attr("fill", prop.key === selectedPropertyKey ? "#38bdf8" : "#cbd5e1")
          .attr("font-family", "monospace")
          .attr("font-size", "10px")
          .attr("font-weight", prop.key === selectedPropertyKey ? "bold" : "600")
          .attr("cursor", "pointer")
          .text(prop.shortLabel)
          .on("click", () => setSelectedPropertyKey(prop.key));
      });

      xAxisG
        .append("text")
        .attr("x", innerWidth / 2)
        .attr("y", -38)
        .attr("text-anchor", "middle")
        .attr("fill", "#38bdf8")
        .attr("font-family", "monospace")
        .attr("font-size", "11px")
        .attr("font-weight", "bold")
        .text("Pearson Correlation Coefficient (r) Matrix: Alloying Element vs Property");

      // Y Axis (Elements on left)
      const yAxisG = g.append("g").attr("class", "y-axis");
      yElements.forEach((elem) => {
        const yPos = (yScale(elem) ?? 0) + yScale.bandwidth() / 2;
        yAxisG
          .append("text")
          .attr("x", -12)
          .attr("y", yPos + 4)
          .attr("text-anchor", "end")
          .attr("fill", elem === selectedElement ? "#38bdf8" : "#94a3b8")
          .attr("font-family", "monospace")
          .attr("font-size", "11px")
          .attr("font-weight", "bold")
          .attr("cursor", "pointer")
          .text(elem)
          .on("click", () => setSelectedElement(elem));
      });

      // Heatmap Cells
      const cellsG = g.append("g").attr("class", "corr-cells");

      correlationData.forEach((cell) => {
        const x0 = xScale(cell.propertyKey) ?? 0;
        const y0 = yScale(cell.element) ?? 0;
        const colWidth = xScale.bandwidth();
        const rowHeight = yScale.bandwidth();

        // Cell Color (Diverging Red to Green)
        const cellColor = cell.sampleCount > 2 ? colorDiverging(cell.r) : "#0c1322";

        const rect = cellsG
          .append("rect")
          .attr("x", x0)
          .attr("y", y0)
          .attr("width", colWidth)
          .attr("height", rowHeight)
          .attr("fill", cellColor)
          .attr("stroke", "rgba(255,255,255,0.08)")
          .attr("stroke-width", 0.75)
          .attr("rx", 4)
          .attr("cursor", "pointer")
          .on("click", () => {
            setSelectedElement(cell.element);
            setSelectedPropertyKey(cell.propertyKey);
          })
          .on("pointerenter", function (event: MouseEvent) {
            d3Select(this).attr("stroke", "#ffffff").attr("stroke-width", 1.8);
            const [mx, my] = d3Pointer(event, svgRef.current);
            const rDesc =
              cell.r > 0.6
                ? "Strong Positive Correlation"
                : cell.r > 0.25
                ? "Moderate Positive Correlation"
                : cell.r < -0.6
                ? "Strong Negative Correlation"
                : cell.r < -0.25
                ? "Moderate Negative Correlation"
                : "Weak / No Correlation";

            setHoveredCell({
              xLabel: `Element [${cell.element}]`,
              yLabel: cell.propertyLabel,
              value: `r = ${cell.r > 0 ? "+" : ""}${cell.r}`,
              extraInfo: `${rDesc} (n=${cell.sampleCount} alloys)`,
              xPos: mx,
              yPos: my,
            });
          })
          .on("pointerleave", function () {
            d3Select(this).attr("stroke", "rgba(255,255,255,0.08)").attr("stroke-width", 0.75);
            setHoveredCell(null);
          });

        // Numeric text label in cell
        if (colWidth > 32 && rowHeight > 14) {
          cellsG
            .append("text")
            .attr("x", x0 + colWidth / 2)
            .attr("y", y0 + rowHeight / 2 + 3.5)
            .attr("text-anchor", "middle")
            .attr("fill", Math.abs(cell.r) > 0.4 ? "#ffffff" : "#cbd5e1")
            .attr("font-family", "monospace")
            .attr("font-size", "9.5px")
            .attr("font-weight", "bold")
            .attr("pointer-events", "none")
            .text(cell.r > 0 ? `+${cell.r.toFixed(2)}` : cell.r.toFixed(2));
        }
      });
    }
  }, [
    dimensions,
    displayedMaterials,
    heatmapMode,
    activeElements,
    selectedMaterial,
    selectedPropertyKey,
    selectedElement,
    colorPalette,
    correlationData,
    binnedDistributionData,
    onSelectMaterial,
  ]);

  const handleExportSVG = () => {
    if (!svgRef.current) return;
    const serializer = new XMLSerializer();
    const source = serializer.serializeToString(svgRef.current);
    const blob = new Blob([source], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Materials_Heatmap_${heatmapMode}_${selectedPropertyKey}.svg`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="bg-[#090e18] p-5 rounded-2xl border border-[#162032] space-y-4 shadow-xl">
      {/* Top Header & View Modes */}
      <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-3 border-b border-[#162032] pb-4">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-sky-500/10 border border-sky-500/30 text-sky-400">
            <Grid className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider">
                D3.js Metallurgical Composition & Property Heatmap
              </h3>
              <span className="px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 text-[10px] font-mono border border-sky-500/40">
                Composition Discovery
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Visualize multi-element alloying concentrations (% wt) against mechanical properties and calculate Pearson correlation coefficients.
            </p>
          </div>
        </div>

        {/* View Mode Switcher */}
        <div className="flex items-center gap-1.5 bg-[#050810] p-1 rounded-xl border border-[#162032] overflow-x-auto">
          <button
            type="button"
            onClick={() => setHeatmapMode("alloy-elements")}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition whitespace-nowrap ${
              heatmapMode === "alloy-elements"
                ? "bg-sky-500/20 text-sky-300 border border-sky-500/40 shadow-[0_0_10px_rgba(56,189,248,0.25)]"
                : "text-slate-400 hover:text-white border border-transparent"
            }`}
          >
            Alloy Composition Matrix
          </button>

          <button
            type="button"
            onClick={() => setHeatmapMode("element-property-binned")}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition whitespace-nowrap ${
              heatmapMode === "element-property-binned"
                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-[0_0_10px_rgba(16,185,129,0.25)]"
                : "text-slate-400 hover:text-white border border-transparent"
            }`}
          >
            2D Property Binned Map
          </button>

          <button
            type="button"
            onClick={() => setHeatmapMode("property-correlation")}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition whitespace-nowrap ${
              heatmapMode === "property-correlation"
                ? "bg-purple-500/20 text-purple-300 border border-purple-500/40 shadow-[0_0_10px_rgba(168,85,247,0.25)]"
                : "text-slate-400 hover:text-white border border-transparent"
            }`}
          >
            Element Correlation (r) Matrix
          </button>
        </div>
      </div>

      {/* Control & Filter Strip */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center bg-[#050810] p-3 rounded-xl border border-[#162032]">
        {/* Target Property Selector */}
        <div className="md:col-span-4 flex items-center gap-2">
          <span className="text-xs font-mono text-slate-400 whitespace-nowrap">Property:</span>
          <select aria-label="Property"
            value={selectedPropertyKey}
            onChange={(e) => setSelectedPropertyKey(e.target.value)}
            className="w-full bg-[#090e18] border border-[#162032] rounded-lg px-2.5 py-1.5 text-xs text-emerald-400 font-mono focus:outline-none focus:border-sky-400"
          >
            {HEATMAP_PROPERTIES.map((prop) => (
              <option key={prop.key} value={prop.key}>
                {prop.label} ({prop.unit})
              </option>
            ))}
          </select>
        </div>

        {/* Focused Element Selector (Relevant for Binned mode & sorting) */}
        <div className="md:col-span-3 flex items-center gap-2">
          <span className="text-xs font-mono text-slate-400 whitespace-nowrap">Element:</span>
          <select aria-label="Element"
            value={selectedElement}
            onChange={(e) => setSelectedElement(e.target.value)}
            className="w-full bg-[#090e18] border border-[#162032] rounded-lg px-2.5 py-1.5 text-xs text-sky-400 font-mono focus:outline-none focus:border-sky-400 font-bold"
          >
            {ALLOYING_ELEMENTS.map((el) => (
              <option key={el} value={el}>
                [{el}] {el === "C" ? "Carbon" : el === "Cr" ? "Chromium" : el === "Ni" ? "Nickel" : el === "Mo" ? "Molybdenum" : el === "Ti" ? "Titanium" : el === "Al" ? "Aluminum" : el === "V" ? "Vanadium" : el === "Cu" ? "Copper" : el}
              </option>
            ))}
          </select>
        </div>

        {/* Sorting Selector */}
        {heatmapMode === "alloy-elements" && (
          <div className="md:col-span-3 flex items-center gap-2">
            <span className="text-xs font-mono text-slate-400 whitespace-nowrap">Sort:</span>
            <select aria-label="Sort"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="w-full bg-[#090e18] border border-[#162032] rounded-lg px-2.5 py-1.5 text-xs text-slate-200 font-mono focus:outline-none"
            >
              <option value="property">By Selected Property</option>
              <option value="element">By [{selectedElement}] Concentration</option>
              <option value="category">By Category</option>
              <option value="name">Alloy Name (A-Z)</option>
            </select>
          </div>
        )}

        {/* Color Palette Selector */}
        <div className={`${heatmapMode === "alloy-elements" ? "md:col-span-2" : "md:col-span-5"} flex items-center justify-end gap-2`}>
          <span className="text-xs font-mono text-slate-400 whitespace-nowrap">Theme:</span>
          <select aria-label="Theme"
            value={colorPalette}
            onChange={(e) => setColorPalette(e.target.value as ColorPaletteKey)}
            className="bg-[#090e18] border border-[#162032] rounded-lg px-2 py-1.5 text-xs text-amber-400 font-mono focus:outline-none"
          >
            <option value="viridis">Viridis</option>
            <option value="plasma">Plasma</option>
            <option value="turbo">Turbo Spectrum</option>
            <option value="emerald">Emerald Sea</option>
            <option value="amber-flame">Inferno Flame</option>
          </select>
        </div>
      </div>

      {/* Statistical Summary Bar */}
      {statsSummary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 font-mono text-xs">
          <div className="p-2.5 bg-[#050810] rounded-xl border border-[#162032]">
            <span className="text-[10px] text-slate-400 uppercase block font-semibold">Evaluated Metric</span>
            <span className="text-white font-bold text-sm block mt-0.5 truncate">{statsSummary.label}</span>
            <span className="text-[10px] text-slate-500">{statsSummary.count} Alloys Plotted</span>
          </div>

          <div className="p-2.5 bg-[#050810] rounded-xl border border-[#162032]">
            <span className="text-[10px] text-slate-400 uppercase block font-semibold">Mean Value (μ)</span>
            <span className="text-emerald-400 font-extrabold text-sm block mt-0.5">
              {statsSummary.mean} <span className="text-xs font-normal text-slate-400">{statsSummary.unit}</span>
            </span>
            <span className="text-[10px] text-slate-500">Median: {statsSummary.median} {statsSummary.unit}</span>
          </div>

          <div className="p-2.5 bg-[#050810] rounded-xl border border-[#162032]">
            <span className="text-[10px] text-slate-400 uppercase block font-semibold">Property Range [Min – Max]</span>
            <span className="text-amber-400 font-bold text-sm block mt-0.5">
              {statsSummary.min} – {statsSummary.max}
            </span>
            <span className="text-[10px] text-slate-500">Unit: {statsSummary.unit}</span>
          </div>

          <div className="p-2.5 bg-[#050810] rounded-xl border border-[#162032]">
            <span className="text-[10px] text-slate-400 uppercase block font-semibold">Active Selection</span>
            <span className="text-sky-400 font-bold text-sm block mt-0.5 truncate">{selectedMaterial.name}</span>
            <span className="text-[10px] text-slate-500">
              {getPropertyValue(selectedMaterial, selectedPropertyKey)} {statsSummary.unit}
            </span>
          </div>
        </div>
      )}

      {/* D3 Heatmap Canvas & Floating Tooltip */}
      <div
        ref={containerRef}
        className="relative w-full bg-[#050810] rounded-xl border border-[#162032] p-2 overflow-x-auto select-none"
      >
        <svg ref={svgRef} className="w-full block" />

        {/* Floating Custom Tooltip */}
        {hoveredCell && (
          <div
            className="absolute pointer-events-none z-30 p-3 rounded-xl bg-[#090e18]/95 backdrop-blur border border-[#1e2d46] shadow-[0_6px_25px_rgba(0,0,0,0.8)] font-mono text-xs text-white space-y-1.5 min-w-[210px]"
            style={{
              left: `${Math.min(dimensions.width - 230, Math.max(10, hoveredCell.xPos + 15))}px`,
              top: `${Math.min(dimensions.height - 130, Math.max(10, hoveredCell.yPos - 20))}px`,
            }}
          >
            <div className="text-[11px] font-bold text-sky-300 border-b border-[#162032] pb-1 truncate">
              {hoveredCell.yLabel}
            </div>
            <div className="flex justify-between items-center text-[11px]">
              <span className="text-slate-400">{hoveredCell.xLabel}:</span>
              <span className="text-emerald-400 font-bold">{hoveredCell.value}</span>
            </div>
            {hoveredCell.extraInfo && (
              <div className="text-[10px] text-amber-300/90 pt-0.5 border-t border-[#162032]">
                {hoveredCell.extraInfo}
              </div>
            )}
            <div className="text-[9px] text-slate-500 pt-0.5 text-center">
              Click to select & inspect full dossier
            </div>
          </div>
        )}
      </div>

      {/* Heatmap Footer Legend & SVG Export */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1 text-xs font-mono">
        <div className="flex items-center gap-4 text-[11px] text-slate-400">
          <div className="flex items-center gap-1.5">
            <div className="w-20 h-2.5 rounded bg-gradient-to-r from-[#0c1322] via-[#0284c7] to-[#facc15]"></div>
            <span>Low ➔ High Intensity</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-sky-500/20 border border-sky-400"></span>
            <span className="text-sky-300">Selected Alloy</span>
          </div>
        </div>

        <button
          type="button"
          onClick={handleExportSVG}
          className="px-3 py-1.5 bg-[#050810] hover:bg-white/10 border border-[#1e2d46] text-slate-300 hover:text-white rounded-lg transition flex items-center gap-1.5 text-xs"
          title="Download D3 Vector Graphic SVG"
        >
          <Download className="w-3.5 h-3.5 text-sky-400" />
          <span>Export Heatmap SVG</span>
        </button>
      </div>
    </div>
  );
};
