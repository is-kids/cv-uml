from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DOCS_DIR = PROJECT_ROOT / "docs"
DATASET_PART2 = DOCS_DIR / "Диаграммы. 2 часть" / "Диаграммы. 2 часть"
DATASET_MIXED = DOCS_DIR / "Диаграммы" / "Диаграммы"

PICTURES_DIR = DATASET_PART2 / "Picture"

TEST_DIR = DATASET_PART2 / "test"
GT_FILE = TEST_DIR / "test.txt"

EVAL_OUTPUT_DIR = PROJECT_ROOT / "eval_output"

SAMPLE_FILES = {
    "PNG": PICTURES_DIR / "1.png",
    "JPG": DATASET_MIXED / "Телеграм_Диаграммы 2" / "uml" / "class.jpg",
    "DrawIO": DATASET_MIXED / "Notion_Диаграммы" / "BPMN" / "bpmn.drawio",
    "BPMN": DATASET_MIXED / "БиблиотечныйСервис_Диаграммы" / "BPMN" / "Process_Booking.bpmn",
    "SVG": DATASET_MIXED / "АналогUber_Диаграммы" / "C4_Architecture" / "Context.svg",
}
