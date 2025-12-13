# Repo-as-Game: Solo D&D-Style Adventure

This repository is a fully offline, file-driven game loop. Any code agent (or human) acts as the Dungeon Master (DM) by following the file protocol in `PROTOCOL.md`. Game state, narration, and dice are stored in the repo for deterministic, auditable play.

## Quickstart
1. `git init && git add . && git commit -m "init: repo DM MVP"`
2. Edit `sessions/example-rogue/turn.md` with: `Start a scene at the city gate.`
3. Instruct your code agent: `Act as DM per PROTOCOL.md for example-rogue.`

## Create a New Character Session
Copy `sessions/example-rogue` to a new slug folder and duplicate `data/characters/example-rogue.json` with the same slug. Reset `state.json` to turn `0`, set your starting location and HP, and clear `transcript.md` and `changelog.md` except for an initialization entry.

## Dice
Deterministic entropy lives in `dice/entropy.ndjson`. Each roll consumes the next unused entry, tracked by its `i` index. See `dice/README.md` for mapping rules and how to extend the pool.

## Licenses and SRD Notice
Open content follows the SRD and Creative Commons terms documented in `LICENSES/`. Read `NOTICE_SRD.md` for attribution details.
