"""Dynamic resolution of the best free model on OpenRouter.

Queries the public OpenRouter ``/api/v1/models`` catalog, keeps models that
are completely free (zero prompt *and* completion cost) and usable as chat
backends, ranks them, and exposes an ordered best-first list so callers can
build fallback chains that survive per-model rate limits.

Zero runtime dependencies: standard library only.
"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.request
from dataclasses import dataclass, field

MODELS_URL = "https://openrouter.ai/api/v1/models"

#: Namespaces that are routers/metadata rather than real model endpoints.
_EXCLUDED_NAMESPACES = frozenset({"openrouter"})

#: Substrings that mark utility endpoints (classifiers, embedders, ...) which
#: are technically free but useless as conversational backends.
_NON_CHAT_PATTERN = re.compile(
    r"safety|guard|moderat|embed|rerank|whisper|tts|transcri|censor",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FreeModel:
    """A free OpenRouter model with the fields used for ranking."""

    id: str
    name: str
    context_length: int
    created: int
    supported_parameters: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "context_length": self.context_length,
            "created": self.created,
            "supported_parameters": list(self.supported_parameters),
        }


def _zero(value) -> bool:
    try:
        return float(value) == 0.0
    except (TypeError, ValueError):
        return False


def _output_is_text(model: dict) -> bool:
    outputs = (model.get("architecture") or {}).get("output_modalities") or []
    return outputs == ["text"]


def is_eligible(model: dict) -> bool:
    """True when a catalog entry can serve as a free chat backend."""
    pricing = model.get("pricing") or {}
    if not (_zero(pricing.get("prompt")) and _zero(pricing.get("completion"))):
        return False
    if not _output_is_text(model):
        return False
    namespace = model.get("id", "").split("/", 1)[0]
    if namespace.lower() in _EXCLUDED_NAMESPACES:
        return False
    haystack = f"{model.get('id', '')} {model.get('name', '')}"
    if _NON_CHAT_PATTERN.search(haystack):
        return False
    return True


def rank_key(model: dict):
    """Sort key: bigger context first, then newer, then more features."""
    return (
        -(model.get("context_length") or 0),
        -(model.get("created") or 0),
        -len(model.get("supported_parameters") or []),
    )


def to_free_model(model: dict) -> FreeModel:
    params = model.get("supported_parameters") or []
    created = model.get("created") or 0
    return FreeModel(
        id=model["id"],
        name=model.get("name", model["id"]),
        context_length=int(model.get("context_length") or 0),
        created=int(created),
        supported_parameters=tuple(params),
    )


def fetch_catalog(timeout: float = 10.0) -> list[dict]:
    """Fetch the raw OpenRouter model catalog."""
    request = urllib.request.Request(MODELS_URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    return payload.get("data", [])


def resolve_free_models(catalog: list[dict]) -> list[FreeModel]:
    """Rank an already-fetched catalog into a best-first free-model list."""
    eligible = [m for m in catalog if is_eligible(m)]
    eligible.sort(key=rank_key)
    return [to_free_model(m) for m in eligible]


def best_free_models(catalog: list[dict], limit: int = 3) -> list[FreeModel]:
    """Best-first slice of the ranked free models from a fetched catalog."""
    return resolve_free_models(catalog)[:limit]


class CachedResolver:
    """TTL cache around :func:`resolve_free_models` for long-running processes.

    Serves the previous ranking when a refresh fails, so transient network or
    API problems never leave callers without a usable model chain.
    """

    def __init__(self, ttl_seconds: float = 3600.0, timeout: float = 10.0):
        self.ttl_seconds = ttl_seconds
        self.timeout = timeout
        self._lock = threading.Lock()
        self._models: list[FreeModel] | None = None
        self._expires_at = 0.0

    def get(self, limit: int = 3, refresh: bool = False) -> list[FreeModel]:
        with self._lock:
            now = time.monotonic()
            fresh = self._models is not None and now < self._expires_at
            if fresh and not refresh:
                return self._models[:limit]
            try:
                self._models = resolve_free_models(fetch_catalog(timeout=self.timeout))
                self._expires_at = now + self.ttl_seconds
            except Exception:
                if self._models is None:
                    raise
                # Serve stale ranking; retry after a short grace period.
                self._expires_at = now + min(self.ttl_seconds, 300.0)
            return self._models[:limit]
