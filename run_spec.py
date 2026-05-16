"""
run_spec.py
────────────
Builds a normalized "run spec" from CLI args, optionally enriched by a local
Ollama model, then expands it into per-variation manifests.

Flow:
    CLI args → _default_spec()
               ↓ (if --llm-prompt + --llm-model)
            _call_ollama_for_spec()   → merge LLM output into spec
               ↓
    validate_and_normalize_spec()     → clamp, type-coerce, fill gaps
               ↓
    expand_variation_manifests()      → deterministic N-variation list

The spec + manifests are consumed by the Orchestrator, which passes the
resolved values through to music, render, and assemble steps.
"""

import json
import random
import urllib.request
import urllib.error
from copy import deepcopy

MAX_VARIATIONS = 32


# ─── Defaults ────────────────────────────────────────────────────────────────

def _coerce_bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"true", "1", "yes", "y", "on"}:
            return True
        if v in {"false", "0", "no", "n", "off"}:
            return False
    return default


def _fallback_music_prompt(config: dict) -> str:
    return config.get("audio", {}).get(
        "fallback_prompt",
        "dark cinematic ambient drone, rain, distant city, slow melancholic pads, Blade Runner aesthetic",
    )


def _heuristic_mood(prompt: str) -> str:
    p = (prompt or "").lower()
    # Check more specific moods first so calm/uplifting aren't shadowed
    # by shared words like "rain" that also appear in dark prompts.
    if any(k in p for k in ["calm", "soft", "gentle", "peaceful"]):
        return "calm"
    if any(k in p for k in ["bright", "hope", "uplift", "happy"]):
        return "uplifting"
    if any(k in p for k in ["dark", "rain", "noir", "cyberpunk", "night", "blade runner"]):
        return "dark"
    return "ambient"


def _default_spec(config: dict, prompt: str, model: str | None, run_id: str | None, variations: int) -> dict:
    return {
        "run_id": run_id,
        "user_prompt": prompt,
        "llm_model": model,
        "theme": config.get("theme"),
        "mood": _heuristic_mood(prompt) if prompt else "ambient",
        "music_prompt": prompt or _fallback_music_prompt(config),
        "seed": int(config.get("seed", 42)),
        "variations": variations,
        "render": {
            "engine":           config.get("render", {}).get("engine", "BLENDER_EEVEE_NEXT"),
            "samples":          int(config.get("render", {}).get("samples", 64)),
            "bloom":            bool(config.get("render", {}).get("bloom", True)),
            "volumetrics":      bool(config.get("render", {}).get("volumetrics", True)),
            "fps":              int(config.get("video", {}).get("fps", 30)),
            "duration_minutes": int(config.get("video", {}).get("duration_minutes", 120)),
            "resolution_x":     int(config.get("video", {}).get("resolution_x", 2560)),
            "resolution_y":     int(config.get("video", {}).get("resolution_y", 1440)),
        },
        "variation_strategy": {
            "camera_jitter_max": 0.06,
            "light_jitter_max":  0.15,
            "noise_offset_max":  35.0,
        },
    }


# ─── Ollama integration ───────────────────────────────────────────────────────

def _call_ollama_for_spec(
    prompt: str,
    model: str,
    ollama_url: str,
    timeout_sec: int,
) -> dict | None:
    """
    Ask a local Ollama model to suggest a structured run-spec from a natural
    language intent string.

    Returns a dict when the model responds with valid JSON, otherwise None.
    None is the safe fallback — the caller uses _default_spec() instead.
    """
    system_instruction = (
        "Return ONLY valid JSON with these exact keys: "
        "theme, mood, music_prompt, render, variation_strategy. "
        "Do NOT include run_id, seed, or variations — those are CLI-controlled. "
        "render keys: engine, samples, bloom, volumetrics, fps, duration_minutes, "
        "resolution_x, resolution_y. "
        "variation_strategy keys: camera_jitter_max, light_jitter_max, noise_offset_max. "
        "No explanation, no markdown, no preamble — only the JSON object."
    )

    payload = {
        "model":  model,
        "stream": False,
        "prompt": f"{system_instruction}\nUser request: {prompt}",
        "format": "json",
    }

    body = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        ollama_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    print(f"[Spec] Querying Ollama ({model}) at {ollama_url} ...")
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
        print(f"[Spec] Ollama unavailable or error ({exc}) — using safe defaults.")
        return None

    response_text = data.get("response")
    if not response_text:
        print("[Spec] Ollama returned empty response — using safe defaults.")
        return None

    try:
        parsed = json.loads(response_text)
        if not isinstance(parsed, dict):
            print("[Spec] Ollama response was not a JSON object — using safe defaults.")
            return None
        print(f"[Spec] Ollama spec received: theme={parsed.get('theme')!r}  mood={parsed.get('mood')!r}")
        return parsed
    except ValueError:
        print("[Spec] Ollama response could not be parsed as JSON — using safe defaults.")
        return None


# ─── Validation / normalisation ───────────────────────────────────────────────

