from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from typing import Any


DEFAULT_IRT_URL = "https://aibenchmarks.dev/data/unified-irt.json"


@dataclass(frozen=True)
class KnownModelElo:
    model: str
    provider: str
    elo: float
    theta: float | None
    se_elo: float | None
    num_benchmarks: int
    effective_benchmarks: float | None
    rank: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "provider": self.provider,
            "elo": self.elo,
            "theta": self.theta,
            "se_elo": self.se_elo,
            "num_benchmarks": self.num_benchmarks,
            "effective_benchmarks": self.effective_benchmarks,
            "rank": self.rank,
        }


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def parse_known_models(payload: dict[str, Any]) -> list[KnownModelElo]:
    models = []
    for raw in payload.get("models", []):
        if not raw.get("model") or raw.get("elo") is None:
            continue
        models.append(
            KnownModelElo(
                model=str(raw["model"]),
                provider=str(raw.get("provider", "")),
                elo=float(raw["elo"]),
                theta=_optional_float(raw.get("theta")),
                se_elo=_optional_float(raw.get("se_elo")),
                num_benchmarks=int(raw.get("num_benchmarks", 0)),
                effective_benchmarks=_optional_float(raw.get("effective_benchmarks")),
                rank=_optional_int(raw.get("rank")),
            )
        )
    return sorted(models, key=lambda model: (model.rank or 10**9, -model.elo))


@lru_cache(maxsize=2)
def fetch_known_models(url: str = DEFAULT_IRT_URL) -> tuple[KnownModelElo, ...]:
    request = urllib.request.Request(url, headers={"User-Agent": "VibeRank/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load leaderboard Elo data from {url}: {exc}") from exc
    return tuple(parse_known_models(payload))


def select_known_models(
    models: tuple[KnownModelElo, ...],
    *,
    limit: int = 200,
    minimum_benchmarks: int = 5,
    include_humans: bool = False,
) -> list[KnownModelElo]:
    selected = [
        model
        for model in models
        if model.num_benchmarks >= minimum_benchmarks
        and (include_humans or model.provider.lower() != "human")
    ]
    return selected[: max(1, min(limit, 1000))]

