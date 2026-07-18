from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_MAX_TOKENS = 60_000


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChatResult:
    content: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    def usage_dict(self) -> dict[str, int | None]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True)
class ChatClient:
    endpoint: str
    api_key: str
    model: str
    provider_name: str

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        json_mode: bool = False,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> str:
        return self.complete_with_usage(
            messages,
            temperature=temperature,
            json_mode=json_mode,
            max_tokens=max_tokens,
        ).content

    def complete_with_usage(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        json_mode: bool = False,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> ChatResult:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "VibeRank/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"{self.provider_name} returned HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ProviderError(f"Could not reach {self.provider_name}: {exc}") from exc
        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"Unexpected {self.provider_name} response: {result}") from exc
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        usage = result.get("usage") or {}
        return ChatResult(
            content=str(content),
            prompt_tokens=_optional_int(usage.get("prompt_tokens")),
            completion_tokens=_optional_int(usage.get("completion_tokens")),
            total_tokens=_optional_int(usage.get("total_tokens")),
        )


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def mistral_client(model: str | None = None) -> ChatClient:
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        raise ProviderError("MISTRAL_API_KEY is not set")
    return ChatClient(
        endpoint="https://api.mistral.ai/v1/chat/completions",
        api_key=key,
        model=model or os.environ.get("MISTRAL_GRADER_MODEL", "mistral-medium-3.5"),
        provider_name="Mistral",
    )


def openrouter_client(model: str) -> ChatClient:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise ProviderError("OPENROUTER_API_KEY is not set")
    return ChatClient(
        endpoint="https://openrouter.ai/api/v1/chat/completions",
        api_key=key,
        model=model,
        provider_name="OpenRouter",
    )
