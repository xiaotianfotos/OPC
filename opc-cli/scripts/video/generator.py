"""Video generation module — submit video workflows to ComfyUI.

Mirrors image.comfyui patterns but handles video-specific outputs.
"""

import json
import sys
import time
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def get_server_url(cfg):
    host = cfg.get("comfyui_host", "127.0.0.1")
    port = cfg.get("comfyui_port", 8188)
    return f"http://{host}:{port}"


def check_connection(cfg):
    try:
        url = f"{get_server_url(cfg)}/system_stats"
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def queue_prompt(workflow, server_url, client_id=""):
    data = json.dumps({"prompt": workflow, "client_id": client_id}).encode("utf-8")
    req = urllib.request.Request(
        f"{server_url}/prompt",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["prompt_id"]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ComfyUI rejected workflow: {body}") from None


def wait_for_completion(prompt_id, server_url):
    print(f"Waiting for completion... (ID: {prompt_id})", file=sys.stderr)
    start = time.time()
    while True:
        try:
            url = f"{server_url}/history/{prompt_id}"
            with urllib.request.urlopen(url) as resp:
                history = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                history = {}
            else:
                raise
        if history and prompt_id in history:
            result = history[prompt_id]
            status = result.get("status", {})
            if status.get("status_str") == "error":
                msgs = status.get("messages", [])
                raise RuntimeError(f"ComfyUI execution error: {msgs}")
            return result
        elapsed = int(time.time() - start)
        print(f"\rWaiting... {elapsed}s", end="", file=sys.stderr, flush=True)
        time.sleep(2)


def download_videos(history_result, server_url, output_dir, filename_prefix="opc_video"):
    """Download video outputs from ComfyUI history result."""
    outputs = history_result.get("outputs", {})
    if not outputs:
        raise RuntimeError("No outputs found in completed workflow")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    saved = []
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    for node_id, node_output in outputs.items():
        # Videos are in 'gifs' or 'images' depending on ComfyUI version
        for key in ("gifs", "images", "videos"):
            for item in node_output.get(key, []):
                params = urllib.parse.urlencode({
                    "filename": item["filename"],
                    "subfolder": item.get("subfolder", ""),
                    "type": item.get("type", "output"),
                })
                url = f"{server_url}/view?{params}"
                # Determine extension from filename or default to mp4
                ext = Path(item["filename"]).suffix or ".mp4"
                save_name = f"{filename_prefix}_{timestamp}_{len(saved)}{ext}"
                save_path = str(Path(output_dir) / save_name)
                with urllib.request.urlopen(url) as resp:
                    with open(save_path, "wb") as f:
                        f.write(resp.read())
                saved.append(save_path)
                print(f"\rDownloaded: {save_path}", file=sys.stderr)

    return saved


def upload_image(image_path, server_url, overwrite=True):
    """Upload a local image file to ComfyUI's input directory."""
    import mimetypes
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    filename = path.name
    mime = mimetypes.guess_type(str(path))[0] or "image/png"

    boundary = "----FormBoundary7MA4YWxkTrZu0gW"
    body_parts = []
    body_parts.append(f"--{boundary}\r\n"
                      f"Content-Disposition: form-data; name=\"image\"; filename=\"{filename}\"\r\n"
                      f"Content-Type: {mime}\r\n\r\n".encode("utf-8"))
    body_parts.append(path.read_bytes())
    body_parts.append(f"\r\n--{boundary}\r\n"
                      f"Content-Disposition: form-data; name=\"overwrite\"\r\n\r\n"
                      f"{'true' if overwrite else 'false'}\r\n"
                      f"--{boundary}--\r\n".encode("utf-8"))

    data = b"".join(body_parts)
    req = urllib.request.Request(
        f"{server_url}/upload/image",
        data=data,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    return result.get("name", filename)


def generate_video(workflow, cfg, filename_prefix="opc_video", prompt=""):
    """Submit a video workflow to ComfyUI and download the result."""
    server_url = get_server_url(cfg)

    if not check_connection(cfg):
        raise ConnectionError(
            f"Cannot connect to ComfyUI at {server_url}. "
            "Make sure ComfyUI is running and configure with: "
            "opc config --set-comfyui-host <host>"
        )

    prompt_id = queue_prompt(workflow, server_url)
    result = wait_for_completion(prompt_id, server_url)

    output_dir = cfg.get("video_output_dir") or cfg.get("output_dir", tempfile.gettempdir())
    paths = download_videos(result, server_url, output_dir, filename_prefix)

    return {"prompt_id": prompt_id, "filepaths": paths}
