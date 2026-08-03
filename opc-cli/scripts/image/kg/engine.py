"""PromptKG — featherweight prompt knowledge graph engine.

Zero external dependencies. Designed for AI agent workflow:

    kg = PromptKG("prompt_graph.json")

    # 1. Agent identifies user intent → seed entities
    # 2. skeleton() → full prompt construction plan
    # 3. Pick from recs, find_prompts() for reference
    # 4. Assemble final prompt
"""

import json
from collections import defaultdict
from pathlib import Path

_USER_DATA_DIR = Path.home() / ".opc_cli" / "opc"
_BUILTIN_DIR = Path(__file__).parent

_USER_GRAPH = _USER_DATA_DIR / "kg" / "prompt_graph.json"
_PACKAGED_GRAPH = _BUILTIN_DIR / "data" / "prompt_graph.json"
_LEGACY_PACKAGED_GRAPH = _BUILTIN_DIR.parent / "examples" / "prompt_graph.json"
DEFAULT_GRAPH = (
    _USER_GRAPH
    if _USER_GRAPH.exists()
    else _PACKAGED_GRAPH
    if _PACKAGED_GRAPH.exists()
    else _LEGACY_PACKAGED_GRAPH
)
EXTENSIONS = _USER_DATA_DIR / "kg" / "extensions.json" if (_USER_DATA_DIR / "kg" / "extensions.json").exists() else _BUILTIN_DIR / "extensions.json"


