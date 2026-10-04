import React, { useEffect, useRef, useState } from "react";
import { AlertTriangle, Check, Copy, MessageSquareText } from "lucide-react";

/** Raster formats the server-side vision route accepts (routes/copilot.ts diagnose-micrograph). */
export const ADVISORY_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"] as const;

interface Props {
  /** data: URL of the loaded raster image, or null when nothing is loaded. */
  imageDataUrl: string | null;
  /** Changes whenever the loaded image changes; a description of an older image is discarded. */
  imageKey: string | null;
}

/**
 * Optional language-model description of an uploaded raster micrograph (POST /api/metallurgy/diagnose-micrograph).
 * Advisory text only: it carries no measurement, no phase identification claim and no conformance statement. The
 * measurements of this module come from python/micrograph_measure.py, never from this text.
 */
export const MicrographAdvisoryDescription: React.FC<Props> = ({ imageDataUrl, imageKey }) => {
  const [note, setNote] = useState("");
  const [running, setRunning] = useState(false);
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const generation = useRef(0);

  // A new image invalidates any description of the previous one.
  useEffect(() => {
    generation.current += 1;
    setText(null);
    setError(null);
    setRunning(false);
  }, [imageKey]);

  const mime = imageDataUrl?.match(/^data:([^;]+);base64,/)?.[1] ?? null;
  const supported = mime !== null && (ADVISORY_IMAGE_TYPES as readonly string[]).includes(mime);

  const run = async () => {
    if (!imageDataUrl || !supported) return;
    const ticket = ++generation.current;
    setRunning(true);
    setError(null);
    setText(null);
    try {
      const prompt =
        "Describe visible microstructure features (grain boundaries, second-phase particles, pores, cracks, " +
        "etch artefacts). State uncertainty. Do not report numbers, phase fractions, grain size, hardness, " +
        "strength or conformance." + (note.trim() ? ` Operator context: ${note.trim()}` : "");
      const res = await fetch("/api/metallurgy/diagnose-micrograph", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ imageBase64: imageDataUrl, prompt }),
      });
      const raw = await res.text();
      let data: { diagnosis?: string; error?: string } = {};
      try {
        data = JSON.parse(raw);
      } catch {
        throw new Error(res.ok ? "Invalid response from server." : `Server error (${res.status}).`);
      }
      if (!res.ok) throw new Error(data.error || `Request failed (${res.status}).`);
      if (ticket === generation.current) setText(data.diagnosis ?? "");
    } catch (err) {
      if (ticket === generation.current) setError(err instanceof Error ? err.message : "Description request failed.");
    } finally {
      if (ticket === generation.current) setRunning(false);
    }
  };

  return (
    <section className="p-4 rounded-xl bg-[#090e18] border border-[#162032] space-y-3" aria-labelledby="micrograph-advisory-title">
      <div className="flex items-center gap-2">
        <MessageSquareText className="w-4 h-4 text-slate-400" />
        <h3 id="micrograph-advisory-title" className="text-xs font-mono font-bold text-slate-200">
          Optional language-model description (advisory text, no measurements)
        </h3>
      </div>
      <p className="text-[11px] text-slate-400">
        Sends the loaded raster image to the server&apos;s language-model route (needs OPENAI_API_KEY; disabled when air-gapped).
        The text is not a measurement and is not used by any calculation.
      </p>
      <label className="block text-[11px] text-slate-400">
        Context note for the description (optional)
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value.slice(0, 500))}
          rows={2}
          className="mt-1 w-full px-2 py-1 bg-[#0c1322] border border-[#162032] rounded text-white font-mono text-xs focus:outline-none focus:border-sky-400"
        />
      </label>
      <button
        type="button"
        onClick={run}
        disabled={running || !supported}
        className="px-3 py-1.5 rounded border border-[#1e2d46] bg-[#0c1322] text-xs font-mono text-slate-200 hover:bg-white/5 disabled:opacity-50"
      >
        {running ? "Requesting description..." : "Describe loaded image"}
      </button>
      {!imageDataUrl && <p className="text-[11px] text-slate-500">Load a PNG, JPEG, WebP or GIF image first.</p>}
      {imageDataUrl && !supported && (
        <p className="text-[11px] text-slate-500">This image type is not accepted by the description route.</p>
      )}
      {running && (
        <div role="status" className="text-[11px] text-slate-400">
          Waiting for the server response. Progress is not reported.
        </div>
      )}
      {error && (
        <div role="alert" className="p-2 bg-rose-950/40 border border-rose-800/80 rounded text-rose-200 text-xs flex items-start gap-2">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}
      {text !== null && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase tracking-widest text-amber-300">Advisory text, not a measurement</span>
            <button
              type="button"
              onClick={() => {
                void navigator.clipboard?.writeText(`Advisory language-model description (not a measurement):\n${text}`);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}
              className="px-2 py-0.5 rounded border border-[#1e2d46] text-[11px] font-mono text-slate-300 flex items-center gap-1"
            >
              {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <div className="text-xs text-slate-200 whitespace-pre-line">{text}</div>
        </div>
      )}
    </section>
  );
};
