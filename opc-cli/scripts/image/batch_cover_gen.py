#!/usr/bin/env python3
"""Batch generate 100 video cover images with randomized styles.

Fixed text:
  - 4060Ti史诗强化
  - Nano Banana
  - 本地平替来了

Randomized each round:
  - art style
  - color palette
  - cartoon character (exaggerated expression, partial text occlusion)
  - composition
  - aspect ratio (3:4 / 4:3 alternating)
"""

import json
import random
import shutil
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from image.comfyui import generate_image, check_connection
from image.workflow import load_workflow, inject_params
from image.json_prompt import json_prompt_to_text

OUTPUT_DIR = "/vol2/1000/output/cover_batch"
BATCH_SIZE = 100

# ── Style Pools ───────────────────────────────────────────

STYLES = [
    "Q版卡通3D风格，圆润可爱，C4D渲染，柔光",
    "美式漫画风格，粗黑线条，高饱和色彩，夸张表情",
    "日式动漫风格，萌系角色，大眼睛，夸张动作",
    "手绘水彩插画风格，笔触明显，温暖色调",
    "赛博朋克霓虹风格，RGB光效，未来科技感",
    "复古波普艺术，网点印刷，高对比度",
    "街头涂鸦风格，喷漆质感，潮流街头",
    "蒸汽波风格，粉色渐变，复古电脑界面",
    "像素游戏风格，8-bit，复古街机",
    "剪纸镂空风格，分层立体，手工质感",
    "黏土动画风格，Stop Motion，手工捏制质感",
    "故障艺术风格，Glitch，数据错乱，RGB分离",
    "荧光涂鸦风格，夜光效果，黑底荧光",
    "金属工业风格，不锈钢拉丝，机械齿轮",
    "魔法奇幻风格，星光粒子，魔法光环",
    "美食卡通风格，奶油质感，糖果色",
    "超级英雄漫画风格，动作张力，速度线",
    "极简几何风格，扁平设计，色块拼接",
    "国潮风格，中式元素，祥云纹样，国风配色",
    "Kawaii可爱风格， pastel色系，圆润造型",
]

CHARACTERS = [
    "一个Q版卡通男孩，眼睛瞪得像铜铃，嘴巴张成O型，手指向前方，表情极度震惊兴奋",
    "一个卡通小女孩，双手捧脸，眼睛冒星星，开心到飞起",
    "一个圆滚滚的机器人，头部天线闪烁，双手举起欢呼",
    "一只拟人化的猫咪，戴着VR眼镜，张大嘴巴惊叹，前爪抬起",
    "一个卡通科学家，爆炸头，眼镜反光，手里举着发光的试管",
    "一个肌肉发达的卡通超人，披风飞扬，握拳怒吼",
    "一个卡通外星人，三只眼睛，触手挥舞，表情好奇",
    "一个卡通小恶魔， horns角，尾巴摇摆，坏笑指着文字",
    "一个卡通熊猫，戴着耳机，摇头晃脑，嗨到不行",
    "一个卡通宇航员，头盔反光，漂浮在空中，手比耶",
    "一个卡通青蛙，鼓着腮帮，瞪大眼睛，手指着文字",
    "一个卡通小怪兽，毛茸茸，只有一只大眼睛，张开双臂",
    "一个卡通忍者，夸张奔跑姿势，手里剑飞出，速度线",
    "一个卡通厨师，帽子歪戴，手里举着锅铲，表情夸张",
    "一个卡通海盗，独眼眼罩，咧嘴大笑，手指前方",
    "一个卡通小丑，彩色爆炸头，大红鼻子，咧嘴笑",
]

