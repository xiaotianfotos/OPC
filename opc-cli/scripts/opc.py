#!/usr/bin/env python3
"""opc - TTS & ASR CLI hub. Designed for AI Agent usage.

Sub-commands each have their own module under scripts/{command}/.
"""

import os
import sys
import json
import asyncio
import argparse
import subprocess
import tempfile
from pathlib import Path

# Add scripts dir to path so we can import sub-skill modules
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)

from shared.config import load_config, save_config
from shared.platform import get_backend, get_backend_label, check_dependency_available
from tts.edge_engine import tts_edge
from tts.qwen_engine import tts_qwen, QWEN_MODELS, QWEN_SPEAKERS, QWEN_SPEAKER_INFO
from asr.qwen_asr_engine import asr_transcribe, asr_align, result_to_dict, ASR_MODELS
from asr.subtitle_gen import generate_srt, generate_ass_karaoke
from asr.pipeline import run_pipeline, split_line_after, _load_lines, _save_lines, stage_check
from image.comfyui import generate_image, check_connection, get_server_url, describe_image, compare_images, extract_comfyui_metadata, upload_image
from image.workflow import discover_workflows, load_workflow, inject_params, analyze_workflow, import_workflow
from image.kg.engine import PromptKG
from image.json_prompt import json_prompt_to_text, validate_json_prompt
from audio.compressor import compress_audio, analyze_loudness, apply_preset, list_presets
from video.generator import generate_video, check_connection as video_check_connection, get_server_url as video_get_server_url, upload_image as video_upload_image
from video.transcribe import download_video, extract_audio, transcribe_audio, save_transcript, summarize_text
from video.describe import describe_video


# ── CLI Commands ──────────────────────────────────────────────────

def cmd_tts(args):
    """Handle 'opc tts' command."""
    text = args.text or ""
    if args.stdin:
        text = sys.stdin.read().strip()
    if not text:
        print("Error: No text provided. Use positional arg or --stdin.")
        sys.exit(1)

    cfg = load_config()
    engine = args.engine or cfg.get("tts_engine", "edge-tts")
    output_dir = cfg.get("output_dir", tempfile.gettempdir())
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    fmt = args.format or cfg.get("tts_format", "mp3")
    if args.output:
        output_file = args.output
    else:
        output_file = os.path.join(output_dir, f"opc_tts_output.{fmt}")

    if engine == "edge-tts":
        voice = args.voice or cfg.get("edge_voice", "zh-CN-XiaoxiaoNeural")
        rate = args.rate or cfg.get("edge_rate", "+0%")
        pitch = args.pitch or cfg.get("edge_pitch", "+0Hz")
        volume = args.volume or cfg.get("edge_volume", "+0%")
        result = tts_edge(text, voice, output_file, rate, pitch, volume)
    elif engine == "qwen":
        mode = args.mode or cfg.get("qwen_mode", "custom_voice")
        model_size = args.model_size or cfg.get("qwen_model_size", "1.7B")
        speaker = args.speaker or cfg.get("qwen_speaker", None)
        language = args.language or cfg.get("qwen_language", "Auto")
        result = tts_qwen(text, output_file, mode, model_size,
                          speaker=speaker, instruct=args.instruct,
                          language=language, ref_audio=args.ref_audio,
                          ref_text=args.ref_text, x_vector_only=args.x_vector_only)
    else:
        print(f"Error: Unknown engine '{engine}'. Available: edge-tts, qwen")
        sys.exit(1)

    print(result)


def cmd_say(args):
    """Handle 'opc say' command: TTS + play on device. Auto-deletes temp file after playback."""
    text = args.text or ""
    if args.stdin:
        text = sys.stdin.read().strip()
    if not text:
        print("Error: No text provided. Use positional arg or --stdin.")
        sys.exit(1)

    cfg = load_config()
    engine = args.engine or cfg.get("tts_engine", "edge-tts")
    output_dir = cfg.get("output_dir", tempfile.gettempdir())
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_file = os.path.join(output_dir, "opc_say_temp.mp3")

    if engine == "edge-tts":
        voice = args.voice or cfg.get("edge_voice", "zh-CN-XiaoxiaoNeural")
        rate = args.rate or cfg.get("edge_rate", "+0%")
        pitch = args.pitch or cfg.get("edge_pitch", "+0Hz")
        volume = args.volume or cfg.get("edge_volume", "+0%")
        result_file = tts_edge(text, voice, output_file, rate, pitch, volume)
    elif engine == "qwen":
        mode = args.mode or cfg.get("qwen_mode", "custom_voice")
        model_size = args.model_size or cfg.get("qwen_model_size", "1.7B")
        speaker = args.speaker or cfg.get("qwen_speaker", None)
        language = args.language or cfg.get("qwen_language", "Auto")
        result_file = tts_qwen(text, output_file, mode, model_size,
                               speaker=speaker, instruct=args.instruct,
                               language=language, ref_audio=args.ref_audio,
                               ref_text=args.ref_text, x_vector_only=args.x_vector_only)
    else:
        print(f"Error: Unknown engine '{engine}'. Available: edge-tts, qwen")
        sys.exit(1)

    print(f"Generated audio: {result_file}")

    device_name = args.device or cfg.get("default_device", "")
    if not device_name:
        print("No default device configured. Use 'opc discover' to find devices and 'xt config --device <name>' to set it.")
        if os.path.exists(result_file):
            os.remove(result_file)
        return

    print(f"Streaming to device: {device_name}...")
    try:
        from shared.device.discover import find_device_by_name
        from shared.device.player import stream_to_device
        device = asyncio.run(find_device_by_name(device_name))
        if not device:
            print(f"Device '{device_name}' not found on network.")
            return
        print(f"Found device: {device.name} ({device.device_type})")
        asyncio.run(stream_to_device(device, Path(result_file)))
    except Exception as e:
        print(f"Playback failed: {e}")
    finally:
        if os.path.exists(result_file):
            os.remove(result_file)
            print(f"Cleaned up: {result_file}")


def cmd_discover(args):
    """Handle 'opc discover' command."""
    from shared.device.discover import discover_all_devices, print_device_list
    devices = asyncio.run(discover_all_devices())
    if not args.quiet:
        print_device_list(devices)

    if args.set_default:
        if len(devices) == 1:
            dev = devices[0]
            save_config("default_device", dev.name)
            save_config("device_type", dev.device_type)
            print(f"\nSet default device to: {dev.name} ({dev.device_type})")
        else:
            print("\nMultiple devices found. Please specify a name:")
            print("  xt config --device <name>")


def cmd_voices(args):
    """Handle 'opc voices' command: list available voices for an engine."""
    cfg = load_config()
    engine = args.engine or cfg.get("tts_engine", "edge-tts")

    if engine == "edge-tts":
        subprocess.run(["edge-tts", "--list-voices"])
    elif engine == "qwen":
        print("Qwen3-TTS built-in speakers (custom_voice mode):\n")
        print(f"  {'Speaker':12s} {'Name':10s} {'Description':50s} {'Native':30s}")
        print(f"  {'-'*12} {'-'*10} {'-'*50} {'-'*30}")
        for name in QWEN_SPEAKERS:
            info = QWEN_SPEAKER_INFO.get(name)
            if info:
                cn_name, desc_en, desc_cn, lang = info
                display_name = cn_name or name
                print(f"  {name:12s} {display_name:10s} {desc_cn:50s} {lang}")
        print(f"\nUsage: xt tts 'text' -e qwen --speaker Vivian")
        print(f"       xt tts 'text' -e qwen --speaker Vivian --instruct '用愤怒的语气说'")
    else:
        print(f"Error: Unknown engine '{engine}'. Available: edge-tts, qwen")
        sys.exit(1)


