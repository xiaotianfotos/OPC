"""MiniMax Music3 generation through a local ComfyUI server."""

import json
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

try:
    from video.comfyui import check_connection, get_server_url, queue_prompt, wait_for_completion
except ModuleNotFoundError:
    from scripts.video.comfyui import check_connection, get_server_url, queue_prompt, wait_for_completion


MUSIC3_DIT = "minimax_music3_dit_fp16.safetensors"
MUSIC3_TEXT_ENCODER = "minimax_music3_text_encoder_pruned_int8_convrot.safetensors"
MUSIC3_VAE = "minimax_music3_dav.safetensors"
MUSIC3_MAX_DURATION = 360.0
MUSIC3_DEFAULT_DURATION = 120.0
MUSIC3_DEFAULT_STEPS = 30
MUSIC3_DEFAULT_CFG = 1.7
MUSIC3_DEFAULT_TOP_K = 50


def build_instrumental_structure(duration):
    """Give the AR model enough explicit sections to avoid premature EOS."""
    sections = ["Intro", "Verse", "Chorus", "Bridge", "Chorus", "Outro"]
    if duration > 90:
        sections[3:3] = ["Instrumental", "Verse", "Chorus"]
    if duration > 180:
        sections[6:6] = ["Solo", "Verse", "Chorus", "Instrumental"]
    return "\n\n".join(f"[{section}]\n[Instrumental]" for section in sections)


def build_music3_workflow(
    caption,
    lyrics,
    duration=MUSIC3_DEFAULT_DURATION,
    seed=0,
    steps=MUSIC3_DEFAULT_STEPS,
    cfg=MUSIC3_DEFAULT_CFG,
    top_k=MUSIC3_DEFAULT_TOP_K,
    output_format="mp3",
    filename_prefix="audio/opc_minimax_music3",
):
    caption = caption.strip()
    lyrics = lyrics.strip()
    if not caption:
        raise ValueError("Music description cannot be empty")
    if not 0.04 <= duration <= MUSIC3_MAX_DURATION:
        raise ValueError(f"Duration must be between 0.04 and {MUSIC3_MAX_DURATION:g} seconds")
    if steps < 1:
        raise ValueError("Steps must be at least 1")
    if cfg < 0:
        raise ValueError("CFG must not be negative")
    if not 1 <= top_k <= 16384:
        raise ValueError("top_k must be between 1 and 16384")
    if output_format not in ("mp3", "flac"):
        raise ValueError("Output format must be mp3 or flac")

    save_node = {
        "class_type": "SaveAudioMP3" if output_format == "mp3" else "SaveAudio",
        "inputs": {
            "audio": ["8", 0],
            "filename_prefix": filename_prefix,
        },
    }
    if output_format == "mp3":
        save_node["inputs"]["quality"] = "V0"

    return {
        "1": {"class_type": "UNETLoader", "inputs": {
            "unet_name": MUSIC3_DIT,
            "weight_dtype": "default",
        }},
        "2": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": MUSIC3_TEXT_ENCODER,
            "type": "minimax",
            "device": "default",
        }},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": MUSIC3_VAE}},
        "4": {"class_type": "MiniMaxMusic3TextEncode", "inputs": {
            "clip": ["2", 0],
            "caption": caption,
            "lyrics": lyrics or "[Instrumental]",
            "seed": seed,
            "max_duration": duration,
            "cfg_scale": cfg,
            "top_k": top_k,
        }},
        "5": {"class_type": "ConditioningZeroOut", "inputs": {
            "conditioning": ["4", 0],
        }},
        "6": {"class_type": "EmptyMiniMaxMusic3LatentAudio", "inputs": {
            "seconds": ["4", 1],
            "batch_size": 1,
        }},
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0],
            "positive": ["4", 0],
            "negative": ["5", 0],
            "latent_image": ["6", 0],
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": "euler",
            "scheduler": "simple",
            "denoise": 1.0,
        }},
        "8": {"class_type": "VAEDecodeAudio", "inputs": {
            "samples": ["7", 0],
            "vae": ["3", 0],
        }},
        "9": save_node,
    }


def generate_music3(workflow, cfg, output_path=None):
    server_url = get_server_url(cfg)
    if not check_connection(cfg):
        raise ConnectionError(f"Cannot connect to ComfyUI at {server_url}")

    started = time.monotonic()
    submitted_at_ms = time.time() * 1000
    prompt_id = queue_prompt(workflow, server_url)
    result = wait_for_completion(prompt_id, server_url)
    elapsed = time.monotonic() - started
    filepath = _download_audio(result, server_url, cfg, output_path)

    return {
        "prompt_id": prompt_id,
        "elapsed_seconds": round(elapsed, 2),
        **_extract_timing(result, submitted_at_ms),
        "filepath": filepath,
    }


