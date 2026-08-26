<div align="center">

# overseer-best-free

**Resolve the best free chat model on [OpenRouter](https://openrouter.ai) — dynamically, every time you ask.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](pyproject.toml)
[![Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)](#why-not-just-use-a-fixed-free-model)

</div>

---

Free models on OpenRouter change constantly: promo lanes appear and vanish, rate limits hit, new models land weekly. Hardcoding a free model slug means your app breaks within days.

`overseer-best-free` queries the live model catalog, filters it down to genuinely usable free chat backends, ranks them, and hands you an **ordered best-first list** so you can fall through on rate limits instead of failing.

- Zero dependencies — standard library only
- Python 3.9+
- Library API *and* CLI
- Offline-safe caching: serves the last known good ranking if the catalog is unreachable
- Built for agents and bots that must never hard-fail on a dead free tier

## Why not just use a fixed free model?

You can — until it disappears or gets rate-limited.

| Approach | Behavior |
|---|---|
| Hardcoded free slug | Breaks when the lane vanishes or is rate-limited |
| `openrouter/free` | Official free router, but picks **randomly** |
| `openrouter/auto` | Routes by market spend — favors paid models |
| **`overseer-best-free`** | **Best-ranked free models, re-evaluated automatically** |

## Install

```bash
pip install git+https://github.com/michael-berardi/overseer-best-free.git
```

Or vendor the single module — [`src/overseer_best_free/core.py`](src/overseer_best_free/core.py) is self-contained.

## Usage

### Library

```python
from overseer_best_free import CachedResolver

resolver = CachedResolver(ttl_seconds=3600)
models = resolver.get(limit=3)   # best-first; refetched at most hourly

primary = models[0].id           # e.g. "thinkingmachines/inkling-small:free"
fallbacks = [m.id for m in models[1:]]
```

Build a fallback chain from the ranking: try `models[0]`, fall through to `models[1]`, `models[2]` on rate limits or errors. The cache serves the previous ranking if the catalog is temporarily unreachable, so callers always have a chain.

### Command line

```bash
python -m overseer_best_free             # top 3, plain text
python -m overseer_best_free --top 5 --json
```

```text
1. thinkingmachines/inkling-small:free  (context=1048576)
2. thinkingmachines/inkling:free  (context=1048576)
3. minimax/minimax-m3:free  (context=1048576)
```

*(Example output — the actual ranking changes as the catalog changes.)*

## Drop-in fallback chain

A complete client with no dependencies beyond this package. It tries the best
free model first and walks down the ranking on any failure or rate limit:

```python
import json, time, urllib.request
from overseer_best_free import CachedResolver

resolver = CachedResolver(ttl_seconds=1800)

def chat(messages, max_retries=3):
    for model in resolver.get(limit=max_retries):
        request = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            method="POST",
        )
        request.add_header("Authorization", "Bearer YOUR_OPENROUTER_KEY")
        request.add_header("Content-Type", "application/json")
        request.data = json.dumps({"model": model.id, "messages": messages}).encode()
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except Exception:
            continue   # rate-limited or down; try the next free model
    raise RuntimeError("all free models exhausted")
```

Need tool calling or structured outputs? Filter on what each model supports:

```python
candidates = [m for m in resolver.get(limit=20) if "tools" in m.supported_parameters]
```

## How models are ranked

A catalog entry is eligible when all of the following hold:

1. **Truly free** — prompt *and* completion price are zero.
2. **Chat-shaped** — output modality is text only (music/image generators and video models are out).
3. **A real endpoint** — router/metadata namespaces like `openrouter/*` are excluded.
4. **Conversational** — classifiers and utility endpoints (content-safety, embeddings, moderation, transcription) are excluded by pattern.

Eligible models are ranked by context length (larger first), then release recency, then count of supported parameters (tools, structured outputs, reasoning).

## Trust and safety

- The catalog endpoint is public; no API key is needed for ranking. You only need your own key when calling the models themselves.
- Free tiers are rate-limited upstream. Treat every result as one lane in a fallback chain, never as a single point of failure.
- No telemetry, and the only network call is the public catalog fetch.

## Honest limits

- Ranking is metadata-driven (price, context, recency, features). It does not
  measure live latency or quality — pair it with your own health checks if you
  need those guarantees.
- Free lanes are offered at providers' discretion and can disappear without
  notice. That is exactly why this package re-resolves every time instead of
  trusting yesterday's answer.

## Development

```bash
python -m unittest discover -s tests -v
```

Tests run fully offline against a recorded catalog fixture. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © Implose Cybernetics
