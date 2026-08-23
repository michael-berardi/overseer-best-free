# overseer-free-best

Resolve the **best free chat model** on [OpenRouter](https://openrouter.ai) — dynamically, every time you ask.

Free models on OpenRouter change constantly: promo lanes appear and vanish, rate limits hit, new models land weekly. Hardcoding a free model slug means your app breaks within days. `overseer-free-best` queries the live model catalog, filters it down to genuinely usable free chat backends, ranks them, and hands you an ordered best-first list so you can fall through on rate limits instead of failing.

Zero dependencies. Standard library only. Python 3.9+.

## Why not just use a fixed free model?

You can — until it disappears or gets rate-limited. And why not `openrouter/free` (OpenRouter's own free router)? It picks a free model **at random**, which is great for availability but says nothing about capability. `openrouter/auto` routes by market spend, which favors paid models. This project sits in between: *best available free model, re-evaluated automatically*.

## Install

```bash
pip install overseer-free-best
```

Or vendor the single module — [`src/overseer_free_best/core.py`](src/overseer_free_best/core.py) is self-contained.

## Usage

### Library

```python
from overseer_free_best import CachedResolver

resolver = CachedResolver(ttl_seconds=3600)
models = resolver.get(limit=3)   # best-first, refreshed from the catalog at most hourly

primary = models[0].id           # e.g. "stealth/ox-alpha"
fallbacks = [m.id for m in models[1:]]
```

Build a fallback chain from the ranking: try `models[0]`, fall through to `models[1]`, `models[2]` on rate limits or errors. The cache serves the previous ranking if the catalog is temporarily unreachable, so callers always have a chain.

### Command line

```bash
python -m overseer_free_best             # top 3, plain text
python -m overseer_free_best --top 5 --json
```

```text
1. stealth/ox-alpha  (context=1048576)
2. nvidia/nemotron-3.5-lightning:free  (context=1000000)
3. nvidia/nemotron-3-ultra-550b-a55b:free  (context=1000000)
```

(Example output — the actual ranking changes as the catalog changes.)

## How models are ranked

A catalog entry is eligible when all of the following hold:

1. **Truly free** — prompt *and* completion price are zero.
2. **Chat-shaped** — output modality is text only (music/image generators and video models are out).
3. **A real endpoint** — router/metadata namespaces like `openrouter/*` are excluded.
4. **Conversational** — classifiers and utility endpoints (content-safety, embeddings, moderation, transcription) are excluded by pattern.

Eligible models are ranked by context length (larger first), then release recency, then count of supported parameters (tools, structured outputs, reasoning).

## Trust and safety notes

- The catalog endpoint is public; no API key is required for ranking. You only need your own key when calling the models themselves.
- Free tiers are rate-limited upstream. Treat every result as one lane in a fallback chain, never as a single point of failure.
- No telemetry, no network calls beyond the public catalog fetch.

## Development

```bash
python -m unittest discover -s tests -v
```

Tests run fully offline against a recorded catalog fixture.

## License

[MIT](LICENSE)
