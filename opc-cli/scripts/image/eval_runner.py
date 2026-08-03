"""Eval runner — batch image generation across models with incremental support.

Usage:
  uv run python scripts/image/eval_runner.py                    # Run all missing tests
  uv run python scripts/image/eval_runner.py --model ernie-full # Run missing for one model
  uv run python scripts/image/eval_runner.py --rerun xian_food  # Rerun specific prompt
  uv run python scripts/image/eval_runner.py --rerun-all        # Rerun everything
  uv run python scripts/image/eval_runner.py --list             # Show status summary
"""

import argparse
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from image.comfyui import generate_image, check_connection, get_server_url
from image.workflow import load_workflow, inject_params
from shared.config import load_config

_USER_DATA_DIR = os.path.join(os.path.expanduser("~"), ".opc_cli", "opc")
_BUILTIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))

EVAL_DIR = os.path.join(_USER_DATA_DIR, "eval")
_PROMPTS_USER = os.path.join(_USER_DATA_DIR, "eval", "prompts")
_PROMPTS_BUILTIN = os.path.join(_BUILTIN_DIR, "eval", "prompts")
RESULTS_DIR = os.path.join(_USER_DATA_DIR, "eval", "results")

os.makedirs(RESULTS_DIR, exist_ok=True)


def _resolve_prompts_dir():
    if os.path.isdir(_PROMPTS_USER) and os.listdir(_PROMPTS_USER):
        return _PROMPTS_USER
    return _PROMPTS_BUILTIN


PROMPTS_DIR = _resolve_prompts_dir()

NEGATIVE_PROMPT = "low quality, blurry, deformed, ugly, duplicate, watermark, signature, cropped, worst quality, low resolution, disfigured, bad anatomy"

DEFAULT_PARAMS = {
    "width": 1024,
    "height": 1024,
    "seed": 42,
    "batch_size": 1,
}

KNOWN_MODELS = ["ernie-full", "qwen-image", "z-image", "klein", "ideogram4"]


def discover_prompts():
    """Find all prompt JSON files in eval/prompts/."""
    prompts = {}
    if not os.path.isdir(PROMPTS_DIR):
        return prompts
    for fname in sorted(os.listdir(PROMPTS_DIR)):
        if fname.endswith(".json"):
            pid = fname[:-5]
            with open(os.path.join(PROMPTS_DIR, fname)) as f:
                data = json.load(f)
            prompts[pid] = data
    return prompts


def load_results(model):
    """Load existing results for a model. Returns {prompt_id: result_entry}."""
    results_file = os.path.join(RESULTS_DIR, model, "results.json")
    if not os.path.exists(results_file):
        return {}
    with open(results_file) as f:
        data = json.load(f)
    entries = data.get("results", [])
    return {e["prompt_id"]: e for e in entries if isinstance(e, dict) and "prompt_id" in e}


def save_results(model, results, meta_overrides=None):
    """Save results.json for a model."""
    model_dir = os.path.join(RESULTS_DIR, model)
    os.makedirs(model_dir, exist_ok=True)
    results_file = os.path.join(model_dir, "results.json")

    # Merge with existing if present
    existing = {}
    if os.path.exists(results_file):
        with open(results_file) as f:
            old = json.load(f)
        existing = {e["prompt_id"]: e for e in old.get("results", []) if isinstance(e, dict)}

    # Overwrite with new results
    for r in results:
        if "prompt_id" in r:
            existing[r["prompt_id"]] = r

    ok = sum(1 for e in existing.values() if e.get("status") == "ok")
    err = sum(1 for e in existing.values() if e.get("status") == "error")

    meta = {
        "alias": model,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total": len(existing),
        "ok": ok,
        "error": err,
    }
    if meta_overrides:
        meta.update(meta_overrides)

    with open(results_file, "w") as f:
        json.dump({"meta": meta, "results": list(existing.values())}, f, indent=2, ensure_ascii=False)


def get_prompt_text(prompt_data):
    """Extract text prompt from prompt JSON."""
    if isinstance(prompt_data, str):
        return prompt_data
    if isinstance(prompt_data, dict):
        # Could be {prompt: "..."} or a full JSON prompt
        if "prompt" in prompt_data:
            return prompt_data["prompt"]
        return json.dumps(prompt_data, ensure_ascii=False)
    return str(prompt_data)


# Keys that are metadata wrappers, not structured prompt content
_WRAPPER_KEYS = {"prompt", "negative", "negative_constraints", "meta"}


def is_json_prompt(prompt_data):
    """Check if prompt should be sent as JSON.

    A dict with only wrapper keys (prompt, negative, meta, negative_constraints)
    is treated as a plain-text wrapper — only the 'prompt' value is sent.
    A dict with structured content keys (subject, style, composition, layout, etc.)
    is serialized as JSON and sent as-is.
    """
    if isinstance(prompt_data, dict) and "prompt" in prompt_data:
        content_keys = set(prompt_data.keys()) - _WRAPPER_KEYS
        if content_keys:
            return True
    return isinstance(prompt_data, dict) and "prompt" not in prompt_data


