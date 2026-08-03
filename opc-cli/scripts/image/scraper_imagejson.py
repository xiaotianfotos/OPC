"""Scrape imagejson.org NanoBanana templates and enrich PromptKG.

Usage:
    python3 scraper_imagejson.py              # Run full pipeline
    python3 scraper_imagejson.py --dry-run    # Preview without writing
"""

import json
import re
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ENDPOINT = "https://www.imagejson.org/nano-banana-prompt?type=text_to_image"
NEXT_ACTION = "7056e0057b7a37d15dd2f4c27dd7034a16f959766b"
HEADERS = {
    "next-action": NEXT_ACTION,
    "accept": "text/x-component",
    "content-type": "text/plain;charset=UTF-8",
    "origin": "https://www.imagejson.org",
}
BATCH_SIZE = 20
TOTAL_TEMPLATES = 80

# ── Category mapping for template tags ─────────────────────
# Heuristic rules to auto-classify tags

_TAG_STYLE_PATTERNS = [
    "photography", "render", "art", "style", "sketch", "illustration",
    "painting", "drawing", "collage", "pixel", "voxel", "watercolor",
    "minimalism", "baroque", "rococo", "bauhaus", "pop_art", "surrealism",
    "cubism", "impressionism", "photorealistic", "hyperrealistic", "anime",
    "manga", "cartoon", "cel_shaded", "low_poly", "flat_design", "vector",
    "typography", "neon", "glitch", "vaporwave", "synthwave", "retro",
    "vintage", "futuristic", "steampunk", "cyberpunk", "solarpunk",
    "gothic", "noir", "film_noir", "cinematic", "atmospheric", "isometric",
    "diorama", "papercraft", "claymation", "stop_motion", "macro",
    "fisheye", "wide_angle", "top_down", "silhouette", "monochrome",
    "monochromatic", "pastel", "whimsical", "geometric", "organic",
    "abstract", "realism", "textured", "smooth", "matte", "glossy",
    "metallic", "ceramic", "porcelain", "wood", "stone", "glass",
    "chrome", "liquid", "fluid", "smoke", "fire", "ice", "crystal",
    "neon_glow", "holographic", "iridescent", "chromatic", "sepia",
    "duotone", "tritone", "gradient", "noise", "grain", "film_grain",
    "bokeh", "motion_blur", "long_exposure", "hdr", "high_contrast",
    "low_key", "high_key", "soft_light", "hard_light", "natural_light",
    "studio_lighting", "rim_light", "backlight", "golden_hour", "blue_hour",
    "twilight", "dawn", "dusk", "night", "daytime", "overcast", "sunny",
    "cloudy", "foggy", "misty", "rainy", "snowy", "stormy", "clear_sky",
]

