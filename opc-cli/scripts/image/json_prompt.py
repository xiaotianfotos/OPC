"""JSON Image Prompt — structured prompt format and converter.

Converts nested JSON prompts to plain text for ComfyUI CLIPTextEncode,
while preserving structure for programmatic manipulation.

Design based on imagejson.org patterns + user caption requirements.
"""

import json
from typing import Any, Optional


# ── Schema Definition ─────────────────────────────────────

JSON_PROMPT_SCHEMA = {
    "version": "1.0",
    "description": "Structured image prompt for AI generation",
    "categories": [
        "subject", "style", "composition", "lighting",
        "background", "color_palette", "negative_constraints",
        "technical_specs", "text_content", "mood",
        "typography_layout", "confrontation", "layout"
    ],
    "fields": {
        "subject": {
            "type": "object",
            "properties": {
                "main": "Primary subject description (required)",
                "details": "Additional subject details (pose, expression, clothing, etc.)",
                "count": "Number of subjects",
                "position": "Subject placement in frame"
            }
        },
        "style": {
            "type": "object",
            "properties": {
                "medium": "Photo / illustration / 3D render / painting / etc.",
                "techniques": "List of artistic techniques",
                "references": "Artist or style references",
                "era": "Time period or artistic movement"
            }
        },
        "composition": {
            "type": "object",
            "properties": {
                "framing": "Close-up / medium shot / wide shot / etc.",
                "angle": "Eye level / low angle / overhead / etc.",
                "depth_of_field": "Shallow / deep / bokeh description",
                "rule_of_thirds": "Whether to apply rule of thirds",
                "focus": "What should be in sharp focus"
            }
        },
        "lighting": {
            "type": "object",
            "properties": {
                "type": "Natural / studio / neon / candlelight / etc.",
                "direction": "Front / side / back / top / under / rim",
                "quality": "Soft / hard / diffused / dramatic",
                "color_temperature": "Warm / cool / mixed"
            }
        },
        "background": {
            "type": "object",
            "properties": {
                "setting": "Indoor / outdoor / abstract / void",
                "environment": "City / nature / studio / space / etc.",
                "details": "Specific background elements",
                "depth": "Layered / flat / atmospheric perspective"
            }
        },
        "color_palette": {
            "type": "object",
            "properties": {
                "dominant": "List of dominant colors (hex or names)",
                "accent": "Accent colors",
                "scheme": "Complementary / monochromatic / analogous / etc.",
                "mood": "Warm / cool / vibrant / muted / pastel"
            }
        },
        "mood": {
            "type": "string_or_object",
            "description": "Overall emotional tone or atmosphere"
        },
        "negative_constraints": {
            "type": "list",
            "description": "Things to avoid in the image"
        },
        "technical_specs": {
            "type": "object",
            "properties": {
                "quality": "8K, ultra-sharp, highly detailed, etc.",
                "render_engine": "Unreal Engine 5, Octane, etc.",
                "camera": "Lens, aperture, film stock simulation",
                "resolution_hint": "Target resolution guidance"
            }
        },
        "text_content": {
            "type": "object",
            "properties": {
                "visible_text": "List of text strings that must appear in image",
                "typography": "Font style, placement, treatment",
                "language": "Language of the text"
            }
        },
        "layout": {
            "type": "string_or_object",
            "description": (
                "Text layout specification for images containing text. "
                "Required when image must render specific text correctly. "
                "Can be: (1) a simple string describing text placement, "
                "(2) a structured object with elements/typography/connectors, "
                "or (3) any free-form layout description. "
                "Design principles: separate 'what text to render' from "
                "'how it looks'; declare each text element with its position; "
                "keep text content as literal strings the model must reproduce."
            )
        }
    }
}


# ── Chinese Typography DSL ────────────────────────────────

TYPOGRAPHY_POSITION_MAP = {
    "top": "顶部",
    "second": "第二行",
    "third": "第三行",
    "middle": "中间",
    "center": "中央",
    "bottom": "底部",
    "bottom_center": "底部中央",
    "bottom_left": "底部左侧",
    "bottom_right": "底部右侧",
    "top_left": "顶部左侧",
    "top_right": "顶部右侧",
    "left": "左侧",
    "right": "右侧",
}


