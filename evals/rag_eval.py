"""Evaluate the retriever: hit@1, hit@k, MRR, and how well the score threshold separates
in-scope from out-of-scope questions.

    python -m evals.rag_eval [--provider gemini] [--k 4] [--json]

Run it after `python -m api.rag.ingest corpus`.
"""
import argparse
import json
import statistics
from pathlib import Path

import yaml

from api.rag.retriever import retrieve
from api.tools.docs import MIN_SCORE

GOLDEN = Path(__file__).with_name("rag_golden.yaml")


def is_hit(hit: dict, expect: list[dict]) -> bool:
    return any(hit["source"].endswith(e["source"]) and e["section"].lower() in hit["heading"].lower()
               for e in expect)


def run(provider: str | None = None, k: int = 4) -> dict:
    g = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))
    ranks, in_top, misses = [], [], []
    for item in g["in_scope"]:
        hits = retrieve(item["q"], k=k, provider_name=provider)
        rank = next((i + 1 for i, h in enumerate(hits) if is_hit(h, item["expect"])), None)
        ranks.append(rank)
        in_top.append(float(hits[0]["score"]))
        if rank is None:
            misses.append(item["q"])
    out_top = [float(retrieve(q, k=1, provider_name=provider)[0]["score"]) for q in g["out_of_scope"]]
    n = len(ranks)
    return {
        "in_scope_questions": n,
        "out_of_scope_questions": len(out_top),
        "hit@1": round(sum(r == 1 for r in ranks) / n, 3),
        f"hit@{k}": round(sum(r is not None for r in ranks) / n, 3),
        "mrr": round(sum(1 / r for r in ranks if r) / n, 3),
        "threshold": MIN_SCORE,
        "answered_at_threshold": round(sum(s >= MIN_SCORE for s in in_top) / n, 3),
        "rejected_at_threshold": round(sum(s < MIN_SCORE for s in out_top) / len(out_top), 3),
        "in_scope_top1_score": {"min": round(min(in_top), 3), "median": round(statistics.median(in_top), 3)},
        "out_scope_top1_score": {"max": round(max(out_top), 3), "median": round(statistics.median(out_top), 3)},
        "misses": misses,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=None)
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON")
    a = ap.parse_args()
    result = run(a.provider, a.k)
    if a.json:
        print(json.dumps(result, indent=2))
    else:
        for key, val in result.items():
            print(f"{key}: {val}")
