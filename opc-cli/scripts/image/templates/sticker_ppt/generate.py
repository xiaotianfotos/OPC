#!/usr/bin/env python3
"""sticker_ppt template generator.

Usage:
    # Generate from a script config file:
    python generate.py --config hermes_openclaw.json --output /path/to/output

    # Generate a single scene:
    python generate.py --scene title --params left_name=Hermes right_name=OpenClaw subtitle="饭局谈资"

    # List available scenes:
    python generate.py --list

Config file format (JSON):
    {
        "output_dir": "/path/to/output",
        "scenes": {
            "01_title": { "scene": "title", "params": {"left_name": "Hermes", ...} },
            "02_hype": { "scene": "hype", "params": {"title": "营销泡泡", ...} },
            ...
        }
    }
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

from shared.config import load_config
from image.workflow import load_workflow, inject_params
from image.comfyui import generate_image

TEMPLATE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_template():
    with open(os.path.join(TEMPLATE_DIR, "template.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def render_prompt(template_str, params):
    """Fill template placeholders with params."""
    prompt = template_str
    for key, value in params.items():
        prompt = prompt.replace("{" + key + "}", str(value))
    # Remove any unfilled placeholders
    return prompt


def generate_one(scene_name, prompt, output_dir, cfg, workflow, meta):
    """Generate a single image."""
    cfg = dict(cfg)
    cfg["image_output_dir"] = output_dir
    os.makedirs(output_dir, exist_ok=True)

    params = {
        "prompt": prompt,
        "width": 1376,
        "height": 768,
        "seed": -1,
        "enhance_prompt": True,
    }

    prepared = inject_params(workflow, meta, params)
    result = generate_image(prepared, cfg, filename_prefix=scene_name)

    if result.get("filepaths"):
        src = result["filepaths"][0]
        dst = os.path.join(output_dir, f"{scene_name}.png")
        if os.path.exists(dst):
            os.remove(dst)
        os.rename(src, dst)
        return dst
    return None


def cmd_list(template):
    """List available scene types."""
    print(f"Template: {template['name']}")
    print(f"Style: {template['style_prefix']}")
    print(f"Resolution: {template['resolution']['width']}x{template['resolution']['height']}")
    print(f"\nScene types:")
    for key, scene in template["scenes"].items():
        params = ", ".join(scene["params"])
        print(f"  {key:20s} {scene['desc']}")
        print(f"  {'':20s} params: {params}")
        print()


def cmd_single(args, template, cfg, workflow, meta):
    """Generate a single scene."""
    scene_key = args.scene
    if scene_key not in template["scenes"]:
        print(f"Error: Unknown scene '{scene_key}'. Use --list to see available scenes.")
        sys.exit(1)

    scene = template["scenes"][scene_key]
    params = {}
    for p in args.params or []:
        if "=" not in p:
            print(f"Error: param must be key=value, got: {p}")
            sys.exit(1)
        k, v = p.split("=", 1)
        params[k.strip()] = v.strip()

    missing = [p for p in scene["params"] if p not in params]
    if missing:
        print(f"Error: Missing params: {', '.join(missing)}")
        print(f"  Required: {', '.join(scene['params'])}")
        sys.exit(1)

    prompt = template["style_prefix"] + render_prompt(scene["template"], params)
    output_dir = args.output or "/tmp/sticker_ppt"
    print(f"Generating: {scene_key}")
    print(f"  Prompt: {prompt[:100]}...")
    path = generate_one(scene_key, prompt, output_dir, cfg, workflow, meta)
    if path:
        print(f"  Saved: {path}")
    else:
        print("  Error: no output")


def cmd_config(args, template, cfg, workflow, meta):
    """Generate from config file."""
    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    output_dir = config.get("output_dir", args.output or "/tmp/sticker_ppt")
    style_prefix = config.get("style_prefix", template["style_prefix"])

    for scene_name, scene_def in config["scenes"].items():
        scene_key = scene_def["scene"]
        params = scene_def.get("params", {})

        if scene_key not in template["scenes"]:
            print(f"  Warning: Unknown scene type '{scene_key}', skipping {scene_name}")
            continue

        scene = template["scenes"][scene_key]
        prompt = style_prefix + render_prompt(scene["template"], params)

        print(f"\nGenerating: {scene_name} ({scene_key})")
        print(f"  Prompt: {prompt[:100]}...")

        try:
            path = generate_one(scene_name, prompt, output_dir, cfg, workflow, meta)
            if path:
                print(f"  Saved: {path}")
        except Exception as e:
            print(f"  Error: {e}")

        time.sleep(2)

    print(f"\nDone! Output: {output_dir}/")


def main():
    parser = argparse.ArgumentParser(description="sticker_ppt template generator")
    parser.add_argument("--list", action="store_true", help="List available scene types")
    parser.add_argument("--scene", help="Scene type to generate")
    parser.add_argument("--params", nargs="*", help="Params as key=value pairs")
    parser.add_argument("--config", help="Config file for batch generation")
    parser.add_argument("--output", help="Output directory")
    args = parser.parse_args()

    template = load_template()
    cfg = load_config()

    if args.list:
        cmd_list(template)
        return

    workflow, meta = load_workflow("ernie-turbo")

    if args.config:
        cmd_config(args, template, cfg, workflow, meta)
    elif args.scene:
        cmd_single(args, template, cfg, workflow, meta)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