def _render_segment(seg: dict) -> str:
    """Render a single text segment with color and style."""
    text = seg.get("text", "")
    color = seg.get("color", "")
    style = seg.get("style", "")

    if not text:
        return ""

    # Handle gradient color
    if isinstance(color, dict):
        grad_from = color.get("from", "")
        grad_to = color.get("to", "")
        direction = color.get("direction", "从左到右")
        color_desc = f"{direction}{grad_from}渐变到{grad_to}"
    else:
        color_desc = str(color) if color else ""

    parts = []
    if color_desc:
        parts.append(color_desc)
    if style:
        parts.append(style)
    if parts:
        return "".join(parts) + f'"{text}"'
    return f'"{text}"'


def _render_typography_line(line: dict) -> str:
    """Render a typography line (position + segments)."""
    position = line.get("position", "")
    segments = line.get("segments", [])
    emphasis = line.get("emphasis", "")

    if not segments:
        return ""

    # Resolve position
    pos_str = TYPOGRAPHY_POSITION_MAP.get(position, position) or ""

    # Render segments
    if isinstance(segments, dict):
        segments = [segments]
    elif isinstance(segments, str):
        segments = [{"text": segments}]

    seg_texts = [_render_segment(s) for s in segments if s.get("text")]
    seg_texts = [s for s in seg_texts if s]

    if not seg_texts:
        return ""

    line_text = pos_str + "".join(seg_texts)

    if emphasis:
        line_text += "，" + emphasis

    return line_text


def _extract_typography_layout(tl: dict) -> str:
    """Convert typography_layout DSL to Chinese descriptive text.

    This produces output similar to the successful prompts from
    cover style experiments where Chinese text placement,
    color, and hierarchy were explicitly described.
    """
    lines = tl.get("lines", [])
    mascot = tl.get("mascot")
    decorations = tl.get("decorations", [])
    global_style = tl.get("style", "")

    parts = []

    # Render each line
    for line in lines:
        rendered = _render_typography_line(line)
        if rendered:
            parts.append(rendered)

    # Render mascot
    if mascot:
        m_pos = TYPOGRAPHY_POSITION_MAP.get(mascot.get("position", ""), mascot.get("position", ""))
        m_type = mascot.get("type", "")
        m_frame = mascot.get("frame", "")
        m_glow = mascot.get("glow", False)
        m_deco = mascot.get("decoration", "")

        mascot_parts = []
        if m_pos:
            mascot_parts.append(m_pos)
        if m_frame:
            mascot_parts.append("一个" + m_frame)
        if m_type:
            mascot_parts.append(m_type)
        if m_glow:
            mascot_parts.append("发光边框")
        if m_deco:
            mascot_parts.append(m_deco)

        if mascot_parts:
            parts.append("".join(mascot_parts))

    # Render decorations
    for deco in decorations:
        parts.append(f"{deco}")

    # Global style note
    if global_style:
        parts.append(f"整体{global_style}")

    return "。\n".join(parts) + "。" if parts else ""


def _extract_confrontation(cf: dict) -> str:
    """Convert confrontation DSL to Chinese descriptive text."""
    layout = cf.get("layout", "left_vs_right")
    left = cf.get("left", {})
    right = cf.get("right", {})
    top = cf.get("top", {})
    bottom = cf.get("bottom", {})

    if layout == "left_vs_right":
        parts = []
        if left:
            l_name = left.get("name", "")
            l_color = left.get("color", "")
            l_feel = left.get("feel", "")
            l_desc = f"左边{l_color}{l_name}" + (f"({l_feel})" if l_feel else "")
            parts.append(l_desc)
        if right:
            r_name = right.get("name", "")
            r_color = right.get("color", "")
            r_feel = right.get("feel", "")
            r_desc = f"右边{r_color}{r_name}" + (f"({r_feel})" if r_feel else "")
            parts.append(r_desc)
        if parts:
            return "，".join(parts) + "对峙构图"

    elif layout == "top_vs_bottom":
        parts = []
        if top:
            t_name = top.get("name", "")
            t_color = top.get("color", "")
            t_desc = f"上方{t_color}{t_name}" if t_color else f"上方{t_name}"
            parts.append(t_desc)
        if bottom:
            b_name = bottom.get("name", "")
            b_color = bottom.get("color", "")
            b_desc = f"下方{b_color}{b_name}" if b_color else f"下方{b_name}"
            parts.append(b_desc)
        if parts:
            return "，".join(parts) + "上下对比构图"

    return ""