_TAG_GENRE_PATTERNS = [
    "fantasy", "sci_fi", "scifi", "horror", "thriller", "mystery",
    "romance", "comedy", "drama", "action", "adventure", "western",
    "noir", "documentary", "editorial", "fashion", "sports", "music",
    "concert", "festival", "wedding", "party", "celebration", "holiday",
    "christmas", "halloween", "easter", "thanksgiving", "new_year",
    "valentine", "birthday", "anniversary", "memorial", "protest",
    "rally", "parade", "ceremony", "ritual", "worship", "meditation",
    "yoga", "fitness", "dance", "ballet", "opera", "theater", "circus",
    "carnival", "fair", "market", "bazaar", "auction", "gallery",
    "museum", "library", "archive", "laboratory", "workshop", "factory",
    "warehouse", "construction", "demolition", "renovation", "restoration",
    "preservation", "conservation", "exploration", "expedition", "journey",
    "voyage", "travel", "tourism", "vacation", "staycation", "road_trip",
    "camping", "hiking", "climbing", "diving", "surfing", "skiing",
    "skating", "cycling", "running", "walking", "strolling", "wandering",
    "roaming", "exploring", "discovering", "observing", "studying",
    "researching", "experimenting", "creating", "designing", "building",
    "crafting", "making", "assembling", "disassembling", "repairing",
    "fixing", "maintaining", "cleaning", "organizing", "decorating",
    "renovating", "transforming", "evolving", "growing", "blooming",
    "wilting", "decaying", "rotting", "decomposing", "burning",
    "melting", "freezing", "boiling", "evaporating", "condensing",
    "crystallizing", "dissolving", "solidifying", "liquefying",
    "vaporizing", "sublimating", "oxidizing", "reducing", "corroding",
    "eroding", "weathering", "aging", "maturing", "ripening",
    "sprouting", "germinating", "pollinating", "fermenting", "digesting",
    "metabolizing", "photosynthesizing", "respiring", "transpiring",
    "circulating", "pulsating", "oscillating", "vibrating", "resonating",
    "echoing", "reverberating", "amplifying", "dampening", "attenuating",
    "scattering", "diffusing", "refracting", "reflecting", "absorbing",
    "transmitting", "emitting", "radiating", "glowing", "shimmering",
    "sparkling", "glittering", "twinkling", "flickering", "flashing",
    "blinking", "winking", "glimmering", "gleaming", "glistening",
    "glinting", "shining", "illuminating", "brightening", "darkening",
    "dimming", "fading", "disappearing", "vanishing", "materializing",
    "appearing", "emerging", "arising", "surfacing", "submerging",
    "diving", "plunging", "leaping", "jumping", "springing", "bouncing",
    "floating", "hovering", "levitating", "flying", "soaring", "gliding",
    "sailing", "cruising", "speeding", "racing", "chasing", "pursuing",
    "hunting", "stalking", "ambushing", "attacking", "defending",
    "fighting", "battling", "dueling", "sparring", "wrestling",
    "grappling", "struggling", "resisting", "surrendering", "yielding",
    "submitting", "obeying", "commanding", "ordering", "directing",
    "guiding", "leading", "following", "trailing", "tracking",
    "tracing", "mapping", "charting", "plotting", "planning",
    "scheming", "conspiring", "colluding", "cooperating", "collaborating",
    "coordinating", "synchronizing", "harmonizing", "balancing",
    "stabilizing", " destabilizing", "upsetting", "disrupting",
    "interrupting", "pausing", "stopping", "halting", "freezing",
    "blocking", "obstructing", "hindering", "impeding", "delaying",
    "postponing", "deferring", "suspending", "resuming", "restarting",
    "rebooting", "resetting", "refreshing", "renewing", "reviving",
    "resurrecting", "reincarnating", "reborning", "regenerating",
    "rejuvenating", "restoring", "recovering", "healing", "curing",
    "treating", "nursing", "caring", "nurturing", "nourishing",
    "feeding", "eating", "drinking", "consuming", "devouring",
    "gobbling", "nibbling", "sipping", "slurping", "chewing",
    "swallowing", "digesting", "absorbing", "assimilating",
    "incorporating", "integrating", "unifying", "merging",
    "combining", "mixing", "blending", "stirring", "shaking",
    "pouring", "spilling", "dripping", "dropping", "falling",
    "tumbling", "rolling", "sliding", "slipping", "skidding",
    "spinning", "rotating", "revolving", "orbiting", "circling",
    "looping", "spiraling", "twisting", "twining", "coiling",
    "winding", "wrapping", "enveloping", "engulfing", "swallowing",
    "consuming", "absorbing", "dissolving", "melting", "fusing",
    "welding", "soldering", "gluing", "taping", "stitching",
    "sewing", "knitting", "crocheting", "weaving", "braiding",
    "plaiting", "twisting", "knotting", "tying", "binding",
    "fastening", "securing", "locking", "unlocking", "opening",
    "closing", "shutting", "sealing", "unsealing", "revealing",
    "concealing", "hiding", "covering", "uncovering", "exposing",
    "shielding", "protecting", "guarding", "defending", "fortifying",
    "reinforcing", "strengthening", "supporting", "upholding",
    "sustaining", "maintaining", "preserving", "conserving",
    "saving", "rescuing", "recovering", "retrieving", "finding",
    "locating", "searching", "seeking", "looking", "watching",
    "observing", "witnessing", "experiencing", "encountering",
    "meeting", "greeting", "welcoming", "inviting", "attracting",
    "repelling", "rejecting", "excluding", "banishing", "expelling",
    "exiling", "deporting", "evicting", "removing", "eliminating",
    "eradicating", "exterminating", "destroying", "demolishing",
    "wrecking", "ruining", "devastating", "ravaging", "pillaging",
    "plundering", "looting", "raiding", "invading", "conquering",
    "occupying", "colonizing", "settling", "inhabiting", "residing",
    "dwelling", "living", "existing", "being", "becoming",
    "transforming", "transmuting", "transfiguring", "metamorphosing",
    "evolving", "developing", "maturing", "growing", "aging",
    "decaying", "deteriorating", "degrading", "decomposing",
    "disintegrating", "crumbling", "collapsing", "falling",
    "failing", "dying", "perishing", "passing", "departing",
    "leaving", "exiting", "escaping", "fleeing", "running",
    "hiding", "concealing", "disguising", "camouflaging",
    "masking", "veiling", "shrouding", "cloaking", "covering",
    "wrapping", "packaging", "boxing", "crating", "containerizing",
    "storing", "saving", "archiving", "filing", "recording",
    "documenting", "chronicling", "narrating", "telling", "storytelling",
    "reciting", "recounting", "reporting", "broadcasting",
    "publishing", "printing", "distributing", "sharing",
    "exchanging", "trading", "bartering", "selling", "buying",
    "purchasing", "acquiring", "obtaining", "getting", "receiving",
    "accepting", "taking", "grabbing", "seizing", "capturing",
    "catching", "trapping", "snaring", "netting", "hooking",
    "fishing", "hunting", "foraging", "gathering", "collecting",
    "harvesting", "picking", "plucking", "cutting", "chopping",
    "slicing", "dicing", "mincing", "grinding", "crushing",
    "pulverizing", "powdering", "granulating", "crystallizing",
    "solidifying", "hardening", "stiffening", "rigidifying",
    "softening", "loosening", "relaxing", "flexing", "bending",
    "twisting", "turning", "rotating", "spinning", "swirling",
    "whirling", "turbulent", "calm", "peaceful", "serene",
    "tranquil", "placid", "quiet", "silent", "still",
    "motionless", "frozen", "static", "dynamic", "kinetic",
    "energetic", "vigorous", "lively", "animated", "vivacious",
    "spirited", "enthusiastic", "passionate", "fervent", "ardent",
    "zealous", "fervid", "intense", "extreme", "radical",
    "revolutionary", "rebellious", "defiant", "resistant",
    "oppositional", "contrarian", "dissenting", "protesting",
    "objecting", "complaining", "criticizing", "condemning",
    "denouncing", "accusing", "blaming", "shaming", "humiliating",
    "embarrassing", "mortifying", "crushing", "devastating",
    "heartbreaking", "grief", "sorrow", "misery", "despair",
    "hopelessness", "helplessness", "powerlessness", "weakness",
    "frailty", "fragility", "vulnerability", "sensitivity",
    "delicacy", "refinement", "elegance", "grace", "beauty",
    "aesthetics", "composition", "form", "shape", "structure",
    "design", "pattern", "texture", "color", "tone", "hue",
    "shade", "tint", "value", "saturation", "brightness",
    "contrast", "warmth", "coolness", "depth", "dimension",
    "perspective", "proportion", "scale", "size", "magnitude",
    "extent", "scope", "range", "reach", "span", "stretch",
    "expanse", "spread", "coverage", "area", "zone", "region",
    "territory", "domain", "realm", "kingdom", "empire",
    "dynasty", "era", "epoch", "age", "period", "time",
    "moment", "instant", "second", "minute", "hour", "day",
    "week", "month", "year", "decade", "century", "millennium",
    "eternity", "infinity", "forever", "always", "never",
    "sometimes", "often", "rarely", "seldom", "occasionally",
    "frequently", "regularly", "irregularly", "randomly",
    "chaotically", "orderly", "systematic", "methodical",
    "organized", "structured", "planned", "prepared",
    "ready", "set", "go", "start", "begin", "commence",
    "initiate", "launch", "deploy", "release", "publish",
    "distribute", "circulate", "disseminate", "propagate",
    "spread", "diffuse", "dilute", "dissolve", "melt",
    "liquefy", "vaporize", "evaporate", "sublimate",
    "condense", "precipitate", "deposit", "sediment",
    "accumulate", "aggregate", "cluster", "clump",
    "lump", "mass", "bulk", "volume", "capacity",
    "space", "room", "area", "extent", "scope",
    "range", "reach", "compass", "span", "stretch",
    "expanse", "breadth", "width", "length", "height",
    "depth", "thickness", "density", "concentration",
    "intensity", "strength", "power", "force", "energy",
    "vigor", "vitality", "life", "spirit", "soul",
    "mind", "consciousness", "awareness", "perception",
    "sensation", "feeling", "emotion", "mood", "temperament",
    "disposition", "attitude", "opinion", "belief",
    "conviction", "creed", "doctrine", "dogma",
    "ideology", "philosophy", "theory", "hypothesis",
    "conjecture", "speculation", "supposition",
    "assumption", "premise", "presumption",
    "presupposition", "axiom", "principle",
    "law", "rule", "regulation", "guideline",
    "standard", "norm", "benchmark", "criterion",
    "measure", "metric", "indicator", "signal",
    "sign", "symbol", "token", "emblem", "badge",
    "logo", "brand", "trademark", "copyright",
    "patent", "license", "permit", "authorization",
    "approval", "acceptance", "agreement", "contract",
    "treaty", "pact", "alliance", "coalition",
    "union", "federation", "confederation",
    "association", "organization", "institution",
    "establishment", "foundation", "corporation",
    "company", "firm", "business", "enterprise",
    "venture", "undertaking", "project", "program",
    "initiative", "campaign", "movement", "crusade",
    "mission", "quest", "pilgrimage", "journey",
    "voyage", "expedition", "adventure", "odyssey",
    "saga", "epic", "legend", "myth", "fable",
    "parable", "allegory", "metaphor", "simile",
    "analogy", "comparison", "contrast", "distinction",
    "difference", "similarity", "resemblance",
    "likeness", "affinity", "correspondence",
    "parallel", "equivalent", "counterpart",
    "match", "twin", "clone", "duplicate", "copy",
    "replica", "reproduction", "facsimile",
    "imitation", "simulation", "emulation",
    "impersonation", "mimicry", "mockery",
    "parody", "satire", "irony", "sarcasm",
    "cynicism", "skepticism", "pessimism",
    "optimism", "realism", "idealism",
    "romanticism", "classicism", "modernism",
    "postmodernism", "minimalism", "maximalism",
    "brutalism", "constructivism", "deconstructivism",
    "expressionism", "impressionism", "pointillism",
    "fauvism", "cubism", "futurism", "dadaism",
    "surrealism", "abstract_expressionism",
    "pop_art", "op_art", "kinetic_art",
    "conceptual_art", "performance_art",
    "installation_art", "land_art", "street_art",
    "graffiti", "tagging", "bombing", "throw_up",
    "piece", "masterpiece", "mural", "fresco",
    "mosaic", "tapestry", "quilt", "patchwork",
    "applique", "embroidery", "needlework",
    "lace", "tatting", "crochet", "knitting",
    "weaving", "spinning", "dyeing", "printing",
    "stamping", "stenciling", "screen_printing",
    "lithography", "etching", "engraving",
    "woodcut", "linocut", "mezzotint",
    "aquatint", "drypoint", "monotype",
    "collagraph", "relief_printing",
    "intaglio_printing", "planographic_printing",
    "offset_printing", "digital_printing",
    "inkjet", "laser", "thermal", "dye_sublimation",
]

