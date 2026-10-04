/**
 * Atrium: the start page shown when the app opens without a module link (or via "Overview").
 * Lazy chunk with its own stylesheet. Everything it states comes from the bundled module registry
 * (labels, descriptions, maturity) or from the engine status the shell already fetched; the artwork is
 * decorative (aria-hidden), carries no numbers and is not a simulation.
 */
import React, { useEffect, useState } from 'react';
import { ArrowRight, Search } from 'lucide-react';
import { MATURITY_BADGE_TITLE, MODULES, WORKSPACES, type ModuleId, type ModuleScope } from '../data/workspaces';
import type { PythonEngineStatus } from '../services/pythonComputationService';
import '../styles/atrium.css';

const SCOPES: ModuleScope[] = ['Production', 'Research', 'Preview', 'Unresolved'];
const two = (n: number) => String(n).padStart(2, '0');

function useMotionAllowed(): boolean {
  const query = typeof window === 'undefined' || !window.matchMedia ? null : window.matchMedia('(prefers-reduced-motion: reduce)');
  const [allowed, setAllowed] = useState(() => !query?.matches);
  useEffect(() => {
    if (!query) return undefined;
    const onChange = () => setAllowed(!query.matches);
    query.addEventListener('change', onChange);
    return () => query.removeEventListener('change', onChange);
  }, [query]);
  return allowed;
}

// Isometric build plate: rhombus around (210, y) with half-width 150 and half-height 75.
const plate = (y: number) => `60,${y} 210,${y - 75} 360,${y} 210,${y + 75}`;
const HATCH = 22;
const TOP = 196;
const hatch = Array.from({ length: HATCH }, (_, i) => {
  const t = (i + 0.5) / HATCH;
  const a = [60 + 150 * t, TOP - 75 * t];
  const b = [210 + 150 * t, TOP + 75 - 75 * t];
  return i % 2 ? [b, a] : [a, b];
});
const scanPath = 'M' + hatch.map(([a, b]) => `${a[0].toFixed(1)} ${a[1].toFixed(1)} L${b[0].toFixed(1)} ${b[1].toFixed(1)}`).join(' L');
const CYCLE_S = 6.4;

/** Decorative build chamber: stacked layers, a hatch being re-scanned, a beam, orbit rings. */
function BuildChamber({ motion }: { motion: boolean }) {
  return (
    <svg className="mk-at-art" viewBox="0 0 420 420" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="mk-at-beam" gradientUnits="userSpaceOnUse" x1="0" x2="0" y1="-200" y2="0">
          <stop offset="0" stopColor="currentColor" stopOpacity="0" />
          <stop offset="1" stopColor="currentColor" stopOpacity="1" />
        </linearGradient>
        <clipPath id="mk-at-top"><polygon points={plate(TOP)} /></clipPath>
      </defs>
      <ellipse className="a-orbit a-orbit-1" cx="210" cy="250" rx="196" ry="70" />
      <ellipse className="a-orbit a-orbit-2" cx="210" cy="250" rx="170" ry="112" transform="rotate(-14 210 250)" />
      {[316, 296, 276, 256, 236, 216].map((y, i) => <polygon key={y} className="a-layer" style={{ opacity: 0.35 + i * 0.1 }} points={plate(y)} />)}
      <polygon className="a-side" points={`60,${TOP} 210,${TOP + 75} 210,${TOP + 84} 60,${TOP + 9}`} />
      <polygon className="a-side a-side-r" points={`210,${TOP + 75} 360,${TOP} 360,${TOP + 9} 210,${TOP + 84}`} />
      <polygon className="a-layer a-top" points={plate(TOP)} />
      <g clipPath="url(#mk-at-top)">
        {hatch.map(([a, b], i) => (
          <line key={i} className="a-hatch" x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} pathLength="100"
            style={{ animationDelay: `${(i * CYCLE_S) / HATCH}s` } as React.CSSProperties} />
        ))}
      </g>
      {/* Without motion the head rests on the middle of the plate. */}
      <g className="a-head" transform={motion ? undefined : `translate(${hatch[8][0][0]} ${hatch[8][0][1]})`}>
        <line className="a-beam" x1="0" y1="-200" x2="0" y2="0" stroke="url(#mk-at-beam)" />
        <circle className="a-spot-glow" r="9" />
        <circle className="a-spot" r="2.6" />
        {motion && <animateMotion dur={`${CYCLE_S}s`} repeatCount="indefinite" path={scanPath} />}
      </g>
    </svg>
  );
}

/** Small line motif per workspace (decorative). */
function Motif({ id }: { id: string }) {
  if (id === 'lpbf') return <svg className="mk-at-motif" viewBox="0 0 120 120" aria-hidden="true">{Array.from({ length: 9 }, (_, i) => <line key={i} x1={20} x2={100} y1={24 + i * 9} y2={24 + i * 9} />)}<circle className="m-hot" cx="74" cy="60" r="3.5" /></svg>;
  if (id === 'materials') return <svg className="mk-at-motif" viewBox="0 0 120 120" aria-hidden="true"><path d="M30 40 60 25 90 40 90 80 60 95 30 80Z M30 40 60 55 90 40 M60 55 60 95" />{[[30, 40], [60, 25], [90, 40], [90, 80], [60, 95], [30, 80], [60, 55]].map(([x, y]) => <circle key={`${x}-${y}`} cx={x} cy={y} r="3" />)}<circle className="m-hot" cx="60" cy="60" r="3.5" /></svg>;
  if (id === 'evidence') return <svg className="mk-at-motif" viewBox="0 0 120 120" aria-hidden="true"><rect x="30" y="22" width="52" height="68" rx="3" /><rect x="40" y="30" width="52" height="68" rx="3" />{[44, 52, 60, 68].map((y) => <line key={y} x1={48} x2={84} y1={y} y2={y} />)}<circle cx="80" cy="86" r="10" /><circle className="m-hot" cx="80" cy="86" r="3.5" /></svg>;
  return <svg className="mk-at-motif" viewBox="0 0 120 120" aria-hidden="true"><path d="M30 34 60 60 92 30 M60 60 40 92 M60 60 90 86" />{[[30, 34], [92, 30], [40, 92], [90, 86]].map(([x, y]) => <circle key={`${x}-${y}`} cx={x} cy={y} r="5" />)}<circle className="m-hot" cx="60" cy="60" r="4" /></svg>;
}

