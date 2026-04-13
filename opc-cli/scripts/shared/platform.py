"""Platform detection for opc-cli.

Auto-detects the compute backend based on OS:
  - macOS → mlx (Apple Silicon)
  - Linux → cuda (NVIDIA GPU)

Can be overridden via config: opc config --set-backend mlx
"""

import platform


def is_macos() -> bool:
    """Check if running on macOS."""
    return platform.system() == "Darwin"


def is_linux() -> bool:
    """Check if running on Linux."""
    return platform.system() == "Linux"


def _auto_detect_backend() -> str:
    """Auto-detect backend from OS."""
    return "mlx" if is_macos() else "cuda"


def get_backend() -> str:
    """Get the compute backend.

    Priority:
    1. Config override (if set and non-empty)
    2. Auto-detect from OS

    Returns:
        'mlx' or 'cuda'
    """
    # Lazy import to avoid circular dependency
    try:
        from .config import load_config
        cfg_backend = load_config().get("backend", "")
        if cfg_backend:
            return cfg_backend
    except Exception:
        pass

    return _auto_detect_backend()


def get_backend_label() -> str:
    """Get a human-readable label for the current backend."""
    backend = get_backend()
    if backend == "mlx":
        return "mlx (Apple Silicon)"
    return "cuda (NVIDIA GPU)"


def check_dependency_available(backend: str) -> bool:
    """Check if the required dependency for a backend is installed.

    Args:
        backend: 'mlx' or 'cuda'

    Returns:
        True if the dependency is importable.
    """
    if backend == "mlx":
        try:
            import mlx_audio  # noqa: F401
            return True
        except ImportError:
            return False
    elif backend == "cuda":
        try:
            import torch  # noqa: F401
            return True
        except ImportError:
            return False
    return False
