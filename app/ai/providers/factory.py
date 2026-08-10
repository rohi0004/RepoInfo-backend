"""Provider factory keyed on `AIProviderEnum`. OpenRouter reuses the OpenAI client
with a different base URL, which is exactly how the OpenRouter API surfaces itself.
"""

from functools import lru_cache

from app.ai.providers.anthropic_provider import AnthropicProvider
from app.ai.providers.base import AIProvider
from app.ai.providers.gemini_provider import GeminiProvider
from app.ai.providers.ollama_provider import OllamaProvider
from app.ai.providers.openai_provider import OpenAIProvider
from app.core.config import settings
from app.models.enums import AIProviderEnum


@lru_cache(maxsize=8)
def get_provider(provider: AIProviderEnum | None = None) -> AIProvider:
    kind = provider or AIProviderEnum(settings.DEFAULT_AI_PROVIDER)
    if kind == AIProviderEnum.OPENAI:
        return OpenAIProvider()
    if kind == AIProviderEnum.CLAUDE:
        return AnthropicProvider()
    if kind == AIProviderEnum.GEMINI:
        return GeminiProvider()
    if kind == AIProviderEnum.OLLAMA:
        return OllamaProvider()
    if kind == AIProviderEnum.OPENROUTER:
        return OpenAIProvider(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            name="openrouter",
        )
    raise ValueError(f"Unknown provider: {kind}")
