"""Video download + ASR transcription script.

Downloads a video from URL (via yt-dlp), extracts audio, runs ASR,
and saves transcript text locally.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def _run(cmd, **kwargs):
    """Run a shell command and return stdout."""
    result = subprocess.run(
        cmd,
        shell=isinstance(cmd, str),
        capture_output=True,
        text=True,
        **kwargs,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {result.stderr.strip()}")
    return result.stdout.strip()


def check_yt_dlp():
    """Check if yt-dlp is installed."""
    try:
        _run(["yt-dlp", "--version"])
        return True
    except (FileNotFoundError, RuntimeError):
        return False


def check_ffmpeg():
    """Check if ffmpeg is installed."""
    try:
        _run(["ffmpeg", "-version"])
        return True
    except (FileNotFoundError, RuntimeError):
        return False


def download_video(url, output_dir):
    """Download video from URL using yt-dlp.

    Returns path to downloaded video file.
    """
    if not check_yt_dlp():
        raise RuntimeError(
            "yt-dlp not found. Install it first:\n"
            "  uv pip install yt-dlp    # or: pip install yt-dlp\n"
            "  brew install yt-dlp      # macOS"
        )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Use yt-dlp to download best quality video+audio merged
    template = str(output_dir / "%(title)s_%(id)s.%(ext)s")

    print(f"Downloading: {url}", file=sys.stderr)
    cmd = [
        "yt-dlp",
        "--no-playlist",
        # Audio-only: download best audio and convert to wav directly
        "-f", "bestaudio/best",
        "--extract-audio",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "-o", template,
    ]
    # Add user-agent and referer for sites like Bilibili
    if "bilibili" in url.lower() or "b23.tv" in url.lower():
        cmd.extend([
            "--add-header", "User-Agent:Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "--add-header", "Referer:https://www.bilibili.com/",
        ])
    cmd.append(url)
    _run(cmd)

    # Find the downloaded file (audio-only: look for wav, mp4, webm, m4a)
    for ext in ("*.wav", "*.mp4", "*.webm", "*.m4a", "*.mp3"):
        files = sorted(output_dir.glob(ext), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            break
    if not files:
        raise RuntimeError("Download completed but no file found")

    downloaded_path = str(files[0])
    print(f"Downloaded: {downloaded_path}", file=sys.stderr)
    return downloaded_path


def extract_audio(media_path, output_dir=None):
    """Extract or convert audio to 16kHz mono WAV using ffmpeg.

    If input is already WAV, re-encodes to ensure correct format.
    Returns path to extracted audio file (wav).
    """
    if not check_ffmpeg():
        raise RuntimeError("ffmpeg not found. Install it first: brew install ffmpeg")

    media_path = Path(media_path)
    if output_dir:
        audio_path = Path(output_dir) / f"{media_path.stem}.wav"
    else:
        audio_path = media_path.with_suffix(".wav")

    # Skip if already the correct wav file
    if media_path.suffix.lower() == ".wav" and str(media_path) == str(audio_path):
        print(f"Audio already in WAV format: {media_path}", file=sys.stderr)
        return str(media_path)

    print(f"Extracting/converting audio: {audio_path}", file=sys.stderr)
    _run([
        "ffmpeg", "-y", "-i", str(media_path),
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        str(audio_path),
    ])

    print(f"Audio ready: {audio_path}", file=sys.stderr)
    return str(audio_path)


def transcribe_audio(audio_path, language=None, model_size="1.7B"):
    """Run ASR transcription on audio file.

    Returns transcribed text string.
    """
    # Import ASR engine from sibling module
    scripts_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(scripts_dir))

    from asr.qwen_asr_engine import asr_transcribe

    print(f"Transcribing with Qwen3-ASR ({model_size})...", file=sys.stderr)
    text = asr_transcribe(audio_path, language=language, model_size=model_size)
    return text


def summarize_text(text, max_chars=500):
    """Generate a brief summary of the transcript.

    Simple heuristic: take first few sentences, or truncate.
    """
    # Split into sentences (roughly)
    sentences = re.split(r'(?<=[。！？.!?])\s+', text)
    summary = ""
    for s in sentences:
        if len(summary) + len(s) < max_chars:
            summary += s + " "
        else:
            break
    return summary.strip() or text[:max_chars]


def save_transcript(text, output_path):
    """Save transcript text to file."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Transcript saved: {output_path}", file=sys.stderr)
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Download video and transcribe to text using Qwen3-ASR",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  # Basic usage
  python -m video.transcribe "https://www.youtube.com/watch?v=..."

  # Specify language
  python -m video.transcribe "https://..." --language Chinese

  # Use smaller model for faster processing
  python -m video.transcribe "https://..." --model-size 0.6B

  # Custom output directory
  python -m video.transcribe "https://..." -o ~/transcripts
""",
    )
    parser.add_argument("url", help="Video URL to download")
    parser.add_argument(
        "-o", "--output-dir",
        default=tempfile.gettempdir(),
        help="Output directory for downloaded video and transcript (default: temp dir)",
    )
    parser.add_argument(
        "--language", "-l",
        help="Language hint for ASR (e.g., Chinese, English). Auto-detect if not specified.",
    )
    parser.add_argument(
        "--model-size", "-m",
        choices=["1.7B", "0.6B"],
        default="1.7B",
        help="ASR model size (default: 1.7B)",
    )
    parser.add_argument(
        "--keep-video", action="store_true",
        help="Keep downloaded video file after transcription",
    )
    parser.add_argument(
        "--keep-audio", action="store_true",
        help="Keep extracted audio file after transcription",
    )

    args = parser.parse_args()

    try:
        # Step 1: Download video
        video_path = download_video(args.url, args.output_dir)

        # Step 2: Extract audio
        audio_path = extract_audio(video_path, args.output_dir)

        # Step 3: Transcribe
        text = transcribe_audio(audio_path, language=args.language, model_size=args.model_size)

        # Step 4: Save transcript
        transcript_path = Path(args.output_dir) / f"{Path(video_path).stem}_transcript.txt"
        save_transcript(text, transcript_path)

        # Step 5: Summary
        summary = summarize_text(text)

        # Cleanup. yt-dlp may return the final WAV directly, in which case
        # video_path and audio_path refer to the same file.
        cleanup_paths = set()
        if not args.keep_video:
            cleanup_paths.add(video_path)
        if not args.keep_audio:
            cleanup_paths.add(audio_path)
        for path in cleanup_paths:
            if os.path.exists(path):
                os.remove(path)
                print(f"Removed: {path}", file=sys.stderr)

        # Output result as JSON
        result = {
            "transcript_path": str(transcript_path),
            "transcript_preview": text[:200] + "..." if len(text) > 200 else text,
            "summary": summary,
            "language": args.language or "auto-detected",
            "model_size": args.model_size,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
