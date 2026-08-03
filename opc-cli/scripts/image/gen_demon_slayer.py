#!/usr/bin/env python3
"""Generate a 4-panel Demon Slayer comic strip."""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from image.comfyui import check_connection, queue_prompt, wait_for_completion, get_server_url
from image.workflow import load_workflow, inject_params
from shared.config import load_config
import urllib.parse
import urllib.request

OUTPUT_DIR = Path("/vol2/1000/output/demon_slayer_comic")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 4-panel story: Rengoku comes back
PANELS = [
    {
        "name": "panel1_sunset",
        "desc": "Panel 1 - 哀伤",
        "prompt": (
            "Demon Slayer 鬼灭之刃 anime manga style, 4-panel comic layout (panel 1 of 4), "
            "top-left panel with white border and black outline: "
            "Kamado Tanjiro 炭治郎 sitting alone on a grassy hill at sunset, "
            "holding Rengoku's broken sword guard 煉獄の鍔 close to his chest, "
            "head bowed down, tears falling from his scarlet eyes, "
            "his checkered haori 黑绿格子羽织 blowing in the wind, "
            "the sunset sky painted in deep orange and purple, "
            "cherry blossom petals floating in the air, "
            "melancholic atmosphere, manga screentone shading, "
            "Japanese sound effect text 'シーン...' (silence) in small text, "
        ),
    },
    {
        "name": "panel2_revival",
        "desc": "Panel 2 - 复活",
        "prompt": (
            "Demon Slayer 鬼灭之刃 anime manga style, 4-panel comic layout (panel 2 of 4), "
            "top-right panel with white border and black outline: "
            "sudden explosion of golden-orange flames erupting from the ground, "
            "a familiar muscular silhouette emerging from the fire — "
            "Rengoku Kyojuro 煉獄杏寿郎 stepping forward with his signature wild smile, "
            "his flame-patterned haori 火焰羽织 blazing brilliantly, "
            "his hair like golden fire tips, eyes bright and determined, "
            "dramatic speed lines radiating outward, "
            "impact frame with bold Japanese text 'ドオオオ!!' (DOOO!!) explosion sound effect, "
            "Tanjiro in the background looking up in absolute shock, "
            "dramatic lighting, manga impact frame, ",
        ),
    },
    {
        "name": "panel3_embrace",
        "desc": "Panel 3 - 重逢",
        "prompt": (
            "Demon Slayer 鬼灭之刃 anime manga style, 4-panel comic layout (panel 3 of 4), "
            "bottom-left panel with white border and black outline: "
            "Tanjiro 炭治郎 lunging forward with tears streaming down his face, "
            "clinging onto Rengoku's 煉獄杏寿郎 waist in a desperate embrace, "
            "Rengoku placing his large warm hand gently on Tanjiro's head, "
            "patting him with a tender fatherly smile, "
            "Rengoku's other hand giving a thumbs up, "
            "sparkling shoujo-style background with warm golden light, "
            "speech bubble from Rengoku: Japanese text '泣くな！心を燃やせ！' (Don't cry! Burn your heart!), "
            "emotional manga scene, soft focus background, touching reunion, ",
        ),
    },
    {
        "name": "panel4_together",
        "desc": "Panel 4 - 出发",
        "prompt": (
            "Demon Slayer 鬼滅の刃 anime manga style, 4-panel comic layout (panel 4 of 4), "
            "bottom-right panel with white border and black outline: "
            "Rengoku Kyojuro 煉獄杏寿郎 and Tanjiro 炭治郎 walking side by side into a brilliant sunrise, "
            "Rengoku's flame haori flowing majestically in the wind, "
            "Tanjiro smiling brightly with determination in his eyes, "
            "Nezuko's box 禰豆子の箱 visible on Tanjiro's back, "
            "vast mountain landscape with morning mist, "
            "cherry blossom petals and embers floating together, "
            "Rengoku's speech bubble: 'よし！出発だ！' (Alright! Let's go!), "
            "warm golden light, hope and courage, manga ending frame, "
            "THE END text in English at bottom corner, ",
        ),
    },
]


