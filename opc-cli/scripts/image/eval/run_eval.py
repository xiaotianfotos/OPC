"""Evaluation runner for image generation models.

Usage:
  cd opc-cli/scripts/image && python3 eval/run_eval.py <alias> [<alias> ...]

Examples:
  python3 eval/run_eval.py ernie-full
  python3 eval/run_eval.py ernie-full z-image qwen-image

For each specified workflow alias, runs all prompts in eval/prompts/ sequentially.
Results are saved to eval/results/<alias>/ with JSON + images.
"""

import json
import os
import shutil
import sys
import time
from datetime import datetime

# Add opc-cli/scripts/ to path so 'image' package can be imported
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(_SCRIPT_DIR)))
sys.path.insert(0, os.path.dirname(os.path.dirname(_SCRIPT_DIR)))

from image.comfyui import generate_image, check_connection
from image.workflow import load_workflow, inject_params

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), 'prompts')
RESULTS_DIR = os.path.join(os.path.dirname(__file__), 'results')

DEFAULT_SEED = 42
DEFAULT_WIDTH = 1024
DEFAULT_HEIGHT = 1024


def load_all_prompts():
    """Load all JSON prompt files from eval/prompts/."""
    prompts = []
    if not os.path.exists(PROMPTS_DIR):
        raise FileNotFoundError(f"Prompts directory not found: {PROMPTS_DIR}")

    for fname in sorted(os.listdir(PROMPTS_DIR)):
        if not fname.endswith('.json'):
            continue
        path = os.path.join(PROMPTS_DIR, fname)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            prompt_id = fname[:-5]  # strip .json
            prompts.append({
                'id': prompt_id,
                'data': data,
                'title': data.get('meta', {}).get('template_name', prompt_id),
            })
        except Exception as e:
            print(f"  [warn] Skip {fname}: {e}")
    return prompts


def run_eval_for_model(alias, all_prompts):
    """Run all prompts for a single model alias, sequentially."""
    cfg = {}
    if not check_connection(cfg):
        print(f"ERROR [{alias}]: Cannot connect to ComfyUI")
        return []

    print(f"\n[{'='*50}")
    print(f"  Model: {alias}")
    print(f"  Prompts: {len(all_prompts)}")
    print(f"{'='*50}")

    wf, meta = load_workflow(alias)
    output_dir = os.path.join(RESULTS_DIR, alias)
    os.makedirs(output_dir, exist_ok=True)

    results = []
    start_time = time.time()
    results_file = os.path.join(output_dir, 'results.json')

    def save_progress():
        elapsed = time.time() - start_time
        summary = {
            'meta': {
                'alias': alias,
                'timestamp': datetime.now().isoformat(),
                'total': len(all_prompts),
                'ok': sum(1 for r in results if r['status'] == 'ok'),
                'error': sum(1 for r in results if r['status'] == 'error'),
                'elapsed_seconds': round(elapsed, 1),
            },
            'results': results,
        }
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

    for i, p in enumerate(all_prompts, 1):
        prompt_id = p['id']
        title = p['title']
        print(f"\n  [{i}/{len(all_prompts)}] [{alias}] {title}...", flush=True)

        try:
            # Read prompt text directly from JSON
            positive_text = p['data'].get('prompt', '')
            negative_text = p['data'].get('negative', '')

            if not positive_text.strip():
                raise ValueError("Empty prompt text")

            params = {
                'prompt': positive_text,
                'seed': DEFAULT_SEED,
                'width': DEFAULT_WIDTH,
                'height': DEFAULT_HEIGHT,
            }
            if 'negative_prompt' in meta.get('params', {}):
                params['negative_prompt'] = negative_text or meta.get('default_negative', '')

            prepared = inject_params(wf, meta, params)
            result = generate_image(prepared, cfg, filename_prefix=prompt_id)

            img_path = result['filepaths'][0]
            new_name = f"{prompt_id}_{alias.replace('-', '_')}.png"
            new_path = os.path.join(output_dir, new_name)
            shutil.move(img_path, new_path)

            results.append({
                'prompt_id': prompt_id,
                'prompt_title': title,
                'model': alias,
                'file': new_name,
                'status': 'ok',
                'positive_preview': positive_text[:200] + '...' if len(positive_text) > 200 else positive_text,
                'negative_preview': negative_text[:200] + '...' if negative_text and len(negative_text) > 200 else negative_text,
            })
            print(f"  [{alias}] {title} -> OK ({os.path.getsize(new_path)/1024:.0f}KB)", flush=True)

        except Exception as e:
            results.append({
                'prompt_id': prompt_id,
                'prompt_title': title,
                'model': alias,
                'file': None,
                'status': 'error',
                'error': str(e),
            })
            print(f"  [{alias}] {title} -> FAIL: {e}", flush=True)

        # Save after each prompt
        save_progress()

    elapsed = time.time() - start_time
    print(f"\n  [{alias}] Done in {elapsed:.0f}s")
    print(f"  [{alias}] Saved results to {results_file}")

    return results


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("Usage: python3 eval/run_eval.py <alias> [<alias> ...]")
        print("\nAvailable workflows:")
        wf_dir = os.path.join(os.path.dirname(__file__), '..', 'workflows')
        for f in sorted(os.listdir(wf_dir)) if os.path.exists(wf_dir) else []:
            if f.endswith('.meta.json'):
                alias = f.replace('image_', '').replace('.meta.json', '')
                print(f"  - {alias}")
        sys.exit(1)

    aliases = sys.argv[1:]
    print(f"Evaluation run starting...")
    print(f"Workflows: {', '.join(aliases)}")

    all_prompts = load_all_prompts()
    print(f"Loaded {len(all_prompts)} prompts from {PROMPTS_DIR}")

    for alias in aliases:
        run_eval_for_model(alias, all_prompts)

    print(f"\n{'='*50}")
    print("All models evaluated.")
    print(f"Results directory: {RESULTS_DIR}")


if __name__ == '__main__':
    main()
