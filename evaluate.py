import json
import logging
import re
import sys
from pathlib import Path
from difflib import SequenceMatcher

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

from app.llm import warmup
from app.pipeline import process_path


TEST_DIR = "docs/Диаграммы. 2 часть/Диаграммы. 2 часть/test"
GT_FILE = "docs/Диаграммы. 2 часть/Диаграммы. 2 часть/test/test.txt"


def parse_ground_truth(test_file: str) -> dict:
    ground_truth = {}
    current_file = None
    current_steps = []
    current_roles = []

    try:
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"File not found: {test_file}")
        return {}

    for line in content.split('\n'):
        line = line.strip()

        if not line or line.startswith('Шаг'):
            continue

        if line.endswith('.png') or line.endswith('.jpg'):
            if current_file and current_steps:
                ground_truth[current_file] = {
                    'steps': current_steps,
                    'roles': current_roles
                }
            current_file = line
            current_steps = []
            current_roles = []
            continue

        match = re.match(r'^(\d+)[\.\)]\s*(.+?)(?:\s*\|\s*(.+))?$', line)
        if match:
            step_num = int(match.group(1))
            action = match.group(2).strip()
            role = match.group(3).strip() if match.group(3) else None

            current_steps.append({
                'number': step_num,
                'action': action,
                'role': role
            })
            if role:
                current_roles.append(role)

    if current_file and current_steps:
        ground_truth[current_file] = {
            'steps': current_steps,
            'roles': current_roles
        }

    return ground_truth


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def text_similarity(text1: str, text2: str) -> float:
    t1 = normalize_text(text1)
    t2 = normalize_text(text2)
    return SequenceMatcher(None, t1, t2).ratio()


def calculate_metrics(extracted: list, ground_truth: list, threshold: float = 0.5) -> dict:
    if not ground_truth:
        return {'precision': 1.0 if not extracted else 0.0, 'recall': 1.0, 'f1': 1.0}
    if not extracted:
        return {'precision': 0.0, 'recall': 0.0, 'f1': 0.0}

    gt_matched = set()
    ex_matched = set()

    for i, ex_step in enumerate(extracted):
        ex_action = ex_step.get('action', '')
        best_match = -1
        best_score = 0

        for j, gt_step in enumerate(ground_truth):
            if j in gt_matched:
                continue
            gt_action = gt_step.get('action', '')
            score = text_similarity(ex_action, gt_action)
            if score > best_score:
                best_score = score
                best_match = j

        if best_score >= threshold:
            gt_matched.add(best_match)
            ex_matched.add(i)

    precision = len(ex_matched) / len(extracted) if extracted else 0
    recall = len(gt_matched) / len(ground_truth) if ground_truth else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'matched': len(gt_matched),
        'gt_total': len(ground_truth),
        'extracted_total': len(extracted)
    }


def find_result(results: list, filename: str):
    for result in results:
        source = Path(result.get('source_file', '')).name
        if source == filename:
            return result
    return None


def evaluate(results: list, ground_truth: dict):
    print("=" * 70)
    print("CV-UML EVALUATION")
    print("=" * 70)

    all_metrics = []
    total_gt = 0
    total_ex = 0

    print(f"\n{'File':<15} {'GT':<5} {'Ex':<5} {'P':<8} {'R':<8} {'F1':<8}")
    print("-" * 70)

    for filename, gt_data in ground_truth.items():
        gt_steps = gt_data['steps']
        total_gt += len(gt_steps)

        result = find_result(results, filename)

        if result:
            extracted = result.get('steps', [])
            total_ex += len(extracted)
            metrics = calculate_metrics(extracted, gt_steps)
            all_metrics.append(metrics)

            print(f"{filename:<15} {len(gt_steps):<5} {len(extracted):<5} "
                  f"{metrics['precision']:.2f}     {metrics['recall']:.2f}     {metrics['f1']:.2f}")
        else:
            print(f"{filename:<15} {len(gt_steps):<5} {'---':<5} {'---':<8} {'---':<8} {'---':<8}")

    print("-" * 70)
    print("\nSUMMARY")
    print("=" * 70)

    if all_metrics:
        avg_p = sum(m['precision'] for m in all_metrics) / len(all_metrics)
        avg_r = sum(m['recall'] for m in all_metrics) / len(all_metrics)
        avg_f1 = sum(m['f1'] for m in all_metrics) / len(all_metrics)

        print(f"Files evaluated:    {len(all_metrics)}/{len(ground_truth)}")
        print(f"Total GT steps:     {total_gt}")
        print(f"Total extracted:    {total_ex}")
        print(f"Avg Precision:      {avg_p:.2f}")
        print(f"Avg Recall:         {avg_r:.2f}")
        print(f"Avg F1:             {avg_f1:.2f}")

        return {'precision': avg_p, 'recall': avg_r, 'f1': avg_f1}

    return None


def run_full_evaluation(test_dir: str = TEST_DIR, gt_file: str = GT_FILE):
    print("Loading model...")
    warmup()

    print(f"\nProcessing {test_dir}...")
    results = process_path(test_dir)

    results_data = [r.model_dump() for r in results]

    output_file = "eval_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({'results': results_data}, f, indent=2, ensure_ascii=False)
    print(f"Results saved to {output_file}")

    gt = parse_ground_truth(gt_file)
    return evaluate(results_data, gt)


def evaluate_from_file(results_file: str, gt_file: str = GT_FILE):
    with open(results_file) as f:
        data = json.load(f)

    results = data.get('results', data) if isinstance(data, dict) else data
    gt = parse_ground_truth(gt_file)

    return evaluate(results, gt)


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        if sys.argv[1] == '--run':
            run_full_evaluation()
        else:
            gt = sys.argv[2] if len(sys.argv) >= 3 else GT_FILE
            evaluate_from_file(sys.argv[1], gt)
    else:
        print("Usage:")
        print("  python evaluate.py --run                    Run extraction + evaluation")
        print("  python evaluate.py results.json             Evaluate existing results")
        print("  python evaluate.py results.json gt.txt      Custom ground truth file")
