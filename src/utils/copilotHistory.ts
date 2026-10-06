export interface HistoryMessage {
  id: string;
  role: string;
  content: string;
}

// UI-authored bubbles (canned welcome / reset notice, client-side error messages) were never produced by the model,
// so they must not be sent back as prior assistant turns.
const NON_MODEL_ID_PREFIXES = ["welcome-", "error-"];

export function buildApiHistory(messages: readonly HistoryMessage[]): { role: string; content: string }[] {
  return messages
    .filter((m) => !NON_MODEL_ID_PREFIXES.some((prefix) => m.id.startsWith(prefix)))
    .map((m) => ({ role: m.role, content: m.content }));
}
