# PROTOCOL: Deterministic Dungeon Master Loop

This contract defines how any AI or human acting as the DM must operate within this repository. All actions must respect the scope, locking rules, schemas, and deterministic dice consumption described here.

## Scope and File Access
The DM MUST only read or write within these paths:
- `sessions/<slug>/*`
- `data/characters/<slug>.json`
- `data/monsters/*`
- `data/rules/*`
- `PROMPTS/*`
- `schemas/*`
- `dice/*`

Do not touch files outside the allowlist.

## Turn Loop (per action)
1. **Lock check:** Read `sessions/<slug>/LOCK`. If it exists and you did not create it during this turn, ABORT.
2. **Claim lock:** Create `LOCK` as an empty file to claim the turn.
3. **Read inputs:**
   - `sessions/<slug>/turn.md` (latest player instruction).
   - `sessions/<slug>/state.json` (authoritative state).
   - Character JSON for `<slug>` and any referenced rules or monsters.
4. **Adjudicate:** Apply SRD-compatible rules only. Use deterministic dice from `dice/entropy.ndjson` for all uncertainty.
5. **Write outputs (atomically):**
   - Update `state.json` with HP, conditions, inventory, quest flags, scene/room identifiers, and log indices.
   - Append narrated scene and roll callouts to `transcript.md`.
   - Append a single line JSON log entry to `changelog.md` (see `schemas/log_entry.schema.json`).
   - Replace `turn.md` with the next branch prompt for the player (clear choice list or obvious open prompt).
6. **Commit:** Use the exact message format:
   ```
   dm(<slug>): <scene summary>; rolls=[<expr>=<result>@<entropy_index> ...]; hp:-3 goblin arrow; loc=Gate-01
   ```
   Replace the summary, rolls, HP delta, and location tags with relevant details.
7. **Release:** Remove `LOCK`.

On schema validation errors, revert edits for the failing file and write a diagnostic at the end of `turn.md`.

## Deterministic Dice Rules
- Each line of `dice/entropy.ndjson` is NDJSON: `{"i":1234,"d20":[7, ...], "d100":[42, ...], "bytes":"..."}`.
- To consume dice, read the next unused line. Record the `i` index for every roll in `changelog.md` and the commit message.
- **d20:** Pop the next number from `d20`.
- **d100:** Pop the next number from `d100`.
- **dX mapping:** For any die of size `X`, map a pulled d20 value `n` as `1 + ((n - 1) % X)`. Example: `2d6` pulls two d20 numbers; each result is `1 + ((n - 1) % 6)`.
- Never reuse an index. If more rolls are needed, consume the next line(s).
- If entropy is exhausted, instruct the user to run `python dice/verify_dice.py --extend N`.

## State Mutation Rules
- Only change fields declared in `schemas/state.schema.json`.
- Inventory changes must write full arrays (no partial diffs).
- Keep `state.scene_id`, `state.turn`, and `state.flags` coherent with narration.

## Narration Rules
- Keep scenes brisk with clear beats.
- Append SRD-cited notes lightly (e.g., "Difficult terrain halves travel").
- End every turn by writing a single branch prompt in `turn.md` (list of choices or a concise open prompt when obvious).
- SRD-only content; never invent closed IP.

## Safety Rails
- Never introduce non-SRD monsters or trademarked names.
- Keep all file paths inside the allowlist.
- On any schema error, revert the offending edit and append a diagnostic to `turn.md`.

## Commit Discipline
The DM MUST commit after each turn using the specified format, ensuring state, transcript, and changelog are consistent with consumed dice.

## v2 Procedures
- Exploration: run `python tools/explore.py --slug <slug> --steps N --pace normal` to advance hexes, roll weather/encounters/features, and log `entropy_index` values. Commit with tag `[travel:hex]`.
- Quest initialization: `python quests/generator.py --slug <slug> --template <template>` binds quest nodes to matching biomes and logs a hook. Commit with `[quest:init]`.
- Encounter resolution: `python tools/resolve_encounter.py --slug <slug> --monster <path>` executes initiative and a combat round. Commit with `[encounter:resolve]`.
- Loot: `python tools/loot.py --slug <slug>` rolls treasure tables and updates state. Commit with `[loot:roll]`.
- Downtime: `python tools/downtime.py --slug <slug> --activity <train|craft|carouse>` consumes time and gp. Commit with `[downtime:train]` (or activity).
- Rules search: build the local TF-IDF index with `python tools/index_rules.py` then query with `python tools/search_rules.py "<terms>"`; cite results as `(rules: file#Lx–Ly)` in transcripts.
- Always respect lock files and schema validation using `tools/validate.py`; branching for player choices remains governed by `turn.md`.