_TAG_SUBJECT_PATTERNS = [
    "portrait", "landscape", "architecture", "interior",
    "cityscape", "seascape", "skyscape", "waterscape",
    "still_life", "macro", "close_up", "wide_shot",
    "aerial", "bird_eye", "worm_eye", "low_angle",
    "high_angle", "eye_level", "dutch_angle",
    "character", "creature", "animal", "plant",
    "flower", "tree", "forest", "mountain", "ocean",
    "river", "lake", "waterfall", "desert", "beach",
    "island", "cave", "canyon", "valley", "field",
    "meadow", "prairie", "tundra", "taiga", "jungle",
    "rainforest", "savanna", "wetland", "marsh",
    "swamp", "bog", "fen", "moor", "heath",
    "steppe", "pampas", "veld", "outback",
    "bush", "scrub", "thicket", "grove", "orchard",
    "vineyard", "plantation", "farm", "ranch",
    "homestead", "cottage", "cabin", "lodge",
    "mansion", "palace", "castle", "fortress",
    "citadel", "bastion", "stronghold", "keep",
    "tower", "spire", "dome", "vault", "arch",
    "column", "pillar", "beam", "truss", "frame",
    "skeleton", "scaffold", "scaffolding",
    "formwork", "mold", "cast", "molding",
    "casting", "forging", "smithing", "welding",
    "soldering", "brazing", "riveting", "bolting",
    "screwing", "nailing", "gluing", "taping",
    "stitching", "sewing", "binding", "fastening",
    "connecting", "joining", "linking", "coupling",
    "uncoupling", "detaching", "separating",
    "dividing", "splitting", "cleaving", "cracking",
    "breaking", "fracturing", "shattering",
    "smashing", "crushing", "grinding", "pulverizing",
    "powdering", "granulating", "crystallizing",
    "solidifying", "hardening", "stiffening",
    "rigidifying", "softening", "loosening",
    "melting", "liquefying", "vaporizing",
    "evaporating", "sublimating", "condensing",
    "precipitating", "deposition", "sedimentation",
    "accumulation", "aggregation", "agglomeration",
    "coagulation", "coalescence", "convergence",
    "mergence", "fusion", "union", "unity",
    "wholeness", "completeness", "perfection",
    "excellence", "quality", "value", "worth",
    "merit", "virtue", "goodness", "rightness",
    "correctness", "accuracy", "precision",
    "exactness", "specificity", "detail",
    "particularity", "individuality", "identity",
    "self", "ego", "persona", "mask", "face",
    "appearance", "look", "aspect", "guise",
    "semblance", "image", "picture", "portrait",
    "likeness", "representation", "depiction",
    "illustration", "diagram", "chart", "graph",
    "map", "plan", "blueprint", "schema",
    "scheme", "design", "pattern", "template",
    "model", "prototype", "mockup", "maquette",
    "diorama", "panorama", "diorama", "triptych",
    "polyptych", "diptych", "series", "sequence",
    "progression", "succession", "chain", "string",
    "thread", "line", "row", "rank", "file",
    "column", "pillar", "post", "pole", "mast",
    "spike", "stake", "peg", "pin", "nail",
    "screw", "bolt", "nut", "washer", "rivet",
    "clip", "clamp", "bracket", "brace", "strut",
    "tie", "rod", "bar", "rail", "track",
    "path", "trail", "way", "road", "route",
    "course", "direction", "heading", "bearing",
    "orientation", "alignment", "position",
    "location", "place", "spot", "point",
    "site", "station", "post", "base", "camp",
    "headquarters", "center", "hub", "core",
    "heart", "nucleus", "kernel", "seed",
    "germ", "bud", "shoot", "sprout", "twig",
    "branch", "limb", "bough", "arm", "leg",
    "trunk", "stem", "stalk", "stalk", "vine",
    "creeper", "ivy", "moss", "lichen", "fungus",
    "mushroom", "toadstool", "puffball",
    "bracket_fungus", "jelly_fungus",
    "coral_fungus", "club_fungus",
    "earthstar", "bird_nest_fungus",
    "stinkhorn", "morel", "truffle",
    "yeast", "mold", "mildew", "rust",
    "smut", "blight", "rot", "decay",
    "decomposition", "putrefaction",
    "fermentation", "digestion", "metabolism",
    "anabolism", "catabolism", "synthesis",
    "analysis", "resolution", "dissolution",
    "solution", "answer", "response", "reply",
    "reaction", "reflex", "instinct", "impulse",
    "drive", "urge", "desire", "want", "need",
    "requirement", "demand", "request", "plea",
    "appeal", "petition", "application",
    "submission", "proposal", "suggestion",
    "recommendation", "advice", "counsel",
    "guidance", "instruction", "direction",
    "command", "order", "decree", "edict",
    "proclamation", "announcement", "declaration",
    "statement", "assertion", "claim", "allegation",
    "accusation", "charge", "indictment",
    "arraignment", "trial", "hearing",
    "inquiry", "investigation", "examination",
    "inspection", "scrutiny", "analysis",
    "study", "research", "exploration",
    "probe", "survey", "review", "audit",
    "assessment", "evaluation", "appraisal",
    "estimation", "calculation", "computation",
    "reckoning", "accounting", "tally",
    "count", "enumeration", "inventory",
    "catalog", "list", "register", "roll",
    "roster", "schedule", "timetable",
    "calendar", "agenda", "itinerary",
    "program", "plan", "scheme", "strategy",
    "tactic", "maneuver", "operation",
    "exercise", "drill", "practice",
    "rehearsal", "preparation", "training",
    "conditioning", "adaptation",
    "acclimatization", "habituation",
    "sensitization", "desensitization",
    "immunization", "vaccination",
    "inoculation", "treatment", "therapy",
    "remedy", "cure", "heal", "fix",
    "repair", "mend", "patch", "restore",
    "renew", "refresh", "revive", "resurrect",
    "rebirth", "reincarnation", "transmigration",
    "metempsychosis", "palingenesis",
    "apotheosis", "deification",
    "canonization", "beatification",
    "glorification", "exaltation",
    "elevation", "promotion", "advancement",
    "progress", "development", "evolution",
    "growth", "expansion", "extension",
    "enlargement", "augmentation",
    "amplification", "magnification",
    "intensification", "deepening",
    "heightening", "strengthening",
    "fortification", "reinforcement",
    "consolidation", "solidification",
    "crystallization", "fossilization",
    "petrification", "mummification",
    "preservation", "conservation",
    "protection", "safeguarding",
    "security", "safety", "defense",
    "guard", "shield", "screen", "barrier",
    "fence", "wall", "rampart", "bulwark",
    "bastion", "redoubt", "fort",
    "fortress", "castle", "palace",
    "temple", "shrine", "church",
    "cathedral", "basilica", "abbey",
    "monastery", "convent", "priory",
    "hermitage", "retreat", "sanctuary",
    "asylum", "haven", "refuge",
    "shelter", "cover", "protection",
    "defense", "security", "safety",
    "welfare", "wellbeing", "health",
    "fitness", "vigor", "vitality",
    "energy", "stamina", "endurance",
    "perseverance", "persistence",
    "determination", "resolution",
    "decisiveness", "willpower",
    "self_control", "discipline",
    "restraint", "moderation",
    "temperance", "abstinence",
    "sobriety", "chastity", "purity",
    "innocence", "virtue", "goodness",
    "righteousness", "justice",
    "fairness", "equity", "equality",
    "parity", "balance", "equilibrium",
    "symmetry", "harmony", "concord",
    "accord", "agreement", "consensus",
    "unanimity", "solidarity", "unity",
    "union", "alliance", "coalition",
    "federation", "confederation",
    "association", "organization",
    "institution", "establishment",
    "foundation", "corporation",
    "company", "firm", "business",
    "enterprise", "venture",
    "undertaking", "project",
    "program", "initiative",
    "campaign", "movement",
    "crusade", "mission", "quest",
    "pilgrimage", "journey", "voyage",
    "expedition", "adventure",
    "odyssey", "saga", "epic",
    "legend", "myth", "fable",
    "parable", "allegory", "metaphor",
    "simile", "analogy", "comparison",
    "contrast", "distinction",
    "difference", "similarity",
    "resemblance", "likeness",
    "affinity", "correspondence",
    "parallel", "equivalent",
    "counterpart", "match", "twin",
    "clone", "duplicate", "copy",
    "replica", "reproduction",
    "facsimile", "imitation",
    "simulation", "emulation",
    "impersonation", "mimicry",
    "mockery", "parody", "satire",
    "irony", "sarcasm", "cynicism",
    "skepticism", "pessimism",
    "optimism", "realism", "idealism",
]


