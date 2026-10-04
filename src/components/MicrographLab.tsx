import React, { useState } from "react";
import { Microscope } from "lucide-react";
import { MicrographAdvisoryDescription } from "./MicrographAdvisoryDescription";
import { MicrographMeasureStudio } from "./MicrographMeasureStudio";

/**
 * Micrograph module: calibrated measurements computed by python/micrograph_measure.py (area fraction with
 * uncertainty, particle statistics, ASTM E112 intercepts) plus an optional advisory language-model description.
 */
export const MicrographLab: React.FC = () => {
  const [advisoryImage, setAdvisoryImage] = useState<{ dataUrl: string; key: string } | null>(null);
  return (
    <div id="micrograph-lab-container" className="space-y-5">
      <div className="p-4 rounded-xl bg-[#090e18] border border-[#162032]">
        <div className="flex items-center gap-2 text-sky-400 font-mono text-[10px] font-semibold uppercase tracking-widest">
          <Microscope className="w-3.5 h-3.5" />
          Micrograph Analysis
        </div>
        <p className="text-xs text-slate-400 mt-1 max-w-3xl">
          Threshold area fractions, particle/pore statistics and ASTM E112 lineal-intercept grain size of one image, computed
          by a Python authority after you calibrate the scale. Measurement software checked only on synthetic images with a
          known answer; it does not identify phases or infer properties.
        </p>
      </div>
      <MicrographMeasureStudio onImageChange={setAdvisoryImage} />
      <MicrographAdvisoryDescription imageDataUrl={advisoryImage?.dataUrl ?? null} imageKey={advisoryImage?.key ?? null} />
    </div>
  );
};
