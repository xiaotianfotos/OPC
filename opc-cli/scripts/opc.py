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
from image.comfyui import generate_image, check_connection, get_server_url, describe_image, compare_images, extract_comfyui_metadata
from image.workflow import discover_workflows, load_workflow, inject_params, analyze_workflow, import_workflow
from image.kg.engine import PromptKG
from image.json_prompt import json_prompt_to_text, validate_json_prompt
from video.comfyui import generate_video, upload_file
from video.h3 import WORKFLOWS as VIDEO_WORKFLOWS, build_h3_workflow, duration_to_frames


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


def cmd_video(args):
    """Handle local ComfyUI video generation workflows."""
    action = getattr(args, "video_action", None)
    if action == "list":
        for alias, meta in VIDEO_WORKFLOWS.items():
            print(f"  {alias:20s} {meta['description']}")
        print(f"\n{len(VIDEO_WORKFLOWS)} workflow(s) available.")
        return
    if action == "info":
        meta = VIDEO_WORKFLOWS.get(args.alias)
        if not meta:
            print(f"Error: Unknown video workflow '{args.alias}'", file=sys.stderr)
            sys.exit(1)
        print(f"Alias: {args.alias}")
        print(f"Description: {meta['description']}")
        print(f"Inputs: {meta['inputs']}")
        print("Defaults: 864x480, 5 seconds, 20 steps, 24 fps")
        return
    _cmd_video_generate(args)


