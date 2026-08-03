#!/usr/bin/env python3
"""Generate cover images in multiple creative styles for comparison."""

import json
import sys
import time
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from comfyui import check_connection, queue_prompt, wait_for_completion, download_images, get_server_url
from workflow import load_workflow, inject_params
from shared.config import load_config

OUTPUT_DIR = Path("/vol2/1000/output/cover_styles")

# Cover content (from original cover.png)
COVER_SUBJECT = (
    "a tech comparison video cover about 'Hermes VS OpenClaw' plagiarism incident. "
    "The scene shows two sides confronting each other: left side is Hermes (blue, elegant, luxury brand feel), "
    "right side is OpenClaw (orange/red, open-source, claw marks). "
    "A cute cat mascot character sits at the bottom center wearing a judge's wig. "
    "Text elements: big bold Chinese text '吃瓜了!' at top, "
    "subtitle '对比 OpenClaw 和 Hermes' in the middle, "
    "giant dramatic title '抄袭事件' as the centerpiece. "
)

STYLES = {
    "cyberpunk_glitch": {
        "name": "赛博朋克故障风",
        "prefix": (
            "Cyberpunk digital glitch art style, RGB color split distortion, "
            "neon cyan and magenta color palette, dark black background with digital noise scanlines, "
            "holographic text effects with chromatic aberration, circuit board patterns, "
            "futuristic HUD interface elements, data corruption aesthetic, "
            "LED light bleeding, broken pixel texture, "
        ),
    },
    "vaporwave": {
        "name": "蒸汽波",
        "prefix": (
            "Vaporwave aesthetic, pastel pink and cyan gradient, "
            "roman marble bust statue fragments, retro computer UI windows, "
            "chrome metallic text, checkerboard floor pattern, "
            "sunset gradient sky, palm tree silhouettes, "
            "80s retro futurism, VHS tape distortion, Greek column elements, "
        ),
    },
    "newspaper_collage": {
        "name": "报纸剪贴拼贴",
        "prefix": (
            "Newspaper collage ransom note style, cut-out letters from different newspapers and magazines, "
            "mixed media scrapbook aesthetic, torn paper edges, coffee stain marks, "
            "tape and glue痕迹, red marker circle and underline annotations, "
            "yellowed newspaper texture background, typewriter font, "
            "investigative journalism cork board with red strings connecting clues, "
        ),
    },
    "ink_wash": {
        "name": "水墨中国风",
        "prefix": (
            "Chinese ink wash painting style 水墨画, elegant brush strokes, "
            "rice paper texture, monochrome black ink with single red seal stamp accent, "
            "negative space 留白 composition, mountain mist atmosphere, "
            "calligraphic brush text, bamboo and plum blossom motifs, "
            "traditional Chinese painting aesthetics, "
        ),
    },
    "pixel_8bit": {
        "name": "像素8位机",
        "prefix": (
            "Retro 8-bit pixel art style, NES game cartridge cover, "
            "limited color palette of 16 colors, chunky pixelated text, "
            "game UI border frame with health bar and score display, "
            "pixel art character sprites, retro arcade cabinet screen, "
            "scanline CRT monitor effect, "
        ),
    },
    "street_graffiti": {
        "name": "街头涂鸦",
        "prefix": (
            "Street art graffiti style on concrete brick wall, "
            "spray paint drips and splatters, stencil art technique, "
            "bold spray-painted text with drip effects, "
            "paint can and marker pen elements, urban hip-hop culture, "
            "wheat paste poster layering, tags and throw-ups, "
            "neon orange and electric blue spray paint colors, gritty texture, "
        ),
    },
}


def generate_one(style_key, style_def, cfg):
    """Generate a single cover image."""
    prompt = style_def["prefix"] + COVER_SUBJECT
    print(f"\n{'='*60}")
    print(f"Generating: {style_def['name']} ({style_key})")
    print(f"{'='*60}")

    workflow, meta = load_workflow("ernie-turbo")
    params = {
        "prompt": prompt,
        "width": 1376,
        "height": 768,
        "seed": -1,
    }
    workflow = inject_params(workflow, meta, params)

    server_url = get_server_url(cfg)
    prompt_id = queue_prompt(workflow, server_url)
    result = wait_for_completion(prompt_id, server_url)

    # Save with style name
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    saved = []
    for node_id, node_output in result.get("outputs", {}).items():
        for img in node_output.get("images", []):
            import urllib.parse, urllib.request
            p = urllib.parse.urlencode({
                "filename": img["filename"],
                "subfolder": img.get("subfolder", ""),
                "type": img.get("type", "output"),
            })
            url = f"{server_url}/view?{p}"
            save_path = str(OUTPUT_DIR / f"{style_key}.png")
            with urllib.request.urlopen(url) as resp:
                with open(save_path, "wb") as f:
                    f.write(resp.read())
            saved.append(save_path)
            print(f"Saved: {save_path}")

    return saved


def main():
    cfg = load_config()

    # Filter styles to generate
    target_keys = sys.argv[1:] if len(sys.argv) > 1 else list(STYLES.keys())

    if not check_connection(cfg):
        print("ERROR: Cannot connect to ComfyUI")
        sys.exit(1)

    print(f"Will generate {len(target_keys)} cover styles: {', '.join(target_keys)}")

    for key in target_keys:
        if key not in STYLES:
            print(f"Unknown style: {key}")
            print(f"Available: {', '.join(STYLES.keys())}")
            sys.exit(1)

    results = {}
    for key in target_keys:
        try:
            paths = generate_one(key, STYLES[key], cfg)
            results[key] = {"status": "ok", "paths": paths}
        except Exception as e:
            print(f"FAILED [{key}]: {e}")
            results[key] = {"status": "failed", "error": str(e)}

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for key, info in results.items():
        status = info["status"]
        name = STYLES[key]["name"]
        if status == "ok":
            print(f"  OK   {name} ({key}) -> {info['paths'][0]}")
        else:
            print(f"  FAIL {name} ({key}) -> {info['error']}")


if __name__ == "__main__":
    main()
