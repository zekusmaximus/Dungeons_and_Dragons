# Deterministic Dice

All randomness is pulled from `entropy.ndjson`. Each line is NDJSON:

```
{"i":1,"d20":[14,2,19,7,5,11,3,9,1,18],"d100":[42,7,88,13,56],"bytes":"..."}
```

- `i` is the unique index for that line.
- `d20` provides a reusable queue of d20 values for smaller dice.
- `d100` provides percentile pulls.
- `bytes` is extra entropy for future tools.

## Mapping Rules
- **1d20:** pop the next number from `d20`.
- **d100:** pop the next number from `d100`.
- **Other dice (dX):** pull from `d20` and map with `1 + ((n - 1) % X)`. Example: pulling `14` for a d6 becomes `1 + ((14 - 1) % 6) = 3`.
- **Multiple dice (e.g., 2d6+3):** pull once per die. For 2d6, take two `d20` numbers, map each to d6, sum, then add modifiers.

Always record the `i` index for each expression in `changelog.md` and in commit messages. Never reuse an index. Consume additional lines if you exhaust the arrays on the current line. If the file runs out, extend it with:

```
python dice/verify_dice.py --extend 5000
```

## Deterministic Extension
`verify_dice.py` appends new lines deterministically based on the last `i` and a fixed seed, ensuring reproducible runs.
