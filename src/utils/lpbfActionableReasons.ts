/**
 * Copy-only mapping of Python compose_verdict reasons into engineer actions.
 * Does not change scores, gates, or printability.
 */

export function toActionableHeadline(headline: string): string {
  if (/Do not print/i.test(headline)) {
    return `${headline} — change hatch, speed, power, or layer before a production build.`;
  }
  if (/Risky/i.test(headline)) {
    return `${headline} — see actions below; do not treat this as a go-build stamp.`;
  }
  if (/Printable/i.test(headline)) {
    return `${headline} — still couple EL, I₀, ΔH/hₛ, W/h, and D/t; VED is not the sole criterion.`;
  }
  return headline;
}

export function toActionableReason(line: string): string {
  // Unresolved-geometry and geometry-independent notes are shown verbatim: the LoF / balling
  // advice below would otherwise be attached to numbers Python declared unavailable.
  if (/not resolved/i.test(line) || /^Geometry-independent gate/i.test(line)) return line;
  if (/Lack of fusion/i.test(line) || (/W\/h/i.test(line) && /D\/t/i.test(line))) {
    if (/marginal/i.test(line)) {
      return `${line} Action: reduce hatch h or layer t, or raise P / lower v so W and D grow.`;
    }
    return `${line} Action: reduce hatch h (or raise P / lower v) if W/h is low; reduce layer t if D/t is low.`;
  }
  if (/Keyhole/i.test(line) || (/ΔH/i.test(line) && /King/i.test(line))) {
    return `${line} Action: lower laser power or raise scan speed / spot size to drop I₀ and ΔH/hₛ.`;
  }
  if (/balling/i.test(line) || /Plateau/i.test(line)) {
    return `${line} Action: lower scan speed or raise power to shorten melt-pool L/W.`;
  }
  if (/Recoater/i.test(line)) {
    return `${line} Action: recoater here is a residual-stress heuristic, not a blade simulation — lower P, raise preheat, or change scan strategy; qualify on coupons.`;
  }
  if (/distortion/i.test(line)) {
    return `${line} Action: reduce energy input or raise preheat. This index is inherent-strain screening, not Goldak FEA.`;
  }
  if (/literature box/i.test(line) || /P–v is outside/i.test(line)) {
    return `${line} Action: click a conduction cell so P and v sit inside the alloy literature window.`;
  }
  return line;
}

export function mapActionableReasons(reasons: string[]): string[] {
  return reasons.map(toActionableReason);
}

export function modelHonestyLine(modelId?: string | null): string {
  const id = modelId || "rosenthal-screening-v1";
  return `${id} — not Goldak FEA; recoater is a stress heuristic; PSD/O₂ not in solver. VED is not the sole criterion.`;
}
