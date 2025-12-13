# Character Creation Module (v2)

This repository treats every character as a deterministic, file-driven artifact. Character creation is not a conversational suggestion: it is a reproducible workflow that consumes entropy, validates schemas, and leaves behind a complete session folder that can immediately enter play.

## Philosophical model: repo-as-game
- **Files are the source of truth.** Every decision—manual or rolled—must be written to disk.
- **Deterministic entropy.** All randomness is drawn from `dice/entropy.ndjson`; indices are never reused.
- **Schema-first.** Character JSON, session state, changelog entries, and intermediate progress all validate against the repository schemas.
- **Atomic commits.** Each creation stage is committed with the `[character:create]` tag so that history mirrors the creation path.

## Two creation paths
1. **DM-guided interactive creation**
   - Triggered when `sessions/<slug>/turn.md` contains a request such as `Start a new character: <name>`.
   - The DM writes prompts and responses into `turn.md`, records interim results in `sessions/<slug>/creation_progress.json`, and advances through the ordered `steps.json` sequence.
   - At each step, the DM appends a single question to `turn.md` to gather the next choice.

2. **Tool-driven creation**
   - Use `python tools/create_character.py` with explicit arguments to produce a fully formed character without DM narration.
   - The tool consumes entropy the same way the DM must, validates inputs through `character_creation/validators.py`, writes all final files, and emits a terse summary to STDOUT.

## Dice consumption
- All random outcomes pull from `dice/entropy.ndjson` using the modulo rule from `PROTOCOL.md` (map each d20 value to the needed die size as `1 + ((n-1) % sides)`).
- Ability scores use the `4d6-drop-lowest` method defined in `steps.json`, consuming one entropy index per ability score (four d20 values from that index).
- Name, background, or inventory rolls (if automated) consume the next available entropy index and record `entropy_index` values in changelog entries.
- Update `state.log_index` to the last consumed entropy index so that later rolls continue safely.

## Session scaffolding
When creation finishes, the following files must exist:

```
sessions/<slug>/state.json
sessions/<slug>/transcript.md
sessions/<slug>/changelog.md
sessions/<slug>/turn.md
```

A transient `sessions/<slug>/creation_progress.json` tracks DM-led steps and **must be deleted** on finalize.

## state.json initialization
- Start at level 1 with `xp: 0`, `turn: 0`, `scene_id: "creation-complete"`, `location: "start"`.
- `hp` is max hit die + Constitution modifier from the generated abilities.
- `inventory` mirrors the finalized starting equipment; `conditions` starts empty; `flags` starts as an empty object.
- `log_index` records the most recent entropy index consumed during creation.

## Inventory derivation
- The `inventories.json` table supplies class kits and background kits. Combine the matching class kit with the background kit and any race-specific starter items to form `starting_equipment` and the starting `inventory` in `state.json`.
- Inventory rolls (if a table has multiple options) must pull from deterministic entropy and be recorded in `changelog.md` rolls.

## Changelog entries
- Each step written to disk should also be logged as a JSON line appended to `sessions/<slug>/changelog.md`.
- Use the `schemas/log_entry.schema.json` shape, with `summary` describing the step and `rolls` including `{expr, total, entropy_index}` for every roll.
- The final creation log entry should note the selected race, class, background, ability totals, and inventory headline.

## DM prompts and branch writing
- The DM follows `steps.json` in order. After resolving a step, rewrite `turn.md` with a short acknowledgement and a single clear prompt for the next step.
- Branch prompts should be actionable (e.g., "Choose a class: Fighter, Rogue, Wizard, Cleric").
- On finalize, overwrite `turn.md` with the first adventure prompt or branch hook that references the new character.

## Folder structure for each new character
```
data/characters/<slug>.json       # Final character sheet (schema-valid)
sessions/<slug>/state.json        # Playable session state
sessions/<slug>/transcript.md     # Log of the creation summary, then play transcript
sessions/<slug>/changelog.md      # JSONL changelog with creation roll references
sessions/<slug>/turn.md           # Player-facing prompt; starts with the first adventure scene after creation
```

## Deterministic commit discipline
- Every creation stage must be committed with the `[character:create]` tag (e.g., `dm(<slug>): [character:create] step=abilities; details...`).
- DM-guided creations should use one commit per resolved step; tool-driven creation typically uses one commit when all files are written.

