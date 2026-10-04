import React, { useMemo, useRef, useState } from 'react';
import { Search } from 'lucide-react';
import { AccessibleModal } from './AccessibleModal';
import { EvidenceBadge } from './sdk/EvidenceBadge';
import { MATURITY_BADGE_TITLE, MODULES, WORKSPACES, type ModuleId } from '../data/workspaces';
import {
  PALETTE_QUERY_MAX_LENGTH, commitPaletteChoice, handlePaletteInputKey, isComposingKey, rankPaletteEntries, type PaletteEffects,
} from '../utils/commandPalette';

// Command palette (Phase 9 shell, DESIGN-9 section 3). Lazy chunk opened from the header button or
// Ctrl/Cmd+K. Entries are the registry-derived navigation modules (MODULES); choosing one calls the
// same navigate() the sidebar uses. Each entry shows the module's maturity and its contract
// evidence ceiling through the shared EvidenceBadge, unchanged.

const ENTRIES = MODULES.map(module => ({
  ...module,
  workspaceLabel: WORKSPACES.find(workspace => workspace.id === module.workspace)?.label ?? module.workspace,
}));

const optionId = (id: string) => `command-palette-option-${id}`;

export function CommandPalette({ activeTab, onNavigate, onClose }: {
  readonly activeTab: ModuleId;
  readonly onNavigate: (id: string) => void;
  readonly onClose: () => void;
}) {
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const results = useMemo(() => rankPaletteEntries(ENTRIES, query), [query]);
  const current = results.length ? Math.min(active, results.length - 1) : -1;
  const activeEntry = current >= 0 ? results[current] : undefined;
  const list = useRef<HTMLUListElement>(null);

  // What Enter and click do is decided in src/utils/commandPalette.ts (tested there with these effects):
  // navigate is the shell's navigate() (the sidebar's path), then the palette closes.
  const effects: PaletteEffects = {
    navigate: onNavigate,
    close: () => {
      onClose();
      // AccessibleModal returns focus to the opener. When the opener sat in the module view that was just
      // hidden, focus would fall to <body>; move it to the main region instead.
      requestAnimationFrame(() => {
        if (!document.activeElement || document.activeElement === document.body) document.getElementById('main-content')?.focus();
      });
    },
    setActive: index => {
      setActive(index);
      document.getElementById(optionId(results[index].id))?.scrollIntoView?.({ block: 'nearest' });
    },
  };

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    const key = {
      key: event.key, altKey: event.altKey, ctrlKey: event.ctrlKey, metaKey: event.metaKey,
      isComposing: event.nativeEvent.isComposing, keyCode: event.keyCode,
    };
    if (isComposingKey(key)) return; // the IME owns Enter and the arrows while composing
    if (handlePaletteInputKey(key, results, current, effects)) event.preventDefault();
  }

  return (
    <AccessibleModal open onClose={onClose} labelledBy="command-palette-title" closeOnBackdrop lockScroll
      overlayClassName="mk-palette-overlay" panelClassName="mk-palette">
      <div className="mk-palette-head">
        <h2 id="command-palette-title" className="mk-palette-title">Go to module</h2>
        <button type="button" className="mk-palette-close" onClick={onClose}>Close <kbd aria-hidden="true">Esc</kbd></button>
      </div>
      <div className="mk-palette-field">
        <Search className="mk-palette-icon" aria-hidden="true" />
        <label htmlFor="command-palette-input" className="sr-only">Search modules by name, workspace or description</label>
        <input id="command-palette-input" type="text" role="combobox" autoFocus autoComplete="off" spellCheck={false} maxLength={PALETTE_QUERY_MAX_LENGTH}
          aria-expanded={results.length > 0} aria-controls="command-palette-listbox" aria-autocomplete="list"
          aria-activedescendant={activeEntry ? optionId(activeEntry.id) : undefined}
          aria-describedby="command-palette-hint"
          value={query} placeholder="Module, workspace or method…" className="mk-palette-input"
          onChange={event => { setQuery(event.target.value); setActive(0); if (list.current) list.current.scrollTop = 0; }} onKeyDown={onKeyDown} />
      </div>
      <p id="command-palette-hint" className="mk-palette-hint">Arrow keys, Home and End move through the results; Enter opens the module; Escape closes.</p>
      <ul ref={list} id="command-palette-listbox" role="listbox" aria-label="Modules" className="mk-palette-list">
        {results.map((entry, index) => (
          <li key={entry.id} id={optionId(entry.id)} role="option" aria-selected={index === current}
            aria-current={entry.id === activeTab ? 'page' : undefined}
            aria-labelledby={`${optionId(entry.id)}-name`} aria-describedby={`${optionId(entry.id)}-workspace ${optionId(entry.id)}-meta`}
            className="mk-palette-option" data-active={index === current ? 'true' : undefined}
            onMouseDown={event => event.preventDefault()}
            onClick={() => commitPaletteChoice(results, index, effects)}>
            <span className="mk-palette-option-main">
              <span id={`${optionId(entry.id)}-name`} className="mk-palette-option-label">{entry.label}</span>
              <span id={`${optionId(entry.id)}-workspace`} className="mk-palette-option-workspace">{entry.workspaceLabel}{entry.id === activeTab ? ' · current' : ''}</span>
            </span>
            <span id={`${optionId(entry.id)}-meta`} className="mk-palette-option-meta">
              <span title={MATURITY_BADGE_TITLE} className={`mk-scope-badge ${entry.scope === 'Preview' ? 'is-preview' : ''}`}>{entry.scope}</span>
              <EvidenceBadge moduleId={entry.id} />
            </span>
          </li>
        ))}
      </ul>
      <p role="status" className="mk-palette-count">
        {results.length ? `${results.length} of ${MODULES.length} modules` : 'No matching modules. Try a material, method or workflow name.'}
      </p>
    </AccessibleModal>
  );
}
