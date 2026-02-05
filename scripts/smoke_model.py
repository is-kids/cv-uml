import sys
from pathlib import Path

from PIL import Image
from app.config import DOCS_DIR
from app.llm import image_inference, warmup
from app.preprocessing import preprocess_image
from app.prompts import IMAGE_PROMPT
from app.postprocessing import parse_llm_response

def main():
    print("=" * 60)
    print("CV-UML Model Test")
    print("=" * 60)

    print("\n[1/4] Loading model...")
    if not warmup():
        print("ERROR: Failed to load model")
        sys.exit(1)
    print("Model loaded!")

    test_images = list(DOCS_DIR.rglob("*.png"))[:3]

    if not test_images:
        print(f"No test images found in {DOCS_DIR}")
        print("Using placeholder test...")
        return

    for i, image_path in enumerate(test_images):
        print(f"\n[{i+2}/4] Processing: {image_path.name}")

        try:
            image = Image.open(image_path)
            print(f"  Original size: {image.size}")

            processed = preprocess_image(image)
            print(f"  Processed size: {processed.size}")

            print("  Running inference...")
            response = image_inference(processed, IMAGE_PROMPT)

            result = parse_llm_response(response, str(image_path))

            print(f"  Diagram type: {result.diagram_type or 'unknown'}")
            print(f"  Confidence: {result.confidence:.2f}")
            print(f"  Steps found: {len(result.steps)}")

            if result.steps:
                print("  First 3 steps:")
                for step in result.steps[:3]:
                    actor = step.actor or "?"
                    print(f"    {step.number}. [{actor}] {step.action}")

            if result.error:
                print(f"  Error: {result.error}")

        except Exception as e:
            print(f"  ERROR: {e}")

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
