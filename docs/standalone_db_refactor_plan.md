# Standalone DB Refactor Plan (Architecture + Persistence Coupling Map)

This document maps the current FastAPI surface to file-based persistence, then proposes a minimal SQLite-backed refactor while keeping API response shapes stable.

## 1) Route inventory (method + path -> handler)

GET /health -> health
GET /schemas/{schema_name} -> get_schema
GET /sessions -> list_sessions
POST /sessions -> create_session
GET /sessions/{slug}/state -> session_state
GET /data/characters/{slug}.json -> character_data
GET /sessions/{slug}/transcript -> session_transcript
GET /sessions/{slug}/changelog -> session_changelog
GET /sessions/{slug}/quests -> session_quests
GET /sessions/{slug}/quests/{quest_id} -> get_quest
POST /sessions/{slug}/quests -> create_quest
PUT /sessions/{slug}/quests/{quest_id} -> update_quest
DELETE /sessions/{slug}/quests/{quest_id} -> delete_quest
GET /sessions/{slug}/npc-memory -> session_npc_memory
GET /sessions/{slug}/npc-memory/{index} -> get_npc
POST /sessions/{slug}/npc-memory -> create_npc
PUT /sessions/{slug}/npc-memory/{index} -> update_npc
DELETE /sessions/{slug}/npc-memory/{index} -> delete_npc
GET /sessions/{slug}/world/factions -> session_factions
GET /sessions/{slug}/world/factions/{faction_id} -> get_faction
POST /sessions/{slug}/world/factions -> create_faction
PUT /sessions/{slug}/world/factions/{faction_id} -> update_faction
DELETE /sessions/{slug}/world/factions/{faction_id} -> delete_faction
GET /sessions/{slug}/world/timeline -> session_timeline
POST /sessions/{slug}/world/timeline -> create_timeline_event
PUT /sessions/{slug}/world/timeline/{event_id} -> update_timeline_event
DELETE /sessions/{slug}/world/timeline/{event_id} -> delete_timeline_event
GET /sessions/{slug}/world/rumors -> session_rumors
GET /sessions/{slug}/world/faction-clocks -> session_faction_clocks
GET /sessions/{slug}/turn -> get_turn
POST /sessions/{slug}/lock/claim -> claim_lock
DELETE /sessions/{slug}/lock -> release_lock
POST /sessions/{slug}/turn/preview -> preview_turn
POST /sessions/{slug}/turn/commit -> commit_turn
POST /sessions/{slug}/turn/commit-and-narrate -> commit_and_narrate
POST /sessions/{slug}/character -> create_character_for_session
GET /sessions/{slug}/player -> get_player_bundle
POST /sessions/{slug}/player/opening -> player_opening_scene
POST /sessions/{slug}/roll -> player_roll
POST /sessions/{slug}/player/roll -> player_roll_legacy
POST /sessions/{slug}/player/turn -> player_turn
POST /jobs/explore -> create_explore_job
POST /jobs/resolve-encounter -> create_resolve_encounter_job
POST /jobs/loot -> create_loot_job
POST /jobs/downtime -> create_downtime_job
POST /jobs/quest/init -> create_quest_init_job
GET /jobs/{job_id} -> get_job_progress
POST /jobs/{job_id}/commit -> commit_job
POST /jobs/{job_id}/cancel -> cancel_job
GET /entropy -> entropy_preview
GET /sessions/{slug}/history/commits -> session_commit_history
GET /sessions/{slug}/diff -> session_diff
GET /sessions/{slug}/turns -> list_turn_records
GET /sessions/{slug}/turns/{turn} -> get_turn_record
GET /sessions/{slug}/entropy/history -> session_entropy_history
GET /llm/config -> get_llm_config
POST /llm/config -> configure_llm
POST /llm/narrate -> generate_narrative
POST /sessions/{slug}/llm/narrate -> generate_scene_narrative
GET /adventure-hooks -> get_adventure_hooks
GET /adventure-hooks/recommended -> get_recommended_hooks
GET /adventure-hooks/{hook_id} -> get_adventure_hook
POST /adventure-hooks/generate -> generate_custom_hook
POST /quests/generate -> generate_dynamic_quest_endpoint
GET /quests/types -> get_quest_types
GET /sessions/{slug}/npcs/relationships -> get_npc_relationships
GET /sessions/{slug}/npcs/{npc_id}/relationship -> get_npc_relationship
POST /sessions/{slug}/npcs/{npc_id}/relationship -> update_npc_relationship
POST /sessions/{slug}/npcs/{npc_id}/dialogue -> generate_npc_dialogue
GET /sessions/{slug}/npcs/relationship-summary -> get_relationship_summary
GET /sessions/{slug}/mood -> get_current_mood
POST /sessions/{slug}/mood -> set_mood_state
PATCH /sessions/{slug}/mood -> adjust_mood_state
GET /sessions/{slug}/mood/suggestions -> get_mood_suggestions
POST /sessions/{slug}/mood/narrate -> generate_mood_narrative
GET /mood/types -> get_mood_types
GET /sessions/{slug}/discoveries -> get_all_discoveries
GET /sessions/{slug}/discoveries/recent -> get_recent_discoveries
GET /sessions/{slug}/discoveries/important -> get_important_discoveries
GET /sessions/{slug}/discoveries/types/{discovery_type} -> get_discoveries_by_type
POST /sessions/{slug}/discoveries -> log_discovery
GET /sessions/{slug}/discoveries/stats -> get_discovery_stats
POST /sessions/{slug}/discoveries/{discovery_id}/describe -> generate_discovery_description
GET /discoveries/types -> get_discovery_types
GET /sessions/{slug}/auto-save/status -> get_auto_save_status
POST /sessions/{slug}/auto-save/start -> start_auto_save
POST /sessions/{slug}/auto-save/stop -> stop_auto_save
POST /sessions/{slug}/auto-save/perform -> perform_auto_save
POST /sessions/{slug}/save -> manual_save
GET /sessions/{slug}/saves -> get_save_history
GET /sessions/{slug}/saves/{save_id} -> get_save_info
POST /sessions/{slug}/saves/{save_id}/restore -> restore_save
GET /events/{slug} -> session_events

## 2) Route persistence and payload shapes (per route)

