"""Update KG extensions with Chinese Typography DSL entities.

Adds typography positions, styles, decorations, color names, and
confrontation layouts to the PromptKG extensions.json.
"""
import json
import os
from pathlib import Path

EXTENSIONS_PATH = Path(__file__).parent / "extensions.json"

# ── New DSL Entities ──────────────────────────────────────

DSL_ENTITIES = {
    # Typography positions (排版位置)
    "typography:top": {"category": "typography", "name": "顶部", "count": 30},
    "typography:second_line": {"category": "typography", "name": "第二行", "count": 25},
    "typography:third_line": {"category": "typography", "name": "第三行", "count": 20},
    "typography:middle": {"category": "typography", "name": "中间", "count": 18},
    "typography:center": {"category": "typography", "name": "中央", "count": 35},
    "typography:bottom": {"category": "typography", "name": "底部", "count": 22},
    "typography:bottom_center": {"category": "typography", "name": "底部中央", "count": 15},
    "typography:top_left": {"category": "typography", "name": "顶部左侧", "count": 8},
    "typography:top_right": {"category": "typography", "name": "顶部右侧", "count": 8},
    "typography:bottom_left": {"category": "typography", "name": "底部左侧", "count": 6},
    "typography:bottom_right": {"category": "typography", "name": "底部右侧", "count": 6},
    "typography:left": {"category": "typography", "name": "左侧", "count": 12},
    "typography:right": {"category": "typography", "name": "右侧", "count": 12},

    # Typography styles (排版样式)
    "typography:large_text": {"category": "typography", "name": "大字", "count": 28},
    "typography:extra_large_title": {"category": "typography", "name": "超大标题", "count": 22},
    "typography:bold_text": {"category": "typography", "name": "粗体大字", "count": 20},
    "typography:handwritten": {"category": "typography", "name": "手写体", "count": 15},
    "typography:brush_calligraphy": {"category": "typography", "name": "毛笔字", "count": 18},
    "typography:embossed_3d": {"category": "typography", "name": "3D浮雕", "count": 16},
    "typography:drop_shadow": {"category": "typography", "name": "重阴影", "count": 14},
    "typography:gradient_text": {"category": "typography", "name": "渐变文字", "count": 12},
    "typography:neon_glow": {"category": "typography", "name": "霓虹发光", "count": 10},

    # Typography decorations (排版装饰)
    "typography:circular_frame": {"category": "typography", "name": "圆形边框", "count": 14},
    "typography:glowing_border": {"category": "typography", "name": "发光边框", "count": 12},
    "typography:red_seal": {"category": "typography", "name": "红色印章", "count": 10},
    "typography:four_corner_seal": {"category": "typography", "name": "四角印章", "count": 8},
    "typography:halftone_texture": {"category": "typography", "name": "网点纹理", "count": 16},
    "typography:paper_grain": {"category": "typography", "name": "纸张颗粒感", "count": 10},
    "typography:ink_bleed": {"category": "typography", "name": "墨迹晕染", "count": 6},

    # Confrontation layouts (对比构图)
    "confrontation:left_vs_right": {"category": "confrontation", "name": "左右对峙", "count": 18},
    "confrontation:top_vs_bottom": {"category": "confrontation", "name": "上下对比", "count": 12},
    "confrontation:three_way": {"category": "confrontation", "name": "三方对比", "count": 5},

    # Specific color names (具体颜色)
    "color_palette:pink": {"category": "color_palette", "name": "粉色", "count": 20},
    "color_palette:white": {"category": "color_palette", "name": "白色", "count": 25},
    "color_palette:blue": {"category": "color_palette", "name": "蓝色", "count": 22},
    "color_palette:orange_red": {"category": "color_palette", "name": "橙红色", "count": 18},
    "color_palette:yellow": {"category": "color_palette", "name": "黄色", "count": 20},
    "color_palette:deep_red": {"category": "color_palette", "name": "深红色", "count": 15},
    "color_palette:gold": {"category": "color_palette", "name": "金色", "count": 16},
    "color_palette:black": {"category": "color_palette", "name": "黑色", "count": 30},
    "color_palette:green": {"category": "color_palette", "name": "绿色", "count": 14},
    "color_palette:purple": {"category": "color_palette", "name": "紫色", "count": 12},
    "color_palette:cyan": {"category": "color_palette", "name": "青色", "count": 10},
    "color_palette:magenta": {"category": "color_palette", "name": "洋红色", "count": 8},
}

# ── Co-occurrence relations ───────────────────────────────