def generate_comic_strip():
    """Generate all 4 panels."""
    cfg = load_config()
    server_url = get_server_url(cfg)

    if not check_connection(cfg):
        print("ERROR: Cannot connect to ComfyUI")
        sys.exit(1)

    # Also generate a combined 4-panel strip
    print("=" * 60)
    print("Generating 4-panel Demon Slayer comic strip")
    print("Story: 炎柱煉獄杏寿郎突然复活，回到了炭治郎身边")
    print("=" * 60)

    # Generate individual panels
    for panel in PANELS:
        print(f"\n--- {panel['desc']} ({panel['name']}) ---")

        workflow, meta = load_workflow("ernie-turbo")
        params = {
            "prompt": panel["prompt"],
            "width": 1024,
            "height": 1024,
            "seed": -1,
        }
        workflow = inject_params(workflow, meta, params)

        prompt_id = queue_prompt(workflow, server_url)
        result = wait_for_completion(prompt_id, server_url)

        for node_id, node_output in result.get("outputs", {}).items():
            for img in node_output.get("images", []):
                p = urllib.parse.urlencode({
                    "filename": img["filename"],
                    "subfolder": img.get("subfolder", ""),
                    "type": img.get("type", "output"),
                })
                url = f"{server_url}/view?{p}"
                save_path = str(OUTPUT_DIR / f"{panel['name']}.png")
                with urllib.request.urlopen(url) as resp:
                    with open(save_path, "wb") as f:
                        f.write(resp.read())
                print(f"  Saved: {save_path}")

    # Generate combined 4-panel strip
    print(f"\n--- Combined 4-panel strip ---")
    combined_prompt = (
        "Demon Slayer 鬼滅の刃 anime manga style, a single image with 4-panel comic strip layout, "
        "2x2 grid with white panel borders and black outlines: "
        "\n\nPanel 1 (top-left): Kamado Tanjiro 炭治郎 sitting alone on a grassy hill at sunset, "
        "holding Rengoku's broken sword guard close to his chest, head bowed, tears falling, "
        "his checkered black-green haori blowing in wind, cherry blossom petals floating, "
        "melancholic sunset sky, sound effect 'シーン...' in small text. "
        "\n\nPanel 2 (top-right): Sudden explosion of golden-orange flames erupting from ground, "
        "Rengoku Kyojuro 煉獄杏寿郎 emerging from fire with his signature wild smile, "
        "flame-patterned haori blazing, golden fire-tipped hair, "
        "dramatic speed lines and impact frame, sound effect 'ドオオオ!!', "
        "Tanjiro in background looking up in shock. "
        "\n\nPanel 3 (bottom-left): Tanjiro lunging forward with streaming tears, "
        "clinging onto Rengoku's waist in desperate embrace, "
        "Rengoku gently patting Tanjiro's head with warm fatherly smile, "
        "other hand giving thumbs up, sparkling warm golden background, "
        "speech bubble: '泣くな！心を燃やせ！', emotional touching scene. "
        "\n\nPanel 4 (bottom-right): Rengoku and Tanjiro walking side by side into brilliant sunrise, "
        "Rengoku's flame haori flowing in wind, Tanjiro smiling with determination, "
        "Nezuko's box on his back, mountain landscape with morning mist, "
        "cherry blossoms and embers floating together, "
        "speech bubble: 'よし！出発だ！', warm golden light, hope and courage, "
        "'THE END' text at bottom corner. "
        "\n\nConsistent Demon Slayer anime art style throughout all panels, "
        "manga screentone shading, black ink outlines, professional manga layout.",
    )

    workflow, meta = load_workflow("ernie-turbo")
    params = {
        "prompt": combined_prompt,
        "width": 1376,
        "height": 1376,
        "seed": -1,
    }
    workflow = inject_params(workflow, meta, params)

    prompt_id = queue_prompt(workflow, server_url)
    result = wait_for_completion(prompt_id, server_url)

    for node_id, node_output in result.get("outputs", {}).items():
        for img in node_output.get("images", []):
            p = urllib.parse.urlencode({
                "filename": img["filename"],
                "subfolder": img.get("subfolder", ""),
                "type": img.get("type", "output"),
            })
            url = f"{server_url}/view?{p}"
            save_path = str(OUTPUT_DIR / "comic_strip_4panel.png")
            with urllib.request.urlopen(url) as resp:
                with open(save_path, "wb") as f:
                    f.write(resp.read())
            print(f"  Saved: {save_path}")

    print(f"\n{'='*60}")
    print("DONE! All panels saved to:")
    for p in sorted(OUTPUT_DIR.glob("*.png")):
        print(f"  {p}")
    print(f"\nMain comic strip: {OUTPUT_DIR / 'comic_strip_4panel.png'}")


if __name__ == "__main__":
    generate_comic_strip()
