"""Offline tests for the ranking and caching logic."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from overseer_best_free import CachedResolver, best_free_models, is_eligible
from overseer_best_free.core import to_free_model

FIXTURE = Path(__file__).parent / "fixtures" / "models_sample.json"


def load_catalog() -> list[dict]:
    return json.loads(FIXTURE.read_text())


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()
        self.ranked = best_free_models(self.catalog, limit=10)

    def test_paid_model_excluded(self):
        # largest context in the fixture, still excluded for being paid
        ids = [m.id for m in self.ranked]
        self.assertNotIn("openai/gpt-5.6-luna-pro", ids)

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
        self.assertEqual(self.ranked[0].id, "thinkingmachines/inkling-small:free")
        self.assertEqual(self.ranked[1].id, "thinkingmachines/inkling:free")
        # equal context tiers break ties on recency: inkling-small > inkling > minimax-m3
        self.assertEqual(self.ranked[2].id, "minimax/minimax-m3:free")
        self.assertEqual(self.ranked[-1].id, "old/small-free:free")

    def test_limit(self):
        self.assertEqual(len(best_free_models(self.catalog, limit=2)), 2)

    def test_eligibility_on_malformed_entries(self):
        self.assertFalse(is_eligible({}))
        self.assertFalse(is_eligible({"id": "x/y", "pricing": None}))


class MalformedCatalogTests(unittest.TestCase):
    def test_non_dict_pricing_and_architecture_skipped(self):
        catalog = [
            {"id": "a/bad-pricing", "pricing": ["0", "0"], "architecture": {"output_modalities": ["text"]}},
            {"id": "b/bad-arch", "pricing": {"prompt": "0", "completion": "0"}, "architecture": ["text"]},
            {"id": "c/good:free", "pricing": {"prompt": "0", "completion": "0"},
             "architecture": {"output_modalities": ["text"]}},
        ]
        ranked = best_free_models(catalog, limit=10)
        self.assertEqual([m.id for m in ranked], ["c/good:free"])

    def test_non_dict_and_bad_id_entries_skipped(self):
        catalog = [
            "not-a-dict",
            {"pricing": {"prompt": 0, "completion": 0}, "architecture": {"output_modalities": ["text"]}},
            {"id": 123, "pricing": {"prompt": 0, "completion": 0}},
            {"id": "acme/good:free", "name": "Good", "context_length": "8k", "created": "yesterday",
             "supported_parameters": "not-a-list", "architecture": {"output_modalities": ["text"]},
             "pricing": {"prompt": 0, "completion": 0}},
        ]
        ranked = best_free_models(catalog, limit=10)
        self.assertEqual([m.id for m in ranked], ["acme/good:free"])
        self.assertEqual(ranked[0].context_length, 0)
        self.assertEqual(ranked[0].created, 0)
        self.assertEqual(ranked[0].supported_parameters, ())

    def test_rank_key_tolerates_garbage_scalars(self):
        from overseer_best_free import rank_key
        key = rank_key({"context_length": "huge", "created": None, "supported_parameters": None})
        self.assertTrue(all(isinstance(v, int) for v in key))


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



class InputModalityTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()
        self.ranked = {m.id: m for m in best_free_models(self.catalog, limit=10)}

    def test_image_input_flag_exposed(self):
        # recorded inkling-small entry accepts text+image+audio inputs
        self.assertTrue(self.ranked["thinkingmachines/inkling-small:free"].supports_image_input)

    def test_missing_input_modalities_defaults_empty(self):
        entry = {
            "id": "x/y",
            "pricing": {"prompt": "0", "completion": "0"},
            "architecture": {"output_modalities": ["text"]},
        }
        m = to_free_model(entry)
        self.assertFalse(m.supports_image_input)
        self.assertEqual(m.input_modalities, ())

    def test_as_dict_round_trips_modalities(self):
        d = self.ranked["thinkingmachines/inkling-small:free"].as_dict()
        self.assertIn("input_modalities", d)
        self.assertEqual(d["input_modalities"], ["text", "image", "audio"])


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


if __name__ == "__main__":
    unittest.main()
