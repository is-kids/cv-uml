import json
import re
import sys
from pathlib import Path

from app.llm import warmup
from app.pipeline import process_path

def parse_ground_truth(test_file: str) -> dict:
    ground_truth = {}
    current_file = None
    current_steps = []

    try:
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Ground truth file not found: {test_file}")
        return {}

    for line in content.split('\n'):
        line = line.strip()

        if not line:
            if current_file and current_steps:
                ground_truth[current_file] = current_steps
            current_file = None
            current_steps = []
            continue

        if line.endswith('.png') or line.endswith('.jpg') or line.endswith('.jpeg'):
            if current_file and current_steps:
                ground_truth[current_file] = current_steps
            current_file = line
            current_steps = []
        elif re.match(r'^\d+[\.\)]\s*', line):
            current_steps.append(line)

    if current_file and current_steps:
        ground_truth[current_file] = current_steps

    return ground_truth

def find_result_for_file(results: list, filename: str) -> dict:
    for result in results:
        source = Path(result['source_file']).name
        if source == filename or filename in result['source_file']:
            return result
    return None

def calculate_step_similarity(extracted_steps: list, gt_steps: list) -> float:
    if not gt_steps:
        return 1.0 if not extracted_steps else 0.0
    if not extracted_steps:
        return 0.0

    extracted_text = ' '.join(s.get('action', '') for s in extracted_steps).lower()
    gt_text = ' '.join(gt_steps).lower()

    extracted_words = set(extracted_text.split())
    gt_words = set(gt_text.split())

    if not gt_words:
        return 0.0

    intersection = extracted_words & gt_words
    return len(intersection) / len(gt_words)

def evaluate_results(results_file: str, ground_truth_file: str):
    print("=" * 60)
    print("CV-UML Evaluation")
    print("=" * 60)

    with open(results_file) as f:
        data = json.load(f)

    results = data.get('results', data) if isinstance(data, dict) else data

    gt = parse_ground_truth(ground_truth_file)

    if not gt:
        print("No ground truth data found!")
        return

    print(f"\nGround truth: {len(gt)} files")
    print(f"Results: {len(results)} extractions")

    total_gt_steps = 0
    total_extracted_steps = 0
    matched_files = 0
    total_similarity = 0.0

    print(f"\n{'File':<30} {'GT Steps':<10} {'Extracted':<10} {'Similarity':<10}")
    print("-" * 60)

    for filename, gt_steps in gt.items():
        total_gt_steps += len(gt_steps)

        result = find_result_for_file(results, filename)

        if result:
            matched_files += 1
            extracted = result.get('steps', [])
            total_extracted_steps += len(extracted)

            similarity = calculate_step_similarity(extracted, gt_steps)
            total_similarity += similarity

            print(f"{filename:<30} {len(gt_steps):<10} {len(extracted):<10} {similarity:.2f}")
        else:
            print(f"{filename:<30} {len(gt_steps):<10} {'N/A':<10} {'N/A':<10}")

    print("-" * 60)

    print(f"\n{'='*60}")
    print("METRICS")
    print(f"{'='*60}")
    print(f"Files matched:     {matched_files}/{len(gt)} ({matched_files/len(gt)*100:.1f}%)")
    print(f"Total GT steps:    {total_gt_steps}")
    print(f"Total extracted:   {total_extracted_steps}")

    if total_gt_steps > 0:
        coverage = total_extracted_steps / total_gt_steps * 100
        print(f"Step coverage:     {coverage:.1f}%")

    if matched_files > 0:
        avg_similarity = total_similarity / matched_files
        print(f"Avg similarity:    {avg_similarity:.2f}")

def run_evaluation(input_dir: str, ground_truth_file: str, output_file: str = "eval_results.json"):
    print("Loading model...")
    warmup()

    print(f"\nProcessing {input_dir}...")
    results = process_path(input_dir)

    results_data = {
        'total': len(results),
        'results': [r.model_dump() for r in results]
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results_data, f, indent=2, ensure_ascii=False)

    print(f"Results saved to {output_file}")

    evaluate_results(output_file, ground_truth_file)

def main():
    if len(sys.argv) >= 3:
        results_file = sys.argv[1]
        gt_file = sys.argv[2]
        evaluate_results(results_file, gt_file)
    elif len(sys.argv) == 2:
        if sys.argv[1] == '--run':
            run_evaluation(
                "docs/Диаграммы. 2 часть/Диаграммы. 2 часть/Picture",
                "docs/Диаграммы. 2 часть/Диаграммы. 2 часть/test/test.txt",
                "eval_results.json"
            )
        else:
            evaluate_results(sys.argv[1], "docs/Диаграммы. 2 часть/Диаграммы. 2 часть/test/test.txt")
    else:
        print("Usage:")
        print("  python evaluate.py <results.json> <ground_truth.txt>")
        print("  python evaluate.py <results.json>  # uses docs/test.txt")
        print("  python evaluate.py --run           # run extraction + evaluate")

if __name__ == "__main__":
    main()
