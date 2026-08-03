"""Video description using vision model API (OpenAI-compatible).

Supports two modes:
- Native video: for models like Nemotron-Omni that accept video files directly
- Frame-based: fallback for models that only accept images
"""

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path


def _encode_image(image_path):
    """Encode an image file to a data URL for vision API."""
    ext = Path(image_path).suffix.lower()
    mime = "image/png" if ext == ".png" else "image/jpeg"
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _encode_video(video_path):
    """Encode a video file to a base64 data URL."""
    ext = Path(video_path).suffix.lower()
    mime = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".mkv": "video/x-matroska",
        ".webm": "video/webm",
    }.get(ext, "video/mp4")
    with open(video_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _call_vision_api(content_parts, prompt_text, cfg):
    """Call vision model API with arbitrary content parts."""
    api_url = cfg.get("video_desc_api_url") or cfg.get("vision_api_url", "")
    if not api_url:
        raise ValueError(
            "Video description API not configured. Set via:\n"
            "  opc config --set-video-desc-api-url <url>\n"
            "Or reuse vision API:\n"
            "  opc config --set-vision-api-url <url>"
        )

    model = cfg.get("video_desc_model") or cfg.get("vision_model", "")
    if not model:
        raise ValueError(
            "Video description model not configured. Set via:\n"
            "  opc config --set-video-desc-model <name>\n"
            "Or reuse vision model:\n"
            "  opc config --set-vision-model <name>"
        )

    api_key = cfg.get("video_desc_api_key") or cfg.get("vision_api_key", "")

    all_content = content_parts + [{"type": "text", "text": prompt_text}]

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": all_content}
        ],
        "max_tokens": 4096,
        "temperature": 0.3,
    }

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=300) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    msg = body["choices"][0]["message"]
    text = msg.get("content") or msg.get("reasoning_content") or ""
    if not text:
        raise RuntimeError("Vision model returned empty response")

    text = re.sub(r'<think[\s\S]*?</think\s*>', '', text, flags=re.IGNORECASE).strip()

    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return {"description": text}


def _supports_native_video(model_name):
    """Check if the model supports native video input."""
    if not model_name:
        return False
    video_models = ["nemotron-omni", "omni", "qwen2.5-vl", "qwen-vl", "gemini", "gpt-4o"]
    name_lower = model_name.lower()
    return any(vm in name_lower for vm in video_models)


def _get_video_resolution(video_path):
    """Get video resolution using ffprobe. Returns (width, height)."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "json",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        info = json.loads(result.stdout)
        stream = info["streams"][0]
        return stream.get("width", 0), stream.get("height", 0)
    except Exception:
        return 0, 0


def _downscale_video(video_path, target_height=540, output_dir=None):
    """Downscale video to target height (preserving aspect ratio).

    Returns path to the downscaled video file.
    """
    video_path = Path(video_path)
    if output_dir is None:
        output_dir = Path(tempfile.gettempdir()) / "opc_video_desc"
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    width, height = _get_video_resolution(video_path)
    if height == 0:
        raise RuntimeError("Could not determine video resolution")

    if height <= target_height:
        print(f"Video already {height}p, no downscale needed", file=sys.stderr)
        return str(video_path)

    output_path = output_dir / f"{video_path.stem}_540p{video_path.suffix}"

    print(f"Downscaling video from {height}p to {target_height}p...", file=sys.stderr)
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vf", f"scale=-2:{target_height}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "copy",
            str(output_path),
        ],
        capture_output=True,
        check=True,
    )
    print(f"Downscaled video: {output_path}", file=sys.stderr)
    return str(output_path)


def extract_frames(video_path, num_frames=8, output_dir=None):
    """Extract evenly-spaced frames from a video using ffmpeg.

    Returns list of frame image paths.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    if output_dir is None:
        output_dir = Path(tempfile.gettempdir()) / "opc_video_frames"
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get video duration using ffprobe
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        duration = float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as e:
        raise RuntimeError(f"Failed to get video duration: {e}")

    if duration <= 0:
        raise RuntimeError("Video duration is zero or negative")

    # Extract frames at evenly spaced timestamps
    frame_paths = []
    for i in range(num_frames):
        timestamp = duration * (i + 1) / (num_frames + 1)
        frame_path = output_dir / f"frame_{i:03d}.jpg"

        subprocess.run(
            [
                "ffmpeg", "-y", "-ss", str(timestamp),
                "-i", str(video_path),
                "-frames:v", "1",
                "-q:v", "2",
                "-vf", "scale='min(1024,iw)':-1",
                str(frame_path),
            ],
            capture_output=True,
            check=True,
        )
        frame_paths.append(str(frame_path))
        print(f"Extracted frame {i + 1}/{num_frames} at {timestamp:.1f}s", file=sys.stderr)

    return frame_paths