def _extract_layout(layout: dict) -> str:
    """Convert layout object to descriptive text.

    Supports free-form layout objects. Common patterns:
    - elements: [{role, text, position}] — list of text elements
    - typography: {font_style, color, alignment} — global type rules
    - connectors: [{from, to, style}] — lines/arrows between elements
    Any unrecognized keys are rendered as key:value pairs.
    """
    parts = []

    # Render elements
    elements = layout.get("elements", [])
    if elements:
        for el in elements:
            if isinstance(el, str):
                parts.append(el)
                continue
            role = el.get("role", "")
            text = el.get("text", "")
            position = el.get("position", "")
            el_parts = []
            if role:
                el_parts.append(role)
            if position:
                el_parts.append(position)
            if text:
                el_parts.append(f'"{text}"')
            if el_parts:
                parts.append(" ".join(el_parts))

    # Render typography
    typo = layout.get("typography", {})
    if isinstance(typo, dict) and typo:
        typo_parts = []
        for k, v in typo.items():
            typo_parts.append(f"{k}: {v}")
        if typo_parts:
            parts.append("typography: " + ", ".join(typo_parts))
    elif isinstance(typo, str):
        parts.append(f"typography: {typo}")

    # Render connectors
    connectors = layout.get("connectors", [])
    if connectors:
        conn_parts = []
        for c in connectors:
            if isinstance(c, str):
                conn_parts.append(c)
            elif isinstance(c, dict):
                conn_parts.append(f"{c.get('from', '')}->{c.get('to', '')} ({c.get('style', '')})")
        if conn_parts:
            parts.append("connectors: " + ", ".join(conn_parts))

    # Render any other keys not already handled
    handled = {"elements", "typography", "connectors"}
    for k, v in layout.items():
        if k not in handled:
            if isinstance(v, str):
                parts.append(f"{k}: {v}")
            elif isinstance(v, (list, dict)):
                parts.append(f"{k}: {json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v}")

    return ", ".join(p for p in parts if p.strip())


# ── Converter ─────────────────────────────────────────────

def _fmt_list(val: Any) -> str:
    if isinstance(val, list):
        return ", ".join(str(x) for x in val)
    return str(val)


def _extract_subject(subject) -> str:
    if isinstance(subject, str):
        return subject
    parts = []
    if isinstance(subject, dict):
        if "main" in subject:
            parts.append(subject["main"])
        if "details" in subject:
            parts.append(subject["details"])
        if "count" in subject:
            parts.append(f"count: {subject['count']}")
        if "position" in subject:
            parts.append(f"positioned {subject['position']}")
    return ", ".join(parts)


def _extract_style(style) -> str:
    if isinstance(style, str):
        return style
    parts = []
    if isinstance(style, dict):
        if "medium" in style:
            parts.append(style["medium"])
        if "techniques" in style:
            parts.append(_fmt_list(style["techniques"]))
        if "references" in style:
            refs = _fmt_list(style["references"])
            parts.append(f"inspired by {refs}")
        if "era" in style:
            parts.append(f"{style['era']} aesthetic")
    return ", ".join(parts)


def _extract_composition(comp: dict) -> str:
    parts = []
    if "framing" in comp:
        parts.append(comp["framing"])
    if "angle" in comp:
        parts.append(f"{comp['angle']} angle")
    if "depth_of_field" in comp:
        parts.append(f"{comp['depth_of_field']} depth of field")
    if "focus" in comp:
        parts.append(f"focus on {comp['focus']}")
    return ", ".join(parts)