Notation:
- Read/Write: exact function names and file paths.
- Request keys: example JSON keys (query params noted explicitly when relevant).
- Response keys: example JSON keys.

### Health + schemas

GET /health -> health
- Persistence: none
- Request: none
- Response keys: {"status"}

GET /schemas/{schema_name} -> get_schema
- Persistence: direct file read in `service/app.py`
  - Read: `schemas/{schema_name}.schema.json`
- Request: path param `schema_name`
- Response keys: schema JSON (arbitrary JSON Schema keys)

### Sessions: list/create/state

GET /sessions -> list_sessions
- Persistence: `storage.list_sessions`
  - Read: `sessions/*/state.json` (world), `sessions/*/LOCK` (has_lock)
- Request: none
- Response keys: list of {"slug", "world", "has_lock", "updated_at"}

POST /sessions -> create_session
- Persistence: `storage.create_session`
  - Read: `sessions/{template_slug}/**` (template copy), `data/characters/{template_slug}.json`
  - Write: `sessions/{slug}/**` (copy), delete `sessions/{slug}/LOCK` if present, delete `sessions/{slug}/previews/**` if present
  - Write: `sessions/{slug}/state.json`, `sessions/{slug}/transcript.md`, `sessions/{slug}/changelog.md`
  - Write: `sessions/{slug}/character.json`, `data/characters/{slug}.json` (via `save_character`)
- Request keys: {"hook_id", "template_slug", "slug"}
- Response keys: {"slug"}

GET /sessions/{slug}/state -> session_state
- Persistence: `storage.load_state`
  - Read: `sessions/{slug}/state.json`
- Request: path `slug`
- Response keys: SessionState (example keys: {"character", "turn", "scene_id", "location", "hp", "log_index", "level", "xp", "inventory", ...})

GET /data/characters/{slug}.json -> character_data
- Persistence: `storage.load_character`
  - Read: `sessions/{slug}/character.json` (preferred)
  - Read: `data/characters/{slug}.json` (fallback)
- Request: path `slug`
- Response keys: Character (example keys: {"slug", "name", "race", "class", "level", "hp", "ac", "abilities", ...})

### Transcript + changelog

GET /sessions/{slug}/transcript -> session_transcript
- Persistence: `storage.load_transcript` -> `load_text_entries`
  - Read: `sessions/{slug}/transcript.md`
- Request: query `tail`, `cursor`
- Response keys: {"items": [{"id", "text"}], "cursor"}

GET /sessions/{slug}/changelog -> session_changelog
- Persistence: `storage.load_changelog` -> `load_text_entries`
  - Read: `sessions/{slug}/changelog.md`
- Request: query `tail`, `cursor`
- Response keys: {"items": [{"id", "text"}], "cursor"}

### Quests (stored in state.json)

GET /sessions/{slug}/quests -> session_quests
- Persistence: `storage.load_quests` -> `load_state`
  - Read: `sessions/{slug}/state.json`
- Request: path `slug`
- Response keys: {"quests": {"<quest_id>": { ... }}}

GET /sessions/{slug}/quests/{quest_id} -> get_quest
- Persistence: `storage.load_quests` -> `load_state`
  - Read: `sessions/{slug}/state.json`
- Request: path `slug`, `quest_id`
- Response keys: quest object (example keys: {"id", "name", "description", "objectives", "rewards", ...})

POST /sessions/{slug}/quests -> create_quest
- Persistence: `storage.validate_data`, `storage.save_quest`
  - Read: `schemas/quest.schema.json` (if present)
  - Read/Write: `sessions/{slug}/state.json`
- Request keys: quest object (example keys: {"id", "name", "description", "objectives", "rewards"})
- Response keys: {"id"} or {"errors"} or {"diff", "warnings"} (dry_run)

PUT /sessions/{slug}/quests/{quest_id} -> update_quest
- Persistence: `storage.validate_data`, `storage.load_quests`, `storage.save_quest`
  - Read: `schemas/quest.schema.json` (if present)
  - Read/Write: `sessions/{slug}/state.json`
- Request keys: quest object (example keys: {"id", "name", "description", "objectives", "rewards"})
- Response keys: {"message"} or {"errors"} or {"diff", "warnings"} (dry_run)

DELETE /sessions/{slug}/quests/{quest_id} -> delete_quest
- Persistence: `storage.load_quests`, `storage.delete_quest`
  - Read/Write: `sessions/{slug}/state.json`
- Request: path `slug`, `quest_id`, query `dry_run`
- Response keys: {"message"} or {"diff", "warnings"} (dry_run)

### NPC memory (session-local file)

GET /sessions/{slug}/npc-memory -> session_npc_memory
- Persistence: `storage.load_npc_memory`
  - Read: `sessions/{slug}/npc_memory.json`
- Response keys: {"npc_memory": [ ... ]}

GET /sessions/{slug}/npc-memory/{index} -> get_npc
- Persistence: `storage.load_npc_memory`
  - Read: `sessions/{slug}/npc_memory.json`
- Response keys: NPC object (example keys are caller-defined)

POST /sessions/{slug}/npc-memory -> create_npc
- Persistence: `storage.load_npc_memory`, `storage.save_npc_memory`
  - Read: `sessions/{slug}/npc_memory.json`
  - Write: `sessions/{slug}/npc_memory.json`
- Request keys: NPC object (example keys: {"name", "role", "notes", ...})
- Response keys: {"index"} or {"diff", "warnings"} (dry_run)

PUT /sessions/{slug}/npc-memory/{index} -> update_npc
- Persistence: `storage.load_npc_memory`, `storage.save_npc_memory`
  - Read/Write: `sessions/{slug}/npc_memory.json`
- Request keys: NPC object
- Response keys: {"message"} or {"diff", "warnings"} (dry_run)

DELETE /sessions/{slug}/npc-memory/{index} -> delete_npc
- Persistence: `storage.load_npc_memory`, `storage.save_npc_memory`
  - Read/Write: `sessions/{slug}/npc_memory.json`
- Response keys: {"message"} or {"diff", "warnings"} (dry_run)
### World data (shared by world name)

GET /sessions/{slug}/world/factions -> session_factions
- Persistence: `storage.load_factions` -> `resolve_world` -> `load_world_file`
  - Read: `sessions/{slug}/state.json` (world name)
  - Read: `worlds/{world}/factions.json`
