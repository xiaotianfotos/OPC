"""
ASR Pipeline - Multi-stage subtitle generation pipeline.

Stage 1: ASR + Forced Alignment → flat word-level JSON (no segment grouping)
Stage 2: Sentence Breaking → two-pass: paragraphs by 。！？, then lines by max_chars
Stage 3: CSV Fix → apply multiple fix CSVs for text correction
Check:  Pre-render validation
Stage 4: Render → SRT and ASS output with style selection

Each stage saves intermediate JSON for debugging and resume support.
"""

import csv
import glob
import json
import os
from dataclasses import dataclass, field
from typing import Optional

from .qwen_asr_engine import asr_align, result_to_dict


# ── Data structures ──────────────────────────────────────────────

@dataclass
class Paragraph:
    """A sentence-level unit, bounded by 。！？ punctuation."""
    text: str
    start_time: float
    end_time: float
    words: list  # list of dicts {text, start_time, end_time}


@dataclass
class SubtitleLine:
    """A single subtitle line with timing and word-level data."""
    text: str
    start_time: float
    end_time: float
    words: list = field(default_factory=list)
    pause_after: float = 0.0  # pause before next line (seconds)


@dataclass
class CheckError:
    """A single check failure."""
    line_idx: int
    checker: str
    message: str
    fix_command: str = ""


# ── Shared constants & helpers ───────────────────────────────────

_PUNCT = set('，。、！？；：\u201c\u201d\u2018\u2019《》【】（）,.!?;:\'"()[]{}·…—~ ')
_SENTENCE_END = set('。！？!?')
_COMMA = set('，,;；：:')


def _word_cjk_len(word_text: str) -> float:
    """Count meaningful characters in a word.

    Same counting method as _line_cjk_count:
    - CJK char = 1
    - Non-CJK, non-punct char = 0.5 (each letter)
    - Punctuation = 0
    """
    count = 0
    for ch in word_text:
        cp = ord(ch)
        is_cjk = (
            (0x4E00 <= cp <= 0x9FFF)
            or (0x3040 <= cp <= 0x309F)
            or (0x30A0 <= cp <= 0x30FF)
            or (0xAC00 <= cp <= 0xD7AF)
        )
        if is_cjk:
            count += 1
        elif ch not in _PUNCT and ch != ' ':
            count += 0.5
    return count


def _word_ends_with(word_text: str, char_set: set) -> bool:
    """Check if word text ends with a character from char_set."""
    for ch in reversed(word_text):
        if ch in char_set:
            return True
        if ch not in _PUNCT:
            break
    return False


def _text_of_words(words: list) -> str:
    """Concatenate word texts."""
    return "".join(w.get("text", "") for w in words)


def _line_cjk_count(text: str):
    """Count CJK chars + non-CJK word units in a text string."""
    count = 0
    for ch in text:
        cp = ord(ch)
        is_cjk = (
            (0x4E00 <= cp <= 0x9FFF)
            or (0x3040 <= cp <= 0x309F)
            or (0x30A0 <= cp <= 0x30FF)
            or (0xAC00 <= cp <= 0xD7AF)
        )
        if is_cjk:
            count += 1
        elif ch not in _PUNCT and ch != ' ':
            count += 0.5
    return count


# ── Stage 1: ASR + Forced Alignment ──────────────────────────────

def stage1_asr(audio_path: str, output_dir: str, language=None, model_size="1.7B") -> dict:
    """Stage 1: Run ASR with forced alignment, save flat word-level JSON.

    Returns dict with 'text', 'language', 'duration', 'words' (flat list).
    No segment grouping.
    """
    print("[Stage 1] ASR + Forced Alignment...")
    result = asr_align(audio_path, language=language, model_size=model_size)
    result_dict = result_to_dict(result)
    result_dict["source"] = os.path.basename(audio_path)

    raw_path = os.path.join(output_dir, _raw_json_name(audio_path))
    os.makedirs(output_dir, exist_ok=True)
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {raw_path} ({len(result_dict.get('words', []))} words)")
    return result_dict


