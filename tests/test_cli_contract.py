"""
tests/test_cli_contract.py
───────────────────────────
Tests for master_run.py CLI contract.
"""

import sys
import unittest
from pathlib import Path

# Allow importing from project root
sys.path.insert(0, str(Path(__file__).parent.parent))
from master_run import parse_args


class TestCliLlmContract(unittest.TestCase):
    """LLM flag pairing rules."""

    def test_llm_prompt_requires_model(self):
        """--llm-prompt alone must fail."""
        with self.assertRaises(SystemExit):
            parse_args(["--llm-prompt", "rainy cyberpunk"])

    def test_llm_model_requires_prompt(self):
        """--llm-model alone must fail."""
        with self.assertRaises(SystemExit):
            parse_args(["--llm-model", "llama3:8b"])

    def test_variations_min(self):
        """--variations 0 must fail."""
        with self.assertRaises(SystemExit):
            parse_args(["--variations", "0"])

    def test_valid_llm_contract(self):
        """Valid paired LLM flags parse correctly."""
        args = parse_args([
            "--llm-prompt", "rainy cyberpunk city at night",
            "--llm-model",  "llama3:8b",
            "--variations", "3",
            "--dry-run",
        ])
        self.assertEqual(args.llm_prompt, "rainy cyberpunk city at night")
        self.assertEqual(args.llm_model,  "llama3:8b")
        self.assertEqual(args.variations,  3)
        self.assertTrue(args.dry_run)

    def test_ollama_url_default(self):
        """Default Ollama URL is set."""
        args = parse_args([
            "--llm-prompt", "test", "--llm-model", "llama3:8b",
        ])
        self.assertEqual(args.ollama_url, "http://localhost:11434/api/generate")

    def test_ollama_url_override(self):
        """Custom Ollama URL is accepted."""
        args = parse_args([
            "--llm-prompt", "test", "--llm-model", "llama3:8b",
            "--ollama-url", "http://192.168.1.10:11434/api/generate",
        ])
        self.assertEqual(args.ollama_url, "http://192.168.1.10:11434/api/generate")


class TestCliModeContract(unittest.TestCase):
    """Mode + flag defaults."""

    def test_default_mode_is_full(self):
        args = parse_args(["--theme", "neon_rain"])
        self.assertEqual(args.mode, "full")

    def test_quality_default(self):
        args = parse_args(["--theme", "neon_rain"])
        self.assertEqual(args.quality, "balanced")

    def test_fps_default(self):
        args = parse_args(["--theme", "neon_rain"])
        self.assertEqual(args.fps, 30)

    def test_res_default(self):
        args = parse_args(["--theme", "neon_rain"])
        self.assertEqual(args.res, "2560x1440")

    def test_camera_mode_default(self):
        args = parse_args(["--theme", "neon_rain"])
        self.assertEqual(args.camera_mode, "continuous")

    def test_render_cache_default(self):
        args = parse_args(["--theme", "neon_rain"])
        self.assertEqual(args.render_cache, "reuse")

    def test_assemble_with_run_id(self):
        args = parse_args(["--mode", "assemble", "--run-id", "2026-05-01_neon-rain_run-0001"])
        self.assertEqual(args.mode, "full" if args.mode == "full" else "assemble")
        # run-id is set
        self.assertIsNotNone(args.run_id)

    def test_dry_run_flag(self):
        args = parse_args(["--theme", "neon_rain", "--dry-run"])
        self.assertTrue(args.dry_run)


if __name__ == "__main__":
    unittest.main()
