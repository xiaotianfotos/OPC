"""
ASS Karaoke Subtitle Generator

Generates SRT and ASS subtitle files from ASR result dicts.
Uses \kf karaoke effect with white text + black border, golden highlight.
"""

from dataclasses import dataclass
from typing import Dict, List, Union
from pathlib import Path


@dataclass
class ASSSubtitleStyle:
    """ASS subtitle style configuration.

    Default: White text with black border, golden highlight for karaoke.
    """

    # ── Character (字符) ──
    font: str = "Source Han Sans SC"
    bold: bool = True
    italic: bool = False
    size: int = 50
    color: str = "&H00FFFFFF"          # White (BGR)
    spacing: float = 0

    # ── Border (边框) ──
    border_width: float = 3
    border_color: str = "&H00000000"   # Black

    # ── Shadow (投影) ──
    shadow_enabled: bool = True
    shadow_color: str = "&H00000000"   # Black
    shadow_offset_x: float = 2
    shadow_offset_y: float = 2
    shadow_blur: float = 0
    shadow_opacity: int = 80           # 0=transparent, 100=opaque

    # ── Position (位置) ──
    alignment: int = 8                 # 8=top-center
    margin_v: int = 150
    margin_l: int = 10
    margin_r: int = 10

    # ── Highlight / Karaoke (高亮) ──
    highlight_enabled: bool = True
    highlight_mode: str = "fill"         # "fill" = \kf karaoke
    highlight_color: str = "&H0000D7FF"  # Golden (BGR)
    highlight_scale: float = 108
    dim_color: str = "&H00FFFFFF"        # White (unhighlighted)

    # ── Meta ──
    style_name: str = "Karaoke"

    # ── Derived helpers ──

    @property
    def has_asymmetric_shadow(self) -> bool:
        """Whether shadow offset is asymmetric (needs inline \\xshad/\\yshad tags)."""
        return self.shadow_offset_x != self.shadow_offset_y

    def _shadow_alpha_byte(self) -> int:
        """Shadow alpha: 0=opaque, 255=transparent."""
        return round((100 - self.shadow_opacity) / 100 * 255)

    def _back_colour_hex(self) -> str:
        """BackColour (shadow color with alpha) for Style line."""
        if not self.shadow_enabled:
            return "&H80000000"
        bgr = self.shadow_color[4:]  # extract BGR from &HAABBGGRR
        return f"&H{self._shadow_alpha_byte():02X}{bgr}"

    @property
    def primary_colour(self) -> str:
        """PrimaryColour for Style line (filled/highlighted color)."""
        if not self.highlight_enabled:
            return self.color
        if self.highlight_mode == "fill":
            return self.highlight_color  # golden for karaoke fill
        return self.dim_color  # gray for pulse mode

    @property
    def secondary_colour(self) -> str:
        """SecondaryColour for Style line (unfilled color in karaoke)."""
        return self.color  # white

    # ── ASS generation ──

    def to_style_line(self) -> str:
        """Generate ASS Style definition line."""
        shadow_depth = self.shadow_offset_x if (
            self.shadow_enabled and not self.has_asymmetric_shadow
        ) else 0
        return (
            f"Style: {self.style_name},{self.font},{self.size},"
            f"{self.primary_colour},{self.secondary_colour},"
            f"{self.border_color},{self._back_colour_hex()},"
            f"{'-1' if self.bold else '0'},{'-1' if self.italic else '0'},0,0,"
            f"100,100,{self.spacing:.0f},0,"
            f"1,{self.border_width:.0f},{shadow_depth:.0f},"
            f"{self.alignment},"
            f"{self.margin_l},{self.margin_r},{self.margin_v},1"
        )

    def shadow_tags(self) -> str:
        """Inline override tags for shadow (per Dialogue line, needed for asymmetric)."""
        if not self.shadow_enabled:
            return ""
        parts: list[str] = []
        if self.has_asymmetric_shadow:
            alpha_hex = f"&H{self._shadow_alpha_byte():02X}&"
            parts.append(f"\\4c{self.shadow_color}")
            parts.append(f"\\4a{alpha_hex}")
            parts.append(f"\\xshad{self.shadow_offset_x:.0f}")
            parts.append(f"\\yshad{self.shadow_offset_y:.0f}")
        if self.shadow_blur > 0:
            parts.append(f"\\be{self.shadow_blur:.0f}")
        return "{" + "".join(parts) + "}" if parts else ""

    def to_header(self) -> str:
        """Generate complete ASS header section."""
        return (
            "[Script Info]\n"
            "Title: Karaoke Subtitles\n"
            "ScriptType: v4.00+\n"
            "PlayResX: 1920\n"
            "PlayResY: 1080\n"
            "WrapStyle: 0\n"
            "ScaledBorderAndShadow: yes\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"{self.to_style_line()}\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )

    @classmethod
    def from_name(cls, name: str) -> "ASSSubtitleStyle":
        """Look up a preset style by name. Only 'default' is available."""
        if name in ("default", "yingshijf", "neon", "warm", "classic", "cyber", "ocean"):
            return cls()
        raise ValueError(f"Unknown style '{name}'. Available: default")


