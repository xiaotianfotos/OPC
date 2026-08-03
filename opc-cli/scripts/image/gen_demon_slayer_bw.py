#!/usr/bin/env python3
"""Generate B&W hand-drawn Demon Slayer comic - Rengoku's soul vs Muzan."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from image.comfyui import check_connection, queue_prompt, wait_for_completion, get_server_url
from image.workflow import load_workflow, inject_params
from shared.config import load_config
import urllib.parse
import urllib.request

OUTPUT_DIR = Path("/vol2/1000/output/demon_slayer_bw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

STYLE_PREFIX = (
    "pure black and white manga, traditional hand-drawn ink pen illustration, "
    "no color whatsoever, heavy crosshatching, screentone dot patterns, "
    "bold brush strokes, rough pen lines, Japanese shonen manga style, "
    "high contrast black ink on white paper, dynamic action linework, "
    "similar to Koyoharu Gotoge's art style, "
)

# Story: Rengoku's soul awakens in Infinity Castle, helps Tanjiro fight Muzan
PANELS = [
    {
        "name": "panel1_despair",
        "prompt": (
            STYLE_PREFIX +
            "4-panel manga page layout (panel 1 of 4, top-left), white border black outline: "
            "inside the Infinity Castle 無限城 with its shifting impossible architecture, "
            "Tanjiro 炭治郎 on his knees, battered and bloodied, uniform torn apart, "
            "blood dripping from his forehead and mouth, one eye swollen shut, "
            "his nichirin sword 日輪刀 cracked and chipped, barely gripping it with trembling hands, "
            "looming shadow of Muzan Kibutsuji 鬼舞辻無惨 casting over him from above, "
            "Muzan's terrifying multiple tentacle-whips extended, his cold merciless smile visible, "
            "despair and hopelessness atmosphere, "
            "speed lines converging on Tanjiro, dramatic downward perspective from Muzan's POV, "
            "manga narration box text: '那一刻，炭治郎以为一切都结束了...' "
            "(In that moment, Tanjiro thought everything was over...), "
        ),
    },
    {
        "name": "panel2_flame",
        "prompt": (
            STYLE_PREFIX +
            "4-panel manga page layout (panel 2 of 4, top-right), white border black outline: "
            "Muzan's tentacles about to strike the defeated Tanjiro, "
            "SUDDENLY a massive wall of FLAMES erupts between them, "
            "the fire rendered in wild aggressive ink brush strokes radiating outward, "
            "from within the inferno, a translucent ghostly figure emerges — "
            "Rengoku Kyojuro's 煉獄杏寿郎 spirit form, semi-transparent with flowing flame aura, "
            "his broken nichirin sword now wreathed in ghostly fire, "
            "his expression fierce and unwavering, shouting with mouth wide open, "
            "massive impact frame with jagged edges, "
            "bold brushstroke Japanese text '炎の呼吸！！！' (Flame Breathing!!!), "
            "explosive speed lines in every direction, Muzan's face showing genuine shock for the first time, "
            "epic dramatic entrance scene,",
        ),
    },
    {
        "name": "panel3_combo",
        "prompt": (
            STYLE_PREFIX +
            "4-panel manga page layout (panel 3 of 4, bottom-left), white border black outline: "
            "Tanjiro and ghost Rengoku fighting side by side against Muzan, "
            "dynamic double-page spread feel compressed into one panel, "
            "Rengoku's spirit executing '炎の呼吸・玖ノ型 煉獄' (9th Form: Rengoku) — "
            "a massive flame slash drawn as wild swirling ink brush strokes, "
            "Tanjiro simultaneously executing '日の呼吸・円舞' (Sun Breathing: Circular Dance) — "
            "water and sun patterns interweaving with Rengoku's flames, "
            "Muzan being pushed back, his tentacles severed and regenerating, "
            "expression of rage and disbelief on Muzan's face, "
            "their combined breathing techniques creating a tornado of energy, "
            "Rengoku's speech bubble: '炭治郎！俺の炎で道を切り開く！' "
            "(Tanjiro! I'll carve a path with my flames!), "
            "intense action, heavy ink splatter, dynamic motion blur lines,",
        ),
    },
    {
        "name": "panel4_dawn",
        "prompt": (
            STYLE_PREFIX +
            "4-panel manga page layout (panel 4 of 4, bottom-right), white border black outline: "
            "the final moment — the Infinity Castle's ceiling CRACKING open, "
            "a single brilliant ray of DAWN SUNLIGHT piercing through, "
            "rendered as blinding white space with radiant ink lines, "
            "Muzan screaming in agony as sunlight touches his skin, his body dissolving, "
            "Rengoku's spirit beginning to fade into golden particles in the dawn light, "
            "turning to Tanjiro with his signature warm wide smile and giving a final thumbs up, "
            "Rengoku's speech bubble: 'よくやった...これで終わりだ' (Well done... it's over now), "
            "Tanjiro reaching out toward the fading Rengoku with tears and a determined smile, "
            "cherry blossom petals and ember particles floating in the dawn light, "
            "the crack of dawn symbolizing hope and victory, "
            "narration box: '大哥的火焰，从未熄灭' (The大哥's flames never extinguished), "
            "emotional bittersweet ending, powerful manga closing frame,",
        ),
    },
]

COMBINED_PROMPT = (
    STYLE_PREFIX +
    "a single manga page with 4-panel comic strip layout, "
    "2x2 grid with white panel borders and black ink outlines: "
    "\n\nPanel 1 (top-left): Inside Infinity Castle 無限城, "
    "Tanjiro 炭治郎 on his knees battered and bloodied, sword cracked, "
    "Muzan 鬼舞辻無惨 looming above with tentacle-whips extended, cold smile, "
    "despair atmosphere, narration: '那一刻，炭治郎以为一切都结束了...'. "
    "\n\nPanel 2 (top-right): Massive wall of flames erupts between them, "
    "Rengoku's 煉獄杏寿郎 ghostly spirit form emerging from the fire, "
    "semi-transparent with flame aura, broken sword wreathed in ghost fire, fierce expression, "
    "impact frame, bold text '炎の呼吸！！！', Muzan's shocked face, explosive speed lines. "
    "\n\nPanel 3 (bottom-left): Tanjiro and ghost Rengoku fighting side by side, "
    "Rengoku executing flame breathing 9th form with massive flame slash, "
    "Tanjiro executing sun breathing circular dance simultaneously, "
    "Muzan being pushed back, tentacles severed, raging expression, "
    "speech bubble: '炭治郎！俺の炎で道を切り開く！', intense action, ink splatter. "
    "\n\nPanel 4 (bottom-right): Infinity Castle ceiling cracking open, "
    "dawn sunlight piercing through as blinding white rays, "
    "Muzan dissolving and screaming, "
    "Rengoku's spirit fading into particles, giving final thumbs up and warm smile, "
    "Tanjiro reaching out with tears, cherry blossoms and embers in dawn light, "
    "speech bubble: 'よくやった...これで終わりだ', "
    "narration: '大哥的火焰，从未熄灭', emotional bittersweet ending. "
    "\n\nConsistent black and white hand-drawn manga art throughout, "
    "heavy crosshatching, screentone, bold brush strokes, Koyoharu Gotoge art style."
)


def generate():
    cfg = load_config()
    server_url = get_server_url(cfg)

    if not check_connection(cfg):
        print("ERROR: Cannot connect to ComfyUI")
        sys.exit(1)

    print("=" * 60)
    print("B&W 手绘漫画: 炎柱灵魂复苏，无限城大战无惨")
    print("=" * 60)

    # Generate individual panels
    for panel in PANELS:
        print(f"\n--- {panel['name']} ---")

        workflow, meta = load_workflow("ernie-turbo")
        params = {"prompt": panel["prompt"], "width": 1024, "height": 1024, "seed": -1}
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
                save_path = str(OUTPUT_DIR / f"{panel['name']}.png")
                with urllib.request.urlopen(f"{server_url}/view?{p}") as resp:
                    with open(save_path, "wb") as f:
                        f.write(resp.read())
                print(f"  Saved: {save_path}")

    # Combined strip
    print(f"\n--- Combined strip ---")
    workflow, meta = load_workflow("ernie-turbo")
    params = {"prompt": COMBINED_PROMPT, "width": 1376, "height": 1376, "seed": -1}
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
            save_path = str(OUTPUT_DIR / "comic_strip_4panel.png")
            with urllib.request.urlopen(f"{server_url}/view?{p}") as resp:
                with open(save_path, "wb") as f:
                    f.write(resp.read())
            print(f"  Saved: {save_path}")

    print(f"\nDONE!")
    for p in sorted(OUTPUT_DIR.glob("*.png")):
        print(f"  {p}")


if __name__ == "__main__":
    generate()