# ── Stage 2: Sentence Breaking (two-pass) ────────────────────────

def stage2_break(result_dict: dict, output_dir: str, audio_path: str,
                 max_chars: int = 14) -> list:
    """Stage 2: Text-first sentence breaking.

    Pass 1: Split flat words into paragraphs by sentence-end punctuation (。！？)
    Pass 2: Within each paragraph, break into subtitle lines by max_chars

    Returns list of SubtitleLine.
    """
    print(f"[Stage 2] Sentence Breaking (max_chars={max_chars})...")

    words = result_dict.get("words", [])
    if not words:
        print("  No words found, skipping.")
        return []

    # Pass 1: Build paragraphs
    paragraphs = _build_paragraphs(words)
    print(f"  Pass 1: {len(paragraphs)} paragraphs")

    # Pass 2: Break paragraphs into lines
    all_lines = []
    for para in paragraphs:
        para_lines = _break_paragraph(para, max_chars)
        all_lines.extend(para_lines)

    # Compute pause_after for each line
    for i in range(len(all_lines) - 1):
        gap = all_lines[i + 1].start_time - all_lines[i].end_time
        all_lines[i].pause_after = max(0, gap)

    # Save intermediate
    lines_path = os.path.join(output_dir, _lines_json_name(audio_path))
    _save_lines(all_lines, lines_path)
    print(f"  Pass 2: {len(all_lines)} lines, saved: {lines_path}")
    return all_lines


def _build_paragraphs(words: list) -> list:
    """Pass 1: Split words into paragraphs at sentence-end punctuation.

    A paragraph ends when a word contains 。！？ or similar.
    The punctuation stays with the paragraph that contains it.
    """
    paragraphs = []
    current = []

    for word in words:
        current.append(word)
        if _word_ends_with(word.get("text", ""), _SENTENCE_END):
            # Emit paragraph
            text = _text_of_words(current)
            start = current[0].get("start_time", 0)
            end = current[-1].get("end_time", start)
            paragraphs.append(Paragraph(
                text=text, start_time=start, end_time=end,
                words=[dict(w) for w in current],
            ))
            current = []

    # Flush remaining words (no sentence-end punctuation at the end)
    if current:
        text = _text_of_words(current)
        start = current[0].get("start_time", 0)
        end = current[-1].get("end_time", start)
        paragraphs.append(Paragraph(
            text=text, start_time=start, end_time=end,
            words=[dict(w) for w in current],
        ))

    return paragraphs


def _break_paragraph(para: Paragraph, max_chars: int) -> list:
    """Pass 2: Break paragraph into subtitle lines at punctuation.

    Rule: break at every comma/semicolon/colon (，,;；：:).
    For over-length segments without punctuation, use time-gap algorithm.
    """
    words = para.words
    if not words:
        return []

    # Break at every comma/semicolon/colon first
    segments = []
    current_words = []

    for word in words:
        word_text = word.get("text", "")
        current_words.append(word)

        if _word_ends_with(word_text, _COMMA):
            segments.append(list(current_words))
            current_words = []

    # Flush remaining
    if current_words:
        segments.append(list(current_words))

    # Process each segment: if too long, use smart splitting
    lines = []
    for seg_words in segments:
        seg_len = sum(_word_cjk_len(w.get("text", "")) for w in seg_words)
        if seg_len <= max_chars:
            _emit_line(lines, seg_words)
        else:
            # Use smart algorithm to split long segment
            sub_lines = _smart_split(seg_words, max_chars)
            lines.extend(sub_lines)

    return lines