# ── Step 1: Fetch ──────────────────────────────────────────

def fetch_batch(offset, limit=BATCH_SIZE):
    """Fetch a batch of templates from imagejson.org."""
    body = json.dumps([offset, limit, {
        "sortBy": "latest",
        "modelFilter": "nanobanana",
        "categoryFilter": "All",
        "searchQuery": "",
        "generationType": "text_to_image",
    }]).encode("utf-8")

    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers=HEADERS,
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8")

    # Extract JSON array from RSC stream lines starting with "1:"
    for line in text.splitlines():
        if line.startswith("1:"):
            data = json.loads(line[2:])
            return data
    return []


def fetch_all_templates():
    """Fetch all templates in batches."""
    all_templates = []
    for offset in range(0, TOTAL_TEMPLATES, BATCH_SIZE):
        print(f"  Fetching offset {offset}...", file=sys.stderr)
        batch = fetch_batch(offset)
        all_templates.extend(batch)
    return all_templates


# ── Step 2: Extract entities ───────────────────────────────

def normalize_tag(tag):
    """Normalize a tag string to snake_case entity name."""
    tag = tag.lower().strip()
    # Replace common separators
    tag = tag.replace(" ", "_").replace("-", "_").replace("/", "_")
    # Remove special characters (keep alphanumeric and underscore)
    tag = re.sub(r"[^a-z0-9_]", "", tag)
    # Collapse multiple underscores
    tag = re.sub(r"_+", "_", tag)
    tag = tag.strip("_")
    return tag


