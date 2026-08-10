"""Provider-agnostic chat and embedding contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal


@dataclass(slots=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(slots=True)
class ChatUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


@dataclass(slots=True)
class ChatChunk:
    delta: str = ""
    done: bool = False
    finish_reason: str | None = None
    usage: ChatUsage | None = None
    raw: dict = field(default_factory=dict)


class AIProvider(ABC):
    name: str
    default_model: str

    @abstractmethod
    async def stream_chat(
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        """Yields incremental chunks; final chunk has done=True + usage populated."""

    @abstractmethod
    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> tuple[str, ChatUsage]:
        """Non-streaming convenience: full completion + usage in one shot."""

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:  # noqa: ARG002
        raise NotImplementedError(f"{self.name} does not implement embeddings.")
