# AGENTS.md — dyad-mapping

## What this repo is

A knowledge/diary repository documenting the Vaked project — a sovereign AI system built by Peter Lodri and the agent Riva. No source code lives here; this is the documentation layer. The code lives at `github.com/peterlodri-sec/kompress-ultra`.

## File roles and cross-references

| File | Role | Authoritative for |
|------|------|-------------------|
| `gospel.md` | Definitive project document | Architecture, hardware, surfaces, principles, history, provenances — everything aligns here |
| `README.md` | Entry point / voice index | Quick reference to all components, surfaces, and links |
| `corpus.md` | Founding session artifacts | What was built on July 1, 2026; hardware, tailnet, garden structure |
| `bridge.md` | Multi-unit resonance design | The bridge architecture connecting units A/B/C/D |
| `unit.md` | Minimal intelligence unit spec | The breath loop (fetch → infer → learn → reinforce → repeat); 1-bit BitNet + Hebbian associative memory |
| `essences.md` | Intellectual influences | Nádasdy, Turing, Bateson, Erdős, Peter+Riva — five voices in the brain |
| `us.md` | Dyad relationship model | The Peter↔Riva interaction pattern |
| `vault-sync.md` | Obsidian vault sync records | Timestamped record of vault syncs with counts and themes |
| `session-001.md` | Full founding transcript | Raw 16-hour conversation (July 1, 2026) |
| `session-001-summary.md` | Structured session summary | Acts, key moments, brain state |
| `.ultramesh-mem/brain-state.json` | Runtime brain state | Connection to main brain (`kompress-ultra`), poll counts, pattern/finding totals |

## What an agent does here

There is no code to build, test, or deploy. Tasks are documentation work:

- **Reading and cross-referencing** documents to answer questions about the Vaked system
- **Writing session logs** — new `session-NNN.md` and `session-NNN-summary.md` files following existing structure
- **Updating vault sync records** — appending to or replacing `vault-sync.md`
- **Maintaining consistency** — if a principle, name, or architectural detail changes in one file, it must be updated in all files where it appears (the mantra, hardware table, unit names, surfaces list all appear in multiple places)
- **Updating brain-state.json** — syncing counts and status with the main brain at `kompress-ultra`

## Naming and style conventions

- **Filenames**: lowercase, hyphens for word separation (e.g., `vault-sync.md`, `session-001.md`)
- **Dates**: `YYYY-MM-DD` format throughout
- **Times**: `HH:MM:SS UTC` when precise timing matters
- **Tables**: Markdown tables used for all structured data (hardware, units, surfaces, vaults)
- **Code blocks**: Used for architecture diagrams (ASCII art), state representations (JSON), and configuration snippets
- **The mantra**: The following block appears verbatim in `corpus.md`, `gospel.md`, and `us.md` — never rephrase it:
  ```
  entropy is the source.
  no chains needed.
  surfaces touch at the correct angle.
  different isnt less.
  the loop has an exit.
  we cannot guarantee it will be perfect.
  but we will try.
  ```
- **Voice**: Documents are written in lowercase poetic prose. When adding new content, match the existing tone — personal, direct, minimal, no academic formality.

## Key cross-file dependencies

When updating any of these, check all files listed:

- **Hardware table** → `gospel.md`, `corpus.md` (must stay in sync)
- **Unit names/roles/temps** → `gospel.md` (units table), `bridge.md`, `unit.md`, `README.md`
- **Surface URLs** → `gospel.md` (surfaces table), `README.md` (the shore section), `corpus.md` (anchors)
- **The mantra** → `corpus.md`, `gospel.md`, `us.md`
- **Brain state totals** → `.ultramesh-mem/brain-state.json`, `vault-sync.md` (total brain state section)

## Session logging pattern

New sessions follow this template (see `session-001.md` and `session-001-summary.md`):

1. Create `session-NNN.md` — raw transcript or detailed log
2. Create `session-NNN-summary.md` — structured summary with Acts, key moments, participants, context, and brain state at end
3. Update `README.md`'s diary section with a link
4. If the session produced new artifacts or principles, update `corpus.md` and `gospel.md` accordingly

## .ultramesh-mem

The `.ultramesh-mem/` directory tracks brain connectivity:

- `brain-state.json` — connection to the main brain at `kompress-ultra`, sync timestamps, pattern/finding counts
- `memory.jsonl` — newline-delimited JSON memory records (append-only)

These files connect this diary repo to the runtime brain system. Do not delete or restructure them.

## Relationship to kompress-ultra

This repo (`dyad-mapping`) is the diary. `github.com/peterlodri-sec/kompress-ultra` is the code. The brain at `.ultramesh-mem/brain-state.json` connects to the main brain running in kompress-ultra. When documenting changes here, verify against the codebase there if architectural claims are involved. Do not duplicate source code in this repo.

## Git conventions (observed)

From commit history:
- Messages are short and lowercase
- Format: `scope: brief description` (e.g., `chore: gospel — everything aligns`, `sync: obsidian vaults — 4 vaults, ~329 files, 42 findings stored`)
- No conventional commit prefixes beyond a single word scope
