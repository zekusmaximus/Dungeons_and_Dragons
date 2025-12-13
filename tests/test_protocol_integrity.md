# Protocol Integrity Checklist

- [ ] LOCK file prevents concurrent turns; DM creates/removes `sessions/<slug>/LOCK` per turn.
- [ ] DM reads only allowlisted paths (`sessions/<slug>`, `data`, `PROMPTS`, `schemas`, `dice`).
- [ ] Every turn updates `state.json`, appends to `transcript.md`, appends one JSON line to `changelog.md`, and replaces `turn.md` with a new prompt.
- [ ] Commit message format: `dm(<slug>): <scene summary>; rolls=[<expr>=<result>@<entropy_index> ...]; hp:-3 goblin arrow; loc=Gate-01`.
- [ ] Dice consumption uses next unused line in `dice/entropy.ndjson`; indices recorded in changelog and commit message.
- [ ] Schema validation passes for `state.json`, `changelog.md` entries, and character data.
