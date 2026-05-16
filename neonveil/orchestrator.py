"""
neonveil/orchestrator.py
─────────────────────────
Central pipeline dispatcher.

Maps --mode values to their pipeline steps:

    full     → assets → render → assemble
    assets   → assets (optional preview render)
    render   → render only
    assemble → assemble (resolve blend + audio, render if needed, mux)

Now accepts an optional `spec` and `manifests` from run_spec.py so that
LLM-derived values (theme, mood, music_prompt, variation jitter) flow
transparently through the pipeline without changing any step contracts.
"""

import logging
import platform
import subprocess
from pathlib import Path

from config.config_loader import load_config, get_theme_dir, get_runs_dir
from neonveil.run_id import make_run_id, resolve_run_dir, parse_theme_from_run_id
from neonveil.manifest import create_manifest, load_manifest, set_status, register_file, update_manifest

log = logging.getLogger(__name__)


class Orchestrator:
    """
    Runs the pipeline for a given set of parsed CLI arguments.

    Args:
        args:      Parsed argparse namespace from master_run.parse_args().
        config:    Loaded config dict (already patched with CLI overrides).
        spec:      Optional normalized run spec from run_spec.build_run_spec().
                   When provided, its music_prompt and mood are recorded in
                   the manifest and forwarded to music generation.
        manifests: Optional list of variation manifests from
                   run_spec.expand_variation_manifests(). When provided and
                   variations > 1, future expansion point; for now only the
                   first manifest is consumed (single-variation pipeline).

    Usage:
        orch = Orchestrator(args, config, spec=spec, manifests=manifests)
        orch.run()
    """

    def __init__(self, args, config: dict, spec: dict = None, manifests: list = None):
        self.args      = args
        self.config    = config
        self.spec      = spec or {}
        self.manifests = manifests or []
        self.verbose   = args.verbose
        self.dry_run   = args.dry_run

    # ─────────────────────────────────────────────────────────────────────────
    def run(self):
        mode = self.args.mode
        log.info(f"[Orchestrator] mode={mode}")

        if mode == "full":
            self._run_full()
        elif mode == "assets":
            self._run_assets()
        elif mode == "render":
            self._run_render()
        elif mode == "assemble":
            self._run_assemble()
        else:
            raise ValueError(f"Unknown mode: {mode}")

    # ─── mode=full ────────────────────────────────────────────────────────────
    def _run_full(self):
        args = self.args

        run_dir, run_id, manifest = self._setup_run(
            theme=self.config["theme"],
            seed=self.config["seed"],
            duration_sec=args.duration,
            mode="full",
        )

        try:
            # Step 1 — Assets (music + .blend copy)
            theme_dir = get_theme_dir(self.config)
            from neonveil.steps.assets import run_assets_step
            assets = run_assets_step(
                run_dir=run_dir,
                theme_dir=theme_dir,
                config=self.config,
                duration_sec=args.duration,
                seed=self.config["seed"],
                music_prompt_override=self.spec.get("music_prompt"),
                dry_run=self.dry_run,
                verbose=self.verbose,
            )
            if not self.dry_run:
                register_file(run_dir, "blend",    assets["blend_path"])
                register_file(run_dir, "full_mix", assets["full_mix"])

            # Step 2 — Assemble (includes render)
            render_mode = args.render_mode or "loop"
            from neonveil.steps.assemble import run_assemble_step
            final_mp4 = run_assemble_step(
                run_dir=run_dir,
                config=self.config,
                duration_sec=args.duration,
                seed=self.config["seed"],
                render_mode=render_mode,
                quality=args.quality,
                res=args.res,
                fps=args.fps,
                camera_mode=args.camera_mode,
                camera=args.camera,
                camera_sequence=self._parse_camera_sequence(),
                cut_every=args.cut_every,
                cut_style=args.cut_style,
                cut_fade=args.cut_fade,
                blend_file_override=args.blend_file,
                audio_file_override=args.audio_file,
                render_cache=args.render_cache,
                dry_run=self.dry_run,
                verbose=self.verbose,
            )

            if not self.dry_run and final_mp4:
                register_file(run_dir, "final_video", final_mp4)

            set_status(run_dir, "complete")
            self._print_summary(run_dir, run_id, final_mp4)

        except Exception:
            if not self.dry_run:
                set_status(run_dir, "failed")
            raise

        if args.open_run_folder:
            _open_folder(run_dir)

    # ─── mode=assets ─────────────────────────────────────────────────────────
    def _run_assets(self):
        args = self.args

        run_dir, run_id, manifest = self._setup_run(
            theme=self.config["theme"],
            seed=self.config["seed"],
            duration_sec=args.duration,
            mode="assets",
        )

        try:
            theme_dir = get_theme_dir(self.config)
            from neonveil.steps.assets import run_assets_step
            assets = run_assets_step(
                run_dir=run_dir,
                theme_dir=theme_dir,
                config=self.config,
                duration_sec=args.duration,
                seed=self.config["seed"],
                music_prompt_override=self.spec.get("music_prompt"),
                dry_run=self.dry_run,
                verbose=self.verbose,
            )

            if not self.dry_run:
                register_file(run_dir, "blend",    assets["blend_path"])
                register_file(run_dir, "full_mix", assets["full_mix"])

            # Optional preview render
            render_mode = args.render_mode or "off"
            if render_mode != "off":
                from neonveil.steps.render import run_render_step
                render_result = run_render_step(
                    run_dir=run_dir,
                    blend_file=assets["blend_path"],
                    config=self.config,
                    duration_sec=args.duration,
                    seed=self.config["seed"],
                    render_mode=render_mode,
                    quality=args.quality,
                    res=args.res,
                    fps=args.fps,
                    camera=args.camera,
                    render_cache=args.render_cache,
                    dry_run=self.dry_run,
                    verbose=self.verbose,
                )
                if not self.dry_run and render_result.get("video_path"):
                    register_file(run_dir, "preview_video", render_result["video_path"])

            if not self.dry_run:
                set_status(run_dir, "assets_ready")

            print(f"\n[System] ═══ Assets ready ═══")
            print(f"[System] Run folder : {run_dir}")
            print(f"[System] Run ID     : {run_id}")
            print(f"[System] .blend     : {assets['blend_path']}")
            print(f"[System] Music      : {assets['music_dir']}")
            print()
            print(f"[System] Edit your files, then assemble:")
            print(f"[System]   python master_run.py --mode assemble --run-id {run_id}")
            print()

        except Exception:
            if not self.dry_run:
                set_status(run_dir, "failed")
            raise

        if args.open_run_folder:
            _open_folder(run_dir)

    # ─── mode=render ─────────────────────────────────────────────────────────
    def _run_render(self):
        args = self.args

        run_dir  = self._require_run_dir()
        manifest = load_manifest(run_dir)

        seed  = args.seed or manifest.get("seed") or self.config.get("seed")
        blend_path  = self._resolve_blend_for_render(run_dir, args.blend_file, self.config["theme"])
        render_mode = args.render_mode or "loop"

        from neonveil.steps.render import run_render_step
        render_result = run_render_step(
            run_dir=run_dir,
            blend_file=blend_path,
            config=self.config,
            duration_sec=manifest.get("duration_sec", args.duration or 7200),
            seed=seed,
            render_mode=render_mode,
            quality=args.quality,
            res=args.res,
            fps=args.fps,
            camera=args.camera,
            render_cache=args.render_cache,
            dry_run=self.dry_run,
            verbose=self.verbose,
        )

        if not self.dry_run and render_result.get("video_path"):
            register_file(run_dir, "render_video", render_result["video_path"])

        print(f"\n[System] Render complete — run folder: {run_dir}")

        if args.open_run_folder:
            _open_folder(run_dir)

    # ─── mode=assemble ────────────────────────────────────────────────────────
    def _run_assemble(self):
        args = self.args

        run_dir  = self._require_run_dir()
        manifest = load_manifest(run_dir)

        duration_sec = manifest.get("duration_sec") or args.duration or 7200
        seed = args.seed or manifest.get("seed") or self.config.get("seed")
        render_mode = args.render_mode or "loop"

        try:
            from neonveil.steps.assemble import run_assemble_step
            final_mp4 = run_assemble_step(
                run_dir=run_dir,
                config=self.config,
                duration_sec=duration_sec,
                seed=seed,
                render_mode=render_mode,
                quality=args.quality,
                res=args.res,
                fps=args.fps,
                camera_mode=args.camera_mode,
                camera=args.camera,
                camera_sequence=self._parse_camera_sequence(),
                cut_every=args.cut_every,
                cut_style=args.cut_style,
                cut_fade=args.cut_fade,
                blend_file_override=args.blend_file,
                audio_file_override=args.audio_file,
                render_cache=args.render_cache,
                dry_run=self.dry_run,
                verbose=self.verbose,
            )

            if not self.dry_run and final_mp4:
                register_file(run_dir, "final_video", final_mp4)
                set_status(run_dir, "complete")

            self._print_summary(run_dir, args.run_id, final_mp4)

        except Exception:
            if not self.dry_run:
                set_status(run_dir, "failed")
            raise

        if args.open_run_folder:
            _open_folder(run_dir)

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _setup_run(self, theme: str, seed: int, duration_sec: int, mode: str):
        """Create run directory + manifest. Returns (run_dir, run_id, manifest)."""
        runs_dir = get_runs_dir()
        run_id   = make_run_id(theme, runs_dir)
        run_dir  = resolve_run_dir(run_id, runs_dir)

        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "logs").mkdir(exist_ok=True)

        cli_args = {k: v for k, v in vars(self.args).items() if v is not None}

        # Enrich manifest with LLM-derived fields if available
        extra = {}
        if self.spec.get("mood"):
            extra["mood"] = self.spec["mood"]
        if self.spec.get("music_prompt"):
            extra["music_prompt"] = self.spec["music_prompt"]
        if self.spec.get("user_prompt"):
            extra["user_prompt"] = self.spec["user_prompt"]
        if self.spec.get("llm_model"):
            extra["llm_model"] = self.spec["llm_model"]
        if self.spec.get("variations", 1) > 1:
            extra["variations"] = self.spec["variations"]

        manifest = create_manifest(
            run_dir=run_dir,
            run_id=run_id,
            theme=theme,
            seed=seed,
            duration_sec=duration_sec,
            mode=mode,
            cli_args={**cli_args, **extra},
        )

        print(f"\n[System] ═══ Neonveil Pipeline ═══")
        print(f"[System] Run ID  : {run_id}")
        print(f"[System] Mode    : {mode}")
        print(f"[System] Theme   : {theme}")
        print(f"[System] Seed    : {seed}")
        if duration_sec:
            print(f"[System] Duration: {duration_sec // 60} min {duration_sec % 60}s")
        if self.spec.get("mood"):
            print(f"[System] Mood    : {self.spec['mood']}")
        if self.spec.get("music_prompt"):
            print(f"[System] Prompt  : {self.spec['music_prompt'][:80]}")
        print(f"[System] Run dir : {run_dir}")
        print()

        return run_dir, run_id, manifest

    def _require_run_dir(self) -> Path:
        """Validate --run-id and return the run directory."""
        run_id  = self.args.run_id
        if not run_id:
            raise ValueError("--run-id is required for this mode.")

        runs_dir = get_runs_dir()
        run_dir  = resolve_run_dir(run_id, runs_dir)

        if not run_dir.exists():
            raise FileNotFoundError(
                f"[System] Run directory not found: {run_dir}\n"
                f"Valid runs in {runs_dir}:\n"
                + _list_runs(runs_dir)
            )

        return run_dir

    def _resolve_blend_for_render(self, run_dir: Path, override: str, theme: str) -> str:
        if override:
            return override
        edited = run_dir / "render" / "edited" / "scene_edited.blend"
        if edited.exists():
            return str(edited)
        used = run_dir / "render" / "scene_used.blend"
        if used.exists():
            return str(used)
        if theme:
            theme_blend = get_theme_dir(self.config) / "scene.blend"
            if theme_blend.exists():
                return str(theme_blend)
        raise FileNotFoundError(
            f"[Render] No .blend found in {run_dir / 'render'}. "
            "Use --blend-file to specify one."
        )

    def _parse_camera_sequence(self) -> list:
        val = self.args.camera_sequence
        if val:
            return [c.strip() for c in val.split(",") if c.strip()]

        if getattr(self.args, "camera_mode", "continuous") == "cuts":
            theme_dir    = get_theme_dir(self.config)
            cameras_yaml = theme_dir / "cameras.yaml"
            if cameras_yaml.exists():
                try:
                    import yaml
                    with open(cameras_yaml, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                    seq = data.get("default_sequence", [])
                    if seq:
                        log.info(f"[Orchestrator] Using cameras.yaml default_sequence: {seq}")
                        return list(seq)
                except Exception as e:
                    log.warning(f"[Orchestrator] Could not read cameras.yaml default_sequence: {e}")

        return []

    def _print_summary(self, run_dir: Path, run_id: str, final_mp4: str):
        print(f"\n[System] ═══ DONE ═══")
        print(f"[System] Run ID   : {run_id}")
        print(f"[System] Run dir  : {run_dir}")
        if final_mp4:
            import os
            size_mb = os.path.getsize(final_mp4) / (1024 * 1024) if os.path.exists(final_mp4) else 0
            print(f"[System] Video    : {final_mp4} ({size_mb:.0f} MB)")
        print()


# ─── Module-level helpers ─────────────────────────────────────────────────────

def _open_folder(path: Path):
    """Open the folder in the OS file manager (best-effort)."""
    try:
        system = platform.system()
        if system == "Windows":
            subprocess.Popen(["explorer", str(path)])
        elif system == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as e:
        log.warning(f"[System] Could not open folder: {e}")


def _list_runs(runs_dir: Path) -> str:
    if not runs_dir.exists():
        return "  (no runs directory)"
    entries = sorted(d.name for d in runs_dir.iterdir() if d.is_dir())
    return "\n".join(f"  {e}" for e in entries) or "  (empty)"
