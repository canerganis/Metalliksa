// Lazy entry of the command palette chunk (App.tsx imports this module dynamically). The stylesheet is
// imported here, not in CommandPalette.tsx, so Vite loads it with the chunk (no unstyled first paint) while
// node:test can still import CommandPalette.tsx directly (node cannot load a .css module).
import '../styles/palette.css';

export { CommandPalette } from './CommandPalette';