class PromptKG:

    def __init__(self, graph_path=None):
        path = graph_path or DEFAULT_GRAPH
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        self.entities = raw["entities"]
        self.prompt_index = raw["prompt_index"]
        self.meta = raw.get("meta", {})

        # Merge extensions if available
        if EXTENSIONS.exists():
            with open(EXTENSIONS, "r", encoding="utf-8") as f:
                ext = json.load(f)
            self.entities.update(ext.get("entities", {}))
            self.meta["extensions"] = ext.get("meta", {})
            # Merge co_occurrence
            for e1, neighbors in ext.get("co_occurrence", {}).items():
                if e1 not in raw.get("co_occurrence", {}):
                    raw["co_occurrence"][e1] = {}
                for e2, count in neighbors.items():
                    raw["co_occurrence"][e1][e2] = raw["co_occurrence"][e1].get(e2, 0) + count
            raw["co_occurrence"] = dict(raw["co_occurrence"])

        # Bidirectional adjacency: co_occurrence stores only A<B pairs
        self._adj = defaultdict(dict)
        for e1, neighbors in raw["co_occurrence"].items():
            for e2, count in neighbors.items():
                self._adj[e1][e2] = count
                self._adj[e2][e1] = count
        self._adj = dict(self._adj)

        # Category → [entity tags] sorted by count desc
        self._by_cat = defaultdict(list)
        for tag, info in self.entities.items():
            self._by_cat[info["category"]].append(tag)
        for cat in self._by_cat:
            self._by_cat[cat].sort(key=lambda t: self.entities[t]["count"], reverse=True)
        self._by_cat = dict(self._by_cat)

        # Entity → prompt IDs
        self._entity_prompts = defaultdict(list)
        for rec in self.prompt_index:
            for tag in rec["tags"]:
                self._entity_prompts[tag].append(rec["id"])
        self._entity_prompts = dict(self._entity_prompts)

        # Load templates: user dir first, then builtin
        self._templates = {}
        _tpl_dirs = [
            _USER_DATA_DIR / "templates",
            Path(__file__).parent.parent / "templates",
        ]
        for templates_dir in _tpl_dirs:
            if not templates_dir.exists():
                continue
            for d in templates_dir.iterdir():
                tpl_path = d / "template.json"
                if tpl_path.exists():
                    try:
                        tpl = json.loads(tpl_path.read_text("utf-8"))
                        if tpl["name"] not in self._templates:
                            self._templates[tpl["name"]] = tpl
                    except Exception:
                        pass

    # ── Properties ──────────────────────────────────────────

    @property
    def categories(self):
        return list(self._by_cat.keys())

    # ── Browse ──────────────────────────────────────────────

    def list_category(self, category):
        """Entities in a category, sorted by frequency."""
        return [
            {"entity": tag, **self.entities[tag]}
            for tag in self._by_cat.get(category, [])
        ]

    def search(self, keyword):
        """Fuzzy search entities by keyword (matches tag or name)."""
        kw = keyword.lower()
        hits = []
        for tag, info in self.entities.items():
            if kw in tag.lower() or kw in info["name"].lower():
                hits.append({"entity": tag, **info})
        hits.sort(key=lambda x: -x["count"])
        return hits

    # ── Core query ──────────────────────────────────────────

    def info(self, entity):
        """Full entity details + top relations + related templates."""
        if entity not in self.entities:
            return None
        e = self.entities[entity]
        result = {
            "entity": entity,
            "category": e["category"],
            "name": e["name"],
            "count": e["count"],
            "prompt_count": len(self._entity_prompts.get(entity, [])),
            "top_relations": self.neighbors(entity, top_n=8),
        }
        related = self.find_templates(entity)
        if related:
            result["related_templates"] = related
        return result

    def neighbors(self, entity, category=None, top_n=10):
        """Co-occurring entities, optionally filtered by category."""
        if entity not in self._adj:
            return []
        results = list(self._adj[entity].items())
        if category:
            results = [(k, v) for k, v in results
                       if self.entities[k]["category"] == category]
        results.sort(key=lambda x: -x[1])
        total = self.entities[entity]["count"]
        return [
            {
                "entity": k,
                "category": self.entities[k]["category"],
                "name": self.entities[k]["name"],
                "co_count": v,
                "confidence": round(v / total, 3),
            }
            for k, v in results[:top_n]
        ]

    def recommend(self, seeds, target_category, top_n=5):
        """Given seed entities, recommend entities in target_category.

        Scoring: aggregate conditional probability.
        score(B) = sum(co_occurrence(Ai, B)) / sum(count(Ai))
        """
        candidates = defaultdict(float)
        total_seed = 0
        for seed in seeds:
            sc = self.entities.get(seed, {}).get("count", 0)
            if sc == 0:
                continue
            total_seed += sc
            for neighbor, count in self._adj.get(seed, {}).items():
                if self.entities[neighbor]["category"] == target_category:
                    candidates[neighbor] += count

        if total_seed == 0:
            return []

        ranked = sorted(candidates.items(), key=lambda x: -x[1])
        return [
            {
                "entity": tag,
                "name": self.entities[tag]["name"],
                "score": int(count),
                "confidence": round(count / total_seed, 3),
            }
            for tag, count in ranked[:top_n]
        ]

    # ── Prompt retrieval ────────────────────────────────────

    def find_prompts(self, entities, top_n=5):
        """Find prompts matching the most entities, ranked by overlap."""
        entity_set = set(entities)
        scored = []
        for rec in self.prompt_index:
            tags = set(rec["tags"])
            overlap = len(entity_set & tags)
            if overlap > 0:
                scored.append((overlap, rec))
        scored.sort(key=lambda x: -x[0])

        results = []
        for overlap, rec in scored[:top_n]:
            results.append({
                "id": rec["id"],
                "title": rec["title"],
                "title_zh": rec["title_zh"],
                "matched": sorted(entity_set & set(rec["tags"])),
                "match_score": overlap,
                "prompt_short": rec["prompt_short"],
                "prompt_short_zh": rec["prompt_short_zh"],
            })
        return results

    # ── High-level agent API ────────────────────────────────

    def skeleton(self, seeds):
        """Generate a prompt construction plan from seed entities.

        Returns recommendations for each unfilled category + example prompts.
        This is the primary entry point for an AI agent.
        """
        seed_cats = {
            self.entities[s]["category"]: s
            for s in seeds if s in self.entities
        }
        unfilled = [c for c in self.categories if c not in seed_cats]

        plan = {
            "seeds": seeds,
            "filled": {
                cat: {"entity": tag, "name": self.entities[tag]["name"]}
                for cat, tag in seed_cats.items()
            },
            "recommendations": {},
            "example_prompts": self.find_prompts(seeds, top_n=3),
        }

        for cat in unfilled:
            recs = self.recommend(seeds, cat, top_n=3)
            if recs:
                plan["recommendations"][cat] = recs

        # Template recommendations
        all_templates = []
        for seed in seeds:
            all_templates.extend(self.find_templates(seed))
        seen = set()
        unique = []
        for t in all_templates:
            if t["template"] not in seen:
                seen.add(t["template"])
                unique.append(t)
        if unique:
            plan["template_recommendations"] = sorted(unique, key=lambda x: -x["relevance"])[:3]

        return plan

    def validate(self, entities):
        """Check if a combination of entities is common, moderate, or unusual."""
        el = list(entities)
        if len(el) < 2:
            return {"valid": True, "pairs": []}

        pairs = []
        for i in range(len(el)):
            for j in range(i + 1, len(el)):
                e1, e2 = el[i], el[j]
                count = self._adj.get(e1, {}).get(e2, 0)
                c1 = self.entities.get(e1, {}).get("count", 1)
                c2 = self.entities.get(e2, {}).get("count", 1)
                conf = count / min(c1, c2) if min(c1, c2) > 0 else 0
                pairs.append({
                    "pair": sorted([e1, e2]),
                    "co_count": count,
                    "confidence": round(conf, 3),
                    "assessment": (
                        "common" if conf > 0.3
                        else "moderate" if conf > 0.1
                        else "unusual"
                    ),
                })

        avg = sum(p["confidence"] for p in pairs) / len(pairs) if pairs else 0
        return {
            "entities": el,
            "pairs": pairs,
            "average_confidence": round(avg, 3),
            "overall": (
                "common" if avg > 0.3
                else "moderate" if avg > 0.1
                else "unusual"
            ),
        }

    # ── Template discovery ──────────────────────────────────

    def list_templates(self):
        """List all available templates."""
        return [
            {
                "name": tpl["name"],
                "description": tpl["description"],
                "scenes": list(tpl["scenes"].keys()),
                "resolution": tpl.get("resolution", {}),
            }
            for tpl in self._templates.values()
        ]

    def find_templates(self, entity):
        """Find templates related to a given entity."""
        results = []
        entity_name = entity.split(":")[-1] if ":" in entity else entity
        for tpl in self._templates.values():
            relevance = 0
            source = tpl.get("source", "")
            prefix = tpl.get("style_prefix", "")
            if entity_name in source:
                relevance += 15
            if entity_name in prefix:
                relevance += 10
            for neighbor in self._adj.get(entity, {}):
                n_name = neighbor.split(":")[-1] if ":" in neighbor else neighbor
                if n_name in source or n_name in prefix:
                    relevance += 3
            if relevance > 0:
                results.append({
                    "template": tpl["name"],
                    "description": tpl["description"],
                    "relevance": relevance,
                    "scenes": list(tpl["scenes"].keys()),
                    "resolution": tpl.get("resolution", {}),
                })
        results.sort(key=lambda x: -x["relevance"])
        return results
