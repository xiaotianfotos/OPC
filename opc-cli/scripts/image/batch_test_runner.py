"""Batch test runner for image model comparison.

Usage: python3 batch_test_runner.py <alias> <output_dir>
Generates all test prompts for a single model."""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from image.comfyui import generate_image, check_connection
from image.workflow import load_workflow, inject_params

OUTPUT_BASE = "/vol2/1000/work/OPC/opc-cli/scripts/image/examples/model_compare"

TEST_PROMPTS = [
    # Plain text prompts
    ("portrait_1", "Portrait: Cyberpunk Girl",
     "A striking portrait of an East Asian woman with glowing blue cybernetic neural implants under her translucent skin, short silver hair with embedded LED light strands. Neon-lit dystopian Tokyo street at night, rain-soaked, holographic billboards reflecting on wet pavement. Cyberpunk aesthetic, bioluminescent glow, 8K ultra detailed, sharp focus on face, cinematic lighting from below in cool blue and hot pink mix. Mysterious intense gaze looking directly at viewer."),

    ("landscape_1", "Landscape: Floating Islands",
     "A breathtaking fantasy landscape of massive floating islands suspended in a golden amber sky, connected by translucent crystalline bridges. Waterfalls cascade from island edges into clouds below. Ancient stone temples with glowing runes sit atop the largest islands. Giant bioluminescent butterflies drift between landmasses. Cinematic wide angle composition, warm golden hour lighting, volumetric fog and light rays, highly detailed matte painting, 8K concept art."),

    ("product_1", "Product: Minimal Watch",
     "A luxury minimalist smartwatch product photography shot. Matte black titanium case with sapphire crystal display showing subtle analog time readout. Tan cognac leather strap with visible hand stitching. Shot on marble surface with subtle warm gradient background. Soft diffused studio lighting from left with fill from right. 100mm macro lens, shallow depth of field, sharp focus on watch face. High-end product catalog quality, premium sophisticated understated elegance."),

    ("fashion_1", "Fashion: Retro Poster",
     "Vintage 1970s fashion editorial poster style. A model in a flowing psychedelic patterned maxi dress in orange, purple and gold stands in a sun-drenched field of wildflowers. Warm golden sunlight creates lens flare. The image has film grain and slightly faded colors characteristic of 1970s magazine photography like Kodak Portra 400. Nostalgic dreamy atmosphere, retro typography framing the composition."),

    ("food_1", "Food: Ramen Bowl",
     "A steaming bowl of authentic Japanese tonkotsu ramen, overhead flat lay food photography. Rich creamy pork bone broth, hand-pulled noodles, chashu pork slices with caramelized edges, soft-boiled halved egg with golden runny yolk, nori sheet, bamboo shoots, fresh green onion garnish, toasted sesame seeds, chili oil swirl on top. Rustic dark wooden table, ceramic chopsticks on ceramic rest. Natural warm window light, appetizing comforting authentic Japanese cuisine photography."),

    ("architecture_1", "Architecture: Modern Museum",
     "An award-winning architectural photograph of a contemporary art museum at twilight. The building features sweeping curved white concrete forms that flow like liquid into reflecting pools. Interior warm light glows through floor-to-ceiling glass walls. Subtle LED accent lighting traces building contours. Long exposure captures motion blur of visitors inside. Dramatic sky with deep indigo and magenta clouds. Ultra-wide angle, 8K, inspired by Zaha Hadid, professional architectural photography."),
]

NEGATIVE_PROMPT = "low quality, blurry, deformed, ugly, duplicate, watermark, signature, text, logo, cropped, worst quality, low resolution, disfigured, bad anatomy, extra limbs, missing limbs"


def run_tests_for_model(alias, output_dir):
    cfg = {}
    if not check_connection(cfg):
        print(f"ERROR [{alias}]: Cannot connect to ComfyUI")
        return []

    print(f"[{alias}] Connected to ComfyUI")

    wf, meta = load_workflow(alias)
    results = []

    for pid, title, prompt_text in TEST_PROMPTS:
        file_name = f"{pid}_{alias.replace('-', '_')}"
        print(f"  [{alias}] {title}...", flush=True)

        try:
            params = {
                "prompt": prompt_text,
                "seed": 42,
                "width": 1024,
                "height": 1024,
            }
            if "negative_prompt" in meta.get("params", {}):
                params["negative_prompt"] = NEGATIVE_PROMPT

            prepared = inject_params(wf, meta, params)
            result = generate_image(prepared, cfg, filename_prefix=file_name)

            # Move to output dir
            img_path = result["filepaths"][0]
            new_path = os.path.join(output_dir, os.path.basename(img_path))
            os.rename(img_path, new_path)

            results.append({
                "prompt_id": pid,
                "prompt_title": title,
                "model": alias,
                "file": os.path.basename(new_path),
                "status": "ok",
            })
            print(f"  [{alias}] {title} -> OK", flush=True)

        except Exception as e:
            results.append({
                "prompt_id": pid,
                "prompt_title": title,
                "model": alias,
                "file": None,
                "status": "error",
                "error": str(e),
            })
            print(f"  [{alias}] {title} -> FAIL: {e}", flush=True)

    # Save results
    results_file = os.path.join(output_dir, f"results_{alias}.json")
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"[{alias}] Saved results to {results_file}")

    return results


if __name__ == "__main__":
    alias = sys.argv[1] if len(sys.argv) > 1 else "ernie-full"
    os.makedirs(OUTPUT_BASE, exist_ok=True)
    run_tests_for_model(alias, OUTPUT_BASE)