def _extract_lighting(light: dict) -> str:
    parts = []
    if "type" in light:
        parts.append(f"{light['type']} lighting")
    if "direction" in light:
        parts.append(f"from {light['direction']}")
    if "quality" in light:
        parts.append(light["quality"])
    if "color_temperature" in light:
        parts.append(f"{light['color_temperature']} color temperature")
    return ", ".join(parts)


def _extract_background(bg: dict) -> str:
    parts = []
    if "setting" in bg:
        parts.append(bg["setting"])
    if "environment" in bg:
        parts.append(bg["environment"])
    if "details" in bg:
        parts.append(bg["details"])
    if "depth" in bg:
        parts.append(f"{bg['depth']} background")
    return ", ".join(parts)


def _extract_colors(cp: dict) -> str:
    parts = []
    if "dominant" in cp:
        parts.append(f"dominant colors: {_fmt_list(cp['dominant'])}")
    if "accent" in cp:
        parts.append(f"accent colors: {_fmt_list(cp['accent'])}")
    if "scheme" in cp:
        parts.append(f"{cp['scheme']} color scheme")
    if "mood" in cp:
        parts.append(f"{cp['mood']} palette mood")
    return ", ".join(parts)


def _extract_technical(tech: dict) -> str:
    parts = []
    if "quality" in tech:
        parts.append(tech["quality"])
    if "render_engine" in tech:
        parts.append(f"rendered in {tech['render_engine']}")
    if "camera" in tech:
        parts.append(f"camera: {tech['camera']}")
    return ", ".join(parts)


def _extract_text_content(tc: dict) -> str:
    """Extract text content — critical for images that must contain specific text."""
    parts = []
    if "visible_text" in tc:
        texts = tc["visible_text"]
        if isinstance(texts, list):
            for t in texts:
                parts.append(f'text "{t}"')
        else:
            parts.append(f'text "{texts}"')
    if "typography" in tc:
        parts.append(f"typography: {tc['typography']}")
    if "language" in tc:
        parts.append(f"text language: {tc['language']}")
    return ", ".join(parts)


def json_prompt_to_text(prompt_json: dict) -> dict:
    """Convert structured JSON prompt to plain text for ComfyUI.

    Returns {"positive": str, "negative": str, "meta": dict}
    """
    positive_parts = []
    negative_parts = []
    meta = {}

    # Order matters for prompt coherence
    if "subject" in prompt_json:
        positive_parts.append(_extract_subject(prompt_json["subject"]))

    if "style" in prompt_json:
        positive_parts.append(_extract_style(prompt_json["style"]))

    if "composition" in prompt_json:
        positive_parts.append(_extract_composition(prompt_json["composition"]))

    if "lighting" in prompt_json:
        positive_parts.append(_extract_lighting(prompt_json["lighting"]))

    if "background" in prompt_json:
        positive_parts.append(_extract_background(prompt_json["background"]))

    if "color_palette" in prompt_json:
        positive_parts.append(_extract_colors(prompt_json["color_palette"]))

    if "mood" in prompt_json:
        if isinstance(prompt_json["mood"], dict):
            mood_parts = []
            for k, v in prompt_json["mood"].items():
                mood_parts.append(f"{k}: {v}")
            positive_parts.append(", ".join(mood_parts))
        else:
            positive_parts.append(str(prompt_json["mood"]))

    if "text_content" in prompt_json:
        text_str = _extract_text_content(prompt_json["text_content"])
        if text_str:
            positive_parts.append(text_str)
            meta["has_text_content"] = True

    # Chinese typography layout DSL — renders as Chinese descriptive text
    # This produces output similar to successful ERNIE prompts where
    # Chinese text placement, color, and hierarchy are explicitly described.
    if "typography_layout" in prompt_json:
        typo_str = _extract_typography_layout(prompt_json["typography_layout"])
        if typo_str:
            positive_parts.append(typo_str)
            meta["has_typography_layout"] = True

    # Confrontation / comparison layout (left-vs-right, top-vs-bottom)
    if "confrontation" in prompt_json:
        conf_str = _extract_confrontation(prompt_json["confrontation"])
        if conf_str:
            positive_parts.append(conf_str)
            meta["has_confrontation"] = True

    if "technical_specs" in prompt_json:
        positive_parts.append(_extract_technical(prompt_json["technical_specs"]))

    # Layout — flexible: string, object, or any free-form description
    if "layout" in prompt_json:
        layout = prompt_json["layout"]
        if isinstance(layout, str):
            if layout.strip():
                positive_parts.append(layout.strip())
                meta["has_layout"] = True
        elif isinstance(layout, dict):
            layout_str = _extract_layout(layout)
            if layout_str:
                positive_parts.append(layout_str)
                meta["has_layout"] = True

    if "negative_constraints" in prompt_json:
        neg = prompt_json["negative_constraints"]
        if isinstance(neg, list):
            negative_parts.extend(neg)
        elif isinstance(neg, str):
            negative_parts.append(neg)
        elif isinstance(neg, dict):
            for k, v in neg.items():
                negative_parts.append(f"{k}: {v}")

    # Flatten: remove empty parts, join with ", "
    positive = ", ".join(p for p in positive_parts if p.strip())
    negative = ", ".join(p for p in negative_parts if p.strip())

    return {
        "positive": positive,
        "negative": negative,
        "meta": meta,
    }