# ── Time formatting ──

def format_ass_time(seconds: float) -> str:
    """Convert seconds to ASS time format (H:MM:SS.cc)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"


def format_srt_time(seconds: float) -> str:
    """Convert seconds to SRT time format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"


# ── Text helpers ──

def is_cjk(char: str) -> bool:
    """Check if character is CJK (Chinese/Japanese/Korean)."""
    codepoint = ord(char)
    return (
        (0x4E00 <= codepoint <= 0x9FFF)
        or (0x3040 <= codepoint <= 0x309F)
        or (0x30A0 <= codepoint <= 0x30FF)
        or (0xAC00 <= codepoint <= 0xD7AF)
    )


_PUNCT = set('，。、！？；：\u201c\u201d\u2018\u2019《》【】（）,.!?;:\'"()[]{}·…—~ ')


def _is_punctuation(ch: str) -> bool:
    """Check if character is a punctuation mark."""
    return ch in _PUNCT


def _split_punctuation(text: str) -> tuple[list[str], str]:
    """Split text into core characters and trailing punctuation."""
    core: list[str] = []
    trail = ""
    for ch in text:
        if not _is_punctuation(ch):
            core.append(ch)
        elif core:
            trail += ch
    return core, trail


# ── Word grouping ──

def group_words_into_lines(
    words: List[Dict], max_chars_per_line: int = 12, min_pause: float = 0.5
) -> List[List[Dict]]:
    """Group words into subtitle lines based on timing and character count."""
    lines: list[list[Dict]] = []
    current_line: list[Dict] = []
    current_chars = 0

    for i, word in enumerate(words):
        word_text = word.get("text", "")
        if word_text and is_cjk(word_text[0]):
            word_len = len(word_text)
        else:
            word_len = 1

        has_pause = False
        if i > 0:
            prev_end = words[i - 1].get("end_time", word.get("start_time", 0))
            curr_start = word.get("start_time", prev_end)
            has_pause = (curr_start - prev_end) > min_pause

        if has_pause or (current_line and current_chars + word_len > max_chars_per_line):
            if current_line:
                lines.append(current_line)
            current_line = [word]
            current_chars = word_len
        else:
            current_line.append(word)
            current_chars += word_len

    if current_line:
        lines.append(current_line)

    return lines


# ── Tag builders ──

def build_kf_tags(words: List[Dict]) -> str:
    r"""Build karaoke fill tags (\kf) for smooth left-to-right fill effect.

    Text starts at SecondaryColour (white), fills to PrimaryColour (golden)
    as each character/syllable is spoken. Classic karaoke look.
    """
    tags: list[str] = []

    for word in words:
        text = word.get("text", "")
        start = word.get("start_time", 0)
        end = word.get("end_time", start)

        core_chars, trail_punct = _split_punctuation(text)

        if not core_chars:
            if tags and trail_punct:
                tags[-1] += trail_punct
            continue

        duration_cs = int((end - start) * 100)
        if duration_cs <= 0:
            duration_cs = 10

        if is_cjk(core_chars[0]):
            # Character-level karaoke for CJK
            char_cs = duration_cs // len(core_chars)
            for i, ch in enumerate(core_chars):
                suffix = trail_punct if i == len(core_chars) - 1 else ""
                tags.append(f"{{\\kf{char_cs}}}{ch}{suffix}")
        else:
            # Word-level karaoke for non-CJK
            core_text = "".join(core_chars)
            tags.append(f"{{\\kf{duration_cs}}}{core_text}{trail_punct}")

    return "".join(tags)


