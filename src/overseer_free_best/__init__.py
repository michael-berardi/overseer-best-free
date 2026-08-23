"""overseer-free-best: dynamic resolution of the best free OpenRouter model."""

from .core import (
    MODELS_URL,
    CachedResolver,
    FreeModel,
    best_free_models,
    fetch_catalog,
    is_eligible,
    rank_key,
    resolve_free_models,
)

__all__ = [
    "MODELS_URL",
    "CachedResolver",
    "FreeModel",
    "best_free_models",
    "fetch_catalog",
    "is_eligible",
    "rank_key",
    "resolve_free_models",
]

__version__ = "0.1.0"
