#!/usr/bin/env python3
"""Compare same prompt across z-image and qwen-image models."""

import shutil
import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from image.comfyui import generate_image, check_connection
from image.workflow import load_workflow, inject_params
from image.json_prompt import json_prompt_to_text

OUTPUT_DIR = "/vol2/1000/output/cover_batch/compare"


def build_prompt():
    """Build the prompt JSON for banana-cut cover."""
    return {
        "style": "波普艺术街头涂鸦风格，粗黑线条，高饱和色彩，网点印刷纹理背景，漫画大爆炸拟声词效果",
        "background": {
            "color": "深灰蓝色",
            "texture": "半调网点纹理，漫画速度线",
            "setting": "clean"
        },
        "typography_layout": {
            "lines": [
                {
                    "position": "top",
                    "segments": [{"text": "4060Ti史诗强化", "color": "亮粉色"}],
                    "emphasis": "粗体大字，漫画字体"
                },
                {
                    "position": "center",
                    "segments": [{"text": "Nano Banana", "style": "超大标题", "color": {"type": "gradient", "from": "青色", "to": "亮蓝色"}}],
                    "emphasis": "3D立体浮雕，文字中间一根被切开的黄色香蕉，一把夸张巨大的黑色战术军刀斜插入香蕉，刀刃锋利银色反光，刀柄黑色防滑纹理，香蕉被整齐切成两半，切口平整露出白色果肉，两半香蕉微微分开"
                },
                {
                    "position": "bottom",
                    "segments": [{"text": "本地平替来了", "color": "亮黄色"}],
                    "emphasis": "超大号粗体大字，漫画拟声词效果，文字周围有爆炸云和放射线条，边缘黑色粗描边"
                }
            ],
            "style": "文字集中在画面中央，底部文字极度炸裂"
        },
        "subject": "画面中央Nano Banana大字中间有一根被切开的黄色香蕉，黑色战术军刀斜插入香蕉，银色刀刃，切口露出果肉",
        "composition": {
            "framing": "medium shot",
            "focus": "文字、香蕉和刀居中"
        },
        "mood": "炸裂，波普艺术，幽默有趣，漫画张力",
        "technical_specs": {"quality": "8K sharp"}
    }


def generate_with_model(model_alias, prompt_text, negative_text, seed, width, height, output_name):
    """Generate with a specific model workflow."""
    cfg = {}
    if not check_connection(cfg):
        print(f"[{model_alias}] Cannot connect to ComfyUI")
        return False, "No connection"

    try:
        workflow, meta = load_workflow(model_alias)
    except FileNotFoundError as e:
        print(f"[{model_alias}] Error: {e}")
        return False, str(e)

    params = {
        "prompt": prompt_text,
        "seed": seed,
        "width": width,
        "height": height,
    }
    if negative_text and "negative_prompt" in meta.get("params", {}):
        params["negative_prompt"] = negative_text

    print(f"\n[{model_alias}] Generating {output_name} (seed={seed}, {width}x{height})")
    try:
        prepared = inject_params(workflow, meta, params)
        result = generate_image(prepared, cfg, filename_prefix=f"compare_{model_alias}")
        src_path = result["filepaths"][0]
        output_path = os.path.join(OUTPUT_DIR, output_name)
        shutil.move(src_path, output_path)
        print(f"  OK -> {output_path}")
        return True, output_path
    except Exception as e:
        print(f"  FAIL: {e}")
        return False, str(e)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    prompt_json = build_prompt()
    converted = json_prompt_to_text(prompt_json)
    prompt_text = converted["positive"]
    negative_text = converted.get("negative", "")

    seed = random.randint(1, 999999)
    width, height = 832, 1216  # 3:4 ratio

    print("=" * 60)
    print(f"Same prompt, different models")
    print(f"Seed: {seed}, Size: {width}x{height}")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 60)
    print(f"\nPrompt:\n{prompt_text[:300]}...")

    # Z-Image
    ok1, result1 = generate_with_model(
        "z-image", prompt_text, negative_text, seed, width, height,
        f"compare_zimage_s{seed}.png"
    )

    # Qwen-Image (different seed to avoid identical issue)
    seed2 = random.randint(1, 999999)
    ok2, result2 = generate_with_model(
        "qwen-image", prompt_text, negative_text, seed2, width, height,
        f"compare_qwen_s{seed2}.png"
    )

    print("\n" + "=" * 60)
    print("Comparison complete!")
    if ok1:
        print(f"  Z-Image:  {result1}")
    if ok2:
        print(f"  Qwen:     {result2}")


if __name__ == "__main__":
    main()