COLOR_THEMES = [
    {"bg": "深黑色", "text1": "亮黄色", "text2": "亮橙色", "text3": "白色", "accent": "红色"},
    {"bg": "深蓝色", "text1": "青色", "text2": "亮蓝色", "text3": "白色", "accent": "紫色"},
    {"bg": "深紫色", "text1": "粉色", "text2": "亮紫色", "text3": "白色", "accent": "青色"},
    {"bg": "深红色", "text1": "亮黄色", "text2": "金色", "text3": "白色", "accent": "橙色"},
    {"bg": "深绿色", "text1": "亮绿色", "text2": "荧光绿", "text3": "白色", "accent": "黄色"},
    {"bg": "深灰色", "text1": "亮粉色", "text2": "亮青色", "text3": "白色", "accent": "黄色"},
    {"bg": "纯白色", "text1": "深红色", "text2": "深蓝色", "text3": "黑色", "accent": "橙色"},
    {"bg": "暖橙色", "text1": "深棕色", "text2": "红色", "text3": "白色", "accent": "黄色"},
    {"bg": "深青色", "text1": "亮黄色", "text2": "亮绿色", "text3": "白色", "accent": "橙色"},
    {"bg": "暗粉色", "text1": "深红色", "text2": "紫色", "text3": "白色", "accent": "金色"},
]

BACKGROUND_DETAILS = [
    "纯色背景，极简",
    "渐变背景，从上到下",
    "放射状光芒背景，从中心向外发散",
    "速度线背景，动感十足",
    "星星点点背景，宇宙感",
    "闪电裂纹背景，炸裂感",
    "几何图案背景，三角形色块",
    "半调网点背景，复古印刷",
    "渐变网格背景，流体感",
    "爆炸云背景，漫画风格",
    "电路板纹理背景，科技感",
    "波浪线条背景，流动感",
    "气泡背景，轻松活泼",
    "菱形格子背景，时尚感",
    "渐变圆环背景，聚焦感",
]

TEXTURE_EFFECTS = [
    "文字内部有熔岩流动纹理",
    "文字内部有星空纹理",
    "文字内部有电路纹理",
    "文字有3D浮雕凸起效果",
    "文字边缘有霓虹发光",
    "文字有金属拉丝质感",
    "文字内部有渐变彩虹色",
    "文字有手绘涂鸦边缘",
    "文字有泼墨晕染效果",
    "文字有水晶透明质感",
    "文字有火焰燃烧效果",
    "文字有冰冻霜花效果",
    "文字内部有棋盘格纹理",
    "文字有像素化边缘",
    "文字有涂鸦喷漆质感",
]

# ── Builder ───────────────────────────────────────────────

def build_prompt(style_idx, char_idx, color_idx, bg_idx, tex_idx, ratio):
    style = STYLES[style_idx]
    character = CHARACTERS[char_idx]
    colors = COLOR_THEMES[color_idx]
    bg_detail = BACKGROUND_DETAILS[bg_idx]
    texture = TEXTURE_EFFECTS[tex_idx]

    # Character position: sometimes left, sometimes right, sometimes bottom
    char_positions = [
        "画面左下角",
        "画面右下角",
        "画面左侧",
        "画面右侧",
        "画面底部中央",
        "画面左上方",
        "画面右上方",
    ]
    char_pos = random.choice(char_positions)

    # Size variation
    sizes = ["较大", "中等", "巨大", "小巧精致"]
    char_size = random.choice(sizes)

    # Occlusion level
    occlusions = [
        "部分身体遮挡住下方的文字",
        "手臂伸展遮挡住一部分文字",
        "头部刚好在文字旁边不遮挡",
        "身体在文字前面，部分遮挡中央文字",
        "夸张动作的手指指向文字",
    ]
    occlusion = random.choice(occlusions)

    prompt = {
        "style": style,
        "background": {
            "color": colors["bg"],
            "details": bg_detail,
            "texture": "极简"
        },
        "typography_layout": {
            "lines": [
                {
                    "position": "top",
                    "segments": [{"text": "4060Ti史诗强化", "color": colors["text1"]}],
                    "emphasis": "粗体大字，" + texture
                },
                {
                    "position": "center",
                    "segments": [{"text": "Nano Banana", "style": "超大标题", "color": colors["text2"]}],
                    "emphasis": "占据画面最大面积，" + texture + "，笔画粗壮有力"
                },
                {
                    "position": "bottom",
                    "segments": [{"text": "本地平替来了", "color": colors["text3"]}],
                    "emphasis": "粗体大字"
                }
            ],
            "style": "文字颜色对比强烈，极简背景"
        },
        "subject": f"{char_pos}有一个{char_size}的{character}，{occlusion}，卡通人物在画面最前面，Z-index最高层",
        "mood": "炸裂，抓眼，令人过目不忘，视频封面",
        "composition": {
            "framing": "medium shot",
            "focus": "文字和卡通人物都在视觉中心区域"
        },
        "color_palette": {
            "dominant": [colors["bg"], colors["text1"], colors["text2"], colors["accent"]],
            "scheme": "high contrast"
        },
        "technical_specs": {
            "quality": "8K sharp clean edges"
        }
    }
    return prompt