def inspect_music_file(file_path, min_duration=0.0):
    samples, sample_rate = sf.read(file_path, dtype="float32", always_2d=True)
    if not sample_rate or samples.size == 0:
        raise ValueError("Generated audio is empty")

    finite = bool(np.isfinite(samples).all())
    absolute = np.abs(samples)
    peak = float(np.max(absolute)) if finite else float("nan")
    rms = float(np.sqrt(np.mean(np.square(samples)))) if finite else float("nan")
    duration = len(samples) / sample_rate
    frame_size = max(1, sample_rate // 20)
    frame_count = len(samples) // frame_size
    if frame_count:
        framed = samples[:frame_count * frame_size].reshape(frame_count, frame_size, -1)
        frame_rms = np.sqrt(np.mean(np.square(framed), axis=(1, 2)))
        silence_ratio = float(np.mean(frame_rms < 0.001))
    else:
        silence_ratio = 0.0
    clipping_ratio = float(np.mean(absolute >= 0.999)) if finite else 1.0

    warnings = []
    if clipping_ratio > 0.001:
        warnings.append("possible clipping")
    if silence_ratio > 0.10:
        warnings.append("more than 10% near-silence")
    if rms < 0.001:
        warnings.append("audio level is nearly silent")
    if not finite:
        warnings.append("audio contains non-finite samples")

    duration_ok = not min_duration or duration + 0.05 >= min_duration
    technical_ok = finite and rms >= 0.001
    return {
        "status": "pass" if duration_ok and technical_ok else "fail",
        "duration_seconds": round(duration, 2),
        "minimum_duration_seconds": round(min_duration, 2),
        "duration_ok": duration_ok,
        "technical_ok": technical_ok,
        "sample_rate": sample_rate,
        "channels": samples.shape[1],
        "peak": round(peak, 4),
        "rms": round(rms, 4),
        "clipping_ratio": round(clipping_ratio, 6),
        "silence_ratio": round(silence_ratio, 4),
        "warnings": warnings,
    }


def _download_audio(history_result, server_url, cfg, output_path):
    audio_items = []
    for node_output in history_result.get("outputs", {}).values():
        audio_items.extend(node_output.get("audio", []))
    if not audio_items:
        raise RuntimeError("Workflow completed without a downloadable audio output")

    item = audio_items[0]
    suffix = Path(item["filename"]).suffix or ".bin"
    if output_path:
        destination = Path(output_path).expanduser()
        if destination.exists() and destination.is_dir():
            destination /= Path(item["filename"]).name
        elif not destination.suffix:
            destination = destination.with_suffix(suffix)
    else:
        output_dir = Path(
            cfg.get("music_output_dir")
            or cfg.get("output_dir")
            or tempfile.gettempdir()
        ).expanduser()
        destination = output_dir / Path(item["filename"]).name
    destination.parent.mkdir(parents=True, exist_ok=True)

    params = urllib.parse.urlencode({
        "filename": item["filename"],
        "subfolder": item.get("subfolder", ""),
        "type": item.get("type", "output"),
    })
    with urllib.request.urlopen(f"{server_url}/view?{params}", timeout=120) as response:
        destination.write_bytes(response.read())
    return str(destination)


def _extract_timing(history_result, submitted_at_ms):
    timestamps = {}
    for event, payload in history_result.get("status", {}).get("messages", []):
        if event in ("execution_start", "execution_success"):
            timestamps[event] = payload.get("timestamp")

    started = timestamps.get("execution_start")
    completed = timestamps.get("execution_success")
    timing = {}
    if started:
        timing["queue_seconds"] = round(max(0, started - submitted_at_ms) / 1000, 2)
    if started and completed:
        timing["execution_seconds"] = round(max(0, completed - started) / 1000, 2)
    return timing


__all__ = [
    "MUSIC3_DEFAULT_CFG",
    "MUSIC3_DEFAULT_DURATION",
    "MUSIC3_DEFAULT_STEPS",
    "MUSIC3_DEFAULT_TOP_K",
    "MUSIC3_MAX_DURATION",
    "build_instrumental_structure",
    "build_music3_workflow",
    "generate_music3",
    "inspect_music_file",
]