def get_prompt_resolution(prompt_data):
    """Extract resolution from prompt data. Returns (width, height) or None."""
    if not isinstance(prompt_data, dict):
        return None
    # Check meta.resolution
    meta = prompt_data.get("meta", {})
    if isinstance(meta, dict):
        res = meta.get("resolution")
        if isinstance(res, dict):
            return (res.get("width", 1024), res.get("height", 1024))
        if isinstance(res, str) and "x" in res:
            parts = res.split("x")
            try:
                return (int(parts[0]), int(parts[1]))
            except ValueError:
                pass
    # Check top-level resolution
    res = prompt_data.get("resolution")
    if isinstance(res, dict):
        return (res.get("width", 1024), res.get("height", 1024))
    # Check technical_specs
    tech = prompt_data.get("technical_specs", {})
    if isinstance(tech, dict):
        if "width" in tech and "height" in tech:
            return (tech["width"], tech["height"])
    return None


def run_one(model, prompt_id, prompt_data, cfg, override_resolution=None):
    """Run a single prompt on a model. Returns result entry."""
    wf, meta = load_workflow(model)
    model_dir = os.path.join(RESULTS_DIR, model)
    os.makedirs(model_dir, exist_ok=True)

    prompt_text = get_prompt_text(prompt_data)
    is_json = is_json_prompt(prompt_data)

    # For JSON prompts, pass the whole thing as-is
    if is_json and isinstance(prompt_data, dict):
        nc = prompt_data.get("negative_constraints", [])
        negative_text = ", ".join(nc) if isinstance(nc, list) else str(nc) if isinstance(nc, str) else ""
        prompt_json_clean = {k: v for k, v in prompt_data.items() if k != "negative_constraints"}
        prompt_text = json.dumps(prompt_json_clean, ensure_ascii=False)
    elif isinstance(prompt_data, dict) and "negative" in prompt_data:
        negative_text = prompt_data.get("negative", NEGATIVE_PROMPT)
    else:
        negative_text = NEGATIVE_PROMPT

    file_prefix = f"{prompt_id}_{model.replace('-', '_')}"

    # Resolve resolution: CLI override > prompt-defined > default
    width, height = DEFAULT_PARAMS["width"], DEFAULT_PARAMS["height"]
    if override_resolution:
        width, height = override_resolution
    elif isinstance(prompt_data, dict):
        prompt_res = get_prompt_resolution(prompt_data)
        if prompt_res:
            width, height = prompt_res

    print(f"  [{model}] {prompt_id} ({len(prompt_text)} chars, {width}x{height})...", end="", flush=True)

    try:
        params = dict(DEFAULT_PARAMS)
        params["prompt"] = prompt_text
        params["width"] = width
        params["height"] = height
        if "negative_prompt" in meta.get("params", {}):
            params["negative_prompt"] = negative_text

        prepared = inject_params(wf, meta, params)
        cfg["image_output_dir"] = model_dir
        result = generate_image(prepared, cfg, filename_prefix=file_prefix, register_gallery=False)

        img_path = result["filepaths"][0]
        new_path = os.path.join(model_dir, os.path.basename(img_path))
        if img_path != new_path:
            shutil.move(img_path, new_path)

        preview = prompt_text[:100].replace("\n", " ")
        entry = {
            "prompt_id": prompt_id,
            "model": model,
            "file": os.path.basename(new_path),
            "status": "ok",
            "positive_preview": preview,
        }
        print(" OK")
        return entry

    except Exception as e:
        print(f" FAIL: {e}")
        return {
            "prompt_id": prompt_id,
            "model": model,
            "file": None,
            "status": "error",
            "error": str(e),
        }


def cmd_list(args):
    """Show status summary."""
    prompts = discover_prompts()
    print(f"Total prompts: {len(prompts)}")
    print()

    for model in KNOWN_MODELS:
        existing = load_results(model)
        ok = sum(1 for e in existing.values() if e.get("status") == "ok")
        err = sum(1 for e in existing.values() if e.get("status") == "error")
        missing = len(prompts) - len(existing)
        print(f"  {model:15s}  ok={ok:3d}  error={err:2d}  missing={missing:3d}")

    print()

    # Show prompts not yet run by any model
    all_covered = set()
    for model in KNOWN_MODELS:
        all_covered.update(load_results(model).keys())
    uncovered = set(prompts.keys()) - all_covered
    if uncovered:
        print(f"Prompts not run by ANY model ({len(uncovered)}):")
        for pid in sorted(uncovered):
            print(f"  - {pid}")


