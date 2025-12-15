# Delivery plan: repo-centric DM to full application

## Goals
- Preserve deterministic, auditable gameplay while moving from file-only workflows to a service + UI.
- Expose the existing rules/entropy/state machinery through stable APIs that a frontend can consume.
- Provide a clear MVP path first, then graduate to a robust UI that covers the full rules surface.

## Guiding assumptions
- Keep the existing schemas/entropy model as the source of truth (see `PROTOCOL.md`, `schemas/`, `dice/`).
- Prefer additive changes: a service layer that can still read/write the current repo assets, so the CLI flow remains usable.
- Determinism and auditability (lock files, changelog, entropy indices) are non-negotiable requirements.

## Milestones and scope
### M0: Project setup (1–2 sprints)
- Choose service stack (Python FastAPI or similar) colocated with repo for schema reuse.
- Add CI for lint/test/type checks; containerize the service for local dev.
- Define environment config for repo path, entropy location, and commit/audit options.

### M1: Core backend service (2–3 sprints)
- Implement adapters for key assets: state, transcript, changelog, entropy (`dice/`), prompts, lock files.
- Recreate the turn loop as a service endpoint/job: lock acquisition, prompt consumption, deterministic dice use, state/transcript updates, and changelog entries that mirror `PROTOCOL.md` expectations.
- Add validation against existing JSON schemas before writes; reject invalid or out-of-order entropy usage.
- Provide read-only endpoints to inspect state, transcript, quests, factions, rumors, and mysteries.

### M2: Deterministic randomness pipeline (1 sprint)
- Centralize entropy management: API to preview remaining dice, reserve/consume indices, and log usage.
- Add audit logging to persist roll context (who, when, what) alongside the changelog file.
- Create tooling to regenerate/append entropy files safely without breaking determinism guarantees.

### M3: Minimal UI (2–3 sprints)
- Build a session selector + dashboard UI that mirrors the current `dashboard.md` links.
- Views: prompt/turn console, transcript reader, state/character inspector, quest tracker, rumor/mystery browser.
- Actions: advance turn (calls turn endpoint), submit player choices, view dice history, download audit logs.
- Add authentication/authorization suitable for small groups (session-based or token), with per-session locks visible in the UI.

### M4: Automation endpoints & background jobs (2–3 sprints)
- Wrap existing CLI tools (`exploration/`, `encounters/`, `loot/`, `downtime/`, `quests/`) as API endpoints or worker jobs with progress events.
- Standardize responses so the UI can show previews, diffs, and confirmations before commits are written.
- Introduce rollback/retry hooks if a job fails schema validation or lock contention is detected.

### M5: Robust UI expansion (3–4 sprints)
- Rich editors for quests, factions, clocks, timelines, NPCs, allies, snapshots, and locations with schema-aware forms.
- Visualization for clocks/timelines and map/location relationships; search and filter across artifacts.
- Inline diffs for pending changes before commit; display audit trails and entropy usage per action.
- Accessibility and responsive layout polish; instrument usage analytics to guide future iterations.

### M6: Release hardening (1–2 sprints)
- End-to-end tests that simulate turns, automation jobs, and UI actions against fixture data.
- Performance profiling on large worlds and long transcripts; add caching where safe without breaking determinism.
- Security review for API auth, file-system access controls, and audit log integrity.

## Workstream owners & cadences
- **Backend lead:** APIs, entropy pipeline, validation, jobs, audit logging.
- **Frontend lead:** UI architecture, design system, state management, deterministic roll visualizations.
- **DevOps:** CI/CD, container images, environment provisioning, repo snapshot/backup strategy.
- Weekly triage against schemas/protocol updates; align with any new rules content added to the repo.

## Acceptance for MVP (end of M3)
- Turn loop callable via API with lock handling and deterministic dice; state/transcript/changelog updates persist to repo.
- UI delivers session selection, prompt/turn console, transcript viewer, and basic inspectors for state/quests/factions/rumors.
- Audit logs clearly show entropy usage and changes per action; validation prevents schema drift.

## Acceptance for “robust UI” (end of M5)
- Feature-complete coverage of rule tools and world data with schema-aware editing and visualizations.
- Safe automation flows with previews/diffs, retry/rollback, and explicit entropy tracking per operation.
- Users can play full campaigns via the UI without touching repo files directly, while deterministic/auditable guarantees remain intact.