def describe_video(video_path, prompt_text=None, cfg=None, num_frames=None):
    """Describe a video using vision model.

    For native video models (e.g. Nemotron-Omni), sends the video file directly.
    For other models, falls back to frame extraction.

    Args:
        video_path: Path to video file
        prompt_text: Custom prompt for the vision model
        cfg: Config dict (uses video_desc_* or vision_* keys)
        num_frames: Number of frames to extract for frame-based mode

    Returns:
        Dict with "description" and other metadata.
    """
    if cfg is None:
        import sys
        scripts_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(scripts_dir))
        from shared.config import load_config
        cfg = load_config()

    model = cfg.get("video_desc_model") or cfg.get("vision_model", "")
    use_native_video = _supports_native_video(model)

    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    if use_native_video:
        # Native video mode: downscale to 540p then send video directly
        print(f"Using native video mode with model: {model}", file=sys.stderr)
        downscaled_path = _downscale_video(video_path, target_height=540)
        video_data_url = _encode_video(downscaled_path)

        content_parts = [{
            "type": "video_url",
            "video_url": {"url": video_data_url},
        }]

        if not prompt_text:
            prompt_text = (
                "Please describe this video in detail, including:\n"
                "1. Main subject(s) and what is happening\n"
                "2. Setting, environment, and background\n"
                "3. Visual style, lighting, and color palette\n"
                "4. Any notable actions, events, or narrative progression\n"
                "5. Overall mood and atmosphere\n\n"
                "Provide a comprehensive description as if explaining the video to someone who cannot see it."
            )

        print(f"Sending video to model...", file=sys.stderr)
        result = _call_vision_api(content_parts, prompt_text, cfg)
        result["mode"] = "native_video"
        result["video_resized"] = downscaled_path != str(video_path)
        return result

    else:
        # Frame-based fallback
        if num_frames is None:
            num_frames = cfg.get("video_desc_max_frames", 8)

        print(f"Using frame-based mode ({num_frames} frames)", file=sys.stderr)
        frame_paths = extract_frames(video_path, num_frames=num_frames)

        content_parts = []
        for frame_path in frame_paths:
            data_url = _encode_image(frame_path)
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": data_url},
            })

        if not prompt_text:
            prompt_text = (
                "These are frames from a video, shown in chronological order. "
                "Please describe the video in detail, including:\n"
                "1. Main subject(s) and what is happening\n"
                "2. Setting, environment, and background\n"
                "3. Visual style, lighting, and color palette\n"
                "4. Any notable actions, events, or narrative progression\n"
                "5. Overall mood and atmosphere\n\n"
                "Provide a comprehensive description as if explaining the video to someone who cannot see it."
            )

        print(f"Sending {len(frame_paths)} frames to vision model...", file=sys.stderr)
        result = _call_vision_api(content_parts, prompt_text, cfg)
        result["mode"] = "frame_based"
        result["frames_extracted"] = len(frame_paths)
        result["frame_paths"] = frame_paths
        return result


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Describe a video using vision model API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  # Basic usage (uses configured API)
  python -m video.describe video.mp4

  # Custom prompt
  python -m video.describe video.mp4 -p "What products are shown in this video?"

  # Force frame-based mode with more frames
  python -m video.describe video.mp4 --frames 12

  # Specify API directly (overrides config)
  python -m video.describe video.mp4 --api-url http://127.0.0.1:5000/v1/chat/completions --model nemotron-omni
""",
    )
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--prompt", "-p", help="Custom prompt for vision model")
    parser.add_argument("--frames", "-n", type=int, help="Force frame-based mode with N frames")
    parser.add_argument("--api-url", help="Vision API URL (overrides config)")
    parser.add_argument("--api-key", help="Vision API key (overrides config)")
    parser.add_argument("--model", "-m", help="Vision model name (overrides config)")

    args = parser.parse_args()

    scripts_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(scripts_dir))
    from shared.config import load_config

    cfg = load_config()
    if args.api_url:
        cfg["video_desc_api_url"] = args.api_url
    if args.api_key:
        cfg["video_desc_api_key"] = args.api_key
    if args.model:
        cfg["video_desc_model"] = args.model

    try:
        result = describe_video(
            args.video,
            prompt_text=args.prompt,
            cfg=cfg,
            num_frames=args.frames,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