- Response keys: {"<faction_id>": { ... }}

GET /sessions/{slug}/world/factions/{faction_id} -> get_faction
- Persistence: `storage.load_factions`
  - Read: `sessions/{slug}/state.json`, `worlds/{world}/factions.json`
- Response keys: faction object (example keys: {"id", "name", "stance", ...})

POST /sessions/{slug}/world/factions -> create_faction
- Persistence: `storage.save_faction`
  - Read/Write: `worlds/{world}/factions.json`
  - Read: `sessions/{slug}/state.json` (world name)
- Request keys: faction object (example keys: {"id", "name", "stance", ...})
- Response keys: {"id"} or {"diff", "warnings"} (dry_run)

PUT /sessions/{slug}/world/factions/{faction_id} -> update_faction
- Persistence: `storage.save_faction`
  - Read/Write: `worlds/{world}/factions.json`
- Request keys: faction object
- Response keys: {"message"} or {"diff", "warnings"} (dry_run)

DELETE /sessions/{slug}/world/factions/{faction_id} -> delete_faction
- Persistence: `storage.delete_faction`
  - Read/Write: `worlds/{world}/factions.json`
- Response keys: {"message"} or {"diff", "warnings"} (dry_run)

GET /sessions/{slug}/world/timeline -> session_timeline
- Persistence: `storage.load_timeline`
  - Read: `worlds/{world}/timeline.json`
  - Read: `sessions/{slug}/state.json` (world name)
- Response keys: {"<event_id>": { ... }}

POST /sessions/{slug}/world/timeline -> create_timeline_event
- Persistence: `storage.save_timeline_event`
  - Read/Write: `worlds/{world}/timeline.json`
- Request keys: event object (example keys: {"id", "title", "description", ...})
- Response keys: {"id"} or {"diff", "warnings"} (dry_run)

PUT /sessions/{slug}/world/timeline/{event_id} -> update_timeline_event
- Persistence: `storage.save_timeline_event`
  - Read/Write: `worlds/{world}/timeline.json`
- Request keys: event object
- Response keys: {"message"} or {"diff", "warnings"} (dry_run)

DELETE /sessions/{slug}/world/timeline/{event_id} -> delete_timeline_event
- Persistence: `storage.delete_timeline_event`
  - Read/Write: `worlds/{world}/timeline.json`
- Response keys: {"message"} or {"diff", "warnings"} (dry_run)

GET /sessions/{slug}/world/rumors -> session_rumors
- Persistence: `storage.load_rumors`
  - Read: `worlds/{world}/rumors.json`
- Response keys: {"<rumor_id>": { ... }}

GET /sessions/{slug}/world/faction-clocks -> session_faction_clocks
- Persistence: `storage.load_faction_clocks`
  - Read: `worlds/{world}/faction_clocks.json`
- Response keys: {"<clock_id>": { ... }}

### Turn prompt + lock

GET /sessions/{slug}/turn -> get_turn
- Persistence: `storage.load_turn`, `storage.load_state`, `storage.get_lock_info`
  - Read: `sessions/{slug}/turn.md`, `sessions/{slug}/state.json`, `sessions/{slug}/LOCK`
- Response keys: {"prompt", "turn_number", "lock_status"}

POST /sessions/{slug}/lock/claim -> claim_lock
- Persistence: `storage.claim_lock`
  - Write: `sessions/{slug}/LOCK` (JSON {"owner", "ttl", "claimed_at"})
- Request keys: {"owner", "ttl"}
- Response keys: {"message"}

DELETE /sessions/{slug}/lock -> release_lock
- Persistence: `storage.release_lock`
  - Delete: `sessions/{slug}/LOCK`
- Response keys: {"message"}

### Turn preview/commit

POST /sessions/{slug}/turn/preview -> preview_turn
- Persistence: `storage.create_preview`
  - Read: `sessions/{slug}/state.json`
  - Read: `dice/entropy.ndjson` (via `_ensure_entropy_available`)
  - Write: `sessions/{slug}/previews/{preview_id}.json`
- Request keys: {"response", "state_patch", "transcript_entry", "changelog_entry", "dice_expressions", "lock_owner"}
- Response keys: {"id", "diffs": [{"path", "changes"}], "entropy_plan": {"indices", "usage"}}

POST /sessions/{slug}/turn/commit -> commit_turn
- Persistence: `storage.commit_preview`
  - Read: `sessions/{slug}/previews/{preview_id}.json`, `sessions/{slug}/state.json`
  - Read: `dice/entropy.ndjson` (verification only)
  - Write: `sessions/{slug}/state.json`
  - Append: `sessions/{slug}/transcript.md`
  - Append: `sessions/{slug}/changelog.md`
  - Delete: `sessions/{slug}/previews/{preview_id}.json`
- Request keys: {"preview_id", "lock_owner"}
- Response keys: {"state": SessionState, "log_indices": {"transcript", "changelog"}}

POST /sessions/{slug}/turn/commit-and-narrate -> commit_and_narrate
- Persistence: `_commit_and_narrate_internal` + `storage.commit_preview` + `storage.persist_turn_record`
  - Same reads/writes as commit_turn
  - Additional write: `sessions/{slug}/turns/{turn}.json` (TurnRecord)
  - Conditional write: `sessions/{slug}/discovery_log.json` (via `DiscoveryLog.create_discovery`)
  - Conditional write: `sessions/{slug}/last_discovery.json` (via `storage.record_last_discovery_turn`)
- Request keys: {"preview_id", "lock_owner"}
- Response keys: {"commit", "dm", "turn_record", "usage"}

### Character creation

POST /sessions/{slug}/character -> create_character_for_session
- Persistence: `storage.save_character`, `storage.save_state`
  - Write: `sessions/{slug}/character.json`
  - Write: `data/characters/{slug}.json`
  - Write: `sessions/{slug}/state.json`
- Request keys: CharacterCreationRequest (example keys: {"name", "ancestry", "class", "background", "level", "abilities", "skills", "equipment", "hook", ...})
- Response keys: {"character", "state"}

### Player bundle/turns/rolls