# Format: {entity: {neighbor: weight}}
DSL_CO_OCCURRENCE = {
    # Typography positions ↔ genres/styles
    "typography:top": {
        "genre:poster": 20, "genre:infographic": 15, "mood:dramatic": 12,
        "style:3d_render": 10, "typography:large_text": 18,
    },
    "typography:center": {
        "genre:poster": 22, "mood:dramatic": 15, "style:pop_art": 12,
        "typography:extra_large_title": 20, "typography:embossed_3d": 14,
    },
    "typography:bottom_center": {
        "genre:poster": 14, "style:3d_render": 10,
        "typography:circular_frame": 12, "typography:glowing_border": 10,
    },
    "typography:second_line": {
        "genre:poster": 16, "genre:infographic": 12,
    },

    # Typography styles ↔ moods/genres
    "typography:extra_large_title": {
        "genre:poster": 18, "mood:dramatic": 14, "style:pop_art": 12,
        "color_palette:gold": 10, "color_palette:yellow": 10,
    },
    "typography:bold_text": {
        "genre:poster": 16, "mood:dramatic": 12, "style:vintage": 10,
    },
    "typography:brush_calligraphy": {
        "style:vintage": 14, "style:hand_drawn": 12, "mood:nostalgic": 10,
        "color_palette:black": 12, "color_palette:gold": 8,
    },
    "typography:embossed_3d": {
        "style:3d_render": 16, "genre:poster": 14, "mood:luxurious": 10,
        "color_palette:gold": 12, "typography:drop_shadow": 14,
    },
    "typography:gradient_text": {
        "genre:poster": 12, "style:pop_art": 10, "mood:dramatic": 10,
        "color_palette:orange_red": 10, "color_palette:yellow": 8,
    },
    "typography:neon_glow": {
        "style:cyberpunk": 16, "lighting:neon": 14, "mood:futuristic": 12,
        "color_palette:cyan": 10, "color_palette:magenta": 10,
    },

    # Decorations ↔ styles
    "typography:halftone_texture": {
        "style:pop_art": 18, "style:vintage": 12, "genre:poster": 14,
    },
    "typography:red_seal": {
        "style:vintage": 14, "style:hand_drawn": 10, "mood:nostalgic": 10,
    },
    "typography:four_corner_seal": {
        "style:vintage": 12, "style:hand_drawn": 10, "genre:poster": 10,
    },
    "typography:circular_frame": {
        "genre:poster": 12, "style:3d_render": 10, "style:digital_art": 8,
    },
    "typography:glowing_border": {
        "style:3d_render": 14, "lighting:neon": 10, "genre:poster": 10,
    },

    # Confrontation ↔ genres
    "confrontation:left_vs_right": {
        "genre:comparison": 18, "genre:poster": 14, "mood:dramatic": 12,
        "composition:horizontal": 14, "style:cinematic": 10,
    },
    "confrontation:top_vs_bottom": {
        "genre:comparison": 12, "genre:infographic": 10, "mood:dramatic": 8,
        "composition:vertical": 12,
    },

    # Colors ↔ moods/styles
    "color_palette:pink": {
        "mood:playful": 12, "style:pastel_aesthetic": 10, "mood:warm": 8,
    },
    "color_palette:gold": {
        "mood:luxurious": 14, "style:3d_render": 10, "mood:dramatic": 8,
        "typography:embossed_3d": 10,
    },
    "color_palette:black": {
        "mood:dark": 16, "style:cinematic": 10, "genre:poster": 10,
        "typography:bold_text": 8,
    },
    "color_palette:blue": {
        "mood:serene": 10, "style:cinematic": 8, "mood:cool": 8,
    },
    "color_palette:orange_red": {
        "mood:dramatic": 12, "style:pop_art": 10, "mood:warm": 10,
        "typography:gradient_text": 8,
    },
    "color_palette:yellow": {
        "mood:warm": 12, "style:pop_art": 8, "mood:playful": 8,
        "typography:extra_large_title": 8,
    },
    "color_palette:purple": {
        "mood:dark": 10, "style:vaporwave": 12, "mood:futuristic": 8,
    },
    "color_palette:cyan": {
        "style:cyberpunk": 12, "lighting:neon": 10, "mood:futuristic": 10,
    },
}


def load_extensions():
    if not EXTENSIONS_PATH.exists():
        return {"meta": {}, "entities": {}, "co_occurrence": {}}
    with open(EXTENSIONS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_extensions(data):
    with open(EXTENSIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def merge_co_occurrence(existing, new):
    """Additive merge: increment weights for existing pairs, add new pairs."""
    for src, neighbors in new.items():
        if src not in existing:
            existing[src] = {}
        for tgt, weight in neighbors.items():
            existing[src][tgt] = existing[src].get(tgt, 0) + weight
    return existing


def main():
    data = load_extensions()

    # Merge entities (update count if already exists)
    for entity_id, info in DSL_ENTITIES.items():
        if entity_id in data["entities"]:
            data["entities"][entity_id]["count"] += info["count"]
        else:
            data["entities"][entity_id] = info

    # Merge co-occurrence
    data["co_occurrence"] = merge_co_occurrence(
        data.get("co_occurrence", {}), DSL_CO_OCCURRENCE
    )

    # Update meta
    data["meta"]["dsl_version"] = "1.0"
    data["meta"]["dsl_description"] = "Chinese Typography DSL entities for video cover / poster generation"
    data["meta"]["dsl_categories"] = ["typography", "confrontation"]
    data["meta"]["entity_count"] = len(data["entities"])

    save_extensions(data)

    print(f"Updated {EXTENSIONS_PATH}")
    print(f"  Total entities: {len(data['entities'])}")
    print(f"  New DSL entities: {len(DSL_ENTITIES)}")
    print(f"  Co-occurrence pairs added/updated: {len(DSL_CO_OCCURRENCE)}")

    # Verify by loading with PromptKG
    print("\nVerification with PromptKG:")
    from image.kg.engine import PromptKG
    kg = PromptKG()
    print(f"  Categories: {kg.categories}")
    print(f"  Typography entities: {len(kg.list_category('typography'))}")
    print(f"  Confrontation entities: {len(kg.list_category('confrontation'))}")

    # Demo skeleton
    print("\nDemo: opc image kg skeleton genre:poster mood:dramatic")
    result = kg.skeleton(["genre:poster", "mood:dramatic"])
    if "recommendations" in result and "typography" in result["recommendations"]:
        recs = result["recommendations"]["typography"][:5]
        print("  Recommended typography:")
        for r in recs:
            print(f"    {r['entity']}: {r['name']} (score={r['score']}, conf={r['confidence']})")


if __name__ == "__main__":
    main()