def validate_and_normalize_spec(
    spec: dict,
    config: dict,
    run_id: str | None = None,
    variations: int | None = None,
) -> dict:
    """
    Validate and normalize a raw spec dict against safe defaults and constraints.

    Ensures required keys exist, coerces types, clamps out-of-range values,
    and applies CLI overrides (run_id, variations) when provided.

    Always returns a fully populated dict — never raises on bad input.
    """
    normalized = deepcopy(spec or {})

    # ── Top-level scalar fields ───────────────────────────────────────────────
    normalized["theme"]        = normalized.get("theme") or config.get("theme")
    normalized["mood"]         = normalized.get("mood")  or "ambient"
    normalized["music_prompt"] = (normalized.get("music_prompt") or _fallback_music_prompt(config)).strip()
    normalized["user_prompt"]  = normalized.get("user_prompt", "")
    normalized["llm_model"]    = normalized.get("llm_model")

    # ── Seed ─────────────────────────────────────────────────────────────────
    seed = normalized.get("seed", config.get("seed", 42))
    try:
        seed = int(seed)
    except (TypeError, ValueError):
        seed = int(config.get("seed", 42))
    normalized["seed"] = seed

    # ── Variations ───────────────────────────────────────────────────────────
    v = variations if variations is not None else normalized.get("variations", 1)
    try:
        v = int(v)
    except (TypeError, ValueError):
        v = 1
    normalized["variations"] = max(1, min(v, MAX_VARIATIONS))

    # ── Run ID ───────────────────────────────────────────────────────────────
    if run_id:
        normalized["run_id"] = run_id
    elif not normalized.get("run_id"):
        normalized["run_id"] = f"{normalized['theme']}-{normalized['seed']}"

    # ── Render block ─────────────────────────────────────────────────────────
    render          = deepcopy(normalized.get("render", {}))
    render_defaults = _default_spec(config, "", None, None, 1)["render"]
    for k, dv in render_defaults.items():
        render[k] = render.get(k, dv)

    try:
        render["samples"]          = max(1, int(render["samples"]))
        render["fps"]              = max(1, int(render["fps"]))
        render["duration_minutes"] = max(1, int(render["duration_minutes"]))
        render["resolution_x"]     = max(64, int(render["resolution_x"]))
        render["resolution_y"]     = max(64, int(render["resolution_y"]))
    except (TypeError, ValueError):
        render = render_defaults

    render["engine"]      = str(render.get("engine", "BLENDER_EEVEE_NEXT"))
    render["bloom"]       = _coerce_bool(render.get("bloom"), True)
    render["volumetrics"] = _coerce_bool(render.get("volumetrics"), True)
    normalized["render"]  = render

    # ── Variation strategy ────────────────────────────────────────────────────
    strategy          = deepcopy(normalized.get("variation_strategy", {}))
    strategy_defaults = _default_spec(config, "", None, None, 1)["variation_strategy"]
    for k, dv in strategy_defaults.items():
        strategy[k] = strategy.get(k, dv)

    for key in ["camera_jitter_max", "light_jitter_max", "noise_offset_max"]:
        try:
            strategy[key] = max(0.0, float(strategy[key]))
        except (TypeError, ValueError):
            strategy[key] = strategy_defaults[key]

    normalized["variation_strategy"] = strategy
    return normalized


# ─── Public API ───────────────────────────────────────────────────────────────

def build_run_spec(config: dict, args) -> dict:
    """
    Build a normalized run spec from config + parsed CLI args.

    If --llm-prompt and --llm-model are both provided, queries Ollama and
    merges the result. CLI flags always win over LLM suggestions.
    """
    prompt   = getattr(args, "llm_prompt", None)
    model    = getattr(args, "llm_model",  None)
    run_id   = getattr(args, "run_id",     None)
    variations = getattr(args, "variations", 1)

    base = _default_spec(
        config=config,
        prompt=prompt,
        model=model,
        run_id=run_id,
        variations=variations,
    )

    if prompt and model:
        ollama_url     = getattr(args, "ollama_url",     "http://localhost:11434/api/generate")
        ollama_timeout = getattr(args, "ollama_timeout", 45)

        llm_spec = _call_ollama_for_spec(
            prompt=prompt,
            model=model,
            ollama_url=ollama_url,
            timeout_sec=ollama_timeout,
        )
        if llm_spec:
            # Only merge top-level keys we recognise — never let the model
            # inject run_id, seed, or variations.
            _safe_merge_keys = {"theme", "mood", "music_prompt", "render", "variation_strategy"}
            for k, v in llm_spec.items():
                if k in _safe_merge_keys:
                    base[k] = v

    # CLI overrides always win over everything (including LLM)
    if getattr(args, "theme", None):
        base["theme"] = args.theme
    if getattr(args, "seed", None) is not None:
        base["seed"] = args.seed

    return validate_and_normalize_spec(
        spec=base,
        config=config,
        run_id=run_id,
        variations=variations,
    )


def expand_variation_manifests(spec: dict) -> list[dict]:
    """
    Expand a normalized spec into deterministic per-variation manifests.

    Each manifest has a unique seed (base_seed + index), a stable variation_id,
    inherited render settings, and derived camera/light/noise jitter values.
    """
    manifests  = []
    base_seed  = int(spec["seed"])
    strategy   = spec["variation_strategy"]

    for idx in range(spec["variations"]):
        variation_seed = base_seed + idx
        rng = random.Random(variation_seed)

        manifests.append({
            "variation_index": idx + 1,
            "variation_id":    f"var-{idx + 1:03d}",
            "run_id":          spec["run_id"],
            "theme":           spec["theme"],
            "mood":            spec["mood"],
            "music_prompt":    spec["music_prompt"],
            "user_prompt":     spec.get("user_prompt", ""),
            "seed":            variation_seed,
            "render":          deepcopy(spec["render"]),
            "variation": {
                "camera_jitter": round(rng.uniform(0.0, strategy["camera_jitter_max"]), 5),
                "light_jitter":  round(rng.uniform(0.0, strategy["light_jitter_max"]), 5),
                "noise_offset":  round(rng.uniform(0.0, strategy["noise_offset_max"]), 5),
            },
        })

    return manifests
