---
name: graft
description: Optional command reference for using a repository Graft graph when it is available and useful.
---

# Graft repository graph

Graft can index a repository into Markdown context nodes and symbol-reference edges. It is an optional way to navigate code; use direct source/docs, ordinary search, or other tools when they fit better. A task never requires Graft.

## Commands

- `graft map` — orient in an unfamiliar repository or area.
- `graft ask "<question>" --source` — retrieve ranked context with code spans. Results are top-N, not exhaustive. Add `--full` for longer definitions, `--in <path>` to scope, or `-n N` to change the result limit.
- `graft grep "<literal>"` — find all indexed matches, grouped by symbol. Add `--fixed`, `-i`, or `--in <path>` as needed. Use regular search for files Graft does not index.
- `graft skeleton <file>` — view definitions and signatures in one file.
- `graft callers <symbol>` — inspect symbol references; `--direction out` shows dependencies and `--depth N` or `--depth all` expands the traversal.
- `graft build` refreshes the graph; `graft check` checks whether it is current.

## Choosing a query

Use `ask` for a focused concept or location, `grep` for exhaustive text matches, `skeleton` for a file overview, and `callers` for symbol relationships. Check cited file spans in source when a result is incomplete or a claim needs broader evidence. `graft/INDEX.md` lists graph nodes. Direct source review remains valid.

Some graph Markdown can lag behind source edits. Prefer fresh command output; rebuild when the graph itself needs updating.
