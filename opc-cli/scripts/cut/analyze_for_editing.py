#!/usr/bin/env python3
# coding=utf-8
"""
ASR Result Analyzer for Podcast/Video Editing

Analyzes the JSON output from asr_align_pipeline.py and provides
editing suggestions like cut points, filler words, and pacing analysis.

Usage:
    python analyze_for_editing.py <input_json> [--output <output_json>]

Example:
    python analyze_for_editing.py 0131.json --output 0131_analysis.json
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class CutSuggestion:
    """Suggested cut point for editing."""
    start_time: float
    end_time: float
    reason: str
    confidence: str  # "high", "medium", "low"


@dataclass
class FillerWord:
    """Filler word detection."""
    text: str
    start_time: float
    end_time: float
    context: str


@dataclass
class PaceSegment:
    """Segment with speaking pace information."""
    start_time: float
    end_time: float
    text: str
    word_count: int
    duration: float
    wpm: float
    pace_category: str  # "slow", "normal", "fast"


@dataclass
class EditingAnalysis:
    """Complete editing analysis."""
    # Basic stats
    total_duration: float
    total_words: int
    overall_wpm: float

    # Cut suggestions
    cut_suggestions: List[CutSuggestion] = field(default_factory=list)

    # Filler words
    filler_words: List[FillerWord] = field(default_factory=list)
    filler_word_count: int = 0

    # Pacing
    pace_segments: List[PaceSegment] = field(default_factory=list)
    slow_segments: List[PaceSegment] = field(default_factory=list)
    fast_segments: List[PaceSegment] = field(default_factory=list)

    # Sentence boundaries
    sentence_boundaries: List[Tuple[float, float, str]] = field(default_factory=list)

    # Long pauses (potential edit points)
    long_pauses: List[Dict] = field(default_factory=list)


def load_asr_result(json_path: str) -> Dict:
    """Load ASR result from JSON file."""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def detect_filler_words(words: List[Dict], language: str) -> List[FillerWord]:
    """Detect filler words in the transcript."""
    fillers = []

    # Chinese filler words
    chinese_fillers = {"嗯", "啊", "呃", "那个", "这个", "就是", "然后", "所以", "对吧", "是吧", "嗯嗯", "啊啊"}
    # English filler words
    english_fillers = {"um", "uh", "like", "you know", "so", "well", "actually", "basically", "literally"}

    filler_set = chinese_fillers if language == "Chinese" else english_fillers

    for i, word in enumerate(words):
        word_text = word["text"].lower().strip()

        if word_text in filler_set:
            # Get context (3 words before and after)
            context_start = max(0, i - 3)
            context_end = min(len(words), i + 4)
            context = "".join([w["text"] for w in words[context_start:context_end]])

            fillers.append(FillerWord(
                text=word["text"],
                start_time=word["start_time"],
                end_time=word["end_time"],
                context=context,
            ))

    return fillers


def analyze_pacing(words: List[Dict], window_seconds: float = 10.0) -> List[PaceSegment]:
    """Analyze speaking pace in windows."""
    if not words:
        return []

    segments = []
    start_time = words[0]["start_time"]
    end_time = words[-1]["end_time"]

    current_time = start_time
    while current_time < end_time:
        window_end = current_time + window_seconds

        # Get words in this window
        window_words = [
            w for w in words
            if current_time <= w["start_time"] < window_end
        ]

        if window_words:
            word_count = len(window_words)
            duration = window_words[-1]["end_time"] - window_words[0]["start_time"]
            wpm = (word_count / duration) * 60 if duration > 0 else 0

            # Categorize pace
            # Chinese: ~200-250 WPM is normal
            # English: ~130-160 WPM is normal
            if wpm < 150:
                pace_category = "slow"
            elif wpm > 280:
                pace_category = "fast"
            else:
                pace_category = "normal"

            text = "".join([w["text"] for w in window_words])

            segments.append(PaceSegment(
                start_time=window_words[0]["start_time"],
                end_time=window_words[-1]["end_time"],
                text=text[:50] + "..." if len(text) > 50 else text,
                word_count=word_count,
                duration=duration,
                wpm=wpm,
                pace_category=pace_category,
            ))

        current_time += window_seconds / 2  # 50% overlap

    return segments


def find_sentence_boundaries(words: List[Dict], language: str) -> List[Tuple[float, float, str]]:
    """Find sentence boundaries based on punctuation."""
    boundaries = []

    # Punctuation marks that end sentences
    if language == "Chinese":
        end_marks = {"。", "？", "！", "；", "…"}
    else:
        end_marks = {".", "?", "!", ";"}

    current_sentence = []
    sentence_start = None

    for word in words:
        if sentence_start is None:
            sentence_start = word["start_time"]

        current_sentence.append(word["text"])

        if any(mark in word["text"] for mark in end_marks):
            sentence_end = word["end_time"]
            sentence_text = "".join(current_sentence)
            boundaries.append((sentence_start, sentence_end, sentence_text))

            current_sentence = []
            sentence_start = None

    # Handle last sentence if no ending punctuation
    if current_sentence and sentence_start is not None:
        sentence_text = "".join(current_sentence)
        boundaries.append((
            sentence_start,
            words[-1]["end_time"],
            sentence_text,
        ))

    return boundaries


def generate_cut_suggestions(
    words: List[Dict],
    long_pauses: List[Dict],
    filler_words: List[FillerWord],
    sentence_boundaries: List[Tuple[float, float, str]],
    language: str,
) -> List[CutSuggestion]:
    """Generate editing cut suggestions."""
    suggestions = []

    # 1. Long pauses are good cut points
    for pause in long_pauses:
        if pause["duration"] > 1.5:  # Very long pause
            suggestions.append(CutSuggestion(
                start_time=pause["start"],
                end_time=pause["end"],
                reason=f"长停顿 ({pause['duration']:.1f}s) - 适合剪辑",
                confidence="high",
            ))

    # 2. Filler words can be removed
    for filler in filler_words[:10]:  # Limit to first 10
        suggestions.append(CutSuggestion(
            start_time=filler.start_time - 0.1,
            end_time=filler.end_time + 0.1,
            reason=f"填充词 '{filler.text}' - 可考虑删除",
            confidence="medium",
        ))

    # 3. Sentence boundaries after long pauses
    for i, (start, end, text) in enumerate(sentence_boundaries):
        if i < len(sentence_boundaries) - 1:
            next_start = sentence_boundaries[i + 1][0]
            gap = next_start - end

            if gap > 0.8:  # Significant pause between sentences
                suggestions.append(CutSuggestion(
                    start_time=end,
                    end_time=next_start,
                    reason=f"句子间停顿 ({gap:.1f}s)",
                    confidence="high" if gap > 1.2 else "medium",
                ))

    # Sort by start time
    suggestions.sort(key=lambda x: x.start_time)

    return suggestions


def analyze_for_editing(asr_data: Dict) -> EditingAnalysis:
    """Perform complete editing analysis."""
    asr_result = asr_data.get("asr_result", {})
    words = []

    if asr_result.get("segments"):
        words = asr_result["segments"][0].get("words", [])

    language = asr_result.get("language", "Chinese")
    duration = asr_result.get("duration", 0)

    # Basic stats
    total_words = len(words)
    overall_wpm = (total_words / duration) * 60 if duration > 0 else 0

    # Detect filler words
    filler_words = detect_filler_words(words, language)

    # Analyze pacing
    pace_segments = analyze_pacing(words)
    slow_segments = [s for s in pace_segments if s.pace_category == "slow"]
    fast_segments = [s for s in pace_segments if s.pace_category == "fast"]

    # Find sentence boundaries
    sentence_boundaries = find_sentence_boundaries(words, language)

    # Get long pauses from original analysis
    editing_analysis = asr_data.get("editing_analysis", {})
    long_pauses = editing_analysis.get("long_pauses", [])

    # Generate cut suggestions
    cut_suggestions = generate_cut_suggestions(
        words, long_pauses, filler_words, sentence_boundaries, language
    )

    return EditingAnalysis(
        total_duration=duration,
        total_words=total_words,
        overall_wpm=overall_wpm,
        cut_suggestions=cut_suggestions,
        filler_words=filler_words,
        filler_word_count=len(filler_words),
        pace_segments=pace_segments,
        slow_segments=slow_segments,
        fast_segments=fast_segments,
        sentence_boundaries=sentence_boundaries,
        long_pauses=long_pauses,
    )


def format_time(seconds: float) -> str:
    """Format seconds to MM:SS.ms"""
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes:02d}:{secs:05.2f}"


def analysis_to_dict(analysis: EditingAnalysis) -> Dict:
    """Convert analysis to dictionary for JSON serialization."""
    return {
        "basic_stats": {
            "total_duration_seconds": analysis.total_duration,
            "total_duration_formatted": format_time(analysis.total_duration),
            "total_words": analysis.total_words,
            "overall_wpm": round(analysis.overall_wpm, 1),
        },
        "filler_words": {
            "count": analysis.filler_word_count,
            "items": [
                {
                    "text": fw.text,
                    "time": f"{format_time(fw.start_time)} - {format_time(fw.end_time)}",
                    "start_time": fw.start_time,
                    "end_time": fw.end_time,
                    "context": fw.context,
                }
                for fw in analysis.filler_words[:20]  # Limit output
            ],
        },
        "pacing": {
            "slow_segments": [
                {
                    "time": f"{format_time(s.start_time)} - {format_time(s.end_time)}",
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "wpm": round(s.wpm, 1),
                    "text": s.text,
                }
                for s in analysis.slow_segments[:10]
            ],
            "fast_segments": [
                {
                    "time": f"{format_time(s.start_time)} - {format_time(s.end_time)}",
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "wpm": round(s.wpm, 1),
                    "text": s.text,
                }
                for s in analysis.fast_segments[:10]
            ],
        },
        "cut_suggestions": [
            {
                "time": f"{format_time(cs.start_time)} - {format_time(cs.end_time)}",
                "start_time": cs.start_time,
                "end_time": cs.end_time,
                "duration": round(cs.end_time - cs.start_time, 2),
                "reason": cs.reason,
                "confidence": cs.confidence,
            }
            for cs in analysis.cut_suggestions[:30]  # Limit output
        ],
        "sentence_boundaries": [
            {
                "time": f"{format_time(start)} - {format_time(end)}",
                "start_time": start,
                "end_time": end,
                "text": text[:80] + "..." if len(text) > 80 else text,
            }
            for start, end, text in analysis.sentence_boundaries[:50]
        ],
        "long_pauses": [
            {
                "time": f"{format_time(p['start'])} - {format_time(p['end'])}",
                "start_time": p["start"],
                "end_time": p["end"],
                "duration": p["duration"],
            }
            for p in analysis.long_pauses[:20]
        ],
    }


def print_analysis_report(analysis: EditingAnalysis):
    """Print a human-readable analysis report."""
    print("\n" + "=" * 70)
    print("口播剪辑分析报告")
    print("=" * 70)

    # Basic stats
    print(f"\n【基本信息】")
    print(f"  总时长: {format_time(analysis.total_duration)}")
    print(f"  总词数: {analysis.total_words}")
    print(f"  平均语速: {analysis.overall_wpm:.1f} 词/分钟")

    # Filler words
    print(f"\n【填充词检测】")
    print(f"  检测到 {analysis.filler_word_count} 个填充词")
    if analysis.filler_words:
        print("  前10个填充词:")
        for fw in analysis.filler_words[:10]:
            print(f"    {format_time(fw.start_time)} '{fw.text}' - {fw.context[:30]}...")

    # Pacing
    print(f"\n【语速分析】")
    print(f"  慢速片段: {len(analysis.slow_segments)} 个")
    print(f"  快速片段: {len(analysis.fast_segments)} 个")

    if analysis.slow_segments:
        print("  慢速片段示例:")
        for s in analysis.slow_segments[:3]:
            print(f"    {format_time(s.start_time)} WPM:{s.wpm:.1f} - {s.text[:40]}...")

    # Cut suggestions
    print(f"\n【剪辑建议】")
    print(f"  共 {len(analysis.cut_suggestions)} 个建议剪辑点")

    high_confidence = [c for c in analysis.cut_suggestions if c.confidence == "high"]
    print(f"  高置信度建议: {len(high_confidence)} 个")

    print("\n  前15个剪辑建议:")
    for i, cs in enumerate(analysis.cut_suggestions[:15], 1):
        duration = cs.end_time - cs.start_time
        print(f"    {i}. {format_time(cs.start_time)} [{duration:.1f}s] {cs.reason}")

    # Long pauses
    print(f"\n【长停顿点】")
    print(f"  检测到 {len(analysis.long_pauses)} 个长停顿 (>1s)")
    for p in analysis.long_pauses[:5]:
        print(f"    {format_time(p['start'])} - {format_time(p['end'])} ({p['duration']:.1f}s)")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="ASR Result Analyzer for Podcast/Video Editing"
    )
    parser.add_argument("input_json", help="Path to ASR result JSON file")
    parser.add_argument(
        "--output", "-o",
        help="Output JSON file path (default: <input>_analysis.json)"
    )
    parser.add_argument(
        "--report", "-r",
        action="store_true",
        help="Print human-readable report to console"
    )

    args = parser.parse_args()

    # Validate input
    if not os.path.exists(args.input_json):
        print(f"Error: Input file not found: {args.input_json}")
        sys.exit(1)

    # Determine output path
    output_path = args.output
    if not output_path:
        base = Path(args.input_json).stem
        output_path = f"{base}_analysis.json"

    # Load and analyze
    print(f"Loading ASR result: {args.input_json}")
    asr_data = load_asr_result(args.input_json)

    print("Analyzing for editing...")
    analysis = analyze_for_editing(asr_data)

    # Print report if requested
    if args.report:
        print_analysis_report(analysis)

    # Save to JSON
    output_data = analysis_to_dict(analysis)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\nAnalysis saved to: {output_path}")


if __name__ == "__main__":
    main()
