"""Gallery database manager — shared JSON file with Node.js dashboard.

Stores image metadata in ~/.opc_cli/opc/gallery.json.
Both Python CLI and Node.js API server read/write this file.
"""

import json
import os
import struct
import time
import uuid
from pathlib import Path

GALLERY_DIR = Path.home() / ".opc_cli" / "opc"
GALLERY_FILE = GALLERY_DIR / "gallery.json"


def ensure_gallery_file():
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    if not GALLERY_FILE.exists():
        with open(GALLERY_FILE, "w") as f:
            json.dump({"images": []}, f, ensure_ascii=False)


def load_gallery():
    ensure_gallery_file()
    with open(GALLERY_FILE, "r") as f:
        return json.load(f)


def save_gallery(data):
    ensure_gallery_file()
    tmp = GALLERY_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(str(tmp), str(GALLERY_FILE))


def _read_png_dimensions(filepath):
    """Read PNG width/height from IHDR chunk — zero dependency."""
    try:
        with open(filepath, "rb") as f:
            header = f.read(24)
        if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        return struct.unpack(">II", header[16:24])
    except Exception:
        return None


def register_images(filepaths, prompt="", alias=""):
    """Register generated images into gallery database.

    Returns list of new gallery IDs.
    """
    if not filepaths:
        return []

    data = load_gallery()
    ids = []

    for fpath in filepaths:
        p = Path(fpath)
        if not p.exists():
            continue

        dims = _read_png_dimensions(fpath)
        entry = {
            "id": f"g_{uuid.uuid4().hex[:12]}",
            "filename": p.name,
            "filepath": p.name,
            "prompt": prompt,
            "alias": alias,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "file_size": p.stat().st_size,
        }
        if dims:
            entry["width"] = dims[0]
            entry["height"] = dims[1]

        data["images"].append(entry)
        ids.append(entry["id"])
        print(f"Gallery: registered {p.name} ({entry['id']})", flush=True)

    save_gallery(data)
    return ids


def scan_output_dir(output_dir):
    """Scan output_dir for image files not yet in gallery, register them.

    Returns count of newly added images.
    """
    output_path = Path(output_dir)
    if not output_path.exists():
        return 0

    data = load_gallery()
    existing = {img["filename"] for img in data["images"]}

    exts = {".png", ".jpg", ".jpeg", ".webp"}
    added = 0
    for f in sorted(output_path.iterdir()):
        if not f.is_file() or f.suffix.lower() not in exts:
            continue
        if f.name in existing:
            continue

        # Try to extract alias from filename prefix (e.g. ernie-turbo_20260420_...)
        parts = f.stem.split("_", 1)
        alias = parts[0] if len(parts) > 1 else ""

        dims = _read_png_dimensions(str(f))
        entry = {
            "id": f"g_{uuid.uuid4().hex[:12]}",
            "filename": f.name,
            "filepath": f.name,
            "prompt": "",
            "alias": alias,
            "created_at": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ",
                time.gmtime(f.stat().st_mtime),
            ),
            "file_size": f.stat().st_size,
        }
        if dims:
            entry["width"] = dims[0]
            entry["height"] = dims[1]

        data["images"].append(entry)
        added += 1

    if added:
        save_gallery(data)
    return added
