/**
 * Atrium: the start page shown when the app opens without a module link (or via "Overview").
 * Lazy chunk with its own stylesheet. Everything it states comes from the bundled module registry
 * (labels, descriptions, maturity) or from the engine status the shell already fetched; the artwork is
 * decorative (aria-hidden), carries no numbers and is not a simulation.
 */
import React, { useEffect, useState } from 'react';
import { ArrowRight, Pause, Play, Search } from 'lucide-react';
import { MATURITY_BADGE_TITLE, MODULES, WORKSPACES, type ModuleId, type ModuleScope } from '../data/workspaces';
import type { PythonEngineStatus } from '../services/pythonComputationService';
import { FoundryStage } from './FoundryStage';
import '../styles/foundry.css';
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
  const motionAllowed = useMotionAllowed();
  // A page-level pause for the ambient motion (review Sol S6): stops the picture, glints, tilt and light.
  const [paused, setPaused] = useState(false);
  const motion = motionAllowed && !paused;
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
  // Ambient light follows the pointer across the page (visual only).
  const spot = (event: React.PointerEvent<HTMLElement>) => {
    if (!motion || event.pointerType !== 'mouse') return;
    const box = event.currentTarget.getBoundingClientRect();
    event.currentTarget.style.setProperty('--mx', `${event.clientX - box.left}px`);
    event.currentTarget.style.setProperty('--my', `${event.clientY - box.top}px`);
  };
  const untilt = (event: React.PointerEvent<HTMLElement>) => {
    event.currentTarget.style.removeProperty('--rx');
    event.currentTarget.style.removeProperty('--ry');
  };

  return (
    <section className="mk-atrium" aria-labelledby="atrium-title" data-motion={String(motion)} onPointerMove={spot}>
      <div className="mk-at-hero">
        <FoundryStage className="mk-at-art" paused={!motion} />
        <div className="mk-at-copy">
          <p className="mk-at-kicker">Metalliksa · Local research workstation · Laser powder-bed fusion</p>
          <h2 id="atrium-title" className="mk-at-title"><span>Built by light,</span> <span>layer by layer.</span></h2>
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
          {motionAllowed && (
            <button type="button" className="mk-at-motion" aria-pressed={paused} onClick={() => setPaused(p => !p)}>
              {paused ? <Play className="h-3.5 w-3.5" aria-hidden="true" /> : <Pause className="h-3.5 w-3.5" aria-hidden="true" />}
              {paused ? 'Play ambient motion' : 'Pause ambient motion'}
            </button>
          )}
        </div>
      </div>

      <div className="mk-at-section">
        <p className="mk-at-section-label"><span>{two(WORKSPACES.length)}</span>Workspaces</p>
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
