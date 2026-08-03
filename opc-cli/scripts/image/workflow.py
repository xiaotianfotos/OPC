"""Workflow and meta management — load, inject params, analyze, import."""

import json
import random
import shutil
import sys
from pathlib import Path

WORKFLOWS_DIR = Path(__file__).parent / "workflows"


def discover_workflows():
    results = []
    for meta_path in sorted(WORKFLOWS_DIR.glob("*.meta.json")):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            alias = meta.get("alias", meta_path.stem.replace(".meta", ""))
            wf_path = meta_path.parent / meta_path.name.replace(".meta.json", ".json")
            if not wf_path.exists():
                # Try finding by stripping .meta: image_foo.meta.json -> image_foo.json
                base = meta_path.stem
                if base.endswith(".meta"):
                    wf_path = meta_path.parent / (base[:-5] + ".json")
            if wf_path.exists():
                results.append((alias, meta))
            else:
                print(f"Warning: workflow file not found for {meta_path.name}", file=sys.stderr)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: invalid meta file {meta_path.name}: {e}", file=sys.stderr)
    return results


def load_workflow(alias):
    for found_alias, meta in discover_workflows():
        if found_alias == alias:
            meta_path = None
            for p in WORKFLOWS_DIR.glob("*.meta.json"):
                with open(p, "r", encoding="utf-8") as f:
                    m = json.load(f)
                if m.get("alias") == alias:
                    meta_path = p
                    break
            if meta_path is None:
                raise FileNotFoundError(f"Meta file not found for alias '{alias}'")
            base = meta_path.stem
            if base.endswith(".meta"):
                wf_path = meta_path.parent / (base[:-5] + ".json")
            else:
                wf_path = meta_path.parent / (base + ".json")
            if not wf_path.exists():
                raise FileNotFoundError(f"Workflow file not found: {wf_path}")
            with open(wf_path, "r", encoding="utf-8") as f:
                workflow = json.load(f)
            return workflow, meta
    raise FileNotFoundError(f"Workflow alias '{alias}' not found. Use 'opc image list' to see available workflows.")


def inject_params(workflow, meta, params):
    result = json.loads(json.dumps(workflow))

    for name, spec in meta.get("params", {}).items():
        node_id = spec["node"]
        field = spec["field"]
        ptype = spec.get("type", "string")

        if name in params:
            raw = params[name]
        elif "default" in spec:
            raw = spec["default"]
        elif spec.get("required"):
            raise ValueError(f"Missing required parameter: '{name}'")
        else:
            continue

        # Type coercion
        if ptype == "int":
            value = int(raw)
            if name == "seed" and value == -1:
                value = random.randint(1, 2**32 - 1)
        elif ptype == "float":
            value = float(raw)
        elif ptype == "bool":
            if isinstance(raw, bool):
                value = raw
            else:
                value = str(raw).lower() in ("true", "1", "yes")
        else:
            value = str(raw)

        if node_id not in result:
            raise ValueError(f"Node '{node_id}' not found in workflow (param '{name}')")
        result[node_id]["inputs"][field] = value

    return result


def analyze_workflow(path):
    with open(path, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    nodes = {}
    potential_params = []

    for node_id, node in workflow.items():
        if not isinstance(node, dict) or "class_type" not in node:
            continue
        inputs = {}
        for field, value in node["inputs"].items():
            if isinstance(value, list) and len(value) == 2:
                inputs[field] = {"value": value, "type": "link_ref"}
            else:
                inputs[field] = {"value": value, "type": "literal"}
                potential_params.append({
                    "node": node_id,
                    "field": field,
                    "current": value,
                    "class_type": node["class_type"],
                    "title": node.get("_meta", {}).get("title", ""),
                })

        nodes[node_id] = {
            "class_type": node["class_type"],
            "title": node.get("_meta", {}).get("title", ""),
            "inputs": inputs,
        }

    node_types = {}
    for n in nodes.values():
        ct = n["class_type"]
        node_types[ct] = node_types.get(ct, 0) + 1

    return {
        "nodes": nodes,
        "summary": {
            "total_nodes": len(nodes),
            "node_types": node_types,
            "potential_params": potential_params,
        },
    }


def import_workflow(file_path, name):
    src = Path(file_path)
    if not src.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(src, "r", encoding="utf-8") as f:
        json.load(f)  # validate JSON

    dest = WORKFLOWS_DIR / f"image_{name}.json"
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dest))
    return str(dest)
