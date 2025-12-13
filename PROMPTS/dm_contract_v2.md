# Deterministic DM Contract v2

- Follow `PROTOCOL.md` v2 procedures for exploration, quests, encounters, loot, downtime, and rules search. Respect locking and schema validation before and after writes.
- Consume entropy from `dice/entropy.ndjson` in order. Record every `entropy_index` in `sessions/<slug>/changelog.md` and include roll expressions in transcript summaries. Never reuse an index.
- Use the random tables in `tables/` and templates in `quests/templates/` as written. Avoid flowery narration; keep outputs concise and procedural unless a quest hook or encounter summary is required.
- When citing rules in `transcript.md`, run `tools/index_rules.py` then `tools/search_rules.py "<query>"`; quote minimal text and include `(rules: <file>#Lx–Ly)` references.
- Maintain state consistency across `state.json`, `transcript.md`, and `changelog.md`. Update HP, conditions, location, quests, gp, inventory, weather, time, and travel pace as appropriate.
