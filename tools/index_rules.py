import json
from collections import Counter
from pathlib import Path


def tokenize(text):
    return [t.strip(".,;:!?").lower() for t in text.split() if t.strip()]


def main():
    rules_dir = Path("data/rules")
    docs = []
    meta = []
    vocab = Counter()
    for path in sorted(rules_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        tokens = tokenize(text)
        docs.append({"file": str(path), "tokens": tokens})
        vocab.update(tokens)
        meta.append({"file": str(path), "lines": len(text.splitlines())})

    out_dir = Path("rules_index")
    out_dir.mkdir(exist_ok=True)
    json.dump(vocab, open(out_dir / "vocab.json", "w", encoding="utf-8"), indent=2)
    json.dump(meta, open(out_dir / "docmeta.json", "w", encoding="utf-8"), indent=2)
    json.dump(docs, open(out_dir / "docs.json", "w", encoding="utf-8"), indent=2)

    print("Indexed", len(docs), "documents")


if __name__ == "__main__":
    main()
