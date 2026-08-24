"""Offline tests for the ranking and caching logic."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from overseer_best_free import CachedResolver, best_free_models, is_eligible

FIXTURE = Path(__file__).parent / "fixtures" / "models_sample.json"


def load_catalog() -> list[dict]:
    return json.loads(FIXTURE.read_text())


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()
        self.ranked = best_free_models(self.catalog, limit=10)

    def test_paid_model_excluded(self):
        ids = [m.id for m in self.ranked]
        self.assertNotIn("acme/paid-model", ids)

    def test_audio_output_excluded(self):
        ids = [m.id for m in self.ranked]
        self.assertNotIn("google/lyria-3-pro-preview", ids)

    def test_router_namespace_excluded(self):
        ids = [m.id for m in self.ranked]
        self.assertNotIn("openrouter/free", ids)

    def test_utility_models_excluded(self):
        ids = [m.id for m in self.ranked]
        self.assertNotIn("nvidia/nemotron-3.5-content-safety:free", ids)
        self.assertNotIn("acme/embed-v2:free", ids)

    def test_ordering_context_then_recency(self):
        self.assertEqual(self.ranked[0].id, "stealth/ox-alpha")
        self.assertEqual(self.ranked[1].id, "nvidia/nemotron-3.5-lightning:free")
        # ultra (262k) ranks above small-old (4096) despite being older
        self.assertEqual(self.ranked[2].id, "nvidia/nemotron-3-ultra-550b-a55b:free")
        self.assertEqual(self.ranked[-1].id, "old/small-free:free")

    def test_limit(self):
        self.assertEqual(len(best_free_models(self.catalog, limit=2)), 2)

    def test_eligibility_on_malformed_entries(self):
        self.assertFalse(is_eligible({}))
        self.assertFalse(is_eligible({"id": "x/y", "pricing": None}))


class CacheTests(unittest.TestCase):
    def test_serves_stale_on_fetch_failure(self):
        resolver = CachedResolver(ttl_seconds=0)
        with mock.patch("overseer_best_free.core.fetch_catalog", return_value=load_catalog()):
            first = resolver.get(limit=1)
        with mock.patch(
            "overseer_best_free.core.fetch_catalog", side_effect=RuntimeError("down")
        ):
            second = resolver.get(limit=1)  # expired cache + failed refresh -> stale
        self.assertEqual(first[0].id, second[0].id)

    def test_raises_when_never_populated(self):
        resolver = CachedResolver()
        with mock.patch(
            "overseer_best_free.core.fetch_catalog", side_effect=RuntimeError("down")
        ):
            with self.assertRaises(RuntimeError):
                resolver.get()


if __name__ == "__main__":
    unittest.main()


class InputModalityTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()
        self.ranked = {m.id: m for m in best_free_models(self.catalog, limit=10)}

    def test_image_input_flag_exposed(self):
        # fixture ox-alpha entry has no input_modalities key -> defaults empty
        self.assertFalse(self.ranked["stealth/ox-alpha"].supports_image_input)

    def test_as_dict_round_trips_modalities(self):
        m = self.ranked["stealth/ox-alpha"]
        d = m.as_dict()
        self.assertIn("input_modalities", d)
        self.assertIsInstance(d["input_modalities"], list)


class NegativeCacheTests(unittest.TestCase):
    def test_empty_result_cached_briefly(self):
        resolver = CachedResolver(ttl_seconds=3600)
        with mock.patch(
            "overseer_best_free.core.fetch_catalog",
            return_value=[{"id": "x/y", "pricing": {"prompt": "1", "completion": "1"}}],
        ):
            first = resolver.get()
        self.assertEqual(first, [])
        with mock.patch(
            "overseer_best_free.core.fetch_catalog",
            return_value=load_catalog(),
        ) as refetch:
            second = resolver.get()  # still within negative-cache TTL
        self.assertEqual(second, [])
        refetch.assert_not_called()