def cmd_run(args):
    """Run missing tests."""
    prompts = discover_prompts()
    if not prompts:
        print("No prompts found in eval/prompts/")
        return

    cfg = load_config()
    print(f"ComfyUI at {get_server_url(cfg)}: ", end="")
    if not check_connection(cfg):
        print("OFFLINE")
        return
    print("OK")

    models = [args.model] if args.model else KNOWN_MODELS
    total_run = 0

    for model in models:
        existing = load_results(model)
        to_run = []
        for pid in sorted(prompts.keys()):
            if pid not in existing or existing[pid].get("status") != "ok":
                to_run.append(pid)

        if not to_run:
            print(f"[{model}] All {len(prompts)} prompts already done, skipping.")
            continue

        print(f"[{model}] Running {len(to_run)} missing prompts...")
        start = time.time()
        results = []
        for pid in to_run:
            entry = run_one(model, pid, prompts[pid], cfg)
            results.append(entry)
            total_run += 1
            save_results(model, results, {"elapsed_seconds": round(time.time() - start, 1)})

        elapsed = time.time() - start
        ok = sum(1 for r in results if r["status"] == "ok")
        err = sum(1 for r in results if r["status"] == "error")
        print(f"[{model}] Done: {ok} ok, {err} error, {elapsed:.0f}s")

    if total_run == 0:
        print("Nothing to run.")


def cmd_rerun(args):
    """Rerun specific prompt(s) across model(s)."""
    prompts = discover_prompts()
    cfg = load_config()

    print(f"ComfyUI at {get_server_url(cfg)}: ", end="")
    if not check_connection(cfg):
        print("OFFLINE")
        return
    print("OK")

    models = [args.model] if args.model else KNOWN_MODELS

    # Find matching prompts
    targets = []
    for pid in sorted(prompts.keys()):
        if args.prompt in pid:
            targets.append(pid)

    if not targets:
        print(f"No prompts matching '{args.prompt}'")
        return

    # Parse override resolution
    override_res = None
    if args.resolution:
        try:
            parts = args.resolution.lower().split("x")
            override_res = (int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            print(f"Invalid resolution: {args.resolution}. Use WxH format, e.g. 1024x1344")
            return

    print(f"Rerunning {len(targets)} prompt(s) matching '{args.prompt}' on {models}...")
    if override_res:
        print(f"  Override resolution: {override_res[0]}x{override_res[1]}")
    start = time.time()

    for model in models:
        results = []
        for pid in targets:
            entry = run_one(model, pid, prompts[pid], cfg, override_resolution=override_res)
            results.append(entry)
        save_results(model, results)

    elapsed = time.time() - start
    print(f"Done in {elapsed:.0f}s")


def cmd_rerun_all(args):
    """Rerun everything."""
    prompts = discover_prompts()
    cfg = load_config()

    print(f"ComfyUI at {get_server_url(cfg)}: ", end="")
    if not check_connection(cfg):
        print("OFFLINE")
        return
    print("OK")

    models = [args.model] if args.model else KNOWN_MODELS

    for model in models:
        print(f"[{model}] Rerunning all {len(prompts)} prompts...")
        start = time.time()
        results = []
        for pid in sorted(prompts.keys()):
            entry = run_one(model, pid, prompts[pid], cfg)
            results.append(entry)
        elapsed = time.time() - start
        save_results(model, results, {"elapsed_seconds": round(elapsed, 1)})
        ok = sum(1 for r in results if r["status"] == "ok")
        print(f"[{model}] Done: {ok}/{len(results)} ok, {elapsed:.0f}s")


def main():
    parser = argparse.ArgumentParser(description="Eval runner for image model comparison")
    parser.add_argument("--model", "-m", help="Only run for this model alias")
    parser.add_argument("--list", "-l", action="store_true", help="Show status summary")
    parser.add_argument("--rerun", "-r", nargs="?", const="", metavar="PROMPT",
                        help="Rerun specific prompt (substring match). No arg = rerun all failed")
    parser.add_argument("--rerun-all", action="store_true", help="Rerun everything")
    parser.add_argument("--resolution", "-R", help="Override resolution WxH, e.g. 1024x1344")
    args = parser.parse_args()

    if args.list:
        cmd_list(args)
    elif args.rerun is not None:
        if args.rerun == "":
            # --rerun with no arg: rerun failed ones
            args.prompt = "__failed__"
            # Special handling for failed rerun
            prompts = discover_prompts()
            cfg = load_config()
            print(f"ComfyUI at {get_server_url(cfg)}: ", end="")
            if not check_connection(cfg):
                print("OFFLINE")
                return
            print("OK")
            models = [args.model] if args.model else KNOWN_MODELS
            for model in models:
                existing = load_results(model)
                failed = [pid for pid, e in existing.items() if e.get("status") == "error"]
                if not failed:
                    print(f"[{model}] No failed prompts.")
                    continue
                print(f"[{model}] Rerunning {len(failed)} failed prompts...")
                results = []
                for pid in failed:
                    if pid in prompts:
                        entry = run_one(model, pid, prompts[pid], cfg)
                        results.append(entry)
                save_results(model, results)
        else:
            args.prompt = args.rerun
            cmd_rerun(args)
    elif args.rerun_all:
        cmd_rerun_all(args)
    else:
        cmd_run(args)


if __name__ == "__main__":
    main()