def build_pulse_tags(words: List[Dict], dialogue_start: float, style: ASSSubtitleStyle) -> str:
    r"""Build pulse-highlight tags using ASS \t() transitions.

    Each character lights up instantly when spoken and dims when done.
    Returns plain text if style.highlight_enabled is False.
    """
    if not style.highlight_enabled:
        return "".join(word.get("text", "") for word in words)

    highlight = style.highlight_color
    dim = style.dim_color
    scale = int(style.highlight_scale)

    tags: list[str] = []

    for word in words:
        text = word.get("text", "")
        start = word.get("start_time", 0)
        end = word.get("end_time", start)

        core_chars, trail_punct = _split_punctuation(text)

        if not core_chars:
            if tags and trail_punct:
                tags[-1] += trail_punct
            continue

        duration = end - start
        if duration <= 0:
            duration = 0.1

        if is_cjk(core_chars[0]):
            char_dur = duration / len(core_chars)
            for i, ch in enumerate(core_chars):
                suffix = trail_punct if i == len(core_chars) - 1 else ""
                cs = start + i * char_dur
                ce = start + (i + 1) * char_dur
                t_on = int((cs - dialogue_start) * 1000)
                t_off = int((ce - dialogue_start) * 1000)
                tags.append(
                    f"{{\\t({t_on},{t_on + 1},\\1c{highlight}\\fscx{scale}\\fscy{scale})"
                    f"\\t({t_off},{t_off + 1},\\1c{dim}\\fscx100\\fscy100)}}"
                    f"{ch}{suffix}"
                )
        else:
            t_on = int((start - dialogue_start) * 1000)
            t_off = int((end - dialogue_start) * 1000)
            core_text = "".join(core_chars)
            tags.append(
                f"{{\\t({t_on},{t_on + 1},\\1c{highlight}\\fscx{scale}\\fscy{scale})"
                f"\\t({t_off},{t_off + 1},\\1c{dim}\\fscx100\\fscy100)}}"
                f"{core_text}{trail_punct}"
            )

    return "".join(tags)


def build_highlight_tags(words: List[Dict], dialogue_start: float, style: ASSSubtitleStyle) -> str:
    """Build highlight tags based on style.highlight_mode."""
    if not style.highlight_enabled:
        return "".join(word.get("text", "") for word in words)
    if style.highlight_mode == "fill":
        return build_kf_tags(words)
    return build_pulse_tags(words, dialogue_start, style)


def build_srt_lines(words: List[Dict]) -> str:
    """Build subtitle text for SRT format."""
    return "".join(word.get("text", "") for word in words)


# ── File generators ──

def generate_srt(result_dict: Dict, output_path: str, words_per_line: int = 12):
    """Generate SRT subtitle file from ASR result dict.

    Supports both old format (segments) and new format (flat words list).
    """
    # Get words from either format
    if "words" in result_dict and "segments" not in result_dict:
        all_words = result_dict["words"]
    else:
        all_words = []
        for seg in result_dict.get("segments", []):
            all_words.extend(seg.get("words", []))

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    srt_lines: list[str] = []
    idx = 1

    for line in group_words_into_lines(all_words, max_chars_per_line=words_per_line):
        if not line:
            continue
        start = line[0].get("start_time", 0)
        end = line[-1].get("end_time", start)
        srt_lines.append(str(idx))
        srt_lines.append(f"{format_srt_time(start)} --> {format_srt_time(end)}")
        srt_lines.append(build_srt_lines(line))
        srt_lines.append("")
        idx += 1

    output.write_text("\n".join(srt_lines), encoding="utf-8")


def generate_ass_karaoke(
    result_dict: Dict,
    output_path: str,
    style: Union[str, ASSSubtitleStyle] = "default",
    max_chars_per_line: int = 12,
):
    """Generate ASS subtitle with karaoke effect.

    Supports both old format (segments) and new format (flat words list).
    """
    ass_style = ASSSubtitleStyle.from_name(style) if isinstance(style, str) else style

    # Get words from either format
    if "words" in result_dict and "segments" not in result_dict:
        all_words = result_dict["words"]
    else:
        all_words = []
        for seg in result_dict.get("segments", []):
            all_words.extend(seg.get("words", []))

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    lines = [ass_style.to_header()]
    shadow_prefix = ass_style.shadow_tags()

    for line in group_words_into_lines(all_words, max_chars_per_line=max_chars_per_line):
        if not line:
            continue
        start = line[0].get("start_time", 0)
        end = line[-1].get("end_time", start)
        text = shadow_prefix + build_highlight_tags(line, start, ass_style)
        lines.append(
                f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},"
                f"{ass_style.style_name},,0,0,0,,{text}"
            )

    output.write_text("\n".join(lines), encoding="utf-8")


