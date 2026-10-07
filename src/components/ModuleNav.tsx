import React, { useState } from 'react';
import { CORE_FLOW, MODULES, WORKSPACES, isCoreModule, type ModuleId } from '../data/workspaces';
import { rovingIndex } from '../utils/rovingFocus';

/**
 * The single Tab stop: the entry focused last while `activeTab` was active, else the active module,
 * else the first visible module. Workspace headings use the key "ws:<workspace id>", the Labs toggle "labs".
 */
export function navTabStop(modules: { id: string; workspace: string }[], focus: { key: string; tab: string }, activeTab: string): string | undefined {
  const shown = (key: string) => key === 'labs' || modules.some(m => m.id === key || 'ws:' + m.workspace === key);
  return [focus.tab === activeTab ? focus.key : '', activeTab].find(shown) ?? modules[0]?.id;
}

/** Clears the remembered entry once the active module differs from the one it was focused under. */
export function syncNavFocus(focus: { key: string; tab: string }, activeTab: string): { key: string; tab: string } {
  return focus.tab === activeTab ? focus : { key: '', tab: activeTab };
}

export const LABS_OPEN_KEY = 'metalliksa.nav.labsOpen';
function readLabsOpen(): boolean {
  try { return window.localStorage.getItem(LABS_OPEN_KEY) === '1'; } catch { return false; }
}
function writeLabsOpen(open: boolean): void {
  try { window.localStorage.setItem(LABS_OPEN_KEY, open ? '1' : '0'); } catch { /* storage unavailable: the choice lasts for this session only */ }
}

/**
 * Sidebar module navigation as one Tab stop (roving tabindex). Its own component so that moving focus
 * between entries re-renders only the navigation, not App and the mounted module views.
 */
export function ModuleNav({ home = false, modules, activeTab, activeWorkspace, onNavigate }: {
  home?: boolean; modules: (typeof MODULES)[number][]; activeTab: ModuleId; activeWorkspace: string; onNavigate: (id: string) => void;
}) {
  // The remembered entry is tied to the active module it was focused under: any navigation (hash change,
  // back button, Next link, navigate event) moves the Tab stop back to the aria-current entry.
  const [focus, setFocus] = useState<{ key: string; tab: string }>({ key: '', tab: activeTab });
  // Forget the remembered entry as soon as the active module changes, so going A -> B -> A (back button)
  // does not revive an entry remembered under A. Render-time adjustment: re-renders only this component.
  const synced = syncNavFocus(focus, activeTab);
  if (synced !== focus) setFocus(synced);
  // Labs are expanded when the active module is a lab, when the list is filtered, or when the user opened them.
  const [userLabsOpen, setUserLabsOpen] = useState(readLabsOpen);
  const coreEntries = CORE_FLOW.map((step, index) => ({ step, index, module: modules.find(m => m.id === step.id) })).filter(entry => entry.module);
  const labEntries = modules.filter(m => !isCoreModule(m.id));
  const forcedOpen = !isCoreModule(activeTab) || modules.length !== MODULES.length;
  const labsOpen = forcedOpen || userLabsOpen;
  const visible = labsOpen ? modules : modules.filter(m => isCoreModule(m.id));
  const stop = navTabStop(visible, synced, activeTab);
  function toggleLabs() {
    if (forcedOpen) return;
    setUserLabsOpen(!userLabsOpen);
    writeLabsOpen(!userLabsOpen);
  }
  const item = (key: string, described = '') => ({ tabIndex: key === stop ? 0 : -1, onFocus: () => setFocus({ key, tab: activeTab }), 'aria-describedby': 'module-nav-hint' + described });
  function onKey(event: React.KeyboardEvent<HTMLElement>) {
    if (event.ctrlKey || event.altKey || event.metaKey) return;
    // Every button in the navigation is a navigation entry (workspace headings and modules).
    const items = Array.from(event.currentTarget.querySelectorAll('button'));
    const next = rovingIndex(items.length, items.indexOf(document.activeElement as HTMLButtonElement), event.key);
    if (next === null) return;
    event.preventDefault();
    items[next].focus();
  }
  // Labs workspace headings are numbered by a CSS counter (.mk-sidebar / .mk-nav-ws in src/index.css).
  const entryButton = (module: (typeof MODULES)[number], number?: number) => (
    <button key={module.id} {...item(module.id, ' nav-desc-' + module.id)} aria-current={!home && activeTab === module.id ? 'page' : undefined} title={module.description} onClick={() => onNavigate(module.id)} className={`mk-nav-item${number ? ' mk-nav-core-item' : ''}${!home && activeTab === module.id ? ' is-active' : ''}`}>
      {number && <span className="mk-nav-num" aria-hidden="true">{number}</span>}{module.label}
    </button>
  );
  return <nav aria-label="Engineering workspaces" onKeyDown={onKey}>
    <p id="module-nav-hint" className="mk-sr-only">Arrow keys move between modules.</p>
    {coreEntries.length > 0 && <div className="mk-nav-core mb-6">
      <p className="mk-nav-core-head">Core - LPBF screening flow</p>
      <div className="space-y-0.5">{coreEntries.map(({ index, module }) => entryButton(module!, index + 1))}</div>
    </div>}
    {labEntries.length > 0 && <button type="button" {...item('labs')} aria-expanded={labsOpen} aria-controls="module-nav-labs" onClick={toggleLabs} className="mk-nav-labs-toggle">
      <span className="mk-nav-labs-caret" aria-hidden="true">{labsOpen ? '▾' : '▸'}</span>Labs ({labEntries.length})
    </button>}
    <div id="module-nav-labs" hidden={!labsOpen || !labEntries.length} className="mk-nav-labs">
      {labsOpen && WORKSPACES.map(workspace => {
        const entries = labEntries.filter(m => m.workspace === workspace.id);
        if (!entries.length) return null;
        return <div key={workspace.id} className="mb-6"><button {...item('ws:' + workspace.id)} onClick={() => onNavigate(workspace.defaultModule)} className={`mk-nav-ws${workspace.id === activeWorkspace ? ' is-current' : ''}`}>{workspace.label}</button><div className="space-y-0.5">{entries.map(module => entryButton(module))}</div></div>;
      })}
    </div>
    <div hidden>{modules.map(module => <span key={module.id} id={'nav-desc-' + module.id}>{module.description}</span>)}</div>
    {!modules.length && <p role="status" className="text-sm text-slate-400">No matching modules. Try a material, method or workflow name.</p>}
  </nav>;
}
