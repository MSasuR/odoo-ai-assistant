from api.providers import get_provider
from api.rag import store
from api.rag.ingest import embed_model_id

DEFAULT_K = 4


def retrieve(query: str, k: int = DEFAULT_K, provider_name: str | None = None) -> list[dict]:
    provider = get_provider(provider_name)
    vector = provider.embed([query], kind="query")[0]
    return store.search(vector, embed_model_id(provider), k)