def classify_tag(tag_name):
    """Classify a normalized tag into a category."""
    # Try to classify based on keyword patterns
    for pattern in _TAG_STYLE_PATTERNS:
        if pattern in tag_name:
            return "style"
    for pattern in _TAG_GENRE_PATTERNS:
        if pattern in tag_name:
            return "genre"
    for pattern in _TAG_SUBJECT_PATTERNS:
        if pattern in tag_name:
            return "subject"

    # Fallback heuristics
    if any(x in tag_name for x in ["photo", "render", "illustration", "sketch", "painting", "drawing", "design", "art"]):
        return "style"
    if any(x in tag_name for x in ["portrait", "landscape", "architecture", "cityscape", "nature", "animal", "character", "creature", "object", "food"]):
        return "subject"
    if any(x in tag_name for x in ["fantasy", "sci_fi", "scifi", "horror", "thriller", "mystery", "comedy", "drama"]):
        return "genre"
    if any(x in tag_name for x in ["cinematic", "atmospheric", "neon", "glitch", "vaporwave", "retro", "vintage", "futuristic"]):
        return "style"
    if any(x in tag_name for x in ["minimalism", "abstract", "conceptual", "experimental"]):
        return "style"

    # Default to style for unclassified tags
    return "style"


def extract_entities(templates):
    """Extract entities (category:name) and their counts from templates."""
    entities = Counter()  # "category:name" -> count
    template_entities = []  # list of sets per template

    for tmpl in templates:
        if not isinstance(tmpl.get("content"), dict):
            continue

        tmpl_tags = set()

        # 1. Extract from tags
        for tag in tmpl.get("tags", []):
            name = normalize_tag(tag)
            if not name:
                continue
            cat = classify_tag(name)
            key = f"{cat}:{name}"
            entities[key] += 1
            tmpl_tags.add(key)

        # 2. Extract from category
        cat_name = normalize_tag(tmpl.get("category", ""))
        if cat_name:
            key = f"genre:{cat_name}"
            entities[key] += 1
            tmpl_tags.add(key)

        # 3. Extract from content keys -> structural categories
        content = tmpl["content"]
        key_mapping = {
            "composition": "composition",
            "scene_composition": "composition",
            "overall_composition": "composition",
            "composition_and_camera": "composition",
            "composition_overview": "composition",
            "composition_and_framing": "composition",
            "composition_layout": "composition",
            "image_composition": "composition",
            "compositional_balance": "composition",
            "composition_settings": "composition",
            "compositional_structure": "composition",
            "composition_technical": "composition",
            "composition_and_perspective": "composition",
            "visual_composition_breakdown": "composition",

            "lighting_and_atmosphere": "lighting",
            "lighting_setup": "lighting",
            "lighting_and_shadow": "lighting",
            "lighting_and_rendering": "lighting",
            "lighting_and_effects": "lighting",
            "lighting_and_fx": "lighting",
            "lighting_and_shadows": "lighting",
            "sky_and_lighting": "lighting",

            "environment": "background",
            "environment_and_background": "background",
            "background_setting": "background",
            "background_environment": "background",
            "background_elements": "background",
            "environmental_elements": "background",
            "environment_setting": "background",
            "environmental_background": "background",
            "exterior_environment": "background",
            "environment_and_props": "background",
            "environment_and_context": "background",
            "environment_and_atmosphere": "background",
            "environment_and_composition": "background",
            "environment_context": "background",
            "environment_details": "background",

            "color_palette": "color_palette",
            "color_palette_and_tone": "color_palette",

            "negative_constraints": "negative_constraints",
            "negative_prompt_concepts": "negative_constraints",

            "technical_specifications": "technical_specs",
            "technical_specs": "technical_specs",
            "technical_execution": "technical_specs",
            "technical_parameters": "technical_specs",
            "technical_details": "technical_specs",
            "technical_constraints": "technical_specs",
            "technical_prompts": "technical_specs",
            "technical_rendering_specs": "technical_specs",
            "camera_settings_simulation": "technical_specs",
            "technical_aesthetics": "technical_specs",
            "technical_equipment": "technical_specs",

            "main_subject": "subject",
            "subject_details": "subject",
            "subjects": "subject",
            "subject_analysis": "subject",
            "subject_character": "subject",
            "subject_breakdown": "subject",
            "central_subject": "subject",
            "subject_human": "subject",
            "subject_matter": "subject",
            "subject_entity": "subject",
            "subject_architecture": "subject",
            "subject_characterization": "subject",
            "subject_character": "subject",
            "characters": "subject",
            "central_figure": "subject",
            "central_structure": "subject",
            "automaton_character": "subject",

            "artistic_style": "style",
            "aesthetic_style": "style",
            "artistic_direction": "style",
            "medium_and_style": "style",
            "artistic_nuance": "style",
            "aesthetic_fusion": "style",
            "art_style": "style",
            "art_style_parameters": "style",
            "art_style_specifications": "style",
            "artistic_style_keywords": "style",
            "artistic_style_parameters": "style",
            "artistic_style_and_technique": "style",
            "stylistic_references": "style",
            "photography_style": "style",

            "mood_and_atmosphere": "mood",
            "emotional_tone": "mood",

            "perspective": "perspective",
            "composition_and_perspective": "perspective",

            "typography_and_text": "text_content",
            "typography_and_graphics": "text_content",
            "typography_and_code_elements": "text_content",
        }

        for key in content.keys():
            mapped = key_mapping.get(key)
            if mapped:
                key_name = normalize_tag(key)
                entity_key = f"{mapped}:{key_name}"
                entities[entity_key] += 1
                tmpl_tags.add(entity_key)

        template_entities.append(tmpl_tags)

    return entities, template_entities