def validate_json_prompt(prompt_json: dict) -> list:
    """Validate a JSON prompt against the schema. Returns list of issues."""
    issues = []

    if not isinstance(prompt_json, dict):
        issues.append("Prompt must be a JSON object")
        return issues

    # Check for unknown top-level keys
    known = set(JSON_PROMPT_SCHEMA["categories"])
    unknown = set(prompt_json.keys()) - known - {"meta"}
    if unknown:
        issues.append(f"Unknown fields: {sorted(unknown)}")

    # Validate subject has 'main' if present
    if "subject" in prompt_json:
        sub = prompt_json["subject"]
        if isinstance(sub, dict) and "main" not in sub:
            issues.append("subject.main is recommended for best results")

    # Validate negative_constraints is list or dict
    if "negative_constraints" in prompt_json:
        neg = prompt_json["negative_constraints"]
        if not isinstance(neg, (list, dict, str)):
            issues.append("negative_constraints must be list, dict, or string")

    # Validate color_palette hex colors roughly
    if "color_palette" in prompt_json:
        cp = prompt_json["color_palette"]
        if isinstance(cp, dict) and "dominant" in cp:
            dom = cp["dominant"]
            if isinstance(dom, list):
                for c in dom:
                    if isinstance(c, str) and c.startswith("#"):
                        if len(c) not in (4, 7, 9):
                            issues.append(f"Suspicious hex color: {c}")

    # Layout validation — warn if missing for text-containing images
    has_text = any(k in prompt_json for k in ("text_content", "typography_layout"))
    has_layout = "layout" in prompt_json

    if has_text and not has_layout:
        issues.append(
            "[WARNING] Image contains text but 'layout' field is missing. "
            "The 'layout' field tells the model where and how to render text. "
            "Design principles: (1) list each text element with its literal content and position, "
            "(2) separate 'what text to show' from 'how it looks', "
            "(3) keep text as literal strings the model must reproduce verbatim. "
            "Example: layout: {elements: [{role: title, text: '破茧成蝶', position: top-center}]}"
        )

    return issues


def text_to_json_prompt(text: str, hints: Optional[dict] = None) -> dict:
    """Stub: Convert plain text to structured JSON prompt.

    This would typically be done by an LLM. The function provides
    a template/structure for the LLM to fill.
    """
    merged_hints = hints or {}
    return {
        "meta": {
            "source": "text_conversion",
            "original_text_preview": text[:200] if text else "",
            **merged_hints
        },
        "subject": {"main": text},
    }