def generate_one(workflow, meta, cfg, prompt_json, seed, width, height, output_path):
    """Generate a single image and save to output_path."""
    converted = json_prompt_to_text(prompt_json)
    prompt_text = converted["positive"]
    negative_text = converted.get("negative", "")

    params = {
        "prompt": prompt_text,
        "seed": seed,
        "width": width,
        "height": height,
    }
    if negative_text and "negative_prompt" in meta.get("params", {}):
        params["negative_prompt"] = negative_text

    try:
        prepared = inject_params(workflow, meta, params)
        result = generate_image(prepared, cfg, filename_prefix="cover_batch")
        src_path = result["filepaths"][0]
        shutil.move(src_path, output_path)
        return True, output_path
    except Exception as e:
        return False, str(e)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    cfg = {}
    if not check_connection(cfg):
        print("Cannot connect to ComfyUI")
        sys.exit(1)

    # Load workflow once
    try:
        workflow, meta = load_workflow("ernie-full")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"Starting batch generation: {BATCH_SIZE} images")
    print(f"Output dir: {OUTPUT_DIR}")
    print("=" * 60)

    for i in range(BATCH_SIZE):
        # Random selections
        style_idx = random.randint(0, len(STYLES) - 1)
        char_idx = random.randint(0, len(CHARACTERS) - 1)
        color_idx = random.randint(0, len(COLOR_THEMES) - 1)
        bg_idx = random.randint(0, len(BACKGROUND_DETAILS) - 1)
        tex_idx = random.randint(0, len(TEXTURE_EFFECTS) - 1)
        seed = random.randint(1, 999999)

        # Alternate ratios: even = 3:4 (832x1216), odd = 4:3 (1216x832)
        if i % 2 == 0:
            width, height = 832, 1216
            ratio = "3x4"
        else:
            width, height = 1216, 832
            ratio = "4x3"

        prompt_json = build_prompt(style_idx, char_idx, color_idx, bg_idx, tex_idx, ratio)

        output_name = f"cover_{i+1:03d}_{ratio}_s{style_idx}_c{char_idx}_cl{color_idx}.png"
        output_path = os.path.join(OUTPUT_DIR, output_name)

        print(f"\n[{i+1}/{BATCH_SIZE}] {output_name}")
        print(f"    Style: {STYLES[style_idx][:40]}...")
        print(f"    Char: {CHARACTERS[char_idx][:40]}...")
        print(f"    Colors: bg={COLOR_THEMES[color_idx]['bg']}, text={COLOR_THEMES[color_idx]['text2']}")
        print(f"    Seed: {seed}, Size: {width}x{height}")

        ok, result = generate_one(workflow, meta, cfg, prompt_json, seed, width, height, output_path)
        if ok:
            print(f"    OK -> {output_path}")
        else:
            print(f"    FAIL: {result}")

        # Small delay between generations
        time.sleep(1)

    print("\n" + "=" * 60)
    print(f"Batch complete. Generated images in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