def _cmd_video_generate(args):
    cfg = load_config()
    alias = getattr(args, "alias", None)
    if not alias:
        print("Error: Specify --workflow. Use 'opc video list' for aliases.", file=sys.stderr)
        sys.exit(1)

    prompt = getattr(args, "prompt", None)
    if getattr(args, "prompt_file", None):
        try:
            with open(args.prompt_file, "r", encoding="utf-8") as prompt_file:
                prompt = prompt_file.read().strip()
        except OSError as error:
            print(f"Error: {error}", file=sys.stderr)
            sys.exit(1)
    if getattr(args, "stdin", False):
        prompt = sys.stdin.read().strip()
    if not prompt:
        print("Error: Provide --prompt, --prompt-file, or --stdin.", file=sys.stderr)
        sys.exit(1)

    image_args = []
    if getattr(args, "first_frame", None):
        image_args.append(("first_frame", args.first_frame))
    if getattr(args, "last_frame", None):
        image_args.append(("last_frame", args.last_frame))
    image_args.extend(
        ("reference_image", path)
        for path in (getattr(args, "reference_image", None) or [])
    )
    image_args.extend(
        ("reference_video", path)
        for path in (getattr(args, "reference_video", None) or [])
    )
    image_args.extend(
        ("reference_audio", path)
        for path in (getattr(args, "reference_audio", None) or [])
    )
    for _, media_path in image_args:
        if not os.path.isfile(media_path):
            print(f"Error: Input file not found: {media_path}", file=sys.stderr)
            sys.exit(1)

    try:
        if args.dry_run:
            uploaded = {}
            for key, media_path in image_args:
                if key.startswith("reference_"):
                    uploaded.setdefault(key, []).append(Path(media_path).name)
                else:
                    uploaded[key] = Path(media_path).name
        else:
            if not check_connection(cfg):
                raise ConnectionError(f"Cannot connect to ComfyUI at {get_server_url(cfg)}")
            uploaded = {}
            for key, media_path in image_args:
                remote_name = upload_file(media_path, get_server_url(cfg))
                if key.startswith("reference_"):
                    uploaded.setdefault(key, []).append(remote_name)
                else:
                    uploaded[key] = remote_name

        references = uploaded.get("reference_image", [])
        if isinstance(references, str):
            references = [references]
        workflow = build_h3_workflow(
            alias=alias,
            prompt=prompt,
            width=args.width,
            height=args.height,
            duration=args.duration,
            steps=args.steps,
            seed=args.seed,
            first_frame=uploaded.get("first_frame"),
            last_frame=uploaded.get("last_frame"),
            reference_images=references,
            reference_videos=uploaded.get("reference_video", []),
            reference_audios=uploaded.get("reference_audio", []),
            include_reference_video_audio=args.reference_video_audio,
            ref_image_size=args.ref_image_size,
            upscale=args.upscale,
            upscale_factor=args.upscale_factor,
        )
        if args.dry_run:
            print(json.dumps(workflow, indent=2, ensure_ascii=False))
            return

        result = generate_video(
            workflow,
            cfg,
            filename_prefix=alias.replace("-", "_"),
            output_dir=args.output,
        )
        result.update({
            "workflow": alias,
            "resolution": f"{args.width}x{args.height}",
            "duration_seconds": args.duration,
            "frames": duration_to_frames(args.duration),
            "steps": args.steps,
        })
        if args.upscale or alias == "h3-t2v-upscale":
            result["upscaled_resolution"] = (
                f"{int(args.width * args.upscale_factor)}x"
                f"{int(args.height * args.upscale_factor)}"
            )
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, RuntimeError, ConnectionError) as error:
        print(f"Error: {error}", file=sys.stderr)
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
    if args.set_video_output_dir:
        save_config("video_output_dir", args.set_video_output_dir)
        print(f"video_output_dir = {args.set_video_output_dir}")
    if args.set_vision_api_url:
        save_config("vision_api_url", args.set_vision_api_url)
        print(f"vision_api_url = {args.set_vision_api_url}")
    if args.set_vision_api_key:
        save_config("vision_api_key", args.set_vision_api_key)
        print(f"vision_api_key = {'*' * 8}{args.set_vision_api_key[-4:]}" if len(args.set_vision_api_key) > 4 else "vision_api_key = ****")
    if args.set_vision_model:
        save_config("vision_model", args.set_vision_model)
        print(f"vision_model = {args.set_vision_model}")
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
    p_conf.add_argument("--set-video-output-dir", metavar="PATH",
                        help="Set video output directory (empty = reuse output_dir)")
    p_conf.add_argument("--set-vision-api-url", metavar="URL",
                        help="Set vision model API URL (OpenAI-compatible)")
    p_conf.add_argument("--set-vision-api-key", metavar="KEY",
                        help="Set vision model API key (leave empty for local models)")
    p_conf.add_argument("--set-vision-model", metavar="NAME",
                        help="Set vision model name (e.g. qwen3.5)")

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

    # ── opc video ──
    p_video = subparsers.add_parser(
        "video",
        help="Generate videos with local ComfyUI workflows",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  opc video list
  opc video -w h3-t2v -p "A cinematic lake at sunrise" --width 864 --height 480 --duration 5
  opc video -w h3-i2v -p "The camera pushes in" --first-frame first.png --last-frame last.png
  opc video -w h3-r2v -p "Preserve the subject" --reference-image subject.png
  opc video -w h3-r2v -p "Use <Video 1> motion and sound" --reference-video clip.mp4
  opc video -w h3-r2v -p "Preserve the subject" --reference-image subject.png --upscale --upscale-factor 2
""",
    )
    video_subparsers = p_video.add_subparsers(dest="video_action", help="Video sub-commands")
    video_subparsers.add_parser("list", help="List available video workflows")
    p_video_info = video_subparsers.add_parser("info", help="Show video workflow details")
    p_video_info.add_argument("alias", help="Workflow alias name")
    p_video.add_argument("--workflow", "-w", dest="alias", choices=sorted(VIDEO_WORKFLOWS))
    p_video.add_argument("--prompt", "-p", help="Video prompt text")
    p_video.add_argument("--prompt-file", help="Read the video prompt from a UTF-8 text file")
    p_video.add_argument("--stdin", action="store_true", help="Read the video prompt from stdin")
    p_video.add_argument("--width", type=int, default=864, help="Base width, multiple of 32 (default: 864)")
    p_video.add_argument("--height", type=int, default=480, help="Base height, multiple of 32 (default: 480)")
    p_video.add_argument("--duration", type=float, default=5, help="Duration in seconds, 5-15 (default: 5)")
    p_video.add_argument("--steps", type=int, default=20, help="H3 sampling steps (default: 20)")
    p_video.add_argument("--seed", type=int, default=-1, help="Seed; -1 selects a random seed")
    p_video.add_argument("--first-frame", help="First frame image for h3-i2v")
    p_video.add_argument("--last-frame", help="Optional last frame image for h3-i2v")
    p_video.add_argument(
        "--reference-image",
        action="append",
        help="Reference image for h3-r2v; repeat up to nine times",
    )
    p_video.add_argument(
        "--reference-video",
        action="append",
        help="Reference video for h3-r2v; repeat up to three times (recommended: 2-15s at 24 fps)",
    )
    p_video.add_argument(
        "--reference-audio",
        action="append",
        help="Standalone reference audio for h3-r2v; repeat up to three times",
    )
    p_video.add_argument(
        "--reference-video-audio",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use each reference video's soundtrack (default: enabled)",
    )
    p_video.add_argument(
        "--ref-image-size",
        choices=["match", "max"],
        default="match",
        help="Reference sizing: match is faster; max improves identity fidelity",
    )
    p_video.add_argument(
        "--upscale",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable or disable SeedVR2 restoration/upscale (default: disabled)",
    )
    p_video.add_argument(
        "--upscale-factor",
        type=float,
        default=2.0,
        help="SeedVR2 scale factor, greater than 1 and at most 4 (default: 2)",
    )
    p_video.add_argument("--output", "-o", help="Directory for the downloaded MP4")
    p_video.add_argument("--dry-run", action="store_true", help="Print the ComfyUI API workflow without running it")

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
    elif args.command == "video":
        cmd_video(args)


if __name__ == "__main__":
    main()
