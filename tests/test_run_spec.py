"""
tests/test_run_spec.py
───────────────────────
Tests for run_spec.py — validation, normalization, and manifest expansion.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from run_spec import (
    validate_and_normalize_spec,
    expand_variation_manifests,
    _heuristic_mood,
    _fallback_music_prompt,
)


BASE_CONFIG = {
    "theme": "neon_rain",
    "seed":  42,
    "audio": {"fallback_prompt": "fallback ambient drone"},
    "video": {
        "fps": 30,
        "duration_minutes": 120,
        "resolution_x": 2560,
        "resolution_y": 1440,
    },
    "render": {
        "engine":      "BLENDER_EEVEE_NEXT",
        "samples":     64,
        "bloom":       True,
        "volumetrics": True,
    },
    "paths": {
        "themes_dir": "themes",
    },
}


class TestValidation(unittest.TestCase):

    def test_empty_spec_uses_config_defaults(self):
        spec = validate_and_normalize_spec({}, BASE_CONFIG)
        self.assertEqual(spec["theme"], "neon_rain")
        self.assertEqual(spec["seed"],  42)
        self.assertEqual(spec["variations"], 1)
        self.assertTrue(spec["music_prompt"])

    def test_variations_clamped_to_max(self):
        spec = validate_and_normalize_spec({"variations": 999}, BASE_CONFIG)
        self.assertEqual(spec["variations"], 32)

    def test_variations_min_is_one(self):
        spec = validate_and_normalize_spec({"variations": -5}, BASE_CONFIG)
        self.assertEqual(spec["variations"], 1)

    def test_samples_min_is_one(self):
        spec = validate_and_normalize_spec(
            {"render": {"samples": -10}}, BASE_CONFIG
        )
        self.assertGreaterEqual(spec["render"]["samples"], 1)

    def test_resolution_min_clamped(self):
        spec = validate_and_normalize_spec(
            {"render": {"resolution_x": 0, "resolution_y": 0}}, BASE_CONFIG
        )
        self.assertGreaterEqual(spec["render"]["resolution_x"], 64)
        self.assertGreaterEqual(spec["render"]["resolution_y"], 64)

    def test_run_id_override(self):
        spec = validate_and_normalize_spec({}, BASE_CONFIG, run_id="my-run")
        self.assertEqual(spec["run_id"], "my-run")

    def test_run_id_auto_generated(self):
        spec = validate_and_normalize_spec({}, BASE_CONFIG)
        self.assertIn("neon_rain", spec["run_id"])

    def test_music_prompt_stripped(self):
        spec = validate_and_normalize_spec(
            {"music_prompt": "  dark ambient  "}, BASE_CONFIG
        )
        self.assertEqual(spec["music_prompt"], "dark ambient")

    def test_render_bloom_and_volumetrics_are_bool(self):
        spec = validate_and_normalize_spec({}, BASE_CONFIG)
        self.assertIsInstance(spec["render"]["bloom"], bool)
        self.assertIsInstance(spec["render"]["volumetrics"], bool)

    def test_variation_strategy_defaults_present(self):
        spec = validate_and_normalize_spec({}, BASE_CONFIG)
        strategy = spec["variation_strategy"]
        self.assertIn("camera_jitter_max", strategy)
        self.assertIn("light_jitter_max",  strategy)
        self.assertIn("noise_offset_max",  strategy)

    def test_bad_seed_falls_back_to_config(self):
        spec = validate_and_normalize_spec({"seed": "not-a-number"}, BASE_CONFIG)
        self.assertEqual(spec["seed"], 42)


class TestManifestExpansion(unittest.TestCase):

    def _make_spec(self, variations=3, seed=101):
        return validate_and_normalize_spec(
            {
                "run_id":       "run-x",
                "theme":        "neon_rain",
                "mood":         "dark",
                "music_prompt": "rain",
                "seed":         seed,
                "variations":   variations,
            },
            BASE_CONFIG,
        )

    def test_correct_count(self):
        manifests = expand_variation_manifests(self._make_spec(3))
        self.assertEqual(len(manifests), 3)

    def test_deterministic(self):
        spec = self._make_spec(3)
        a = expand_variation_manifests(spec)
        b = expand_variation_manifests(spec)
        self.assertEqual(a, b)

    def test_seed_increments(self):
        manifests = expand_variation_manifests(self._make_spec(3, seed=100))
        self.assertEqual(manifests[0]["seed"], 100)
        self.assertEqual(manifests[1]["seed"], 101)
        self.assertEqual(manifests[2]["seed"], 102)

    def test_variation_ids(self):
        manifests = expand_variation_manifests(self._make_spec(3))
        ids = [m["variation_id"] for m in manifests]
        self.assertEqual(ids, ["var-001", "var-002", "var-003"])

    def test_variation_jitter_in_range(self):
        manifests = expand_variation_manifests(self._make_spec(5))
        for m in manifests:
            v = m["variation"]
            self.assertGreaterEqual(v["camera_jitter"], 0.0)
            self.assertLessEqual(v["camera_jitter"],    0.06)
            self.assertGreaterEqual(v["light_jitter"],  0.0)
            self.assertLessEqual(v["light_jitter"],     0.15)
            self.assertGreaterEqual(v["noise_offset"],  0.0)
            self.assertLessEqual(v["noise_offset"],     35.0)

    def test_single_variation(self):
        spec = self._make_spec(1)
        manifests = expand_variation_manifests(spec)
        self.assertEqual(len(manifests), 1)
        self.assertEqual(manifests[0]["variation_id"], "var-001")


class TestHeuristicMood(unittest.TestCase):

    def test_dark_keywords(self):
        self.assertEqual(_heuristic_mood("dark rainy night"), "dark")
        self.assertEqual(_heuristic_mood("cyberpunk city"), "dark")
        self.assertEqual(_heuristic_mood("blade runner aesthetic"), "dark")

    def test_calm_keywords(self):
        self.assertEqual(_heuristic_mood("soft gentle rain"), "calm")

    def test_uplifting_keywords(self):
        self.assertEqual(_heuristic_mood("bright hopeful morning"), "uplifting")

    def test_default_ambient(self):
        self.assertEqual(_heuristic_mood(""), "ambient")
        self.assertEqual(_heuristic_mood("something unrelated"), "ambient")


if __name__ == "__main__":
    unittest.main()
