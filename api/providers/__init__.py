from api.config import settings
from api.providers.base import Provider


def get_provider(name: str | None = None) -> Provider:
    name = name or settings.llm_provider
    if name == "gemini":
        from api.providers.gemini import GeminiProvider
        return GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    if name == "openai":
        from api.providers.openai import OpenAIProvider
        return OpenAIProvider(settings.openai_api_key, settings.openai_model)
    raise ValueError(f"Unknown provider: {name}")
