"""Minimal ComfyUI HTTP client for video workflows."""

import json
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


def get_server_url(cfg):
    host = cfg.get("comfyui_host", "127.0.0.1")
    port = cfg.get("comfyui_port", 8188)
    return f"http://{host}:{port}"


def check_connection(cfg):
    try:
        with urllib.request.urlopen(f"{get_server_url(cfg)}/system_stats", timeout=5) as response:
            return response.status == 200
    except Exception:
        return False


def queue_prompt(workflow, server_url):
    request = urllib.request.Request(
        f"{server_url}/prompt",
        data=json.dumps({"prompt": workflow}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))["prompt_id"]
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ComfyUI rejected workflow: {body}") from None


def wait_for_completion(prompt_id, server_url):
    print(f"Waiting for completion... (ID: {prompt_id})", file=sys.stderr)
    started = time.monotonic()
    while True:
        try:
            with urllib.request.urlopen(f"{server_url}/history/{prompt_id}") as response:
                history = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            history = {}

        if prompt_id in history:
            result = history[prompt_id]
            status = result.get("status", {})
            if status.get("status_str") == "error":
                for event, payload in reversed(status.get("messages", [])):
                    if event == "execution_error":
                        node = f"{payload.get('node_type', 'unknown')}[{payload.get('node_id', '?')}]"
                        message = payload.get("exception_message", "Unknown execution error").strip()
                        raise RuntimeError(f"ComfyUI {node}: {message}")
                raise RuntimeError("ComfyUI execution failed without error details")
            return result

        elapsed = int(time.monotonic() - started)
        print(f"\rWaiting... {elapsed}s", end="", file=sys.stderr, flush=True)
        time.sleep(2)


def upload_file(file_path, server_url):
    """Upload an input asset using ComfyUI's generic upload endpoint."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {file_path}")

    boundary = f"----opc-{uuid.uuid4().hex}"
    remote_name = f"opc_{uuid.uuid4().hex[:12]}_{path.name}"
    parts = []

    def add_field(name, value):
        parts.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            str(value).encode(),
            b"\r\n",
        ])

    add_field("type", "input")
    add_field("overwrite", "false")
    parts.extend([
        f"--{boundary}\r\n".encode(),
        (
            'Content-Disposition: form-data; name="image"; '
            f'filename="{remote_name}"\r\n'
        ).encode(),
        b"Content-Type: application/octet-stream\r\n\r\n",
        path.read_bytes(),
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])

    request = urllib.request.Request(
        f"{server_url}/upload/image",
        data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))
    name = result["name"]
    subfolder = result.get("subfolder", "")
    return f"{subfolder}/{name}" if subfolder else name


def upload_image(image_path, server_url):
    """Backward-compatible alias for callers that only upload images."""
    return upload_file(image_path, server_url)


def download_outputs(history_result, server_url, output_dir, filename_prefix):
    outputs = history_result.get("outputs", {})
    if not outputs:
        raise RuntimeError("No outputs found in completed workflow")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    saved = []
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    for node_output in outputs.values():
        for item in node_output.get("images", []):
            params = urllib.parse.urlencode({
                "filename": item["filename"],
                "subfolder": item.get("subfolder", ""),
                "type": item.get("type", "output"),
            })
            suffix = Path(item["filename"]).suffix or ".bin"
            save_path = Path(output_dir) / f"{filename_prefix}_{timestamp}_{len(saved)}{suffix}"
            with urllib.request.urlopen(f"{server_url}/view?{params}") as response:
                save_path.write_bytes(response.read())
            saved.append(str(save_path))
            print(f"\rDownloaded: {save_path}", file=sys.stderr)

    if not saved:
        raise RuntimeError("Workflow completed without downloadable outputs")
    return saved


def generate_video(workflow, cfg, filename_prefix="opc_video", output_dir=None):
    server_url = get_server_url(cfg)
    if not check_connection(cfg):
        raise ConnectionError(f"Cannot connect to ComfyUI at {server_url}")

    started = time.monotonic()
    submitted_at_ms = time.time() * 1000
    prompt_id = queue_prompt(workflow, server_url)
    result = wait_for_completion(prompt_id, server_url)
    elapsed = time.monotonic() - started
    target_dir = (
        output_dir
        or cfg.get("video_output_dir")
        or cfg.get("output_dir")
        or tempfile.gettempdir()
    )
    paths = download_outputs(result, server_url, target_dir, filename_prefix)
    timing = _extract_timing(result, submitted_at_ms)
    return {
        "prompt_id": prompt_id,
        "elapsed_seconds": round(elapsed, 2),
        **timing,
        "filepaths": paths,
    }


def _extract_timing(history_result, submitted_at_ms):
    timestamps = {}
    for event, payload in history_result.get("status", {}).get("messages", []):
        if event in ("execution_start", "execution_success"):
            timestamps[event] = payload.get("timestamp")

    started = timestamps.get("execution_start")
    completed = timestamps.get("execution_success")
    result = {}
    if started:
        result["queue_seconds"] = round(max(0, started - submitted_at_ms) / 1000, 2)
    if started and completed:
        result["execution_seconds"] = round(max(0, completed - started) / 1000, 2)
    return result


__all__ = [
    "check_connection",
    "generate_video",
    "get_server_url",
    "upload_file",
    "upload_image",
]