def cmd_asr(args):
    """Handle 'opc asr' command."""
    audio = args.audio
    if not os.path.exists(audio):
        print(f"Error: Audio file not found: {audio}")
        sys.exit(1)

    cfg = load_config()
    model_size = args.model_size or cfg.get("asr_model_size", "1.7B")
    language = args.language or cfg.get("asr_language", "") or None
    output_dir = cfg.get("output_dir", tempfile.gettempdir())

    fmt = args.format  # "text", "json", "srt", "ass"

    if fmt == "text" or fmt is None:
        # Simple transcription
        text = asr_transcribe(audio, language=language, model_size=model_size)
        print(text)

    elif fmt == "json":
        result = asr_align(audio, language=language, model_size=model_size)
        output_path = args.output or os.path.join(output_dir,
            os.path.splitext(os.path.basename(audio))[0] + ".asr.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result_to_dict(result), f, ensure_ascii=False, indent=2)
        print(f"Saved: {output_path}")

    elif fmt in ("srt", "ass"):
        # Use pipeline for subtitle generation
        fix_dir = getattr(args, 'fix_dir', None)
        resume = getattr(args, 'resume_from', None)
        max_chars = min(getattr(args, 'max_chars', 14), 20)
        style = args.style or "neon"

        paths = run_pipeline(
            audio_path=audio,
            output_dir=output_dir,
            fmt="all",
            ass_style=style,
            fix_dir=fix_dir,
            language=language,
            model_size=model_size,
            max_chars=max_chars,
            resume_from=resume,
        )

        # Check if pipeline was blocked by check errors
        if "check_errors" in paths:
            print(f"\nRender blocked by {len(paths['check_errors'])} check error(s).")
            print(f"Lines file: {paths['lines_path']}")
            print("Fix the issues using 'opc asr-split', then re-run:")
            print(f"  xt asr {audio} --format {fmt} --resume-from render --max-chars {max_chars}")
            sys.exit(1)

        for name, path in paths.items():
            print(f"Saved: {path}")


def cmd_asr_split(args):
    """Handle 'opc asr-split' command: split subtitle lines by text match or CSV."""
    import csv as csv_mod
    lines_path = args.lines_json
    if not os.path.exists(lines_path):
        print(f"Error: File not found: {lines_path}")
        sys.exit(1)

    lines = _load_lines(lines_path)

    if args.csv:
        # Batch mode: read CSV with line_number,after_text columns
        if not os.path.exists(args.csv):
            print(f"Error: CSV file not found: {args.csv}")
            sys.exit(1)

        rules = []
        with open(args.csv, "r", encoding="utf-8") as f:
            reader = csv_mod.reader(f)
            for row in reader:
                if not row or row[0].strip().startswith("#"):
                    continue
                if len(row) >= 2:
                    li = int(row[0].strip())
                    after = row[1].strip()
                    rules.append((li, after))

        print(f"Applying {len(rules)} split rules from {args.csv}...")

        # Sort descending by line index so splits don't shift earlier line numbers
        rules.sort(key=lambda r: r[0], reverse=True)

        for li, after in rules:
            if li < 1 or li > len(lines):
                print(f"  Skip line {li}: out of range")
                continue
            try:
                lines = split_line_after(lines, li, after)
                print(f"  Line {li}: OK")
            except ValueError as e:
                print(f"  Line {li}: {e}")

    else:
        # Single mode
        line_idx = args.line
        after_text = args.after

        if line_idx < 1 or line_idx > len(lines):
            print(f"Error: Line index {line_idx} out of range (1-{len(lines)})")
            sys.exit(1)

        print(f"Line {line_idx}: \"{lines[line_idx - 1].text}\"")

        try:
            lines = split_line_after(lines, line_idx, after_text)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

        print("Result:")
        for i, l in enumerate(lines):
            marker = " → " if line_idx - 1 <= i < line_idx + 1 else "   "
            print(f"  {marker}Line {i+1}: \"{l.text}\"")

    # Save
    _save_lines(lines, lines_path)
    print(f"Saved: {lines_path}")

    # Re-run check
    print()
    errors = stage_check(lines, max_chars=14)
    if not errors:
        print("Ready to render. Re-run with --resume-from render")


def cmd_cut(args):
    """Handle 'opc cut' command: start cutx video editing server using Node.js dashboard."""
    import subprocess
    import webbrowser
    import time

    # Get the directory where this script is located
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    SKILL_DIR = os.path.dirname(SCRIPT_DIR)
    DASHBOARD_SERVER_DIR = os.path.join(SKILL_DIR, 'dashboard', 'server')

    print(f"[OPC] Starting Cut Dashboard server at {DASHBOARD_SERVER_DIR}")

    # Check if node_modules exists
    node_modules = os.path.join(DASHBOARD_SERVER_DIR, 'node_modules')
    if not os.path.exists(node_modules):
        print("[OPC] node_modules not found. Running 'npm install'...")
        subprocess.run(['npm', 'install'], cwd=DASHBOARD_SERVER_DIR, check=True)
        print("[OPC] Dependencies installed.")

    # Check if dist exists (built frontend)
    dist_dir = os.path.join(DASHBOARD_SERVER_DIR, 'dist')
    if not os.path.exists(dist_dir):
        print("[OPC] Frontend not built. Running 'npm run build'...")
        subprocess.run(['npm', 'run', 'build'], cwd=DASHBOARD_SERVER_DIR, check=True)
        print("[OPC] Frontend built.")

    # Default port
    port = args.port or 8080

    # Start the Node.js server
    print(f"[OPC] Starting server on port {port}...")
    server_proc = subprocess.Popen(
        ['node', 'server.js'],
        cwd=DASHBOARD_SERVER_DIR,
        env={**os.environ, 'PORT': str(port)},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    # Wait a bit for server to start
    time.sleep(2)

    # Check if server started successfully
    if server_proc.poll() is None:
        url = f'http://localhost:{port}'
        print(f"[OPC] Server started at {url}")
        print(f"[OPC] Open your browser to: {url}/skill/cut")

        # Open browser if not disabled
        if not args.no_browser:
            webbrowser.open(f'{url}/skill/cut')
            print("[OPC] Browser opened.")

        # Keep server running
        try:
            server_proc.wait()
        except KeyboardInterrupt:
            print("\n[OPC] Shutting down server...")
            server_proc.terminate()
            server_proc.wait()
    else:
        print("[OPC] Failed to start server. Check logs above.")
        sys.exit(1)


def cmd_cut_start_server(args):
    """Handle 'opc cut start-server' command (alias for opc cut)."""
    # For backwards compatibility, just call cmd_cut with the same args
    cmd_cut(args)


def cmd_image(args):
    """Handle 'opc image' command."""
    image_action = getattr(args, "image_action", None)
    if image_action == "list":
        _cmd_image_list(args)
    elif image_action == "info":
        _cmd_image_info(args)
    elif image_action == "import_wf":
        _cmd_image_import(args)
    elif image_action == "analyze":
        _cmd_image_analyze(args)
    elif image_action == "test":
        _cmd_image_test(args)
    elif image_action == "kg":
        _cmd_image_kg(args)
    else:
        _cmd_image_generate(args)


def _cmd_image_list(args):
    workflows = discover_workflows()
    if not workflows:
        print("No workflows found. Use 'opc image import <file> --name <alias>' to add one.")
        return
    for alias, meta in workflows:
        desc = meta.get("description", "")
        print(f"  {alias:20s} {desc}")
    print(f"\n{len(workflows)} workflow(s) available.")


def _cmd_image_info(args):
    alias = args.alias
    try:
        workflow, meta = load_workflow(alias)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    print(f"Alias: {meta.get('alias', alias)}")
    print(f"Description: {meta.get('description', '')}")
    print(f"\nParameters:")
    for name, spec in meta.get("params", {}).items():
        ptype = spec.get("type", "?")
        required = "required" if spec.get("required") else "optional"
        default = spec.get("default", "")
        desc = spec.get("description", "")
        parts = f"  --{name} ({ptype}, {required})"
        if default != "" and default is not None:
            parts += f", default={default}"
        if desc:
            parts += f" -- {desc}"
        print(parts)


def _cmd_image_import(args):
    try:
        dest = import_workflow(args.file, args.name)
        print(f"Imported: {dest}")
        print(f"Next step: create a meta.json file for this workflow.")
        print(f"  Use 'opc image analyze {dest}' to understand its structure.")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error: {e}")
        sys.exit(1)


def _cmd_image_analyze(args):
    if getattr(args, "describe", False):
        _cmd_image_describe(args)
        return
    try:
        report = analyze_workflow(args.file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error: {e}")
        sys.exit(1)
    print(json.dumps(report, indent=2, ensure_ascii=False))


def _validate_image_file(path):
    """Validate that path exists and is an image file."""
    if not os.path.exists(path):
        print(f"Error: File not found: {path}")
        sys.exit(1)
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        print(f"Error: Only supports image files (PNG/JPG/WEBP), got: {ext}")
        sys.exit(1)


def _cmd_image_describe(args):
    cfg = load_config()
    image_path = args.file
    _validate_image_file(image_path)

    compare_path = getattr(args, "compare", None)
    if compare_path:
        _validate_image_file(compare_path)

    prompt = args.prompt or ""

    # Try ComfyUI metadata extraction first
    comfy_meta = extract_comfyui_metadata(image_path)
    if comfy_meta:
        print("=== ComfyUI Metadata Found ===", file=sys.stderr)
        if "positive_prompt" in comfy_meta:
            print(f"Positive prompt ({len(comfy_meta['positive_prompt'])} chars):", file=sys.stderr)
            print(comfy_meta["positive_prompt"], file=sys.stderr)
        if "negative_prompt" in comfy_meta:
            print(f"\nNegative prompt: {comfy_meta['negative_prompt']}", file=sys.stderr)
        if "resolution" in comfy_meta:
            r = comfy_meta["resolution"]
            print(f"\nResolution: {r['width']}x{r['height']}", file=sys.stderr)
        for k in ["seed", "steps", "cfg", "sampler", "scheduler", "batch_size"]:
            if k in comfy_meta:
                print(f"  {k}: {comfy_meta[k]}", file=sys.stderr)
        print(file=sys.stderr)

    if compare_path:
        prompt = prompt or (
            "I'm showing you two images. The FIRST image is the reference/target, "
            "the SECOND image is the generated attempt. "
            "Please compare them in detail:\n"
            "1. What are the key differences in style, composition, and color?\n"
            "2. What elements does the generated image capture well?\n"
            "3. What elements are missing or different from the reference?\n"
            "4. Rate the similarity from 1-10.\n"
            "5. Provide specific suggestions to make the generated image closer to the reference."
        )
        print(f"Comparing images with vision model...", file=sys.stderr)
        try:
            result = compare_images(image_path, compare_path, prompt, cfg)
            if comfy_meta:
                result["comfyui_metadata"] = comfy_meta
            print(json.dumps(result, indent=2, ensure_ascii=False))
        except ValueError as e:
            print(f"Config error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        prompt = prompt or (
            "Describe this image in detail. Include: main subject, style, composition, "
            "lighting, colors, mood, and any notable details. "
            "If this appears to be an AI-generated image, note any artifacts or issues."
        )
        print(f"Analyzing image with vision model...", file=sys.stderr)
        try:
            result = describe_image(image_path, prompt, cfg)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        except ValueError as e:
            print(f"Config error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)


def _cmd_image_test(args):
    cfg = load_config()
    print("Checking ComfyUI connection...")
    if not check_connection(cfg):
        print(f"Error: Cannot connect to ComfyUI at {get_server_url(cfg)}")
        print("Make sure ComfyUI is running. Configure with:")
        print("  opc config --set-comfyui-host <host>")
        print("  opc config --set-comfyui-port <port>")
        sys.exit(1)
    print(f"Connected to ComfyUI at {get_server_url(cfg)}")

    alias = args.alias
    try:
        workflow, meta = load_workflow(alias)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    raw_prompt = args.prompt.strip()
    is_json = raw_prompt.startswith("{")
    prompt_text = raw_prompt
    negative_text = ""

    if is_json:
        try:
            prompt_json = json.loads(raw_prompt)
            issues = validate_json_prompt(prompt_json)
            if issues:
                print(f"JSON prompt warnings: {issues}", file=sys.stderr)
            converted = json_prompt_to_text(prompt_json)
            prompt_text = converted["positive"]
            negative_text = converted["negative"]
            if negative_text:
                print(f"Note: negative prompt detected but current workflow may not support it: {negative_text[:100]}...", file=sys.stderr)
            print(f"JSON prompt converted to: {prompt_text[:100]}...", file=sys.stderr)
        except json.JSONDecodeError as e:
            print(f"Error: Prompt looks like JSON but failed to parse: {e}")
            sys.exit(1)

    params = {}
    for name, spec in meta.get("params", {}).items():
        if spec.get("required"):
            params[name] = prompt_text if name == "prompt" else spec.get("default", "")
        elif spec.get("default") is not None:
            params[name] = spec["default"]

    # Auto-inject negative prompt from JSON conversion if workflow supports it
    if negative_text and "negative_prompt" in meta.get("params", {}):
        params["negative_prompt"] = negative_text
        print(f"Auto-injected negative prompt ({len(negative_text)} chars)", file=sys.stderr)

    print(f"Testing workflow '{alias}' with prompt: {prompt_text[:50]}...")
    try:
        prepared = inject_params(workflow, meta, params)
        output_prefix = meta.get("alias", "test")
        result = generate_image(prepared, cfg, filename_prefix=output_prefix,
                                prompt=prompt_text)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)


def _cmd_image_generate(args):
    cfg = load_config()
    alias = args.alias
    if not alias:
        print("Error: Specify a workflow alias. Use 'opc image list' to see available workflows.")
        sys.exit(1)

    try:
        workflow, meta = load_workflow(alias)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    params = {}
    raw_prompt = getattr(args, "prompt", None)
    if not raw_prompt:
        print("Error: --prompt is required for generation.")
        print("  JSON example: -p '{\"subject\":\"a cat\",\"style\":\"digital art\"}'")
        print("  Text example:  --text -p \"a beautiful sunset\"")
        sys.exit(1)
    prompt_text = raw_prompt
    negative_text = ""

    if raw_prompt:
        raw_prompt = raw_prompt.strip()
        if args.text:
            # Plain text mode
            prompt_text = raw_prompt
        else:
            # Default: JSON structured prompt mode
            try:
                prompt_json = json.loads(raw_prompt)
            except json.JSONDecodeError:
                print("\n" + "=" * 60)
                print("  JSON PROMPT FORMAT REQUIRED")
                print("=" * 60)
                print("\nYour prompt could not be parsed as JSON structured format.")
                print("\nIf you want to use plain text, add the --text flag:")
                print("  opc image -w <alias> --text -p \"your plain text prompt\"")
                print("\n--- Why use JSON structured prompts? ---")
                print("  1. 8-15% higher CLIP score & 20-30% lower FID")
                print("  2. Automatic negative prompt injection")
                print("  3. Semantic token weighting")
                print("  4. Model-agnostic structure (works across SD/Flux/DALL-E)")
                print("  5. Better token efficiency (~12% fewer tokens)")
                print("  6. Built-in style control and multi-subject isolation")
                print("  7. Easier to edit, version, and programmatically generate")
                print("  8. Reusable templates with parameter substitution")
                print("\n--- Explore prompt structure with Knowledge Graph ---")
                print("  opc image kg list              # Show all categories")
                print("  opc image kg skeleton subject:food lighting:neon")
                print("  opc image kg search portrait")
                print("\n--- Quick JSON example ---")
                print('{\"subject\": \"a cyberpunk cat\", \"style\": \"digital art\"}')
                print("=" * 60 + "\n")
                sys.exit(1)

            issues = validate_json_prompt(prompt_json)
            if issues:
                print(f"JSON prompt warnings: {issues}", file=sys.stderr)

            # Extract negative_constraints for negative prompt
            nc = prompt_json.get("negative_constraints", [])
            if isinstance(nc, list):
                negative_text = ", ".join(nc)
            elif isinstance(nc, str):
                negative_text = nc
            else:
                negative_text = ""
            # Remove negative_constraints from JSON before sending as prompt
            prompt_json_clean = {k: v for k, v in prompt_json.items() if k != "negative_constraints"}
            prompt_text = json.dumps(prompt_json_clean, ensure_ascii=False)
            if negative_text:
                print(f"Note: negative prompt extracted ({len(negative_text)} chars)", file=sys.stderr)
            print(f"JSON prompt passed as-is ({len(prompt_text)} chars)", file=sys.stderr)
        params["prompt"] = prompt_text

    param_list = getattr(args, "param", []) or []
    for pv in param_list:
        if "=" not in pv:
            print(f"Error: --param requires key=value format, got: {pv}")
            sys.exit(1)
        key, value = pv.split("=", 1)
        params[key.strip()] = value.strip()

    # Auto-inject negative prompt from JSON conversion if workflow supports it
    if negative_text and "negative_prompt" in meta.get("params", {}):
        params["negative_prompt"] = negative_text
        print(f"Auto-injected negative prompt ({len(negative_text)} chars)", file=sys.stderr)

    for name, spec in meta.get("params", {}).items():
        if spec.get("required") and name not in params:
            print(f"Error: Missing required parameter '{name}'")
            print(f"  Use: --prompt \"text\" or --param {name}=value")
            sys.exit(1)

    try:
        prepared = inject_params(workflow, meta, params)
        output_prefix = meta.get("alias", alias)
        # Override output directory if -o is specified
        output_dir = getattr(args, "output", None)
        if output_dir:
            cfg["image_output_dir"] = output_dir
        result = generate_image(prepared, cfg, filename_prefix=output_prefix,
                                prompt=prompt_text)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_image_edit(args):
    """Handle 'opc image-edit' — edit images using ComfyUI workflows."""
    cfg = load_config()
    alias = getattr(args, "alias", None) or "klein-edit"
    images = getattr(args, "images", [])

    if not images:
        print("Error: Provide at least one image with --image <path>.")
        sys.exit(1)

    prompt_text = getattr(args, "prompt", None)
    if not prompt_text:
        print("Error: --prompt is required. Describe how to edit the image.")
        print('  Example: opc image-edit --image photo.png -p "add a red hat"')
        sys.exit(1)

    try:
        workflow, meta = load_workflow(alias)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    server_url = get_server_url(cfg)
    if not check_connection(cfg):
        print(f"Error: Cannot connect to ComfyUI at {server_url}.", file=sys.stderr)
        sys.exit(1)

    # Upload images and inject filenames into workflow
    image_params = meta.get("image_params", {})
    uploaded_names = []
    for i, img_path in enumerate(images):
        print(f"Uploading image {i + 1}/{len(images)}: {img_path}", file=sys.stderr)
        try:
            remote_name = upload_image(img_path, server_url)
            uploaded_names.append(remote_name)
            print(f"  -> {remote_name}", file=sys.stderr)
        except Exception as e:
            print(f"Error uploading {img_path}: {e}", file=sys.stderr)
            sys.exit(1)

    # Inject uploaded image names into the appropriate nodes
    result_wf = json.loads(json.dumps(workflow))
    for i, remote_name in enumerate(uploaded_names):
        param_key = f"image_{i}" if i > 0 else "image"
        spec = image_params.get(param_key)
        if spec:
            node_id = spec["node"]
            field = spec.get("field", "image")
            if node_id in result_wf:
                result_wf[node_id]["inputs"][field] = remote_name
            else:
                print(f"Warning: node '{node_id}' not found for image param '{param_key}'", file=sys.stderr)

    # Inject regular params (prompt, seed, steps, etc.)
    params = {"prompt": prompt_text}
    param_list = getattr(args, "param", []) or []
    for pv in param_list:
        if "=" not in pv:
            print(f"Error: --param requires key=value format, got: {pv}")
            sys.exit(1)
        key, value = pv.split("=", 1)
        params[key.strip()] = value.strip()

    negative_text = ""
    if not getattr(args, "text", False):
        try:
            prompt_json = json.loads(prompt_text)
            nc = prompt_json.get("negative_constraints", [])
            if isinstance(nc, list):
                negative_text = ", ".join(nc)
            elif isinstance(nc, str):
                negative_text = nc
            prompt_json_clean = {k: v for k, v in prompt_json.items() if k != "negative_constraints"}
            prompt_text = json.dumps(prompt_json_clean, ensure_ascii=False)
            params["prompt"] = prompt_text
        except json.JSONDecodeError:
            pass  # treat as plain text
    else:
        params["prompt"] = prompt_text

    if negative_text and "negative_prompt" in meta.get("params", {}):
        params["negative_prompt"] = negative_text

    result_wf = inject_params(result_wf, meta, params)

    output_dir = getattr(args, "output", None)
    if output_dir:
        cfg["image_output_dir"] = output_dir
    output_prefix = meta.get("alias", alias)

    try:
        result = generate_image(result_wf, cfg, filename_prefix=output_prefix,
                                prompt=prompt_text)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_image_kg(args):
    kg = PromptKG()
    kg_action = getattr(args, "kg_action", None)

    if kg_action == "list":
        cat = getattr(args, "category", None)
        if cat:
            items = kg.list_category(cat)
            if not items:
                print(f"No entities in category '{cat}'. Available: {', '.join(kg.categories)}")
                sys.exit(1)
            print(json.dumps(items, ensure_ascii=False, indent=2))
        else:
            for c in kg.categories:
                items = kg.list_category(c)
                names = ", ".join(f"{i['name']}({i['count']})" for i in items)
                print(f"  {c:15s} {names}")

    elif kg_action == "info":
        r = kg.info(args.entity)
        if not r:
            print(f"Entity '{args.entity}' not found. Use 'opc image kg search <keyword>'.")
            sys.exit(1)
        print(json.dumps(r, ensure_ascii=False, indent=2))

    elif kg_action == "search":
        results = kg.search(args.keyword)
        if not results:
            print(f"No entities matching '{args.keyword}'.")
            sys.exit(1)
        print(json.dumps(results, ensure_ascii=False, indent=2))

    elif kg_action == "query":
        recs = kg.neighbors(args.entity,
                            category=getattr(args, "category", None),
                            top_n=getattr(args, "top", 10))
        if not recs:
            print(f"No relations for '{args.entity}'.")
            sys.exit(1)
        print(json.dumps(recs, ensure_ascii=False, indent=2))

    elif kg_action == "skeleton":
        if not args.entities:
            print("Error: Provide at least one entity. e.g. opc image kg skeleton subject:food")
            sys.exit(1)
        result = kg.skeleton(args.entities)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif kg_action == "validate":
        if len(args.entities) < 2:
            print("Error: Provide at least 2 entities to validate.")
            sys.exit(1)
        result = kg.validate(args.entities)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif kg_action == "similar":
        if not args.entities:
            print("Error: Provide at least one entity.")
            sys.exit(1)
        results = kg.find_prompts(args.entities, top_n=getattr(args, "top", 5))
        if not results:
            print("No matching prompts found.")
            sys.exit(1)
        print(json.dumps(results, ensure_ascii=False, indent=2))

    elif kg_action == "templates":
        entity = getattr(args, "entity", None)
        if entity:
            results = kg.find_templates(entity)
            if not results:
                print(f"No templates related to '{entity}'.")
                sys.exit(1)
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            templates = kg.list_templates()
            if not templates:
                print("No templates available.")
                sys.exit(1)
            for t in templates:
                scenes = ", ".join(t["scenes"])
                res = t.get("resolution", {})
                print(f"  {t['name']:20s} {t['description'][:60]}")
                print(f"  {'':20s} scenes: {scenes}")
                print(f"  {'':20s} resolution: {res.get('width', '?')}x{res.get('height', '?')}")
                print()

    else:
        print("Usage: opc image kg <list|info|search|query|skeleton|validate|similar|templates>")
        print("  list [--category CAT]          Show all entities")
        print("  info <entity>                   Entity details")
        print("  search <keyword>                Fuzzy search")
        print("  query <entity> [--category C]    What goes with X?")
        print("  skeleton <e1> [e2] ...          Full prompt plan")
        print("  validate <e1> <e2> [e3] ...     Check combination")
        print("  similar <e1> [e2] ...           Find similar prompts")
        print("  templates [--entity E]           List templates or find by entity")


def cmd_audio(args):
    """Handle 'opc audio' command: audio processing (compress, analyze, etc.)."""
    audio_action = getattr(args, "audio_action", None)

    if audio_action == "compress":
        _cmd_audio_compress(args)
    elif audio_action == "analyze":
        _cmd_audio_analyze(args)
    elif audio_action == "presets":
        _cmd_audio_presets(args)
    else:
        print("Usage: opc audio <compress|analyze|presets>")
        print("  compress <file>    Apply dynamic range compression")
        print("  analyze <file>     Analyze audio loudness (LUFS)")
        print("  presets            List available compressor presets")


def _cmd_audio_compress(args):
    """Apply compression to an audio file."""
    input_path = args.input
    if not os.path.exists(input_path):
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    # Build parameters
    params = {}
    if args.preset:
        params = apply_preset(args.preset)
        print(f"Using preset: {args.preset}")
    else:
        # Use explicit parameters or defaults from screenshot
        params = {
            "threshold": args.threshold,
            "ratio": args.ratio,
            "attack": args.attack,
            "release": args.release,
            "knee": args.knee,
            "makeup": args.makeup,
            "mix": args.mix,
        }

    print(f"Parameters: threshold={params['threshold']}dB, ratio={params['ratio']}:1, "
          f"attack={params['attack']}ms, release={params['release']}ms, "
          f"knee={params['knee']}dB, makeup={params['makeup']}dB, mix={params['mix']}")

    try:
        output_path = compress_audio(
            input_path,
            output_path=args.output,
            **params,
        )
        print(f"Compressed: {output_path}")

        # Show file sizes
        input_size = os.path.getsize(input_path) / 1024 / 1024
        output_size = os.path.getsize(output_path) / 1024 / 1024
        print(f"  Input:  {input_size:.2f} MB")
        print(f"  Output: {output_size:.2f} MB")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def _cmd_audio_analyze(args):
    """Analyze audio loudness."""
    input_path = args.input
    if not os.path.exists(input_path):
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    print(f"Analyzing: {input_path}")
    result = analyze_loudness(input_path)

    if result.get("integrated_lufs") is not None:
        print(f"  Integrated loudness: {result['integrated_lufs']:.1f} LUFS")
    else:
        print("  Integrated loudness: N/A")

    if result.get("loudness_range") is not None:
        print(f"  Loudness range:      {result['loudness_range']:.1f} LU")
    else:
        print("  Loudness range:      N/A")

    if result.get("true_peak") is not None:
        print(f"  True peak:           {result['true_peak']:.1f} dB")
    else:
        print("  True peak:           N/A")


def _cmd_audio_presets(args):
    """List available compressor presets."""
    presets = list_presets()
    print("Available compressor presets:")
    for name, desc in presets.items():
        print(f"  {name:12s} {desc}")
    print("\nUsage: opc audio compress file.mp3 --preset voice")


def cmd_video_gen(args):
    """Handle 'opc video-gen' command — generate videos via ComfyUI workflows."""
    cfg = load_config()
    alias = getattr(args, "alias", None)
    if not alias:
        print("Error: Specify a workflow alias. Use 'opc video-gen list' to see available workflows.")
        sys.exit(1)

    # Use image workflow system — video workflows are stored alongside image ones
    try:
        workflow, meta = load_workflow(alias)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    server_url = video_get_server_url(cfg)
    if not video_check_connection(cfg):
        print(f"Error: Cannot connect to ComfyUI at {server_url}.", file=sys.stderr)
        sys.exit(1)

    # Upload images if provided
    image_params = meta.get("image_params", {})
    uploaded_names = {}

    # Handle i2v (single image)
    image_path = getattr(args, "image", None)
    if image_path:
        print(f"Uploading image: {image_path}", file=sys.stderr)
        try:
            remote_name = video_upload_image(image_path, server_url)
            uploaded_names["image"] = remote_name
            print(f"  -> {remote_name}", file=sys.stderr)
        except Exception as e:
            print(f"Error uploading {image_path}: {e}", file=sys.stderr)
            sys.exit(1)

    # Handle flf (first/last frames)
    first_frame = getattr(args, "first_frame", None)
    if first_frame:
        print(f"Uploading first frame: {first_frame}", file=sys.stderr)
        try:
            remote_name = video_upload_image(first_frame, server_url)
            uploaded_names["first_frame"] = remote_name
            print(f"  -> {remote_name}", file=sys.stderr)
        except Exception as e:
            print(f"Error uploading {first_frame}: {e}", file=sys.stderr)
            sys.exit(1)

    last_frame = getattr(args, "last_frame", None)
    if last_frame:
        print(f"Uploading last frame: {last_frame}", file=sys.stderr)
        try:
            remote_name = video_upload_image(last_frame, server_url)
            uploaded_names["last_frame"] = remote_name
            print(f"  -> {remote_name}", file=sys.stderr)
        except Exception as e:
            print(f"Error uploading {last_frame}: {e}", file=sys.stderr)
            sys.exit(1)

    # Build workflow copy and inject uploaded image names
    result_wf = json.loads(json.dumps(workflow))
    for param_key, remote_name in uploaded_names.items():
        spec = image_params.get(param_key)
        if spec:
            node_id = spec["node"]
            field = spec.get("field", "image")
            if node_id in result_wf:
                result_wf[node_id]["inputs"][field] = remote_name
            else:
                print(f"Warning: node '{node_id}' not found for image param '{param_key}'", file=sys.stderr)

    # Inject prompt and other params
    params = {}
    prompt_text = args.prompt or ""
    if prompt_text:
        params["prompt"] = prompt_text

    param_list = getattr(args, "param", []) or []
    for pv in param_list:
        if "=" not in pv:
            print(f"Error: --param requires key=value format, got: {pv}")
            sys.exit(1)
        key, value = pv.split("=", 1)
        params[key.strip()] = value.strip()

    # Calculate frames from duration and fps for video workflows
    if "duration" in params and "frame_rate" in params:
        try:
            duration = int(params["duration"])
            fps = int(params["frame_rate"])
            params["frames"] = duration * fps
            print(f"  Calculated frames: {params['frames']} ({duration}s * {fps}fps)", file=sys.stderr)
        except ValueError:
            pass

    # Handle --turbo flag: switch model/LoRA for faster generation
    turbo = getattr(args, "turbo", False)
    if turbo:
        print("Turbo mode enabled (distilled model)", file=sys.stderr)
        # For i2v: turbo is controlled via LoRA strength (already in meta params)
        if "turbo" in meta.get("params", {}):
            params["turbo"] = meta["params"]["turbo"]["default"]  # 0.5
        # For flf: turbo switches checkpoint model
        turbo_cfg = meta.get("turbo_config")
        if turbo_cfg:
            ckpt_value = turbo_cfg.get("enabled", {}).get("ckpt_name")
            field = turbo_cfg.get("field", "ckpt_name")
            for node_key, node_id in turbo_cfg.get("nodes", {}).items():
                if node_id in result_wf and ckpt_value:
                    result_wf[node_id]["inputs"][field] = ckpt_value
                    print(f"  Turbo: set {node_key} -> {ckpt_value}", file=sys.stderr)
        # Turbo mode: use distilled sigma schedules
        # Two-stage workflow: 8 + 4 steps
        # Single-stage workflow: LTXVScheduler (15 steps) + ManualSigmas (8 steps)
        main_sigmas_node = "4984"
        refine_sigmas_node = "4985"
        scheduler_node = "4966"
        if scheduler_node in result_wf:
            # Single-stage: LTXVScheduler with 15 steps
            result_wf[scheduler_node]["inputs"]["steps"] = 15
            print(f"  Turbo: scheduler set to 15 steps", file=sys.stderr)
        elif main_sigmas_node in result_wf:
            # Two-stage: ManualSigmas 8 steps
            result_wf[main_sigmas_node]["inputs"]["sigmas"] = "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"
            print(f"  Turbo: main sampler set to 8 steps", file=sys.stderr)
        if refine_sigmas_node in result_wf:
            result_wf[refine_sigmas_node]["inputs"]["sigmas"] = "0.85, 0.7250, 0.4219, 0.0"
            print(f"  Turbo: refine sampler set to 4 steps", file=sys.stderr)
    else:
        # Standard mode: disable turbo optimizations, use more steps for quality
        if "turbo" in meta.get("params", {}):
            # Standard mode: bypass ALL LoRA nodes by rewiring model connections
            # from CheckpointLoader directly to Guider nodes
            ckpt_node = "3940"  # CheckpointLoaderSimple
            # Find all LoRA nodes in the workflow
            lora_nodes = []
            for nid, node in result_wf.items():
                if isinstance(node, dict) and node.get("class_type") == "LoraLoaderModelOnly":
                    lora_nodes.append(nid)
            # Rewire all nodes that receive model from any LoRA
            for nid, node in result_wf.items():
                if not isinstance(node, dict):
                    continue
                for field, val in node.get("inputs", {}).items():
                    if isinstance(val, list) and len(val) == 2 and val[0] in lora_nodes:
                        node["inputs"][field] = [ckpt_node, 0]
                        print(f"  Standard: bypass LoRA {val[0]}, rewired {nid} to {ckpt_node}", file=sys.stderr)
            # Standard mode: increase steps for quality (no LoRA acceleration)
            scheduler_node = "4966"
            main_sigmas_node = "4984"
            refine_sigmas_node = "4985"
            if scheduler_node in result_wf:
                # Single-stage: increase LTXVScheduler steps
                result_wf[scheduler_node]["inputs"]["steps"] = 30
                print(f"  Standard: scheduler set to 30 steps", file=sys.stderr)
            elif main_sigmas_node in result_wf:
                # Two-stage: increase main sampler steps
                steps = 40
                sigmas = ", ".join(f"{1.0 - i/(steps-1):.4f}" for i in range(steps))
                result_wf[main_sigmas_node]["inputs"]["sigmas"] = sigmas
                print(f"  Standard: main sampler set to {steps} steps", file=sys.stderr)
            if refine_sigmas_node in result_wf:
                result_wf[refine_sigmas_node]["inputs"]["sigmas"] = "0.8500, 0.7250, 0.4219, 0.0000"
                print(f"  Standard: refine sampler set to 4 steps", file=sys.stderr)
        turbo_cfg = meta.get("turbo_config")
        if turbo_cfg:
            ckpt_value = turbo_cfg.get("disabled", {}).get("ckpt_name")
            field = turbo_cfg.get("field", "ckpt_name")
            for node_key, node_id in turbo_cfg.get("nodes", {}).items():
                if node_id in result_wf and ckpt_value:
                    result_wf[node_id]["inputs"][field] = ckpt_value

    for name, spec in meta.get("params", {}).items():
        if spec.get("required") and name not in params:
            print(f"Error: Missing required parameter '{name}'")
            print(f"  Use: --prompt \"text\" or --param {name}=value")
            sys.exit(1)

    result_wf = inject_params(result_wf, meta, params)

    output_dir = getattr(args, "output", None)
    if output_dir:
        cfg["video_output_dir"] = output_dir
    output_prefix = meta.get("alias", alias)

    try:
        result = generate_video(result_wf, cfg, filename_prefix=output_prefix,
                                prompt=prompt_text)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_video_describe(args):
    """Handle 'opc video-describe' command — describe a video using vision model."""
    video_path = args.video
    if not os.path.exists(video_path):
        print(f"Error: Video file not found: {video_path}")
        sys.exit(1)

    cfg = load_config()
    if args.api_url:
        cfg["video_desc_api_url"] = args.api_url
    if args.api_key:
        cfg["video_desc_api_key"] = args.api_key
    if args.model:
        cfg["video_desc_model"] = args.model

    try:
        result = describe_video(
            video_path,
            prompt_text=args.prompt,
            cfg=cfg,
            num_frames=args.frames,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except ValueError as e:
        print(f"Config error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_video_transcribe(args):
    """Handle 'opc video-transcribe' command — download video and transcribe."""
    import tempfile
    import os

    url = args.url
    output_dir = args.output_dir or tempfile.gettempdir()
    language = args.language
    model_size = args.model_size or "1.7B"

    try:
        # Step 1: Download video
        video_path = download_video(url, output_dir)

        # Step 2: Extract audio
        audio_path = extract_audio(video_path, output_dir)

        # Step 3: Transcribe
        text = transcribe_audio(audio_path, language=language, model_size=model_size)

        # Step 4: Save transcript
        transcript_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(video_path))[0]}_transcript.txt")
        save_transcript(text, transcript_path)

        # Step 5: Summary
        summary = summarize_text(text)

        # Cleanup. yt-dlp may return the final WAV directly, in which case
        # video_path and audio_path refer to the same file.
        cleanup_paths = set()
        if not args.keep_video:
            cleanup_paths.add(video_path)
        if not args.keep_audio:
            cleanup_paths.add(audio_path)
        for path in cleanup_paths:
            if os.path.exists(path):
                os.remove(path)
                print(f"Removed: {path}", file=sys.stderr)

        # Output result
        result = {
            "transcript_path": transcript_path,
            "transcript_preview": text[:200] + "..." if len(text) > 200 else text,
            "summary": summary,
            "language": language or "auto-detected",
            "model_size": model_size,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_config(args):
    """Handle 'opc config' command."""
    if args.set_engine:
        save_config("tts_engine", args.set_engine)
        print(f"tts_engine = {args.set_engine}")
    if args.set_voice:
        save_config("edge_voice", args.set_voice)
        print(f"edge_voice = {args.set_voice}")
    if args.set_mode:
        save_config("qwen_mode", args.set_mode)
        print(f"qwen_mode = {args.set_mode}")
    if args.set_speaker:
        save_config("qwen_speaker", args.set_speaker)
        print(f"qwen_speaker = {args.set_speaker}")
    if args.set_model_size:
        save_config("qwen_model_size", args.set_model_size)
        print(f"qwen_model_size = {args.set_model_size}")
    if args.set_format:
        save_config("tts_format", args.set_format)
        print(f"tts_format = {args.set_format}")
    if args.set_language:
        save_config("qwen_language", args.set_language)
        print(f"qwen_language = {args.set_language}")
    if args.set_edge_rate:
        save_config("edge_rate", args.set_edge_rate)
        print(f"edge_rate = {args.set_edge_rate}")
    if args.set_edge_pitch:
        save_config("edge_pitch", args.set_edge_pitch)
        print(f"edge_pitch = {args.set_edge_pitch}")
    if args.set_edge_volume:
        save_config("edge_volume", args.set_edge_volume)
        print(f"edge_volume = {args.set_edge_volume}")
    if args.device:
        save_config("default_device", args.device)
        print(f"default_device = {args.device}")
    if args.set_asr_model_size:
        save_config("asr_model_size", args.set_asr_model_size)
        print(f"asr_model_size = {args.set_asr_model_size}")
    if args.set_asr_language:
        save_config("asr_language", args.set_asr_language)
        print(f"asr_language = {args.set_asr_language}")
    if args.set_workspace:
        save_config("workspace_dir", args.set_workspace)
        print(f"workspace_dir = {args.set_workspace}")
    if args.set_dashboard_host:
        save_config("dashboard_host", args.set_dashboard_host)
        print(f"dashboard_host = {args.set_dashboard_host}")
    if args.set_dashboard_port:
        save_config("dashboard_port", args.set_dashboard_port)
        print(f"dashboard_port = {args.set_dashboard_port}")
    if args.set_cut_server_port:
        save_config("cut_server_port", args.set_cut_server_port)
        print(f"cut_server_port = {args.set_cut_server_port}")
    if args.set_backend:
        save_config("backend", args.set_backend)
        print(f"backend = {args.set_backend}")
    if args.set_model_source:
        save_config("model_source", args.set_model_source)
        print(f"model_source = {args.set_model_source}")
    if args.set_model_cache_dir:
        save_config("model_cache_dir", args.set_model_cache_dir)
        print(f"model_cache_dir = {args.set_model_cache_dir}")
    if args.set_comfyui_host:
        save_config("comfyui_host", args.set_comfyui_host)
        print(f"comfyui_host = {args.set_comfyui_host}")
    if args.set_comfyui_port:
        save_config("comfyui_port", args.set_comfyui_port)
        print(f"comfyui_port = {args.set_comfyui_port}")
    if args.set_image_output_dir:
        save_config("image_output_dir", args.set_image_output_dir)
        print(f"image_output_dir = {args.set_image_output_dir}")
    if args.set_vision_api_url:
        save_config("vision_api_url", args.set_vision_api_url)
        print(f"vision_api_url = {args.set_vision_api_url}")
    if args.set_vision_api_key:
        save_config("vision_api_key", args.set_vision_api_key)
        print(f"vision_api_key = {'*' * 8}{args.set_vision_api_key[-4:]}" if len(args.set_vision_api_key) > 4 else "vision_api_key = ****")
    if args.set_vision_model:
        save_config("vision_model", args.set_vision_model)
        print(f"vision_model = {args.set_vision_model}")
    if args.set_video_desc_api_url:
        save_config("video_desc_api_url", args.set_video_desc_api_url)
        print(f"video_desc_api_url = {args.set_video_desc_api_url}")
    if args.set_video_desc_api_key:
        save_config("video_desc_api_key", args.set_video_desc_api_key)
        print(f"video_desc_api_key = {'*' * 8}{args.set_video_desc_api_key[-4:]}" if len(args.set_video_desc_api_key) > 4 else "video_desc_api_key = ****")
    if args.set_video_desc_model:
        save_config("video_desc_model", args.set_video_desc_model)
        print(f"video_desc_model = {args.set_video_desc_model}")
    if args.set_video_desc_max_frames:
        save_config("video_desc_max_frames", args.set_video_desc_max_frames)
        print(f"video_desc_max_frames = {args.set_video_desc_max_frames}")
    if args.show:
        # Show backend info alongside config
        backend = get_backend()
        label = get_backend_label()
        available = check_dependency_available(backend)
        status = "installed" if available else "NOT installed (run: uv sync --extra " + backend + ")"
        print(f"# Backend: {label} ({status})")
        cfg = load_config()
        # Mask sensitive fields before display
        if cfg.get("vision_api_key"):
            cfg["vision_api_key"] = "****"
        if cfg.get("video_desc_api_key"):
            cfg["video_desc_api_key"] = "****"
        print(json.dumps(cfg, indent=2, ensure_ascii=False))


# ── Shared argparse arguments for tts/say ─────────────────────────

def _add_tts_args(parser):
    """Add TTS-related arguments to a subparser (used by both tts and say commands)."""
    # ── Common ──
    parser.add_argument(
        "--engine", "-e",
        choices=["edge-tts", "qwen"],
        help="TTS engine to use. Overrides config default. (default: from config)")
    parser.add_argument(
        "--voice", "-v",
        help="Voice name. For edge-tts: e.g. 'zh-CN-XiaoxiaoNeural'. "
             "For qwen custom_voice mode, use --speaker instead. "
             "Use 'xt voices -e <engine>' to list available voices.")
    parser.add_argument(
        "--language", "-l",
        help="Language for synthesis (qwen only). Options: Auto, Chinese, English, Japanese, "
             "Korean, German, French, Russian, Portuguese, Spanish, Italian. (default: Auto)")
    parser.add_argument(
        "-o", "--output",
        help="Output file path. Extension determines format (.mp3 or .wav).")
    parser.add_argument(
        "--format", "-f",
        choices=["mp3", "wav"],
        help="Output audio format. Ignored when -o is specified. (default: mp3)")
    parser.add_argument(
        "--stdin", action="store_true",
        help="Read text from stdin instead of positional argument.")

    # ── edge-tts specific ──
    eg = parser.add_argument_group("edge-tts options")
    eg.add_argument(
        "--rate",
        help="Speaking speed. Format: '+N%%' or '-N%%', e.g. '+20%%', '-10%%'. (default: +0%%)")
    eg.add_argument(
        "--pitch",
        help="Pitch adjustment. Format: '+NHz' or '-NHz', e.g. '+10Hz', '-5Hz'. (default: +0Hz)")
    eg.add_argument(
        "--volume",
        help="Volume adjustment. Format: '+N%%' or '-N%%', e.g. '+50%%'. (default: +0%%)")

    # ── qwen specific ──
    qg = parser.add_argument_group("qwen options")
    qg.add_argument(
        "--mode", "-m",
        choices=["custom_voice", "voice_design", "voice_clone"],
        help="Qwen3-TTS mode. "
             "custom_voice: built-in speaker + optional emotion instruct. "
             "voice_design: design voice from text description (--instruct required). "
             "voice_clone: clone voice from reference audio (--ref-audio required). "
             "(default: from config, usually custom_voice)")
    qg.add_argument(
        "--speaker", "-s",
        help="Built-in speaker name (custom_voice mode). "
             f"Options: {', '.join(QWEN_SPEAKERS)}. (default: from config)")
    qg.add_argument(
        "--instruct", "-i",
        help="Emotion/style instruction. "
             "custom_voice mode: e.g. '用愤怒的语气说', 'Very happy.' (1.7B only). "
             "voice_design mode: voice description, e.g. '温柔的女声，音调偏高'. (required)")
    qg.add_argument(
        "--ref-audio",
        help="Reference audio file path for voice cloning (voice_clone mode, required). "
             "Supports local wav file path.")
    qg.add_argument(
        "--ref-text",
        help="Transcription text of the reference audio (voice_clone mode). "
             "Required for ICL mode (better quality). Omit if using --x-vector-only.")
    qg.add_argument(
        "--x-vector-only", action="store_true",
        help="Use x-vector only for voice cloning, without ICL. "
             "Lower quality but does not require --ref-text. (voice_clone mode)")
    qg.add_argument(
        "--model-size",
        choices=["1.7B", "0.6B"],
        help="Qwen3-TTS model size. 1.7B supports all features; 0.6B has limitations "
             "(no instruct for custom_voice, no voice_design). (default: from config)")


def main():
    parser = argparse.ArgumentParser(
        description="opc - TTS & ASR CLI Hub for AI Agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  # Basic usage (uses config defaults)
  opc tts "Hello world"
  opc say "你好世界"

  # edge-tts with parameters
  opc tts "你好" -e edge-tts --rate +20% --pitch +5Hz
  opc tts "Hello" -e edge-tts --voice en-US-AriaNeural

  # qwen custom_voice with emotion
  opc tts "你好" -e qwen --speaker Vivian --instruct "用愤怒的语气说"

  # qwen voice_design
  opc tts "你好" -e qwen --mode voice_design --instruct "温柔的女声，音调偏高"

  # qwen voice_clone
  opc tts "你好" -e qwen --mode voice_clone --ref-audio ref.wav --ref-text "参考文本"

  # List voices
  opc voices -e edge-tts
  opc voices -e qwen

  # Discover devices
  opc discover --set-default
""")
    subparsers = parser.add_subparsers(dest="command")

    # ── opc tts ──
    p_tts = subparsers.add_parser("tts", help="Generate speech audio file",
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    p_tts.add_argument("text", nargs="?", help="Text to synthesize. Can also use --stdin.")
    _add_tts_args(p_tts)

    # ── opc say ──
    p_say = subparsers.add_parser("say", help="Generate speech and play on device (tts + playback)",
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    p_say.add_argument("text", nargs="?", help="Text to synthesize. Can also use --stdin.")
    _add_tts_args(p_say)
    p_say.add_argument("--device", "-d", help="Playback device name. Overrides config default.")

    # ── opc discover ──
    p_dis = subparsers.add_parser("discover", help="Discover AirPlay and DLNA devices on network")
    p_dis.add_argument("--set-default", action="store_true",
                       help="Auto-set as default device if exactly one is found")
    p_dis.add_argument("-q", "--quiet", action="store_true",
                       help="Suppress output (useful with --set-default)")

    # ── opc config ──
    p_conf = subparsers.add_parser("config", help="View and manage configuration",
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
    p_conf.add_argument("--show", action="store_true", help="Show current configuration")
    p_conf.add_argument("--set-engine", choices=["edge-tts", "qwen"],
                        help="Set default TTS engine")
    p_conf.add_argument("--set-voice", metavar="VOICE",
                        help="Set default edge-tts voice name")
    p_conf.add_argument("--set-mode", choices=["custom_voice", "voice_design", "voice_clone"],
                        help="Set default qwen mode")
    p_conf.add_argument("--set-speaker", metavar="NAME",
                        help="Set default qwen speaker name")
    p_conf.add_argument("--set-model-size", choices=["1.7B", "0.6B"],
                        help="Set default qwen model size")
    p_conf.add_argument("--set-format", choices=["mp3", "wav"],
                        help="Set default output format for tts command")
    p_conf.add_argument("--set-language", metavar="LANG",
                        help="Set default language (qwen)")
    p_conf.add_argument("--set-edge-rate", metavar="RATE",
                        help="Set default edge-tts rate, e.g. '+20%%'")
    p_conf.add_argument("--set-edge-pitch", metavar="PITCH",
                        help="Set default edge-tts pitch, e.g. '+10Hz'")
    p_conf.add_argument("--set-edge-volume", metavar="VOL",
                        help="Set default edge-tts volume, e.g. '+50%%'")
    p_conf.add_argument("--device", metavar="NAME",
                        help="Set default playback device name")
    p_conf.add_argument("--set-asr-model-size", choices=["1.7B", "0.6B"],
                        help="Set default ASR model size")
    p_conf.add_argument("--set-asr-language", metavar="LANG",
                        help="Set default ASR language hint")
    p_conf.add_argument("--set-workspace", metavar="PATH",
                        help="Set default workspace directory for ASR/Cut")
    p_conf.add_argument("--set-dashboard-host", metavar="HOST",
                        help="Set dashboard server host (default: 0.0.0.0)")
    p_conf.add_argument("--set-dashboard-port", type=int, metavar="PORT",
                        help="Set dashboard server port (default: 12080)")
    p_conf.add_argument("--set-cut-server-port", type=int, metavar="PORT",
                        help="Set cut server port (default: 12082)")
    p_conf.add_argument("--set-backend", choices=["cuda", "mlx", ""],
                        help="Force compute backend. Empty string = auto-detect. (default: auto-detect)")
    p_conf.add_argument("--set-model-source", choices=["modelscope", "huggingface"],
                        help="Model download source. (default: modelscope)")
    p_conf.add_argument("--set-model-cache-dir", metavar="PATH",
                        help="Model cache directory for downloads. Leave empty for default.")
    p_conf.add_argument("--set-comfyui-host", metavar="HOST",
                        help="Set ComfyUI server host (default: 127.0.0.1)")
    p_conf.add_argument("--set-comfyui-port", type=int, metavar="PORT",
                        help="Set ComfyUI server port (default: 8188)")
    p_conf.add_argument("--set-image-output-dir", metavar="PATH",
                        help="Set image output directory (empty = reuse output_dir)")
    p_conf.add_argument("--set-vision-api-url", metavar="URL",
                        help="Set vision model API URL (OpenAI-compatible)")
    p_conf.add_argument("--set-vision-api-key", metavar="KEY",
                        help="Set vision model API key (leave empty for local models)")
    p_conf.add_argument("--set-vision-model", metavar="NAME",
                        help="Set vision model name (e.g. qwen3.5)")
    p_conf.add_argument("--set-video-desc-api-url", metavar="URL",
                        help="Set video description API URL (OpenAI-compatible, fallback to vision_api_url)")
    p_conf.add_argument("--set-video-desc-api-key", metavar="KEY",
                        help="Set video description API key (fallback to vision_api_key)")
    p_conf.add_argument("--set-video-desc-model", metavar="NAME",
                        help="Set video description model name (e.g. nemotron-omni, fallback to vision_model)")
    p_conf.add_argument("--set-video-desc-max-frames", type=int, metavar="N",
                        help="Set max frames to extract for video description (default: 8)")

    # ── opc asr ──
    p_asr = subparsers.add_parser("asr", help="Speech recognition - transcribe audio to text or subtitles",
                                  formatter_class=argparse.RawDescriptionHelpFormatter,
                                  epilog="""\
examples:
  # Simple transcription (text to stdout)
  opc asr audio.mp3
  opc asr audio.wav --language Chinese

  # Generate subtitles (pipeline: align -> break -> fix -> render)
  opc asr audio.mp3 --format srt
  opc asr audio.mp3 --format ass --style neon
  opc asr audio.mp3 --format json -o result.json

  # With CSV fixes (apply fix_1.csv, fix_2.csv, ... from directory)
  opc asr audio.mp3 --format srt --fix-dir ./fixes

  # Resume from a stage (skip GPU-heavy ASR, reuse cached files)
  opc asr audio.mp3 --format srt --resume-from break
  opc asr audio.mp3 --format srt --resume-from fix --fix-dir ./fixes

  # Adjust max chars per subtitle line
  opc asr audio.mp3 --format srt --max-chars 18
""")
    p_asr.add_argument("audio", help="Audio file path (wav, mp3, flac, etc.)")
    p_asr.add_argument("--format", "-f", choices=["text", "json", "srt", "ass"],
                       default="text", help="Output format (default: text). "
                       "srt/ass generates both SRT+ASS unless --format is specified.")
    p_asr.add_argument("--language", "-l",
                       help="Language hint (Chinese, English, etc.). Auto-detect if not specified.")
    p_asr.add_argument("--model-size", choices=["1.7B", "0.6B"],
                       help="ASR model size (default: from config)")
    p_asr.add_argument("--style", choices=["default"],
                       help="ASS subtitle color style (default: default)")
    p_asr.add_argument("-o", "--output", help="Output file path (for json/srt/ass formats)")
    p_asr.add_argument("--fix-dir", help="Directory containing fix_*.csv files for text correction")
    p_asr.add_argument("--resume-from", choices=["asr", "break", "fix", "render"],
                       dest="resume_from",
                       help="Resume pipeline from this stage (reuses cached intermediate files)")
    p_asr.add_argument("--max-chars", type=int, default=14, dest="max_chars",
                       help="Max characters per subtitle line (default: 14, max: 20)")

    # ── opc asr-split ──
    p_split = subparsers.add_parser("asr-split",
                                    help="Split long subtitle lines",
                                    formatter_class=argparse.RawDescriptionHelpFormatter,
                                    epilog="""\
examples:
  # Single: split line 10 after "理解"
  opc asr-split audio.lines.json --line 10 --after "理解"

  # Batch: apply all splits from CSV
  opc asr-split audio.lines.json --csv splits.csv

  # After fixing, re-run render
  opc asr audio.mp3 --format srt --resume-from render

CSV format (line_number,after_text):
  5,一个 AI 发展
  10,怎么样理解
  12,核心洞察
  # lines starting with # are comments
""")
    p_split.add_argument("lines_json", help="Path to .lines.json file")
    p_split.add_argument("--csv", type=str,
                         help="CSV file with split rules (line_number,after_text)")
    p_split.add_argument("--line", type=int,
                         help="1-based line number to split (single mode)")
    p_split.add_argument("--after", type=str,
                         help="Text to match — split after this text (single mode)")

    # ── opc voices ──
    p_voices = subparsers.add_parser("voices", help="List available voices for an engine")
    p_voices.add_argument("--engine", "-e", choices=["edge-tts", "qwen"],
                          help="Engine to list voices for (default: from config)")

    # ── opc cut ──
    p_cut = subparsers.add_parser("cut", help="Video editing based on ASR word-level timestamps",
                                  formatter_class=argparse.RawDescriptionHelpFormatter,
                                  epilog="""\
examples:
  # Start Cut dashboard (opens in browser)
  opc cut

  # Custom port
  opc cut --port 9090

  # Don't open browser automatically
  opc cut --no-browser
""")
    p_cut.add_argument("--video", "-v", help="Video file path (optional, can upload via web UI)")
    p_cut.add_argument("--json", "-j", help="Existing ASR result JSON path (optional)")
    p_cut.add_argument("--language", "-l", default="Chinese", help="Language for ASR")
    p_cut.add_argument("--port", "-p", type=int, default=8080, help="Server port (default: 8080)")
    p_cut.add_argument("--host", "-H", default=None, help="Server host (default: localhost)")
    p_cut.add_argument("--no-browser", action="store_true", help="Do not open browser")
    p_cut.set_defaults(func=cmd_cut)

    cut_subparsers = p_cut.add_subparsers(dest="cut_command", help="Cut commands (legacy)")

    # opc cut start-server (legacy alias)
    p_cut_start = cut_subparsers.add_parser("start-server", help="[Legacy] Start cutx editing server")
    p_cut_start.add_argument("--video", "-v", required=True, help="Video file path")
    p_cut_start.add_argument("--json", "-j", help="Existing ASR result JSON path")
    p_cut_start.add_argument("--language", "-l", default="Chinese", help="Language for ASR")
    p_cut_start.add_argument("--port", "-p", type=int, default=None, help="Server port")
    p_cut_start.add_argument("--host", "-H", default=None, help="Server host")
    p_cut_start.add_argument("--no-browser", action="store_true", help="Do not open browser")

    # ── opc image ──
    p_image = subparsers.add_parser("image", help="Generate images via ComfyUI workflows",
                                    formatter_class=argparse.RawDescriptionHelpFormatter,
                                    epilog="""\
examples:
  # Generate image with JSON structured prompt (DEFAULT)
  opc image -w ernie-turbo -p '{"subject":"a cat","style":"digital art"}'
  opc image -w ernie-turbo -p '{"subject":"cyberpunk city","lighting":"neon","mood":"dystopian"}'

  # Generate with plain text (add --text flag)
  opc image -w ernie-turbo --text -p "a beautiful sunset over mountains"

  # Override workflow parameters
  opc image -w ernie-turbo -p '{"subject":"a cat"}' --param width=512 --param seed=42

  # List available workflows
  opc image list

  # Show workflow parameters
  opc image info ernie-turbo

  # Import a workflow file
  opc image import workflow.json --name my-workflow

  # Analyze a workflow file (for meta.json creation)
  opc image analyze workflow.json

  # Test workflow connectivity and basic generation
  opc image test ernie-turbo --prompt "test image"

  # Explore prompt structure with Knowledge Graph
  opc image kg list              # Show all categories
  opc image kg skeleton subject:food lighting:neon
""")
    image_subparsers = p_image.add_subparsers(dest="image_action", help="Image sub-commands")

    p_img_list = image_subparsers.add_parser("list", help="List available workflows")

    p_img_info = image_subparsers.add_parser("info", help="Show workflow parameter details")
    p_img_info.add_argument("alias", help="Workflow alias name")
    p_img_info.set_defaults(image_action="info")

    p_img_import = image_subparsers.add_parser("import", help="Import a workflow JSON file")
    p_img_import.add_argument("file", help="Path to workflow JSON file")
    p_img_import.add_argument("--name", "-n", required=True, help="Workflow alias name")

    p_img_analyze = image_subparsers.add_parser("analyze", help="Analyze workflow structure or describe an image")
    p_img_analyze.add_argument("file", help="Path to workflow JSON file or image file (PNG/JPG)")
    p_img_analyze.add_argument("--describe", action="store_true",
                               help="Use vision model to describe the image")
    p_img_analyze.add_argument("--compare", "-c", metavar="IMAGE",
                               help="Compare with a second image (reference vs generated)")
    p_img_analyze.add_argument("--prompt", "-p", default="",
                               help="Custom prompt for vision model (with --describe)")

    p_img_test = image_subparsers.add_parser("test", help="Test workflow with minimal params")
    p_img_test.add_argument("alias", help="Workflow alias name")
    p_img_test.add_argument("--prompt", "-p", required=True, help="Test prompt text")

    # ── opc image kg ──
    p_img_kg = image_subparsers.add_parser("kg", help="Prompt knowledge graph engine")
    p_img_kg.set_defaults(image_action="kg")
    kg_sub = p_img_kg.add_subparsers(dest="kg_action", help="KG sub-commands")

    kg_list = kg_sub.add_parser("list", help="List all entities by category")
    kg_list.add_argument("--category", "-c", help="Filter to a specific category")

    kg_info = kg_sub.add_parser("info", help="Show entity details and relations")
    kg_info.add_argument("entity", help="Entity tag (e.g. style:photography)")

    kg_search = kg_sub.add_parser("search", help="Fuzzy search entities")
    kg_search.add_argument("keyword", help="Search keyword")

    kg_query = kg_sub.add_parser("query", help="What goes with an entity?")
    kg_query.add_argument("entity", help="Entity tag")
    kg_query.add_argument("--category", "-c", help="Filter results to a category")
    kg_query.add_argument("--top", "-n", type=int, default=10, help="Top N results")

    kg_skeleton = kg_sub.add_parser("skeleton", help="Generate prompt construction plan")
    kg_skeleton.add_argument("entities", nargs="+", help="Seed entity tags")

    kg_validate = kg_sub.add_parser("validate", help="Check if entity combination is common")
    kg_validate.add_argument("entities", nargs="+", help="Entity tags to validate")

    kg_similar = kg_sub.add_parser("similar", help="Find similar prompts")
    kg_similar.add_argument("entities", nargs="+", help="Entity tags to match")
    kg_similar.add_argument("--top", "-n", type=int, default=5, help="Top N results")

    kg_templates = kg_sub.add_parser("templates", help="List available templates or find by entity")
    kg_templates.add_argument("--entity", "-e", help="Find templates related to a specific entity")

    # Default generate action when no subcommand is used
    p_image.add_argument("--workflow", "-w", dest="alias", help="Workflow alias for generation")
    p_image.add_argument("--prompt", "-p",
                         help="Prompt for generation. Defaults to JSON structured format. Use --text for plain text.")
    p_image.add_argument("--text", action="store_true",
                         help="Treat prompt as plain text instead of JSON structured prompt")
    p_image.add_argument("--param", "-P", action="append", help="Workflow parameter as key=value")
    p_image.add_argument("--output", "-o", help="Output directory for generated images (overrides config)")

    # ── opc image-edit ──
    p_edit = subparsers.add_parser("image-edit", help="Edit images using ComfyUI workflows",
                                   formatter_class=argparse.RawDescriptionHelpFormatter,
                                   epilog="""\
examples:
  # Edit an image with a text instruction
  opc image-edit --image photo.png -p "add a red hat to the person"

  # Edit with JSON structured prompt
  opc image-edit --image input.jpg -p '{"subject":"add snow","style":"winter"}'

  # Use a specific edit workflow
  opc image-edit -w klein-edit --image photo.png -p "make it look like a painting"

  # Edit with multiple input images
  opc image-edit --image ref1.png --image ref2.png -p "blend these two images"

  # Override parameters
  opc image-edit --image photo.png -p "add sunset" --param steps=30 --param seed=42
""")
    p_edit.add_argument("--workflow", "-w", dest="alias", default="klein-edit",
                        help="Workflow alias (default: klein-edit)")
    p_edit.add_argument("--image", "-i", dest="images", action="append",
                        help="Input image path (can specify multiple times)")
    p_edit.add_argument("--prompt", "-p", required=True,
                        help="Edit instruction prompt")
    p_edit.add_argument("--text", action="store_true",
                        help="Treat prompt as plain text instead of JSON")
    p_edit.add_argument("--param", "-P", action="append",
                        help="Workflow parameter as key=value")
    p_edit.add_argument("--output", "-o", help="Output directory for edited images")

    # ── opc video-gen ──
    p_video = subparsers.add_parser("video-gen", help="Generate videos via ComfyUI workflows (i2v, flf)",
                                      formatter_class=argparse.RawDescriptionHelpFormatter,
                                      epilog="""\
examples:
  # Image-to-Video (i2v): animate a single image
  opc video-gen i2v --image frame.png -p "camera slowly zooms in, dramatic lighting"

  # First-Last-Frame (flf): transition between two images
  opc video-gen flf --first-frame start.png --last-frame end.png -p "smooth camera movement"

  # Turbo mode (distilled model, faster generation)
  opc video-gen i2v --image frame.png -p "slow motion" --turbo

  # Override parameters (default: 50fps, 720p, 10s)
  opc video-gen i2v --image frame.png -p "slow motion" --param duration=5 --param frame_rate=25

  # List available video workflows
  opc image list
""")
    video_subparsers = p_video.add_subparsers(dest="video_action", help="Video generation mode")

    # i2v subcommand
    p_video_i2v = video_subparsers.add_parser("i2v", help="Image-to-Video: animate a single image")
    p_video_i2v.add_argument("--workflow", "-w", dest="alias", default="ltx-i2v",
                             help="Workflow alias (default: ltx-i2v)")
    p_video_i2v.add_argument("--image", "-i", required=True,
                             help="Input image path")
    p_video_i2v.add_argument("--prompt", "-p", required=True,
                             help="Text prompt describing the video motion")
    p_video_i2v.add_argument("--turbo", action="store_true",
                             help="Use distilled LoRA for faster generation (slightly lower quality)")
    p_video_i2v.add_argument("--param", "-P", action="append",
                             help="Workflow parameter as key=value")
    p_video_i2v.add_argument("--output", "-o", help="Output directory for generated videos")

    # flf subcommand
    p_video_flf = video_subparsers.add_parser("flf", help="First-Last-Frame: transition between two images")
    p_video_flf.add_argument("--workflow", "-w", dest="alias", default="ltx-flf",
                             help="Workflow alias (default: ltx-flf)")
    p_video_flf.add_argument("--first-frame", "-f", required=True,
                             help="First frame image path")
    p_video_flf.add_argument("--last-frame", "-l", required=True,
                             help="Last frame image path")
    p_video_flf.add_argument("--prompt", "-p", required=True,
                             help="Text prompt describing the transition motion")
    p_video_flf.add_argument("--turbo", action="store_true",
                             help="Use distilled model for faster generation (slightly lower quality)")
    p_video_flf.add_argument("--param", "-P", action="append",
                             help="Workflow parameter as key=value")
    p_video_flf.add_argument("--output", "-o", help="Output directory for generated videos")

    # ── opc video-transcribe ──
    p_vt = subparsers.add_parser("video-transcribe", help="Download video and transcribe to text",
                                  formatter_class=argparse.RawDescriptionHelpFormatter,
                                  epilog="""\
examples:
  # Download and transcribe a video
  opc video-transcribe "https://www.youtube.com/watch?v=..."

  # Specify language for better accuracy
  opc video-transcribe "https://..." --language Chinese

  # Use smaller model for faster processing
  opc video-transcribe "https://..." --model-size 0.6B

  # Keep downloaded video and audio files
  opc video-transcribe "https://..." --keep-video --keep-audio
""")
    p_vt.add_argument("url", help="Video URL to download and transcribe")
    p_vt.add_argument("-o", "--output-dir", default=tempfile.gettempdir(),
                      help="Output directory for transcript (default: temp dir)")
    p_vt.add_argument("--language", "-l",
                      help="Language hint (e.g., Chinese, English). Auto-detect if not specified.")
    p_vt.add_argument("--model-size", "-m", choices=["1.7B", "0.6B"], default="1.7B",
                      help="ASR model size (default: 1.7B)")
    p_vt.add_argument("--keep-video", action="store_true",
                      help="Keep downloaded video file after transcription")
    p_vt.add_argument("--keep-audio", action="store_true",
                      help="Keep extracted audio file after transcription")

    # ── opc video-describe ──
    p_vd = subparsers.add_parser("video-describe", help="Describe a video using vision model API",
                                  formatter_class=argparse.RawDescriptionHelpFormatter,
                                  epilog="""\
examples:
  # Describe a local video file
  opc video-describe video.mp4

  # Custom prompt
  opc video-describe video.mp4 -p "What products are shown in this video?"

  # Extract more frames for better coverage
  opc video-describe video.mp4 --frames 12

  # Use a specific provider (overrides config)
  opc video-describe video.mp4 --api-url http://127.0.0.1:5000/v1/chat/completions --model nemotron-omni
""")
    p_vd.add_argument("video", help="Path to video file")
    p_vd.add_argument("--prompt", "-p", help="Custom prompt for vision model")
    p_vd.add_argument("--frames", "-n", type=int, help="Number of frames to extract (default: from config)")
    p_vd.add_argument("--api-url", help="Vision API URL (overrides config)")
    p_vd.add_argument("--api-key", help="Vision API key (overrides config)")
    p_vd.add_argument("--model", "-m", help="Vision model name (overrides config)")

    # ── opc audio ──
    p_audio = subparsers.add_parser("audio", help="Audio processing tools (compressor, analyzer)",
                                    formatter_class=argparse.RawDescriptionHelpFormatter,
                                    epilog="""\
examples:
  # Compress audio with voice preset (default parameters from DAW)
  opc audio compress input.mp3 --preset voice

  # Compress with custom parameters matching the screenshot
  opc audio compress input.mp3 -t -20.0 -r 4.0 -a 10 --release 130

  # Analyze loudness (LUFS)
  opc audio analyze input.mp3

  # List available presets
  opc audio presets
""")
    audio_subparsers = p_audio.add_subparsers(dest="audio_action", help="Audio sub-commands")

    # opc audio compress
    p_audio_compress = audio_subparsers.add_parser("compress", help="Apply dynamic range compression")
    p_audio_compress.add_argument("input", help="Input audio file path (mp3, wav, flac, etc.)")
    p_audio_compress.add_argument("-o", "--output", help="Output file path (default: auto-generated)")
    p_audio_compress.add_argument("--preset", choices=["voice", "music", "limiter", "punch", "gentle"],
                                  help="Use a preset configuration")
    p_audio_compress.add_argument("-t", "--threshold", type=float, default=-20.0,
                                  help="Threshold in dB (default: -20.0)")
    p_audio_compress.add_argument("-r", "--ratio", type=float, default=4.0,
                                  help="Compression ratio (default: 4.0)")
    p_audio_compress.add_argument("-a", "--attack", type=float, default=10.0,
                                  help="Attack time in ms (default: 10.0)")
    p_audio_compress.add_argument("--release", type=float, default=130.0,
                                  help="Release time in ms (default: 130.0)")
    p_audio_compress.add_argument("--knee", type=float, default=0.0,
                                  help="Knee width in dB (default: 0.0)")
    p_audio_compress.add_argument("--makeup", type=float, default=0.0,
                                  help="Makeup gain in dB (default: 0.0)")
    p_audio_compress.add_argument("--mix", type=float, default=1.0,
                                  help="Wet/dry mix ratio 0-1 (default: 1.0)")

    # opc audio analyze
    p_audio_analyze = audio_subparsers.add_parser("analyze", help="Analyze audio loudness")
    p_audio_analyze.add_argument("input", help="Input audio file path")

    # opc audio presets
    p_audio_presets = audio_subparsers.add_parser("presets", help="List available compressor presets")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    if args.command == "tts":
        cmd_tts(args)
    elif args.command == "say":
        cmd_say(args)
    elif args.command == "discover":
        cmd_discover(args)
    elif args.command == "config":
        cmd_config(args)
    elif args.command == "asr":
        cmd_asr(args)
    elif args.command == "asr-split":
        cmd_asr_split(args)
    elif args.command == "voices":
        cmd_voices(args)
    elif args.command == "cut":
        # Handle cut command - either direct (new) or via subcommand (legacy)
        if args.cut_command == "start-server":
            cmd_cut_start_server(args)
        else:
            # Direct call to cmd_cut (new behavior)
            cmd_cut(args)
    elif args.command == "image":
        cmd_image(args)
    elif args.command == "image-edit":
        _cmd_image_edit(args)
    elif args.command == "video-gen":
        cmd_video_gen(args)
    elif args.command == "video-transcribe":
        cmd_video_transcribe(args)
    elif args.command == "video-describe":
        cmd_video_describe(args)
    elif args.command == "audio":
        cmd_audio(args)


if __name__ == "__main__":
    main()
