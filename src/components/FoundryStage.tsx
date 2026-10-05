/**
 * Foundry stage: the studio picture of a metal world being built by a laser (public/images, carried over
 * from the earlier art direction, see design-system/metalliksa/MASTER.md "Artwork provenance") brought to
 * life as a cinemagraph. Live layers sit exactly on the beam and its melt point in the picture: a
 * flickering beam, a pulsing melt bloom, scan rings spreading over the new layer, sparks, a slow camera
 * push and a light sweep. Purely decorative: no data, no numbers, not a simulation.
 *
 * No caption is shown by default (maintainer decision 2026-10-05: the picture is obviously decorative); a host
 * may pass `caption` to show one. Children (the optional WebGL spark layer) are placed inside the picture frame so they line up with it. All motion is transform and
 * opacity only and stops when `paused` is set or the user asks for reduced motion.
 * Styles: src/styles/foundry.css, imported by the host (Atrium statically, the boot screen on demand).
 */
import React from 'react';

export const FOUNDRY_ART = '/images/metalliksa-foundry-art.webp';
const SPARKS = 14;

export function FoundryStage({ className = '', caption, paused = false, sparks = false, children }: {
  className?: string; caption?: string; paused?: boolean;
  /** CSS sparks (the boot's fallback when the WebGL layer is absent). Off on long-lived pages: they cost
   *  main-thread style work every frame, and the atrium must idle cheaply (review S2). */
  sparks?: boolean; children?: React.ReactNode;
}) {
  return (
    <div className={`mk-foundry-host ${className}`}>
      <div className={`mk-foundry${paused ? ' is-paused' : ''}`}>
        <div className="f-frame">
          <img className="f-art" src={FOUNDRY_ART} alt="" aria-hidden="true" decoding="async" draggable={false} />
          <span className="f-sheen" aria-hidden="true" />
          <span className="f-beam" aria-hidden="true" />
          <span className="f-rings" aria-hidden="true"><i /><i /><i /></span>
          <span className="f-hit" aria-hidden="true" />
          {sparks && <span className="f-sparks" aria-hidden="true">
            {/* Each spark flies along its own static direction; the animation itself is the same transform for all,
                so it runs on the compositor (no per-frame style work). */}
            {Array.from({ length: SPARKS }, (_, i) => (
              <i key={i} style={{ transform: `rotate(${i * 27 - 200}deg) scale(${(0.75 + (i % 5) * 0.12).toFixed(2)})`, animationDelay: `${-i * 83}ms` } as React.CSSProperties}><b /></i>
            ))}
          </span>}
          {children}
        </div>
      </div>
      {caption && <p className="mk-foundry-caption">{caption}</p>}
    </div>
  );
}