GET /sessions/{slug}/player -> get_player_bundle
- Persistence: `storage.load_state`, `storage.load_character`, `storage.load_turn_records`, `storage.load_quests`, `DiscoveryLog.get_recent_discoveries`
  - Read: `sessions/{slug}/state.json`
  - Read: `sessions/{slug}/character.json` or `data/characters/{slug}.json`
  - Read: `sessions/{slug}/turns/*.json`
  - Read: `sessions/{slug}/discovery_log.json`
- Response keys: {"state", "character", "recaps", "discoveries", "quests", "suggestions"}

POST /sessions/{slug}/player/opening -> player_opening_scene
- Persistence: `storage.claim_lock` (if needed), `storage.create_preview`, `storage.commit_preview`, `storage.persist_turn_record`, `DiscoveryLog.create_discovery`, `storage.record_last_discovery_turn`, `storage.release_lock`
  - Read/Write: `sessions/{slug}/LOCK`
  - Read: `sessions/{slug}/state.json`, `sessions/{slug}/character.json` or `data/characters/{slug}.json`
  - Write: `sessions/{slug}/previews/{preview_id}.json`
  - Write: `sessions/{slug}/state.json`, append `sessions/{slug}/transcript.md`, append `sessions/{slug}/changelog.md`
  - Write: `sessions/{slug}/turns/{turn}.json`
  - Conditional write: `sessions/{slug}/discovery_log.json`, `sessions/{slug}/last_discovery.json`
- Request keys: {"hook"}
- Response keys: {"state", "narration", "turn_record", "suggestions", "roll_request"}

POST /sessions/{slug}/roll -> player_roll
POST /sessions/{slug}/player/roll -> player_roll_legacy
- Persistence: `storage.perform_roll`
  - Read: `sessions/{slug}/state.json`
  - Read: `sessions/{slug}/character.json` or `data/characters/{slug}.json`
  - Read: `dice/entropy.ndjson`
  - Write: `sessions/{slug}/state.json` (log_index increment)
  - Append: `sessions/{slug}/transcript.md`
  - Write: `sessions/{slug}/turns/{turn}.json` (append roll payload if turn record exists)
- Request keys: {"type"|"kind", "ability", "skill", "dc", "advantage", "notes"}
- Response keys: {"d20", "total", "breakdown", "text"}

POST /sessions/{slug}/player/turn -> player_turn
- Persistence: `storage.claim_lock` (if needed), `storage.create_preview`, `storage.commit_preview`, `storage.persist_turn_record`, optional discovery writes, `storage.release_lock`
  - Same files as commit-and-narrate + lock file
- Request keys: {"action", "state_patch"}
- Response keys: {"state", "narration", "turn_record", "suggestions", "roll_request"}
### Jobs (disabled)

POST /jobs/explore -> create_explore_job
POST /jobs/resolve-encounter -> create_resolve_encounter_job
POST /jobs/loot -> create_loot_job
POST /jobs/downtime -> create_downtime_job
POST /jobs/quest/init -> create_quest_init_job
GET /jobs/{job_id} -> get_job_progress
POST /jobs/{job_id}/commit -> commit_job
POST /jobs/{job_id}/cancel -> cancel_job
- Persistence: none in handlers (all raise 501)
- Request/Response: 501 error envelope

### Entropy + history

GET /entropy -> entropy_preview
- Persistence: `storage.load_entropy_preview`
  - Read: `dice/entropy.ndjson`
- Request: query `limit`
- Response keys: {"entropy": [ {"i", "d20", ...} ]}

GET /sessions/{slug}/history/commits -> session_commit_history
- Persistence: `storage.load_commit_history`
  - Read: `sessions/{slug}/changelog.md`
- Response keys: list of {"id", "tags", "entropy_indices", "timestamp", "description"}

GET /sessions/{slug}/diff -> session_diff
- Persistence: `storage.load_session_diff` (placeholder, no file access)
- Request: query `from_commit`, `to`
- Response keys: {"files": [{"path", "changes"}]}

GET /sessions/{slug}/turns -> list_turn_records
- Persistence: `storage.load_turn_records`
  - Read: `sessions/{slug}/turns/*.json`
- Request: query `limit`
- Response keys: list of TurnRecord (example keys: {"turn", "player_intent", "diff", "dm", "created_at", "rolls"})

GET /sessions/{slug}/turns/{turn} -> get_turn_record
- Persistence: `storage.load_turn_record`
  - Read: `sessions/{slug}/turns/{turn}.json`
- Response keys: TurnRecord

GET /sessions/{slug}/entropy/history -> session_entropy_history
- Persistence: `storage.load_entropy_history` -> `load_entropy_preview`
  - Read: `dice/entropy.ndjson`
- Request: query `limit`
- Response keys: list of {"timestamp", "who", "what", "indices"}

### LLM config and narration

GET /llm/config -> get_llm_config
- Persistence: `get_effective_llm_config` -> `load_persisted_llm_config`
  - Read: `.dm_llm_config.json`
- Response keys: {"api_key_set", "current_model", "base_url", "temperature", "max_tokens", "source"}

POST /llm/config -> configure_llm
- Persistence: `persist_llm_config`
  - Read/Write: `.dm_llm_config.json`
- Request keys: {"api_key", "base_url", "model"}
- Response keys: same as GET /llm/config

POST /llm/narrate -> generate_narrative
- Persistence: none (network call only)
- Request keys: {"prompt", "context", "scene_type", "tone", "max_tokens"}
- Response keys: {"narrative", "tokens_used", "model", "usage"}

POST /sessions/{slug}/llm/narrate -> generate_scene_narrative
- Persistence: `storage.load_state`, `storage.load_character`
  - Read: `sessions/{slug}/state.json`, `sessions/{slug}/character.json` or `data/characters/{slug}.json`
- Request keys: {"prompt", "context", "scene_type", "tone", "max_tokens"}
- Response keys: {"narrative", "tokens_used", "model", "usage"}

### Adventure hooks + dynamic quests

GET /adventure-hooks -> get_adventure_hooks
- Persistence: `AdventureHooksService.get_available_hooks`
  - Read: `data/adventure_hooks.json`
  - Write (if file missing/empty): `data/adventure_hooks.json` (via `_save_hooks`)
- Response keys: list of {"hook_id", "title", "description", "hook_type", "location", "difficulty", "rewards", "starting_scene"}

