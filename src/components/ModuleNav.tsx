import React, { useState } from 'react';
import { MODULES, WORKSPACES, type ModuleId } from '../data/workspaces';
import { rovingIndex } from '../utils/rovingFocus';

/**
 * The single Tab stop: the entry focused last while `activeTab` was active, else the active module,
 * else the first visible module. Workspace headings use the key "ws:<workspace id>".
 */
export function navTabStop(modules: { id: string; workspace: string }[], focus: { key: string; tab: string }, activeTab: string): string | undefined {
  const shown = (key: string) => modules.some(m => m.id === key || 'ws:' + m.workspace === key);
  return [focus.tab === activeTab ? focus.key : '', activeTab].find(shown) ?? modules[0]?.id;
}

/** Clears the remembered entry once the active module differs from the one it was focused under. */
export function syncNavFocus(focus: { key: string; tab: string }, activeTab: string): { key: string; tab: string } {
  return focus.tab === activeTab ? focus : { key: '', tab: activeTab };
}

/**
 * Sidebar module navigation as one Tab stop (roving tabindex). Its own component so that moving focus
 * between entries re-renders only the navigation, not App and the mounted module views.
 */
export function ModuleNav({ modules, activeTab, activeWorkspace, onNavigate }: {
  modules: (typeof MODULES)[number][]; activeTab: ModuleId; activeWorkspace: string; onNavigate: (id: string) => void;
}) {
  // The remembered entry is tied to the active module it was focused under: any navigation (hash change,
  // back button, Next link, navigate event) moves the Tab stop back to the aria-current entry.
  const [focus, setFocus] = useState<{ key: string; tab: string }>({ key: '', tab: activeTab });
  // Forget the remembered entry as soon as the active module changes, so going A -> B -> A (back button)
  // does not revive an entry remembered under A. Render-time adjustment: re-renders only this component.
  const synced = syncNavFocus(focus, activeTab);
  if (synced !== focus) setFocus(synced);
  const stop = navTabStop(modules, synced, activeTab);
  // Module entries are described by the hint and by their own description (hidden text below), so the
  // description a mouse user gets from `title` is not replaced by the hint for screen-reader users.
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
  // Workspace headings are numbered by a CSS counter (.mk-sidebar / .mk-nav-ws in src/index.css).
  return <nav aria-label="Engineering workspaces" onKeyDown={onKey}>
    <p id="module-nav-hint" className="mk-sr-only">Arrow keys move between modules.</p>
    {WORKSPACES.map(workspace => {
      const entries = modules.filter(m => m.workspace === workspace.id);
      if (!entries.length) return null;
      return <div key={workspace.id} className="mb-6"><button {...item('ws:' + workspace.id)} onClick={() => onNavigate(workspace.defaultModule)} className={`mk-nav-ws${workspace.id === activeWorkspace ? ' is-current' : ''}`}>{workspace.label}</button><div className="space-y-0.5">{entries.map(module => <button key={module.id} {...item(module.id, ' nav-desc-' + module.id)} aria-current={activeTab === module.id ? 'page' : undefined} title={module.description} onClick={() => onNavigate(module.id)} className={`mk-nav-item${activeTab === module.id ? ' is-active' : ''}`}>{module.label}</button>)}</div></div>;
    })}
    <div hidden>{modules.map(module => <span key={module.id} id={'nav-desc-' + module.id}>{module.description}</span>)}</div>
    {!modules.length && <p role="status" className="text-sm text-slate-400">No matching modules. Try a material, method or workflow name.</p>}
  </nav>;
}