def generate_ass_plain(
    result_dict: Dict,
    output_path: str,
    style: Union[str, ASSSubtitleStyle] = "classic",
    max_chars_per_line: int = 12,
):
    """Generate plain ASS subtitle without karaoke effects."""
    ass_style = ASSSubtitleStyle.from_name(style) if isinstance(style, str) else style
    ass_style = ASSSubtitleStyle(**{
        **ass_style.__dict__,
        "highlight_enabled": False,
    })

    # Get words from either format
    if "words" in result_dict and "segments" not in result_dict:
        all_words = result_dict["words"]
    else:
        all_words = []
        for seg in result_dict.get("segments", []):
            all_words.extend(seg.get("words", []))

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    lines = [ass_style.to_header()]
    shadow_prefix = ass_style.shadow_tags()

    for line in group_words_into_lines(all_words, max_chars_per_line=max_chars_per_line):
        if not line:
            continue
        start = line[0].get("start_time", 0)
        end = line[-1].get("end_time", start)
        text = shadow_prefix + build_srt_lines(line)
        lines.append(
            f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},"
            f"{ass_style.style_name},,0,0,0,,{text}"
        )

    output.write_text("\n".join(lines), encoding="utf-8")


def generate_all_formats(
    result_dict: Dict,
    output_dir: str,
    base_name: str = "subtitle",
    ass_style: Union[str, ASSSubtitleStyle] = "default",
    words_per_line: int = 12,
):
    """Generate all subtitle formats (SRT + ASS karaoke + ASS plain)."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    srt_path = out / f"{base_name}.srt"
    generate_srt(result_dict, str(srt_path), words_per_line=words_per_line)

    karaoke_path = out / f"{base_name}_karaoke.ass"
    generate_ass_karaoke(result_dict, str(karaoke_path), style=ass_style,
                         max_chars_per_line=words_per_line)

    plain_path = out / f"{base_name}_plain.ass"
    generate_ass_plain(result_dict, str(plain_path), style=ass_style,
                       max_chars_per_line=words_per_line)

    return {"srt": str(srt_path), "ass_karaoke": str(karaoke_path), "ass_plain": str(plain_path)}


# ── Pipeline-based render functions (accept SubtitleLine objects) ──

def render_srt_from_lines(lines, output_path: str):
    """Render list of SubtitleLine to SRT file.

    Args:
        lines: List of SubtitleLine (from pipeline)
        output_path: Output .srt file path
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    srt_lines = []
    idx = 1
    for line in lines:
        if not line.text:
            continue
        srt_lines.append(str(idx))
        srt_lines.append(f"{format_srt_time(line.start_time)} --> {format_srt_time(line.end_time)}")
        srt_lines.append(line.text)
        srt_lines.append("")
        idx += 1

    output.write_text("\n".join(srt_lines), encoding="utf-8")


def render_ass_from_lines(lines, output_path: str, style: ASSSubtitleStyle):
    """Render list of SubtitleLine to ASS file with karaoke effect.

    Args:
        lines: List of SubtitleLine (from pipeline)
        output_path: Output .ass file path
        style: ASSSubtitleStyle instance
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    ass_lines = [style.to_header()]
    shadow_prefix = style.shadow_tags()

    for line in lines:
        if not line.text:
            continue

        words = line.words
        if words:
            text = shadow_prefix + build_highlight_tags(words, line.start_time, style)
        else:
            # Words lost during fix, use plain text
            text = shadow_prefix + line.text

        ass_lines.append(
            f"Dialogue: 0,{format_ass_time(line.start_time)},{format_ass_time(line.end_time)},"
            f"{style.style_name},,0,0,0,,{text}"
        )

    output.write_text("\n".join(ass_lines), encoding="utf-8")


if __name__ == "__main__":
    sample = {
        "language": "Chinese",
        "text": "你好世界，这是一个测试。",
        "duration": 5.0,
        "segments": [{
            "text": "你好世界",
            "start_time": 0.0,
            "end_time": 2.0,
            "words": [
                {"text": "你", "start_time": 0.0, "end_time": 0.5},
                {"text": "好", "start_time": 0.5, "end_time": 1.0},
                {"text": "世", "start_time": 1.0, "end_time": 1.5},
                {"text": "界", "start_time": 1.5, "end_time": 2.0},
            ],
        }, {
            "text": "这是一个测试",
            "start_time": 2.5,
            "end_time": 5.0,
            "words": [
                {"text": "这", "start_time": 2.5, "end_time": 2.9},
                {"text": "是", "start_time": 2.9, "end_time": 3.2},
                {"text": "一", "start_time": 3.2, "end_time": 3.5},
                {"text": "个", "start_time": 3.5, "end_time": 3.8},
                {"text": "测", "start_time": 3.8, "end_time": 4.3},
                {"text": "试", "start_time": 4.3, "end_time": 5.0},
            ],
        }],
    }

    print("Generating sample subtitles...")
    import tempfile
    sample_dir = tempfile.mkdtemp(prefix='opc-subtitle-')
    paths = generate_all_formats(sample, sample_dir, base_name="sample")
    for name, path in paths.items():
        print(f"  {name}: {path}")
    print("Done.")