GET /adventure-hooks/recommended -> get_recommended_hooks
- Persistence: same as get_adventure_hooks
- Request: query `character_class`, `character_level`
- Response keys: list of AdventureHookResponse

GET /adventure-hooks/{hook_id} -> get_adventure_hook
- Persistence: same as get_adventure_hooks
- Request: path `hook_id`
- Response keys: AdventureHookResponse

POST /adventure-hooks/generate -> generate_custom_hook
- Persistence: `AdventureHooksService.generate_llm_enhanced_hook`
  - Read: `data/adventure_hooks.json` (fallback) and prompts in LLM enhancer
  - Write: none (unless defaults are generated)
- Request keys: character context object (example keys: {"name", "class", "level", ...})
- Response keys: AdventureHookResponse

POST /quests/generate -> generate_dynamic_quest_endpoint
- Persistence: none (pure function)
- Request keys: character_context, session_context (both objects), query `use_llm`
- Response keys: quest object (keys: {"id", "name", "description", "objectives", "rewards", "difficulty", "starting_scene", "quest_type", ...})

GET /quests/types -> get_quest_types
- Persistence: none
- Response keys: {"quest_types": {"combat": "...", ...}}

### NPC relationships (separate file)

GET /sessions/{slug}/npcs/relationships -> get_npc_relationships
- Persistence: `NPCRelationshipService._load_relationships`
  - Read: `sessions/{slug}/npc_relationships.json`
- Response keys: list of {"npc_id", "name", "relationship_status", "attitude", "relationship_level", "trust", "liking", "fear", "last_interaction"}

GET /sessions/{slug}/npcs/{npc_id}/relationship -> get_npc_relationship
- Persistence: `NPCRelationshipService._load_relationships`
  - Read: `sessions/{slug}/npc_relationships.json`
- Response keys: NPCRelationshipResponse

POST /sessions/{slug}/npcs/{npc_id}/relationship -> update_npc_relationship
- Persistence: `NPCRelationshipService.update_relationship` -> `_save_relationships`
  - Read/Write: `sessions/{slug}/npc_relationships.json`
- Request keys: {"interaction_type", "success", "context"}
- Response keys: {"message", "changes"}

POST /sessions/{slug}/npcs/{npc_id}/dialogue -> generate_npc_dialogue
- Persistence: `NPCRelationshipService._load_relationships` (read-only)
  - Read: `sessions/{slug}/npc_relationships.json`
- Request keys: context object
- Response keys: {"dialogue"}

GET /sessions/{slug}/npcs/relationship-summary -> get_relationship_summary
- Persistence: `NPCRelationshipService._load_relationships`
  - Read: `sessions/{slug}/npc_relationships.json`
- Response keys: {"total_npcs", "relationships_by_status", "average_relationship_level", "most_trusted_npc", "most_liked_npc"}

### Mood system

GET /sessions/{slug}/mood -> get_current_mood
- Persistence: `MoodSystem._load_mood_state`
  - Read: `sessions/{slug}/mood_state.json`
- Response keys: {"current_mood", "mood_intensity", "mood_history"}

POST /sessions/{slug}/mood -> set_mood_state
- Persistence: `MoodSystem.set_mood` -> `_save_mood_state`
  - Write: `sessions/{slug}/mood_state.json`
- Request keys: {"mood", "intensity", "reason"}
- Response keys: {"message", "changes"}

PATCH /sessions/{slug}/mood -> adjust_mood_state
- Persistence: `MoodSystem.adjust_mood` -> `_save_mood_state`
  - Write: `sessions/{slug}/mood_state.json`
- Request keys: {"mood_change", "intensity_change", "reason"}
- Response keys: {"message", "changes"}

GET /sessions/{slug}/mood/suggestions -> get_mood_suggestions
- Persistence: `MoodSystem._load_mood_state` (read only)
  - Read: `sessions/{slug}/mood_state.json`
- Response keys: {"description", "suggestions"}

POST /sessions/{slug}/mood/narrate -> generate_mood_narrative
- Persistence: `MoodSystem._load_mood_state` (read only)
  - Read: `sessions/{slug}/mood_state.json`
- Request keys: prompt string and context object
- Response keys: {"narrative", "mood", "intensity"}

GET /mood/types -> get_mood_types
- Persistence: none
- Response keys: {"mood_types": {...}}
### Discoveries

GET /sessions/{slug}/discoveries -> get_all_discoveries
GET /sessions/{slug}/discoveries/recent -> get_recent_discoveries
GET /sessions/{slug}/discoveries/important -> get_important_discoveries
GET /sessions/{slug}/discoveries/types/{discovery_type} -> get_discoveries_by_type
GET /sessions/{slug}/discoveries/stats -> get_discovery_stats
- Persistence: `DiscoveryLog._load_discoveries`
  - Read: `sessions/{slug}/discovery_log.json`
- Response keys: list of {"discovery_id", "name", "discovery_type", "description", "location", "discovered_at", "importance", ...} or stats keys

POST /sessions/{slug}/discoveries -> log_discovery
- Persistence: `DiscoveryLog.create_discovery` -> `_save_discoveries` + `storage.record_last_discovery_turn`
  - Write: `sessions/{slug}/discovery_log.json`, `sessions/{slug}/last_discovery.json`
  - Read: `sessions/{slug}/state.json` (turn)
- Request keys: {"name", "discovery_type", "description", "location", "importance", "related_quest", "rewards"}
- Response keys: DiscoveryResponse

POST /sessions/{slug}/discoveries/{discovery_id}/describe -> generate_discovery_description
- Persistence: `DiscoveryLog._load_discoveries` (read only)
  - Read: `sessions/{slug}/discovery_log.json`
- Request: path `discovery_id`
- Response keys: {"discovery_id", "original_description", "enhanced_description"}

GET /discoveries/types -> get_discovery_types
- Persistence: none
- Response keys: {"discovery_types": {...}}

### Auto-save

GET /sessions/{slug}/auto-save/status -> get_auto_save_status
- Persistence: `AutoSaveSystem._load_save_data`
  - Read: `sessions/{slug}/auto_save.json`
- Response keys: {"running", "save_interval", "last_save_time", "save_count", "next_save_in"}