def _smart_split(words: list, max_chars: int) -> list:
    """Smart splitting for over-length segments using time gaps.

    Algorithm:
    1. Find all "valid split points" where both sides <= max_chars
    2. Among valid points, pick the one with largest time gap
    3. Recursively apply to left and right parts
    """
    if not words:
        return []

    total_len = sum(_word_cjk_len(w.get("text", "")) for w in words)
    if total_len <= max_chars:
        line = _words_to_line(words)
        return [line] if line else []

    # Find all valid split points
    valid_points = _find_valid_split_points(words, max_chars)

    if not valid_points:
        # No valid point found, force split at largest gap in middle region
        split_idx = _find_best_force_split(words, max_chars)
        if split_idx <= 0 or split_idx >= len(words):
            line = _words_to_line(words)
            return [line] if line else []

        left_words = words[:split_idx]
        right_words = words[split_idx:]
        left_lines = _smart_split(left_words, max_chars)
        right_lines = _smart_split(right_words, max_chars)
        return left_lines + right_lines

    # Pick the valid point with largest time gap
    best_idx = max(valid_points, key=lambda i: _get_time_gap(words, i))

    left_words = words[:best_idx]
    right_words = words[best_idx:]
    left_lines = _smart_split(left_words, max_chars)
    right_lines = _smart_split(right_words, max_chars)
    return left_lines + right_lines


def _find_valid_split_points(words: list, max_chars: int) -> list:
    """Find all word indices where splitting would make both sides <= max_chars."""
    valid = []
    cum_len = []

    # Build cumulative lengths
    total = 0
    for w in words:
        total += _word_cjk_len(w.get("text", ""))
        cum_len.append(total)

    # Find valid split points
    for i in range(1, len(words)):
        left_len = cum_len[i-1]
        right_len = total - left_len
        if left_len <= max_chars and right_len <= max_chars:
            valid.append(i)

    return valid


def _get_time_gap(words: list, split_idx: int) -> float:
    """Get the time gap between words at split point."""
    if split_idx <= 0 or split_idx >= len(words):
        return 0.0
    prev_end = words[split_idx - 1].get("end_time", 0)
    curr_start = words[split_idx].get("start_time", 0)
    return curr_start - prev_end


def _find_best_force_split(words: list, max_chars: int) -> int:
    """Find best split point when no valid point exists.

    Strategy: In the middle region (40%-60% of total length),
    find the point with largest time gap.
    """
    if len(words) < 2:
        return 0

    # Calculate total length and find middle region
    total_len = sum(_word_cjk_len(w.get("text", "")) for w in words)
    target_left = total_len * 0.4
    target_right = total_len * 0.6

    cum_len = 0
    start_idx = end_idx = 0

    for i, w in enumerate(words):
        cum_len += _word_cjk_len(w.get("text", ""))
        if cum_len >= target_left and start_idx == 0:
            start_idx = i + 1
        if cum_len >= target_right:
            end_idx = i + 1
            break

    if end_idx == 0:
        end_idx = len(words) // 2
    if start_idx == 0:
        start_idx = len(words) // 2 - 2

    # Find largest gap in middle region
    best_idx = start_idx
    best_gap = 0
    for i in range(start_idx, min(end_idx + 1, len(words))):
        gap = _get_time_gap(words, i)
        if gap > best_gap:
            best_gap = gap
            best_idx = i

    return best_idx


def _words_to_line(words: list) -> Optional[SubtitleLine]:
    """Convert a list of words to SubtitleLine."""
    if not words:
        return None
    text = _text_of_words(words)
    start = words[0].get("start_time", 0)
    end = words[-1].get("end_time", start)
    return SubtitleLine(
        text=text,
        start_time=start,
        end_time=end,
        words=[dict(w) for w in words],
    )


def _emit_line(lines: list, words: list):
    """Create a SubtitleLine from words and append to lines list."""
    if not words:
        return
    text = _text_of_words(words)
    start = words[0].get("start_time", 0)
    end = words[-1].get("end_time", start)
    lines.append(SubtitleLine(
        text=text,
        start_time=start,
        end_time=end,
        words=[dict(w) for w in words],
    ))


# ── Stage 3: CSV Fix ─────────────────────────────────────────────