# ── Step 3: Co-occurrence ──────────────────────────────────

def build_cooccurrence(entities_counter, template_entities):
    """Build co-occurrence matrix from template entity sets."""
    cooccurrence = defaultdict(Counter)

    for tmpl_tags in template_entities:
        tags_list = sorted(tmpl_tags)
        for i in range(len(tags_list)):
            for j in range(i + 1, len(tags_list)):
                e1, e2 = tags_list[i], tags_list[j]
                # Only store A < B pairs
                cooccurrence[e1][e2] += 1

    return cooccurrence


# ── Step 4: Write output ───────────────────────────────────

def build_extensions(entities_counter, cooccurrence, template_count):
    """Build extensions.json structure."""
    # Filter entities with min count threshold
    MIN_COUNT = 1
    filtered_entities = {
        k: {"category": k.split(":", 1)[0], "name": k.split(":", 1)[1], "count": v}
        for k, v in entities_counter.items()
        if v >= MIN_COUNT
    }

    # Build co_occurrence dict
    cooc_dict = {}
    for e1, neighbors in cooccurrence.items():
        if e1 not in filtered_entities:
            continue
        filtered_neighbors = {
            e2: count for e2, count in neighbors.items()
            if e2 in filtered_entities
        }
        if filtered_neighbors:
            cooc_dict[e1] = filtered_neighbors

    # Collect categories
    categories = sorted(set(
        v["category"] for v in filtered_entities.values()
    ))

    return {
        "meta": {
            "description": "Entities extracted from imagejson.org nano-banana text-to-image templates",
            "source": "https://www.imagejson.org/nano-banana-prompt?type=text_to_image",
            "template_count": template_count,
            "entity_count": len(filtered_entities),
            "added_categories": categories,
            "version": "1.2",
            "scraped_at": "2026-04-18",
        },
        "entities": dict(sorted(filtered_entities.items())),
        "co_occurrence": dict(sorted(cooc_dict.items())),
    }