export interface AtriumProps {
  continueId: ModuleId;
  engine: PythonEngineStatus | null;
  engineChecking: boolean;
  shortcutLabel: string;
  onNavigate: (id: string) => void;
  onSearch: () => void;
}

export function Atrium({ continueId, engine, engineChecking, shortcutLabel, onNavigate, onSearch }: AtriumProps) {
  const motion = useMotionAllowed();
  const resume = MODULES.find((m) => m.id === continueId) ?? MODULES[0];
  const maturity = SCOPES.map((scope) => [scope, MODULES.filter((m) => m.scope === scope).length] as const).filter(([, n]) => n > 0);
  const engineText = engineChecking && !engine ? 'checking' : engine?.online ? 'online' : 'unavailable';
  // Pointer tilt for the workspace plates (motion allowed only); a pure visual transform.
  const tilt = (event: React.PointerEvent<HTMLElement>) => {
    if (!motion || event.pointerType !== 'mouse') return;
    const box = event.currentTarget.getBoundingClientRect();
    event.currentTarget.style.setProperty('--rx', `${((event.clientY - box.top) / box.height - 0.5) * -5}deg`);
    event.currentTarget.style.setProperty('--ry', `${((event.clientX - box.left) / box.width - 0.5) * 7}deg`);
  };
  const untilt = (event: React.PointerEvent<HTMLElement>) => {
    event.currentTarget.style.removeProperty('--rx');
    event.currentTarget.style.removeProperty('--ry');
  };

  return (
    <section className="mk-atrium" aria-labelledby="atrium-title" data-motion={String(motion)}>
      <div className="mk-at-hero">
        <div className="mk-at-copy">
          <p className="mk-at-kicker">Local research workstation · Laser powder-bed fusion</p>
          <h2 id="atrium-title" className="mk-at-title">Metalliksa</h2>
          <p className="mk-at-lede">LPBF engineering, materials intelligence and evidence &amp; qualification. Traceable thermal research, material characterization and reviewed literature evidence.</p>
          <div className="mk-at-actions">
            <button type="button" className="mk-at-cta" onClick={() => onNavigate(resume.id)}>
              <span className="mk-at-cta-dot" aria-hidden="true" />Continue · {resume.label}<ArrowRight className="h-4 w-4" aria-hidden="true" />
            </button>
            <button type="button" className="mk-at-ghost" onClick={onSearch} aria-haspopup="dialog">
              <Search className="h-4 w-4" aria-hidden="true" />Search modules<kbd aria-hidden="true">{shortcutLabel}</kbd>
            </button>
          </div>
          <dl className="mk-at-readout">
            <div><dt>Engine</dt><dd data-tone={engine?.online ? 'ok' : engineText === 'checking' ? 'neutral' : 'fail'}>{engineText}</dd></div>
            <div><dt>Modules</dt><dd>{MODULES.length} registered</dd></div>
            <div title={MATURITY_BADGE_TITLE}><dt>Maturity</dt><dd>{maturity.map(([scope, n]) => `${n} ${scope.toLowerCase()}`).join(' · ')}</dd></div>
          </dl>
          <p className="mk-at-note">Maturity describes a module, not a validation claim for any result.</p>
        </div>
        <BuildChamber motion={motion} />
      </div>

      <div className="mk-at-section">
        <p className="mk-at-section-label"><span>02</span>Select a workspace · {WORKSPACES.length}</p>
      </div>
      <div className="mk-at-grid">
        {WORKSPACES.map((workspace, index) => {
          const entries = MODULES.filter((m) => m.workspace === workspace.id);
          const shown = entries.slice(0, 4);
          return (
            <article key={workspace.id} className="mk-at-card" onPointerMove={tilt} onPointerLeave={untilt}>
              <div className="mk-at-card-top">
                <span className="mk-at-code">WS·{two(index + 1)}</span>
                <span className="mk-at-count">{two(entries.length)} modules</span>
              </div>
              <Motif id={workspace.id} />
              <h3 className="mk-at-card-title">{workspace.label}</h3>
              <p className="mk-at-card-text">{workspace.description}</p>
              <ul className="mk-at-mods" aria-label={`${workspace.label} modules`}>
                {shown.map((m) => (
                  <li key={m.id}><button type="button" onClick={() => onNavigate(m.id)}>{m.label}<span className="mk-at-scope" title={MATURITY_BADGE_TITLE}>{m.scope}</span></button></li>
                ))}
                {entries.length > shown.length && <li className="mk-at-more">+{entries.length - shown.length} more in this workspace</li>}
              </ul>
              <button type="button" className="mk-at-enter" onClick={() => onNavigate(workspace.defaultModule)}>
                Enter workspace<ArrowRight className="h-4 w-4" aria-hidden="true" />
              </button>
            </article>
          );
        })}
      </div>
    </section>
  );
}
