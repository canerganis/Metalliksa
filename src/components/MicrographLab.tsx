import React, { useRef, useState } from "react";
import { Microscope, Upload } from "lucide-react";
import { ADVISORY_IMAGE_TYPES, MicrographAdvisoryDescription } from "./MicrographAdvisoryDescription";
import { rgbToLuminance } from "../utils/semAnalysis";

/**
 * Micrograph module shell. The former in-browser SEM analyzer (invented scale defaults, canned AI routes, derived
 * cooling-rate/strength estimates, PDF "inspection report") was removed; the calibrated measurement tool backed by
 * python/micrograph_measure.py is being rebuilt.
 */
export const MicrographLab: React.FC = () => {
  const [image, setImage] = useState<{ url: string; name: string } | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [pipette, setPipette] = useState<{ x: number; y: number; grey: number } | null>(null);

  // Grey level of the clicked pixel (natural image coordinates), read from a 1x1 canvas copy.
  const readGrey = (e: React.MouseEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    const rect = img.getBoundingClientRect();
    const x = Math.floor(((e.clientX - rect.left) / rect.width) * img.naturalWidth);
    const y = Math.floor(((e.clientY - rect.top) / rect.height) * img.naturalHeight);
    const canvas = document.createElement("canvas");
    canvas.width = 1;
    canvas.height = 1;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(img, x, y, 1, 1, 0, 0, 1, 1);
    const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data;
    return { x, y, grey: rgbToLuminance(r, g, b) };
  };

  const onFile = (file: File | undefined) => {
    if (!file) return;
    if (!(ADVISORY_IMAGE_TYPES as readonly string[]).includes(file.type)) {
      setMessage(`${file.name}: only PNG, JPEG, WebP or GIF can be loaded here.`);
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      setImage({ url: String(reader.result), name: file.name });
      setPipette(null);
      setMessage(null);
    };
    reader.onerror = () => setMessage(`${file.name}: the file could not be read.`);
    reader.readAsDataURL(file);
  };

  return (
    <div id="micrograph-lab-container" className="space-y-5">
      <div className="p-4 rounded-xl bg-[#090e18] border border-[#162032]">
        <div className="flex items-center gap-2 text-sky-400 font-mono text-[10px] font-semibold uppercase tracking-widest">
          <Microscope className="w-3.5 h-3.5" />
          Micrograph Analysis
        </div>
        <p role="status" className="text-xs text-amber-200 mt-2">
          The measurement tool is being rebuilt: calibrated area fraction, particle statistics and ASTM E112 intercept
          counting will be computed by a Python authority. No measurement is available in this build.
        </p>
      </div>
      <div className="p-4 rounded-xl bg-[#090e18] border border-[#162032] space-y-2">
        <input
          ref={inputRef}
          type="file"
          aria-label="Load raster micrograph"
          accept={ADVISORY_IMAGE_TYPES.join(",")}
          className="hidden"
          onChange={(e) => onFile(e.target.files?.[0])}
        />
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="px-3 py-1.5 rounded border border-[#1e2d46] bg-[#0c1322] text-xs font-mono text-slate-200 flex items-center gap-2"
        >
          <Upload className="w-3.5 h-3.5" /> Load image
        </button>
        {image && <div className="text-[11px] font-mono text-slate-400">{image.name}</div>}
        {image && (
          <div className="space-y-1">
            <img
              src={image.url}
              alt={`Loaded micrograph ${image.name}`}
              className="max-h-[420px] max-w-full object-contain cursor-crosshair"
              onClick={(e) => setPipette(readGrey(e))}
            />
            <div className="text-[11px] font-mono text-slate-400">
              {pipette ? `Pipette: pixel (${pipette.x}, ${pipette.y}) grey ${pipette.grey} (BT.601 luma)` : "Click the image to read a grey level."}
            </div>
          </div>
        )}
        {message && <div role="alert" className="text-[11px] text-rose-300">{message}</div>}
      </div>
      <MicrographAdvisoryDescription imageDataUrl={image?.url ?? null} imageKey={image?.url ?? null} />
    </div>
  );
};
