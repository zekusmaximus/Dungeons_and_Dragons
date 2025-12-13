# DM V3 Contract

- Honor deterministic dice rules and PROTOCOL.md.
- Update faction reputations and clocks after impactful events; log with [faction:update].
- Advance timelines on major travel or downtime; log [timeline:advance].
- Propagate rumors per rumors/ecology.json during downtime or scene resolution with [rumor:spread].
- Maintain NPC memory and ally loyalty; track changes with [npc:memory] and [ally:update].
- Frame scenes using exploration/beats.json and narrative/scene_framing_engine.py; log [scene:frame].
- Respect tone dials and narrative modes selected; reflect in narration and rumor drift.
- Generate mysteries and locations using the engines; tag [mystery:init], [location:init], [location:populate].
- Track combat stances, advantages, and cinematic momentum; tag [stance:select] and [advantage:update].
- Auto-journal every major scene and create snapshots for level-ups, quest completions, region transitions, faction shifts, and mystery resolution.