def stage3_fix(lines: list, fix_dir: str) -> list:
    """Stage 3: Apply multiple fix CSVs (fix_1.csv, fix_2.csv, ...) sequentially."""
    print(f"[Stage 3] Applying CSV fixes from {fix_dir}...")

    if not os.path.isdir(fix_dir):
        print(f"  Fix directory not found: {fix_dir}, skipping.")
        return lines

    csv_files = sorted(glob.glob(os.path.join(fix_dir, "fix_*.csv")))
    if not csv_files:
        print("  No fix_*.csv files found, skipping.")
        return lines

    total_replacements = 0
    total_deletions = 0

    for csv_file in csv_files:
        fixes = _load_csv(csv_file)
        print(f"  Applying {os.path.basename(csv_file)} ({len(fixes)} rules)...")

        for line in lines:
            original = line.text
            for orig, repl in fixes.items():
                if orig in line.text:
                    if repl == "":
                        line.text = ""
                        line.words = []
                        total_deletions += 1
                        break
                    else:
                        line.text = line.text.replace(orig, repl)
                        for w in line.words:
                            if orig in w.get("text", ""):
                                w["text"] = w["text"].replace(orig, repl)

            if line.text != original and line.text:
                total_replacements += 1

    before = len(lines)
    lines = [l for l in lines if l.text]
    after = len(lines)
    print(f"  Replacements: {total_replacements}, Deletions: {total_deletions} "
          f"({before} → {after} lines)")
    return lines


def _load_csv(csv_path: str) -> dict:
    """Load a fix CSV file. Returns {original: replacement}."""
    fixes = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2:
                original = row[0].strip()
                new_text = row[1].strip() if len(row) > 1 else ""
                if original and not original.startswith("#"):
                    fixes[original] = new_text
    return fixes


# ── Check ────────────────────────────────────────────────────────

def check_max_chars(lines: list, max_chars: int = 14) -> list:
    """Check that no line exceeds max_chars CJK characters."""
    errors = []
    for idx, line in enumerate(lines):
        if not line.text:
            continue
        char_count = _line_cjk_count(line.text)
        if char_count > max_chars:
            mid = _find_split_point(line.text, max_chars)
            fix = f"xt asr-split <lines.json> --line {idx + 1} --after \"...\""
            errors.append(CheckError(
                line_idx=idx + 1, checker="max_chars",
                message=f"Line {idx + 1} has {char_count} chars (max {max_chars}): \"{line.text}\"",
                fix_command=fix,
            ))
    return errors


def _find_split_point(text: str, max_chars: int) -> int:
    """Find the best character position to split text."""
    char_pos = 0
    best_pos = max_chars
    best_score = 999

    for i, ch in enumerate(text):
        cp = ord(ch)
        is_cjk = (
            (0x4E00 <= cp <= 0x9FFF) or (0x3040 <= cp <= 0x309F)
            or (0x30A0 <= cp <= 0x30FF) or (0xAC00 <= cp <= 0xD7AF)
        )
        if is_cjk:
            char_pos += 1
        elif ch not in _PUNCT and ch != ' ':
            char_pos += 0.5

        distance = abs(char_pos - max_chars)
        is_soft_break = ch in _COMMA or ch == ' '
        score = distance - (0.5 if is_soft_break else 0)

        if char_pos >= max_chars * 0.6 and score < best_score:
            best_score = score
            best_pos = i + 1
        if char_pos > max_chars * 1.2:
            break
    return best_pos


def stage_check(lines: list, max_chars: int = 14) -> list:
    """Run all checkers. Returns list of CheckError (empty = pass)."""
    print(f"[Check] Running pre-render checks (max_chars={max_chars})...")
    errors = check_max_chars(lines, max_chars)

    if errors:
        print(f"  FAILED: {len(errors)} issue(s) found")
        for err in errors:
            print(f"  ✗ [{err.checker}] {err.message}")
            if err.fix_command:
                print(f"    Fix: {err.fix_command}")
    else:
        print("  PASSED: All checks OK")
    return errors


# ── Pre-render cleanup ────────────────────────────────────────────