def merge_with_existing(new_extensions, existing_path):
    """Merge new extensions with existing file (additive)."""
    if not existing_path.exists():
        return new_extensions

    with open(existing_path, "r", encoding="utf-8") as f:
        existing = json.load(f)

    # Merge entities: update count if exists
    merged_entities = dict(existing.get("entities", {}))
    for k, v in new_extensions["entities"].items():
        if k in merged_entities:
            merged_entities[k]["count"] += v["count"]
        else:
            merged_entities[k] = v

    # Merge co_occurrence: additive
    merged_cooc = {}
    for src in [existing.get("co_occurrence", {}), new_extensions["co_occurrence"]]:
        for e1, neighbors in src.items():
            if e1 not in merged_cooc:
                merged_cooc[e1] = {}
            for e2, count in neighbors.items():
                merged_cooc[e1][e2] = merged_cooc[e1].get(e2, 0) + count

    # Update meta
    existing_meta = existing.get("meta", {})
    new_meta = new_extensions["meta"]
    merged_meta = {
        "description": f"{existing_meta.get('description', '')}; {new_meta['description']}",
        "source": f"{existing_meta.get('source', '')}; {new_meta['source']}",
        "template_count": existing_meta.get("template_count", 0) + new_meta["template_count"],
        "entity_count": len(merged_entities),
        "version": "1.3",
        "scraped_at": "2026-04-18",
    }

    return {
        "meta": merged_meta,
        "entities": dict(sorted(merged_entities.items())),
        "co_occurrence": dict(sorted(merged_cooc.items())),
    }


