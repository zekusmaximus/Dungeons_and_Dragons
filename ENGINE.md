# Exploration and Procedure Engine v2

This repository models deterministic travel, encounters, quests, loot, and rules lookup for tabletop sessions. Tools consume entropy from `dice/entropy.ndjson` in order, recording the `entropy_index` in `sessions/<slug>/changelog.md` for traceability. Data is defined by JSON schemas in `schemas/` and example assets in `data/`, `tables/`, and `worlds/`.

Key components:
- **Exploration (`tools/explore.py`)** advances hex positions, rolls weather/encounters/features, and logs procedural results.
- **Quest Generator (`quests/generator.py`)** binds quest templates to matching biome hexes and writes quest files.
- **Encounter Resolver (`tools/resolve_encounter.py`)** simulates initiative and a combat round, updating HP and conditions.
- **Loot and Downtime (`tools/loot.py`, `tools/downtime.py`)** apply treasure rolls and downtime actions that affect state.
- **Rules Search (`tools/index_rules.py`, `tools/search_rules.py`)** indexes Markdown rules with TF-IDF for local citations.

See `PROTOCOL.md` for operational guidance and `PROMPTS/dm_contract_v2.md` for DM-facing instructions.
