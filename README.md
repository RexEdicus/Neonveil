# Neonveil

Fully local ambience video generator — dark ambient music + Blender 3D renders + final YouTube MP4.

No paid APIs. Everything runs on your machine.

---

## What it does

1. **Optionally queries a local Ollama model** to derive theme, mood, and music prompt from a natural-language description
2. **Generates ambient music** (stems, MIDI, mix) using the resolved prompt
3. **Prepares a Blender scene** for rendering (`scene_used.blend`)
4. **Renders the 3D animation** via Blender (supports camera cuts)
5. **Assembles the final MP4** with ffmpeg

Each step produces **editable artifacts** so you can:
- Import stems/MIDI into FL Studio and produce your own mix
- Edit the `.blend` in Blender before rendering
- Re-assemble the final video from your edited files at any time

---

## Requirements

- **Python 3.12+** with `pyyaml` and `numpy`
- **Blender 5.0** (or 4.x) — set path in `config/config.yaml`
- **FFmpeg** — set path in `config/config.yaml`
- **Ollama** (optional) — for LLM-assisted spec generation: https://ollama.com

Install Python dependencies:
```bash
pip install -r requirements.txt
```

---

## Quick start

### Option A — Manual (specify theme yourself)

```bash
python master_run.py --mode assets --theme neon_rain --duration 7200 --seed 42
```

### Option B — LLM-guided (describe what you want)

```bash
# Requires Ollama running locally with a model pulled, e.g.:
#   ollama pull llama3:8b

python master_run.py --mode full \
  --llm-prompt "foggy cyberpunk alley, rain on glass, neon reflections at 3am" \
  --llm-model llama3:8b
```

Ollama automatically selects the theme, mood, and music prompt. Falls back to
config defaults gracefully if Ollama is unavailable.

### Multiple variations

```bash
python master_run.py --mode full \
  --llm-prompt "neon rain city" --llm-model llama3:8b \
  --variations 3
```

Generates 3 seeded variations (var-001, var-002, var-003) in one run.
Each gets a unique seed, slightly different camera/light jitter.

### Dry-run (preview the spec without rendering)

```bash
python master_run.py --mode full \
  --llm-prompt "dark cyberpunk" --llm-model llama3:8b \
  --dry-run
```

Prints the normalized spec + manifests as JSON and exits — no Blender, no ffmpeg.

---

## Run folder layout

```
runs/2026-05-15_neon-rain_run-0001/
├── manifest.json               ← run metadata + LLM spec (if used)
├── music/
│   ├── stems/main_mix.wav      ← import into FL Studio
│   ├── midi/main.mid           ← MIDI for your DAW
│   ├── meta/sections.csv
│   ├── meta/tempo_map.json
│   ├── full_mix.wav            ← auto-generated mix
│   └── edited/                 ← PUT YOUR FL STUDIO EXPORT HERE
│       └── final_from_fl.wav   ← (auto-detected on assemble)
├── render/
│   ├── scene_used.blend        ← the render-ready .blend
│   └── edited/                 ← PUT YOUR EDITED BLEND HERE
│       └── scene_edited.blend  ← (auto-detected on assemble)
└── video/
    └── final_youtube.mp4       ← final output
```

---

## All modes

| Mode | What it does | Required flags |
|------|-------------|----------------|
| `full` | Assets + render + assemble (complete pipeline) | `--theme` + `--duration`, or `--llm-prompt` + `--llm-model` |
| `assets` | Generate music + `.blend` only | same as full |
| `render` | Render `.blend` in an existing run | `--run-id` |
| `assemble` | Build final MP4 from existing/edited assets | `--run-id` |

---

## All CLI flags

### Run identity
```
--theme THEME_NAME      Theme folder under themes/
--run-id RUN_ID         Existing run folder ID (for assemble/render)
--seed INT              Master seed (default: from config)
--duration SECONDS      Duration in seconds (3600 = 1h, 7200 = 2h)
```

### LLM-assisted generation (Ollama)
```
--llm-prompt TEXT       Natural-language description of desired video
--llm-model MODEL       Ollama model name (e.g. llama3:8b, mistral:7b)
--variations N          Number of seeded render variations (default: 1, max: 32)
--ollama-url URL        Ollama endpoint (default: http://localhost:11434/api/generate)
--ollama-timeout SEC    Request timeout in seconds (default: 45)
```

### Output format
```
--render-mode loop|frames|both|off    Render output type (default: loop for full/assemble)
--res 1920x1080|2560x1440|3840x2160   Resolution (default: 2560x1440)
--fps 30|60                           Frame rate (default: 30)
--quality fast|balanced|final         Quality preset (default: balanced)
```

### Camera controls
```
--camera-mode continuous|cuts         Camera mode (default: continuous)
--camera CAMERA_NAME                  Camera for continuous mode (default: auto)
--camera-sequence CAM_A,CAM_B,...     Camera order for cuts mode
--cut-every SECONDS                   Seconds per segment for cuts (default: 240)
--cut-style hard|crossfade            Transition style (default: hard)
--cut-fade SECONDS                    Crossfade length (default: 1.0)
--list-cameras                        Print cameras for theme and exit
```

### Editable file overrides
```
--blend-file PATH       Explicit .blend to use (skips auto-selection)
--audio-file PATH       Explicit audio file to use
--render-cache reuse|rerender  Cache policy (default: reuse)
```

### Utility
```
--open-run-folder       Open run folder in file manager after completion
--dry-run               Print spec + planned actions, do not render
--verbose               Extra log output
```

---

## Music prompt priority

When generating music, the prompt is resolved in this order:

1. **LLM override** — from `--llm-prompt` + `--llm-model` (Ollama)
2. **Theme prompt** — `themes/<theme>/prompts.yaml` → `music_prompt`
3. **Fallback** — `config/config.yaml` → `audio.fallback_prompt`

---

## Adding a new theme

```
themes/
└── my_theme/
    ├── scene.blend         ← Blender scene template (required)
    ├── prompts.yaml        ← music_prompt + sfx_prompts
    └── cameras.yaml        ← camera list + default_sequence
```

Then run:
```bash
python master_run.py --mode full --theme my_theme --duration 7200
```

---

## Running tests

```bash
pytest tests/ -v
```
