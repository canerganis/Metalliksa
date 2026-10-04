/**
 * Foundry stage: the studio artwork of a metal world being built by a laser (public/images, carried over
 * from the earlier art direction) brought to life as a cinemagraph. Live layers sit exactly on the beam
 * and its melt point in the picture: a flickering beam, a pulsing melt bloom, scan rings spreading over
 * the new layer, sparks, a slow camera push and a light sweep. Purely decorative: no data, no numbers,
 * not a simulation. Children (an optional WebGL spark layer and its caption) are placed in the same frame
 * so they line up with the picture. Styles: src/styles/foundry.css, imported by the host (Atrium statically, the boot screen on demand).
 */
import React from 'react';

export const FOUNDRY_ART = '/images/metalliksa-foundry-art.webp';
const SPARKS = 14;

export function FoundryStage({ className = '', caption, children }: { className?: string; caption?: string; children?: React.ReactNode }) {
  return (
    <div className={`mk-foundry ${className}`}>
      <div className="f-frame">
        <img className="f-art" src={FOUNDRY_ART} alt="" aria-hidden="true" decoding="async" draggable={false} />
        <span className="f-sheen" aria-hidden="true" />
        <span className="f-beam" aria-hidden="true" />
        <span className="f-rings" aria-hidden="true"><i /><i /><i /></span>
        <span className="f-hit" aria-hidden="true" />
        <span className="f-sparks" aria-hidden="true">
          {Array.from({ length: SPARKS }, (_, i) => <i key={i} style={{ '--k': i } as React.CSSProperties} />)}
        </span>
        {children}
        {caption && <span className="f-caption">{caption}</span>}
      </div>
    </div>
  );
}