POST /sessions/{slug}/auto-save/start -> start_auto_save
POST /sessions/{slug}/auto-save/stop -> stop_auto_save
- Persistence: none (start/stop thread only)
- Response keys: {"message"}

POST /sessions/{slug}/auto-save/perform -> perform_auto_save
- Persistence: `AutoSaveSystem.perform_auto_save`, `_save_metadata`
  - Write: `sessions/{slug}/saves/auto-<timestamp>.json`
  - Write: `sessions/{slug}/auto_save.json`
- Request keys: query `lock_owner`
- Response keys: {"message"} (success) or error

POST /sessions/{slug}/save -> manual_save
- Persistence: `AutoSaveSystem.manual_save`
  - Write: `sessions/{slug}/saves/{save_name}-<timestamp>.json`
- Request keys: {"save_name", "lock_owner"}
- Response keys: {"message", "save_id", "timestamp"}

GET /sessions/{slug}/saves -> get_save_history
- Persistence: `AutoSaveSystem.get_save_history`
  - Read: `sessions/{slug}/saves/*.json`
- Request: query `limit`
- Response keys: list of save metadata (example keys: {"save_id", "session_slug", "timestamp", "save_type", "data"})

GET /sessions/{slug}/saves/{save_id} -> get_save_info
- Persistence: `AutoSaveSystem.get_save_info`
  - Read: `sessions/{slug}/saves/{save_id}.json`
- Response keys: save metadata

POST /sessions/{slug}/saves/{save_id}/restore -> restore_save
- Persistence: `AutoSaveSystem.restore_save` (placeholder)
  - Read: `sessions/{slug}/saves/{save_id}.json`
- Response keys: {"message", "note"}

### Observability

GET /events/{slug} -> session_events
- Persistence: none (501/disabled)
- Response: error envelope

## 3) Files written per turn (current behavior)

Turn-related writes happen in three paths:

1) Turn preview (no turn increment, reservation only)
- `sessions/{slug}/previews/{preview_id}.json` (preview metadata)

2) Turn commit (no narration)
- `sessions/{slug}/state.json` (turn increment, log_index update, state patch)
- `sessions/{slug}/transcript.md` (append transcript entry or response)
- `sessions/{slug}/changelog.md` (append changelog entry if provided)
- Delete `sessions/{slug}/previews/{preview_id}.json`

3) Turn commit-and-narrate / player turn
- All files from commit
- `sessions/{slug}/turns/{turn}.json` (TurnRecord)
- Conditional: `sessions/{slug}/discovery_log.json` (if discovery added)
- Conditional: `sessions/{slug}/last_discovery.json` (tracking last discovery turn)

Additional per-turn side effects:
- `sessions/{slug}/LOCK` may be created/released around player turn flows.
- `sessions/{slug}/transcript.md` may also be appended by `POST /sessions/{slug}/roll`.
- `sessions/{slug}/turns/{turn}.json` may be updated by `POST /sessions/{slug}/roll` to append roll payloads.

## 4) Source of truth vs derived state

Source of truth (canonical):
- `sessions/{slug}/state.json` (authoritative state, turn number, log_index)
- `dice/entropy.ndjson` (authoritative entropy source)
- `worlds/{world}/*.json` (shared world state)
- `data/characters/{slug}.json` and `sessions/{slug}/character.json` (character sheet)

Derived/rebuildable (can be regenerated from source or recomputed):
- `sessions/{slug}/transcript.md` (append-only narrative log)
- `sessions/{slug}/changelog.md` (append-only diffs; could be recomputed from state deltas)
- `sessions/{slug}/turns/{turn}.json` (turn recap; can be recomputed if narrative and diffs are reproducible)
- `sessions/{slug}/previews/{preview_id}.json` (ephemeral)
- `sessions/{slug}/last_discovery.json` (derived from discovery history)
- `sessions/{slug}/saves/*.json` (backup metadata only)

## 5) Determinism and indexing

### 5A) Entropy consumption

- The next entropy row is determined by `state.log_index` in `sessions/{slug}/state.json`.
- `perform_roll` uses `next_index = state.log_index + 1`, loads `dice/entropy.ndjson` entry with matching `i`, and then persists the incremented `log_index` back to `state.json`.
- `create_preview` reserves a range of indices based on `dice_expressions` length: indices `[log_index+1, log_index+dice_count]`. It does not persist them to state; it stores them in `sessions/{slug}/previews/{preview_id}.json`.
- `commit_preview` validates reservations and sets `state.log_index` to the last reserved index (or leaves it unchanged if no dice reserved).
- There is no separate persistence of entropy usage beyond updating `state.log_index`; no per-session entropy log is written.

### 5B) log_index and turn_number semantics

- `turn` and `log_index` live in `sessions/{slug}/state.json` and are treated as monotonically increasing counters.
- `turn` increments by 1 on each `commit_preview` (turn commit), not on preview.
- `log_index` increments in two places:
  - `perform_roll`: increments immediately on roll and persists to `state.json`.
  - `commit_preview`: increments to the last reserved index if dice were reserved during preview.
- Returned `log_indices` in commit responses are derived by counting lines in `transcript.md` and `changelog.md` after append (line count minus one). These are not stored elsewhere.
- Roll results are linked to transcript by appending a text line in `transcript.md`. If a turn record exists for the current `state.turn`, the roll payload is appended to `sessions/{slug}/turns/{turn}.json`.

### 5C) Locking and concurrency hazards

Current lock is a file `sessions/{slug}/LOCK` with JSON {"owner", "ttl", "claimed_at"}. Invariants it is intended to protect:
- Only one writer mutates `state.json`, `transcript.md`, `changelog.md`, and preview/commit state at a time.
- Preview/commit is serialized so `base_hash` and `base_turn` checks remain valid.

Known hazards:
- Lock TTL is not enforced; stale locks never auto-expire.
- Lock acquisition uses a check-then-create; no atomic file create, so parallel claims can race.
- Many write paths do not check or require the lock (e.g., `perform_roll`, `save_character`, quest edits, NPC edits).
- `perform_roll` is a read-modify-write of `state.log_index` without locking; concurrent rolls can consume the same entropy index.
- Commit writes `state.json`, `transcript.md`, `changelog.md` separately with no transactional boundary; partial writes can occur on crash.
## 6) Current persistence contract (READS/WRITES table)

