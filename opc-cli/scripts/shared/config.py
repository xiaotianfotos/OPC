"""Shared config for opc CLI."""

import json
import os
import tempfile
from pathlib import Path

CONFIG_DIR = Path.home() / ".opc_cli" / "opc"
CONFIG_FILE = CONFIG_DIR / "config.json"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG = {
    "tts_engine": "edge-tts",
    "output_dir": os.environ.get("OPC_OUTPUT_DIR", tempfile.gettempdir()),
    "workspace_dir": os.environ.get("OPC_WORKSPACE_DIR", str(Path.home() / ".opc_cli" / "workspace")),  # Default workspace for ASR/Cut
    "tts_format": "mp3",
    # edge-tts defaults
    "edge_voice": "zh-CN-XiaoxiaoNeural",
    "edge_rate": "+0%",
    "edge_pitch": "+0Hz",
    "edge_volume": "+0%",
    # qwen defaults
    "qwen_model_size": "1.7B",
    "qwen_mode": "custom_voice",
    "qwen_speaker": "Vivian",
    "qwen_language": "Auto",
    # device
    "default_device": "",
    "device_type": "",
    # asr defaults
    "asr_model_size": "1.7B",
    "asr_language": "",
    # backend: "" = auto-detect, "cuda" = force CUDA, "mlx" = force MLX
    "backend": "",
    # model source: "modelscope" (default, China-friendly) or "huggingface"
    "model_source": "modelscope",
    # model cache directory (used by modelscope/huggingface for downloads)
    # leave empty to use each library's default cache location
    "model_cache_dir": "",
    # dashboard defaults
    "dashboard_host": "0.0.0.0",
    "dashboard_port": 12080,
    "cut_server_port": 12082,
    # cut defaults
    "cut_video": "",
    "cut_json": "",
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            cfg.update(json.load(f))
    return cfg


def save_config(key, value):
    cfg = load_config()
    cfg[key] = value
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
