# DM Character Creation Prompt

The DM must watch for player requests inside `sessions/<slug>/turn.md` that start with **"Start a new character"**. When detected:

1. **Follow `character_creation/steps.json` in order.** After each step, rewrite `turn.md` with a concise acknowledgment and a single question for the next choice.
2. **Use deterministic dice.** Pull entropy from `dice/entropy.ndjson` using the mapping rule `1 + ((n-1) % sides)` for any die size.
3. **Track progress.** Write interim data to `sessions/<slug>/creation_progress.json`, including the resolved step id, chosen value, and the latest `entropy_index`.
4. **Apply validation.** Use `character_creation/validators.py` to ensure selections are legal before advancing.
5. **Record rolls.** Store `{expr, total, entropy_index}` in `creation_progress.json` and echo the entropy indices in `changelog.md` entries.
6. **Finalize.** When the `finalize` step completes:
   - Write `data/characters/<slug>.json` (schema-valid), `sessions/<slug>/state.json`, `sessions/<slug>/transcript.md`, and `sessions/<slug>/changelog.md`.
   - Delete `creation_progress.json` after successful writes.
   - Overwrite `turn.md` with the first adventure branch prompt that references the new character.
   - Initialize `state.log_index` with the last used entropy index and set `scene_id` to `creation-complete`.
   - Commit with `dm(<slug>): [character:create] step=<id>; details...`.
7. **Lock discipline.** Continue to observe LOCK rules from `PROTOCOL.md` while creating characters.

