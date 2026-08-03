"""Audio compressor using pydub + ffmpeg.

Implements a dynamic range compressor with parameters matching
professional DAW compressor plugins:
- Threshold: dB level above which compression kicks in
- Ratio: compression ratio (e.g. 4:1 means 4dB input = 1dB output above threshold)
- Attack: how fast compression engages (ms)
- Release: how fast compression releases (ms)
- Knee: soft knee width (dB) for smooth transition
- Makeup gain: output level compensation

Uses ffmpeg's acompressor filter internally.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


def compress_audio(
    input_path: str,
    output_path: Optional[str] = None,
    threshold: float = -20.0,
    ratio: float = 4.0,
    attack: float = 10.0,
    release: float = 130.0,
    knee: float = 0.0,
    makeup: float = 0.0,
    mix: float = 1.0,
) -> str:
    """Apply dynamic range compression to an audio file.

    Args:
        input_path: Path to input audio file (mp3, wav, flac, etc.)
        output_path: Path for output file. If None, auto-generated.
        threshold: Threshold in dB (-50.0 to 0.0). Default -20.0.
        ratio: Compression ratio (1.0 to 20.0). Default 4.0.
        attack: Attack time in ms (0.01 to 2000). Default 10.0.
        release: Release time in ms (0.01 to 9000). Default 130.0.
        knee: Knee width in dB (0 to 40). Default 0.0 (hard knee).
        makeup: Makeup gain in dB. Default 0.0.
        mix: Wet/dry mix ratio (0.0 = dry, 1.0 = fully compressed). Default 1.0.

    Returns:
        Path to the output audio file.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Auto-generate output path if not provided
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_compressed{ext}"

    # Ensure output directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)

    # Build ffmpeg acompressor filter string
    # ffmpeg acompressor uses amplitude ratio for threshold (0.000976563 to 1)
    # threshold=1 means no compression, threshold=0.125 means -18dB
    # Formula: amplitude = 10^(threshold_dB / 20)
    import math
    ffmpeg_threshold = max(0.001, min(1.0, 10 ** (threshold / 20.0)))

    # makeup is gain multiplier (1 to 64), convert from dB: gain = 10^(makeup_dB/20)
    ffmpeg_makeup = max(1.0, min(64.0, 10 ** (makeup / 20.0))) if makeup > 0 else 1.0

    # knee in ffmpeg is 1-8, map from dB (0-40dB) to 1-8 range
    # 0dB -> 1, 40dB -> 8
    ffmpeg_knee = max(1.0, min(8.0, 1.0 + knee / 40.0 * 7.0))

    filter_str = (
        f"acompressor=threshold={ffmpeg_threshold}:"
        f"ratio={ratio}:"
        f"attack={attack}:"
        f"release={release}:"
        f"makeup={ffmpeg_makeup}:"
        f"knee={ffmpeg_knee}"
    )

    if mix < 1.0:
        # Use amix for wet/dry blend
        filter_complex = (
            f"[0:a]acopy[dry];"
            f"[0:a]{filter_str}[wet];"
            f"[dry][wet]amix=inputs=2:weights={1-mix} {mix}:duration=first[aout]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-filter_complex", filter_complex,
            "-map", "[aout]",
            "-c:a", "libmp3lame", "-q:a", "2",
            output_path,
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-af", filter_str,
            "-c:a", "libmp3lame", "-q:a", "2",
            output_path,
        ]

    # If input is wav/flac, preserve format
    input_ext = os.path.splitext(input_path)[1].lower()
    if input_ext == ".wav":
        cmd[-4:] = ["-c:a", "pcm_s16le", output_path]
    elif input_ext == ".flac":
        cmd[-4:] = ["-c:a", "flac", output_path]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg compression failed: {e.stderr}") from e
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found. Please install ffmpeg.") from None

    return output_path


def get_audio_info(path: str) -> dict:
    """Get audio file info using ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        import json
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}


def analyze_loudness(path: str) -> dict:
    """Analyze audio loudness using ffmpeg's ebur128 filter.

    Returns dict with:
        - integrated_lufs: Integrated loudness (LUFS)
        - loudness_range: Loudness range (LU)
        - true_peak: True peak level (dB)
    """
    cmd = [
        "ffmpeg", "-i", path,
        "-af", "ebur128=peak=true",
        "-f", "null", "-",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        stderr = result.stderr

        # Parse ebur128 output
        integrated = None
        loudness_range = None
        true_peak = None

        for line in stderr.split("\n"):
            if "Integrated loudness:" in line:
                # Format: "Integrated loudness:\n    I:     -16.5 LUFS"
                pass
            elif "I:" in line and "LUFS" in line:
                try:
                    integrated = float(line.split("I:")[1].split("LUFS")[0].strip())
                except ValueError:
                    pass
            elif "Loudness range:" in line:
                pass
            elif "LRA:" in line and "LU" in line:
                try:
                    loudness_range = float(line.split("LRA:")[1].split("LU")[0].strip())
                except ValueError:
                    pass
            elif "Peak:" in line and "dB" in line:
                try:
                    true_peak = float(line.split(":")[-1].replace("dB", "").strip())
                except ValueError:
                    pass

        return {
            "integrated_lufs": integrated,
            "loudness_range": loudness_range,
            "true_peak": true_peak,
        }
    except FileNotFoundError:
        return {}


# ── Presets ─────────────────────────────────────────────────────────

PRESETS = {
    "voice": {
        "description": "Optimized for voice/vocal content",
        "threshold": -20.0,
        "ratio": 4.0,
        "attack": 10.0,
        "release": 130.0,
        "knee": 0.0,
        "makeup": 0.0,
        "mix": 1.0,
    },
    "music": {
        "description": "Gentle compression for music",
        "threshold": -18.0,
        "ratio": 2.5,
        "attack": 15.0,
        "release": 200.0,
        "knee": 3.0,
        "makeup": 2.0,
        "mix": 1.0,
    },
    "limiter": {
        "description": "Hard limiting / brickwall",
        "threshold": -6.0,
        "ratio": 20.0,
        "attack": 1.0,
        "release": 50.0,
        "knee": 0.0,
        "makeup": 0.0,
        "mix": 1.0,
    },
    "punch": {
        "description": "Punchy drums/percussion",
        "threshold": -12.0,
        "ratio": 6.0,
        "attack": 3.0,
        "release": 80.0,
        "knee": 2.0,
        "makeup": 3.0,
        "mix": 1.0,
    },
    "gentle": {
        "description": "Very gentle, barely noticeable",
        "threshold": -24.0,
        "ratio": 1.8,
        "attack": 30.0,
        "release": 300.0,
        "knee": 6.0,
        "makeup": 1.0,
        "mix": 1.0,
    },
}


def apply_preset(preset_name: str) -> dict:
    """Get compressor parameters for a named preset."""
    if preset_name not in PRESETS:
        available = ", ".join(PRESETS.keys())
        raise ValueError(f"Unknown preset '{preset_name}'. Available: {available}")
    preset = PRESETS[preset_name].copy()
    del preset["description"]
    return preset


def list_presets() -> dict:
    """Return all available presets with descriptions."""
    return {name: info["description"] for name, info in PRESETS.items()}