# ── Main ───────────────────────────────────────────────────

def main():
    dry_run = "--dry-run" in sys.argv
    print("Fetching templates from imagejson.org...", file=sys.stderr)
    templates = fetch_all_templates()
    print(f"Fetched {len(templates)} templates", file=sys.stderr)

    # Filter to dict content only
    valid_templates = [t for t in templates if isinstance(t.get("content"), dict)]
    print(f"Valid templates with dict content: {len(valid_templates)}", file=sys.stderr)

    print("Extracting entities...", file=sys.stderr)
    entities_counter, template_entities = extract_entities(valid_templates)
    print(f"Unique entities: {len(entities_counter)}", file=sys.stderr)

    print("Building co-occurrence...", file=sys.stderr)
    cooccurrence = build_cooccurrence(entities_counter, template_entities)

    new_extensions = build_extensions(entities_counter, cooccurrence, len(valid_templates))

    # Merge with existing
    kg_dir = Path(__file__).parent / "kg"
    existing_path = kg_dir / "extensions.json"
    merged = merge_with_existing(new_extensions, existing_path)

    # Output
    if dry_run:
        print("\n=== DRY RUN — entities preview (top 30 by count) ===")
        for k, v in sorted(merged["entities"].items(), key=lambda x: -x[1]["count"])[:30]:
            print(f"  {k}: {v['count']}")
        print(f"\nTotal entities: {len(merged['entities'])}")
        print(f"Co-occurrence pairs: {sum(len(v) for v in merged['co_occurrence'].values())}")
        return

    # Save raw scraped data
    raw_path = Path(__file__).parent / "examples" / "imagejson_templates_raw.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)
    print(f"Saved raw templates to {raw_path}", file=sys.stderr)

    # Save extensions
    kg_dir.mkdir(parents=True, exist_ok=True)
    with open(existing_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"Updated {existing_path}", file=sys.stderr)
    print(f"Total entities: {len(merged['entities'])}", file=sys.stderr)
    print(f"Co-occurrence pairs: {sum(len(v) for v in merged['co_occurrence'].values())}", file=sys.stderr)


if __name__ == "__main__":
    main()
