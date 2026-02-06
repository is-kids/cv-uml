"""Speed test for single image."""
import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)

print("Loading model with 4-bit quantization...")
start = time.time()

from app.llm import warmup, MODEL_ID, USE_4BIT
print(f"Model: {MODEL_ID}, 4-bit: {USE_4BIT}")

warmup()
load_time = time.time() - start
print(f"Model loaded in {load_time:.1f}s")

# Test single image
from app.pipeline import process_path

from app.config import SAMPLE_FILES

test_image = SAMPLE_FILES["PNG"]
if test_image.exists():
    print(f"\nProcessing {test_image.name}...")
    start = time.time()
    results = process_path(test_image)
    inference_time = time.time() - start

    print(f"\nResults:")
    for r in results:
        steps = len(r.steps) if r.steps else 0
        print(f"  Steps: {steps}, Type: {r.diagram_type}")

    print(f"\n>>> Inference time: {inference_time:.1f}s <<<")

    if inference_time > 20:
        print("SLOW - need more optimization")
    else:
        print("FAST - target achieved!")
else:
    print(f"Test image not found: {test_image}")
