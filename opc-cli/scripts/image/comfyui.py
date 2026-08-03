"""ComfyUI HTTP client — submit workflows, poll for completion, download images.

Uses only stdlib urllib. No external dependencies.
"""

import base64
import json
import re
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


def download_images(history_result, server_url, output_dir, filename_prefix="opc_image"):
    outputs = history_result.get("outputs", {})
    if not outputs:
        raise RuntimeError("No outputs found in completed workflow")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    saved = []
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    for node_id, node_output in outputs.items():
        for img in node_output.get("images", []):
            params = urllib.parse.urlencode({
                "filename": img["filename"],
                "subfolder": img.get("subfolder", ""),
                "type": img.get("type", "output"),
            })
            url = f"{server_url}/view?{params}"
            save_name = f"{filename_prefix}_{timestamp}_{len(saved)}.png"
            save_path = str(Path(output_dir) / save_name)
            with urllib.request.urlopen(url) as resp:
                with open(save_path, "wb") as f:
                    f.write(resp.read())
            saved.append(save_path)
            print(f"\rDownloaded: {save_path}", file=sys.stderr)

    return saved


def upload_image(image_path, server_url, overwrite=True):
    """Upload a local image file to ComfyUI's input directory.

    Returns the filename as stored in ComfyUI's input folder.
    """
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


def generate_image(workflow, cfg, filename_prefix="opc_image", prompt="",
                   register_gallery=True):
    server_url = get_server_url(cfg)

    if not check_connection(cfg):
        raise ConnectionError(
            f"Cannot connect to ComfyUI at {server_url}. "
            "Make sure ComfyUI is running and configure with: "
            "opc config --set-comfyui-host <host>"
        )

    prompt_id = queue_prompt(workflow, server_url)
    result = wait_for_completion(prompt_id, server_url)

    output_dir = cfg.get("image_output_dir") or cfg.get("output_dir", tempfile.gettempdir())
    paths = download_images(result, server_url, output_dir, filename_prefix)

    if register_gallery and paths:
        try:
            from image.gallery import register_images
            register_images(paths, prompt=prompt, alias=filename_prefix)
        except Exception as e:
            print(f"Gallery registration failed (non-critical): {e}", file=sys.stderr)

    return {"prompt_id": prompt_id, "filepaths": paths}


def _encode_image(image_path):
    """Encode an image file to a data URL for vision API."""
    ext = Path(image_path).suffix.lower()
    mime = "image/png" if ext == ".png" else "image/jpeg"
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _call_vision_api(content_parts, prompt_text, cfg):
    """Call vision model API with arbitrary content parts."""
    api_url = cfg.get("vision_api_url", "")
    if not api_url:
        raise ValueError("Vision API not configured. Set vision_api_url via: opc config --set-vision-api-url <url>")

    model = cfg.get("vision_model", "qwen3.5")
    api_key = cfg.get("vision_api_key", "")

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

    with urllib.request.urlopen(req, timeout=120) as resp:
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


def extract_comfyui_metadata(image_path):
    """Extract ComfyUI workflow/prompt metadata embedded in a PNG image.

    ComfyUI saves the full workflow JSON in the PNG 'prompt' text chunk.
    Returns a dict with keys: 'positive_prompt', 'negative_prompt', 'resolution',
    'seed', 'steps', 'cfg', 'sampler', 'scheduler', 'workflow' (raw), or None
    if no ComfyUI metadata found.
    """
    try:
        from PIL import Image
    except ImportError:
        return None

    try:
        img = Image.open(image_path)
    except Exception:
        return None

    text_meta = getattr(img, "text", {})
    raw = text_meta.get("prompt") or text_meta.get("workflow")
    if not raw:
        return None

    try:
        workflow = json.loads(raw)
    except json.JSONDecodeError:
        return None

    # Heuristic: find prompt strings and latent image nodes
    positive = None
    negative = None
    width = height = batch_size = None
    seed = steps = cfg_val = None
    sampler = scheduler = None

    for nid, node in workflow.items():
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type", "")
        inputs = node.get("inputs", {})

        # Positive prompt: longest string input in PrimitiveString* or text field
        if ct in ("PrimitiveStringMultiline", "PrimitiveString"):
            val = inputs.get("value") or inputs.get("string", "")
            if isinstance(val, str) and len(val) > 20:
                positive = val

        # CLIPTextEncode nodes — identify by link to negative KSampler input
        if ct == "CLIPTextEncode":
            txt = inputs.get("text", "")
            if isinstance(txt, str) and not positive and len(txt) > 20:
                positive = txt
            elif isinstance(txt, str) and len(txt) > 5 and not negative:
                # Check if this links to negative side (heuristic: short text = negative)
                negative = txt

        # EmptyLatentImage / EmptyFlux2LatentImage
        if "LatentImage" in ct:
            width = inputs.get("width")
            height = inputs.get("height")
            batch_size = inputs.get("batch_size")

        # KSampler
        if "KSampler" in ct or ct == "SamplerCustomAdvanced":
            seed = inputs.get("seed")
            steps = inputs.get("steps")
            cfg_val = inputs.get("cfg")
            sampler = inputs.get("sampler_name")
            scheduler = inputs.get("scheduler")

    result = {"workflow": workflow}
    if positive:
        result["positive_prompt"] = positive
    if negative:
        result["negative_prompt"] = negative
    if width and height:
        result["resolution"] = {"width": width, "height": height}
    if batch_size is not None:
        result["batch_size"] = batch_size
    for k, v in [("seed", seed), ("steps", steps), ("cfg", cfg_val),
                 ("sampler", sampler), ("scheduler", scheduler)]:
        if v is not None:
            result[k] = v

    return result if len(result) > 1 else None


def describe_image(image_path, prompt_text, cfg):
    """Use vision model (OpenAI-compatible API) to describe/analyze an image.

    If the image contains ComfyUI metadata, it is automatically extracted and
    included in the response under the 'comfyui_metadata' key.
    """
    result = {}

    # Try extracting ComfyUI metadata first
    comfy_meta = extract_comfyui_metadata(image_path)
    if comfy_meta:
        result["comfyui_metadata"] = comfy_meta

    # Always run vision description as well
    data_url = _encode_image(image_path)
    vision_result = _call_vision_api(
        [{"type": "image_url", "image_url": {"url": data_url}}],
        prompt_text,
        cfg,
    )
    result.update(vision_result)
    return result


def compare_images(image_path_a, image_path_b, prompt_text, cfg):
    """Use vision model to compare two images."""
    url_a = _encode_image(image_path_a)
    url_b = _encode_image(image_path_b)
    return _call_vision_api(
        [
            {"type": "image_url", "image_url": {"url": url_a}},
            {"type": "image_url", "image_url": {"url": url_b}},
        ],
        prompt_text,
        cfg,
    )
