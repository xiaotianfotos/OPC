"""Sequential batch test runner for all image models.

Runs one model at a time to avoid ComfyUI loading/unloading models repeatedly.
Usage: python3 run_all_models.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from batch_test_runner import run_tests_for_model, OUTPUT_BASE

MODELS = ['ernie-full', 'z-image', 'qwen-image']

if __name__ == '__main__':
    os.makedirs(OUTPUT_BASE, exist_ok=True)
    for alias in MODELS:
        print(f"\n{'='*50}")
        print(f"Starting model: {alias}")
        print(f"{'='*50}")
        run_tests_for_model(alias, OUTPUT_BASE)
        print(f"Finished model: {alias}")
    print(f"\nAll models done. Results in {OUTPUT_BASE}")