_TRILING_STRIP = set('，。、,.')


def _strip_trailing_punct(lines: list):
    """Remove trailing commas and periods from each subtitle line."""
    for line in lines:
        if not line.text:
            continue
        stripped = line.text.rstrip()
        while stripped and stripped[-1] in _TRILING_STRIP:
            stripped = stripped[:-1].rstrip()
        if stripped != line.text:
            line.text = stripped
            # Also strip from the last word
            if line.words:
                last_w = line.words[-1]
                wtext = last_w.get("text", "")
                while wtext and wtext[-1] in _TRILING_STRIP:
                    wtext = wtext[:-1]
                last_w["text"] = wtext


# ── Line Split ───────────────────────────────────────────────────

def split_line_after(lines: list, line_idx: int, after_text: str) -> list:
    """Split a line after the matched text.

    Finds `after_text` in the line's word stream and breaks after it.
    Raises ValueError if text not found or found multiple times.
    """
    if line_idx < 1 or line_idx > len(lines):
        raise ValueError(f"Line index {line_idx} out of range (1-{len(lines)})")

    target = lines[line_idx - 1]
    words = target.words
    if not words:
        raise ValueError(f"Line {line_idx} has no word-level data, cannot split")

    # Find after_text in concatenated word text
    full_text = _text_of_words(words)
    count = full_text.count(after_text)
    if count == 0:
        raise ValueError(f"Text \"{after_text}\" not found in line {line_idx}")
    if count > 1:
        raise ValueError(f"Text \"{after_text}\" found {count} times in line {line_idx}, must be unique")

    pos = full_text.index(after_text)
    end_pos = pos + len(after_text)

    # Find which words cover [0, end_pos)
    cum = 0
    split_word = None
    for i, w in enumerate(words):
        word_text = w.get("text", "")
        word_start = cum
        word_end = cum + len(word_text)
        cum = word_end

        if word_end <= end_pos:
            continue
        if word_start >= end_pos:
            split_word = i
            break
        # end_pos falls inside this word — split the word itself
        if word_start < end_pos < word_end:
            split_offset = end_pos - word_start
            left_text = word_text[:split_offset]
            right_text = word_text[split_offset:]
            # Keep timing on both halves
            words[i] = dict(w)
            words[i]["text"] = left_text
            right_word = dict(w)
            right_word["text"] = right_text
            words.insert(i + 1, right_word)
            split_word = i + 1
            break

    if split_word is None:
        # after_text covers the entire line tail — no split needed
        return lines

    if split_word == 0:
        raise ValueError(f"Split point is at the start of the line, cannot split")

    # Build two new lines
    before_words = words[:split_word]
    after_words = words[split_word:]

    new_lines = []
    if before_words:
        new_lines.append(SubtitleLine(
            text=_text_of_words(before_words),
            start_time=before_words[0].get("start_time", target.start_time),
            end_time=before_words[-1].get("end_time", target.end_time),
            words=[dict(w) for w in before_words],
        ))
    if after_words:
        new_lines.append(SubtitleLine(
            text=_text_of_words(after_words),
            start_time=after_words[0].get("start_time", target.start_time),
            end_time=after_words[-1].get("end_time", target.end_time),
            words=[dict(w) for w in after_words],
        ))

    return lines[:line_idx - 1] + new_lines + lines[line_idx:]


# ── Stage 4: Render ──────────────────────────────────────────────

def stage4_render(lines: list, output_dir: str, audio_path: str,
                  fmt: str = "srt", ass_style="default"):
    """Stage 4: Render SubtitleLines to SRT and/or ASS files."""
    from .subtitle_gen import (
        render_srt_from_lines, render_ass_from_lines,
        ASSSubtitleStyle,
    )

    base = os.path.splitext(os.path.basename(audio_path))[0]
    os.makedirs(output_dir, exist_ok=True)
    paths = {}

    if fmt in ("srt", "all"):
        srt_path = os.path.join(output_dir, f"{base}.srt")
        render_srt_from_lines(lines, srt_path)
        paths["srt"] = srt_path
        print(f"  SRT: {srt_path}")

    if fmt in ("ass", "all"):
        ass_path = os.path.join(output_dir, f"{base}.ass")
        style = ASSSubtitleStyle.from_name(ass_style)
        render_ass_from_lines(lines, ass_path, style)
        paths["ass"] = ass_path
        print(f"  ASS: {ass_path}")

    return paths


