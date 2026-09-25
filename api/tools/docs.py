from api.auth import UserContext
from api.rag.retriever import retrieve
from api.tools.base import tool

# Chosen between the highest off-topic score (0.66) and the lowest relevant score (0.69) measured
# by `python -m evals.rag_eval` on the sample corpus. That margin is thin and tuned in-sample on
# 26 questions: re-calibrate whenever the corpus or the embedding model changes.
MIN_SCORE = 0.68


@tool(
    "search_documents",
    "Search the internal documents (procedures, policies, guides) and return the most relevant "
    "passages with their source. Use it for 'how do I...' questions, policies and processes. "
    "Always cite the source in the answer.",
    {"type": "object", "properties": {
        "query": {"type": "string", "description": "The question or topic to look up, in natural language"}},
     "required": ["query"]},
)
def search_documents(ctx: UserContext, args: dict) -> dict:
    hits = [h for h in retrieve(args["query"]) if h["score"] >= MIN_SCORE]
    return {
        "results": [
            {"source": h["source"], "section": h["heading"], "score": round(float(h["score"]), 3),
             "text": h["content"]}
            for h in hits
        ],
        "note": "" if hits else "No relevant documents found; do not invent an answer.",
    }
