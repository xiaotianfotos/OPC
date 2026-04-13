"""Model path resolution for opc-cli.

Supports two model sources:
  - modelscope (default): Downloads from ModelScope, China-friendly
  - huggingface: Downloads from HuggingFace (mlx-community models)

Also supports local path override: if the model_id points to an existing
directory, it will be used directly without downloading.

Config keys:
  - model_source: "modelscope" (default) or "huggingface"
  - model_cache_dir: Root directory for model downloads (optional)

The model_cache_dir is set as MODELSCOPE_CACHE / HF_HOME environment variable
before calling the download functions, ensuring consistent behavior.
"""

import os

from .config import load_config


def get_model_source() -> str:
    """Get configured model source."""
    cfg = load_config()
    return cfg.get("model_source", "modelscope")


def get_model_cache_dir() -> str:
    """Get configured model cache directory, or empty string for default."""
    cfg = load_config()
    return cfg.get("model_cache_dir", "")


def _ensure_env(cache_dir: str):
    """Set environment variables for model download libraries.

    Sets MODELSCOPE_CACHE for ModelScope, HF_HOME for HuggingFace.
    Both point to the same user-configured directory.
    """
    if cache_dir:
        os.environ["MODELSCOPE_CACHE"] = cache_dir
        os.environ["HF_HOME"] = cache_dir


def resolve_model_path(model_id: str) -> str:
    """Resolve a model ID to a local path.

    Resolution order:
    1. If model_id is an existing directory path, use it directly
    2. If model_source is "modelscope", download from ModelScope
    3. If model_source is "huggingface", download from HuggingFace

    Args:
        model_id: Model ID (e.g. "Qwen/Qwen3-ASR-1.7B") or local path

    Returns:
        Local path to the model directory.
    """
    # Check if it's already a local path
    if os.path.isdir(model_id):
        return model_id

    cache_dir = get_model_cache_dir()
    _ensure_env(cache_dir)

    source = get_model_source()

    if source == "huggingface":
        return _resolve_huggingface(model_id)
    else:
        return _resolve_modelscope(model_id)


def _resolve_modelscope(model_id: str) -> str:
    """Download/resolve model from ModelScope.

    Uses MODELSCOPE_CACHE environment variable (set by _ensure_env).
    """
    try:
        from modelscope.hub.snapshot_download import snapshot_download
    except ImportError:
        raise ImportError(
            "modelscope is not installed. Install with:\n"
            "  uv sync"
        )

    print(f"[ModelScope] Checking model: {model_id}...")
    # cache_dir=None means use MODELSCOPE_CACHE env var
    local_path = snapshot_download(model_id, cache_dir=None)
    print(f"  -> Found at: {local_path}")
    return local_path


def _resolve_huggingface(model_id: str) -> str:
    """Download/resolve model from HuggingFace.

    Uses HF_HOME environment variable (set by _ensure_env).
    """
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        raise ImportError(
            "huggingface_hub is not installed. Install with:\n"
            "  uv sync"
        )

    print(f"[HuggingFace] Checking model: {model_id}...")
    # cache_dir=None means use HF_HOME env var
    local_path = snapshot_download(model_id, cache_dir=None)
    print(f"  -> Found at: {local_path}")
    return local_path


def check_model_exists(model_id: str) -> bool:
    """Check if a model is already downloaded locally.

    Args:
        model_id: Model ID or local path

    Returns:
        True if the model directory exists.
    """
    if os.path.isdir(model_id):
        return True

    cache_dir = get_model_cache_dir()
    if not cache_dir:
        return False

    source = get_model_source()

    if source == "huggingface":
        # HF cache structure: $HF_HOME/hub/models--org--name/
        safe_id = model_id.replace("/", "--")
        model_dir = os.path.join(cache_dir, "hub", f"models--{safe_id}")
    else:
        # ModelScope cache structure: $MODELSCOPE_CACHE/models/org/name___with___dots/
        # org/model.name → models/org/model___name (dots in model part become ___)
        parts = model_id.split("/", 1)
        if len(parts) == 2:
            org, name = parts
            safe_name = name.replace(".", "___")
            model_dir = os.path.join(cache_dir, "models", org, safe_name)
        else:
            model_dir = os.path.join(cache_dir, "models", model_id)

    return os.path.isdir(model_dir)