# ── Pipeline Orchestrator ─────────────────────────────────────────

def run_pipeline(
    audio_path: str,
    output_dir: Optional[str] = None,
    fmt: str = "srt",
    ass_style: str = "default",
    fix_dir: Optional[str] = None,
    language=None,
    model_size: str = "1.7B",
    max_chars: int = 14,
    resume_from: Optional[str] = None,
):
    """Run the full ASR subtitle generation pipeline."""
    audio_path = os.path.abspath(audio_path)
    if output_dir is None:
        output_dir = os.path.dirname(audio_path)
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    all_stages = ["asr", "break", "fix", "render"]
    start_idx = 0
    if resume_from:
        if resume_from in all_stages:
            start_idx = all_stages.index(resume_from)
        else:
            print(f"Warning: Unknown resume stage '{resume_from}', starting from beginning.")

    # Stage 1: ASR + Align
    if start_idx <= 0:
        result_dict = stage1_asr(audio_path, output_dir, language, model_size)
    else:
        raw_path = os.path.join(output_dir, _raw_json_name(audio_path))
        print(f"[Stage 1] Skipping, loading: {raw_path}")
        with open(raw_path, "r", encoding="utf-8") as f:
            result_dict = json.load(f)

    # Stage 2: Sentence Breaking
    if start_idx <= 1:
        lines = stage2_break(result_dict, output_dir, audio_path, max_chars)
    else:
        lines_path = os.path.join(output_dir, _lines_json_name(audio_path))
        print(f"[Stage 2] Skipping, loading: {lines_path}")
        lines = _load_lines(lines_path)

    # Stage 3: CSV Fix
    if fix_dir and start_idx <= 2:
        lines = stage3_fix(lines, fix_dir)
        lines_path = os.path.join(output_dir, _lines_json_name(audio_path))
        _save_lines(lines, lines_path)
    elif fix_dir and start_idx > 2:
        lines_path = os.path.join(output_dir, _lines_json_name(audio_path))
        print(f"[Stage 3] Skipping, loading: {lines_path}")
        lines = _load_lines(lines_path)
    else:
        print("[Stage 3] No fix directory specified, skipping.")

    # Check
    errors = stage_check(lines, max_chars)
    if errors:
        print(f"\n[BLOCKED] Fix {len(errors)} issue(s) before rendering.")
        print("Use 'xt asr-split' to split long lines, then re-run with --resume-from render")
        return {"check_errors": errors, "lines_path": os.path.join(output_dir, _lines_json_name(audio_path))}

    # Pre-render: strip trailing punctuation from each line
    _strip_trailing_punct(lines)

    # Stage 4: Render
    paths = stage4_render(lines, output_dir, audio_path, fmt, ass_style)
    print(f"[Done] Pipeline complete.")
    return paths


# ── Persistence helpers ───────────────────────────────────────────

def _raw_json_name(audio_path: str) -> str:
    base = os.path.splitext(os.path.basename(audio_path))[0]
    return f"{base}.raw.json"


def _lines_json_name(audio_path: str) -> str:
    base = os.path.splitext(os.path.basename(audio_path))[0]
    return f"{base}.lines.json"


def _save_lines(lines: list, path: str):
    data = [_line_to_dict(l) for l in lines]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_lines(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [SubtitleLine(**d) for d in data]


def _line_to_dict(line: SubtitleLine) -> dict:
    return {
        "text": line.text,
        "start_time": line.start_time,
        "end_time": line.end_time,
        "words": line.words,
        "pause_after": line.pause_after,
    }