This table is a compact view; see Section 2 for per-route details and payloads.

| Route | Reads | Writes |
|---|---|---|
| GET /health | none | none |
| GET /schemas/{schema_name} | schemas/{schema_name}.schema.json | none |
| GET /sessions | sessions/*/state.json, sessions/*/LOCK | none |
| POST /sessions | sessions/{template_slug}/**, data/characters/{template_slug}.json | sessions/{slug}/**, sessions/{slug}/state.json, transcript.md, changelog.md, character.json, data/characters/{slug}.json |
| GET /sessions/{slug}/state | sessions/{slug}/state.json | none |
| GET /data/characters/{slug}.json | sessions/{slug}/character.json or data/characters/{slug}.json | none |
| GET /sessions/{slug}/transcript | sessions/{slug}/transcript.md | none |
| GET /sessions/{slug}/changelog | sessions/{slug}/changelog.md | none |
| GET /sessions/{slug}/quests | sessions/{slug}/state.json | none |
| POST/PUT/DELETE /sessions/{slug}/quests | sessions/{slug}/state.json, schemas/quest.schema.json | sessions/{slug}/state.json |
| GET/POST/PUT/DELETE /sessions/{slug}/npc-memory | sessions/{slug}/npc_memory.json | sessions/{slug}/npc_memory.json |
| GET/POST/PUT/DELETE /sessions/{slug}/world/factions | sessions/{slug}/state.json, worlds/{world}/factions.json | worlds/{world}/factions.json |
| GET/POST/PUT/DELETE /sessions/{slug}/world/timeline | sessions/{slug}/state.json, worlds/{world}/timeline.json | worlds/{world}/timeline.json |
| GET /sessions/{slug}/world/rumors | sessions/{slug}/state.json, worlds/{world}/rumors.json | none |
| GET /sessions/{slug}/world/faction-clocks | sessions/{slug}/state.json, worlds/{world}/faction_clocks.json | none |
| GET /sessions/{slug}/turn | sessions/{slug}/turn.md, state.json, LOCK | none |
| POST /sessions/{slug}/lock/claim | none | sessions/{slug}/LOCK |
| DELETE /sessions/{slug}/lock | sessions/{slug}/LOCK | delete LOCK |
| POST /sessions/{slug}/turn/preview | sessions/{slug}/state.json, dice/entropy.ndjson | sessions/{slug}/previews/{preview_id}.json |
| POST /sessions/{slug}/turn/commit | sessions/{slug}/state.json, previews/{id}.json, dice/entropy.ndjson | state.json, transcript.md, changelog.md, delete preview |
| POST /sessions/{slug}/turn/commit-and-narrate | same as commit | state.json, transcript.md, changelog.md, turns/{turn}.json, discovery_log.json (conditional), last_discovery.json (conditional) |
| POST /sessions/{slug}/character | sessions/{slug}/state.json | sessions/{slug}/character.json, data/characters/{slug}.json, sessions/{slug}/state.json |
| GET /sessions/{slug}/player | state.json, character.json/data, turns/*.json, discovery_log.json | none |
| POST /sessions/{slug}/player/opening | state.json, character.json/data, dice/entropy.ndjson | LOCK (create/delete), previews/{id}.json, state.json, transcript.md, changelog.md, turns/{turn}.json, discovery_log.json (conditional), last_discovery.json (conditional) |
| POST /sessions/{slug}/roll (+ legacy) | state.json, character.json/data, dice/entropy.ndjson | state.json, transcript.md, turns/{turn}.json (if exists) |
| POST /sessions/{slug}/player/turn | state.json, dice/entropy.ndjson | LOCK (create/delete), previews/{id}.json, state.json, transcript.md, changelog.md, turns/{turn}.json, discovery_log.json (conditional), last_discovery.json (conditional) |
| GET /entropy | dice/entropy.ndjson | none |
| GET /sessions/{slug}/history/commits | changelog.md | none |
| GET /sessions/{slug}/diff | none (placeholder) | none |
| GET /sessions/{slug}/turns | turns/*.json | none |
| GET /sessions/{slug}/turns/{turn} | turns/{turn}.json | none |
| GET /sessions/{slug}/entropy/history | dice/entropy.ndjson | none |
| GET /llm/config | .dm_llm_config.json | none |
| POST /llm/config | .dm_llm_config.json | .dm_llm_config.json |
| POST /llm/narrate | none | none |
| POST /sessions/{slug}/llm/narrate | state.json, character.json/data | none |
| GET/POST /adventure-hooks* | data/adventure_hooks.json | data/adventure_hooks.json (defaults only) |
| POST /quests/generate | none | none |
| GET /quests/types | none | none |
| GET/POST /sessions/{slug}/npcs/relationships | npc_relationships.json | npc_relationships.json |
| GET/POST /sessions/{slug}/npcs/{npc_id}/dialogue | npc_relationships.json | none |
| GET /sessions/{slug}/npcs/relationship-summary | npc_relationships.json | none |
| GET/POST/PATCH /sessions/{slug}/mood | mood_state.json | mood_state.json (writes on POST/PATCH) |
| GET /sessions/{slug}/mood/suggestions | mood_state.json | none |
| POST /sessions/{slug}/mood/narrate | mood_state.json | none |
| GET /mood/types | none | none |
| GET/POST /sessions/{slug}/discoveries* | discovery_log.json, state.json (log only) | discovery_log.json, last_discovery.json (log only) |
| POST /sessions/{slug}/discoveries/{id}/describe | discovery_log.json | none |
| GET /discoveries/types | none | none |
| GET /sessions/{slug}/auto-save/status | auto_save.json | none |
| POST /sessions/{slug}/auto-save/perform | auto_save.json | saves/*.json, auto_save.json |
| POST /sessions/{slug}/save | none | saves/*.json |
| GET /sessions/{slug}/saves | saves/*.json | none |
| GET /sessions/{slug}/saves/{save_id} | saves/{save_id}.json | none |
| POST /sessions/{slug}/saves/{save_id}/restore | saves/{save_id}.json | none (placeholder) |
| GET /events/{slug} | none | none |
## 7) Proposed storage interfaces (minimal)

Keep API shapes unchanged; migrate persistence behind these interfaces.

### SessionStore

- list_sessions() -> List[SessionSummary]
- create_session(slug: str, template_slug: str) -> str
- get_session(slug: str) -> SessionState
- update_session(slug: str, state: SessionState) -> SessionState
- get_lock(slug: str) -> Optional[LockInfo]
- claim_lock(slug: str, owner: str, ttl: int) -> None
- release_lock(slug: str) -> None

### StateStore

- load_state(slug: str) -> SessionState
- save_state(slug: str, state: SessionState) -> SessionState
- apply_state_patch(slug: str, patch: Dict[str, Any]) -> SessionState

### TurnStore

- load_turn_prompt(slug: str) -> str
- preview_turn(slug: str, request: PreviewRequest) -> PreviewResponse
- commit_preview(slug: str, preview_id: str, lock_owner: Optional[str]) -> CommitResponse
- persist_turn_record(slug: str, record: TurnRecord) -> None
- list_turn_records(slug: str, limit: int) -> List[TurnRecord]
- get_turn_record(slug: str, turn: int) -> TurnRecord

### EntropyStore

- peek(limit: int) -> List[Dict]
- ensure_available(target_index: int) -> None
- load_entry(index: int) -> Dict
- reserve_indices(log_index: int, count: int) -> List[int]
- commit_indices(slug: str, reserved_indices: List[int]) -> int  # returns new log_index

### CharacterStore

- load_character(slug: str) -> Dict[str, Any]
- save_character(slug: str, character: Dict[str, Any], persist_to_shared: bool) -> Dict[str, Any]

### SnapshotStore

- create_save(slug: str, save_name: str, save_type: str) -> Dict[str, Any]
- list_saves(slug: str, limit: int) -> List[Dict[str, Any]]
- get_save(slug: str, save_id: str) -> Optional[Dict[str, Any]]
- restore_save(slug: str, save_id: str) -> Dict[str, Any]

## 8) Minimal SQLite schema (JSON blob-first)

Goals: keep response shapes stable; store complex documents as JSON.

Tables:

1) sessions
- id INTEGER PRIMARY KEY
- slug TEXT UNIQUE NOT NULL
- world TEXT DEFAULT 'default'
- created_at TEXT NOT NULL
- updated_at TEXT NOT NULL

2) session_state
- session_id INTEGER PRIMARY KEY REFERENCES sessions(id)
- state_json TEXT NOT NULL  -- SessionState as JSON
- turn_number INTEGER NOT NULL
- log_index INTEGER NOT NULL
- updated_at TEXT NOT NULL

3) turns
- id INTEGER PRIMARY KEY
- session_id INTEGER NOT NULL REFERENCES sessions(id)
- turn_number INTEGER NOT NULL
- turn_record_json TEXT NOT NULL
- created_at TEXT NOT NULL
- UNIQUE(session_id, turn_number)

4) characters
- id INTEGER PRIMARY KEY
- session_id INTEGER NOT NULL REFERENCES sessions(id)
- slug TEXT NOT NULL
- character_json TEXT NOT NULL
- is_shared INTEGER NOT NULL DEFAULT 0
- created_at TEXT NOT NULL
- updated_at TEXT NOT NULL
- UNIQUE(session_id, slug)

5) entropy
- id INTEGER PRIMARY KEY
- entropy_index INTEGER UNIQUE NOT NULL  -- corresponds to ndjson "i"
- entropy_json TEXT NOT NULL

6) snapshots
- id INTEGER PRIMARY KEY
- session_id INTEGER NOT NULL REFERENCES sessions(id)
- save_id TEXT NOT NULL
- save_type TEXT NOT NULL
- created_at TEXT NOT NULL
- snapshot_json TEXT NOT NULL
- UNIQUE(session_id, save_id)

Optional (future, but keep JSON blobs first):
- discovery_log(session_id, log_json)
- mood_state(session_id, mood_json)
- npc_relationships(session_id, relationships_json)

## 9) Migration approach (disk -> SQLite)

1) Scan `sessions/` and create `sessions` rows for each slug.
2) For each session:
   - Load `state.json` and insert into `session_state` (turn_number from state.turn, log_index from state.log_index).
   - If `turns/*.json` exist, insert each as `turns` rows (JSON blob).
   - If `character.json` exists, insert into `characters` (is_shared=0).
3) Load `data/characters/*.json` into `characters` with is_shared=1 (no session_id or map to a special shared session if needed).
4) Load `dice/entropy.ndjson` into `entropy` (one row per line, keyed by `i`).
5) Load `sessions/{slug}/saves/*.json` into `snapshots`.
6) For auxiliary files (`discovery_log.json`, `mood_state.json`, `npc_relationships.json`), store in JSON blob tables if present.

Idempotency strategy:
- Use upserts keyed by `slug` and `entropy_index` and `(session_id, turn_number)`.
- Re-run migration safely: skip or replace identical JSON blobs based on hash.

## 10) Test plan (additions)

Integration (API shape freeze):
- Golden-response tests for all existing endpoints that return structured JSON (store expected keys, not full text).
- Snapshot tests for `/sessions/{slug}/state`, `/player`, `/turn/preview`, `/turn/commit`, `/turn/commit-and-narrate`.

Unit (atomicity + determinism):
- `commit_preview` writes are atomic: state + transcript + changelog updates behave as a single transaction in the DB path.
- Entropy consumption is consistent: `log_index` increments exactly once per roll/commit and indices are contiguous.
- Concurrency tests: lock owner enforcement and stale preview detection.

## 11) Deployment plan (standalone app)

- Serve built UI from FastAPI (static files in `ui/dist`) in the same process.
- Add environment toggles:
  - `STORAGE_BACKEND=file|sqlite` (default file for now)
  - `DATABASE_URL=sqlite:///...` (or local file path)
- On startup, ensure schema (migrations or `CREATE TABLE IF NOT EXISTS` plus version table).
- Optional minimal auth for friends: single shared access token with header check (e.g., `X-API-Key`).

## 12) Concrete refactor plan

1) Add storage interface layer (adapters for file and sqlite).
2) Implement SQLite adapters with transaction boundaries for preview/commit and roll.
3) Add migration script: disk -> sqlite, with idempotent re-run.
4) Wire backend selection via `STORAGE_BACKEND` and `DATABASE_URL`.
5) Serve UI build from FastAPI (single-process deploy).
