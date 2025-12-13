import argparse
import json
from collections import Counter
from pathlib import Path


def tokenize(text):
    return [t.strip(".,;:!?").lower() for t in text.split() if t.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="+")
    args = parser.parse_args()
    query_tokens = tokenize(" ".join(args.query))

    out_dir = Path("rules_index")
    docs = json.load(open(out_dir / "docs.json", "r", encoding="utf-8"))
    meta = json.load(open(out_dir / "docmeta.json", "r", encoding="utf-8"))

    scores = []
    q_count = Counter(query_tokens)
    for doc in docs:
        doc_count = Counter(doc["tokens"])
        score = sum(doc_count.get(tok, 0) * q_count.get(tok, 1) for tok in query_tokens)
        scores.append(score)

    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:5]
    for idx in top_indices:
        print(f"{meta[idx]['file']}: score={scores[idx]} lines=1-{meta[idx]['lines']}")


if __name__ == "__main__":
    main()
