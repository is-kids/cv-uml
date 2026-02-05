# CV-UML: Руководство по коду

## Содержание

1. [Архитектура проекта](#архитектура-проекта)
2. [Установка и запуск](#установка-и-запуск)
3. [API Reference](#api-reference)
4. [CLI Reference](#cli-reference)
5. [Модули](#модули)
6. [Примеры использования](#примеры-использования)
7. [Расширение функционала](#расширение-функционала)

---

## Архитектура проекта

```
cv-uml/
├── app/
│   ├── __init__.py          # Версия пакета
│   ├── models.py            # Pydantic модели данных
│   ├── llm.py               # Загрузка и инференс Qwen2-VL-2B
│   ├── preprocessing.py     # Предобработка изображений
│   ├── prompts.py           # Промпты для LLM
│   ├── postprocessing.py    # Парсинг ответов LLM
│   ├── ocr.py               # Tesseract OCR (опционально)
│   ├── scanner.py           # Сканирование директорий
│   ├── router.py            # Маршрутизация по типам файлов
│   ├── pipeline.py          # Главный оркестратор
│   └── converters/          # Конвертеры форматов
│       ├── svg.py           # SVG → PNG
│       ├── drawio.py        # DrawIO XML → текст
│       ├── bpmn.py          # BPMN XML → текст
│       ├── archive.py       # ZIP/RAR/7Z
│       ├── pptx.py          # PowerPoint
│       ├── docx.py          # Word
│       └── pdf.py           # PDF
├── main.py                  # FastAPI сервер
├── batch_process.py         # CLI инструмент
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

### Поток данных

```
Файл → Router → Converter → Preprocessing → LLM → Postprocessing → Result
         │
         ├─ IMAGE  ────────────────────────→ preprocess → image_inference
         ├─ SVG    → render_svg ───────────→ preprocess → image_inference
         ├─ PDF    → render_pdf_pages ─────→ preprocess → image_inference (per page)
         ├─ PPTX   → extract_pptx_images ──→ preprocess → image_inference (per slide)
         ├─ DOCX   → extract_docx_images ──→ preprocess → image_inference (per image)
         ├─ DRAWIO → parse_drawio ─────────→ text_inference
         ├─ BPMN   → parse_bpmn ───────────→ text_inference
         └─ ARCHIVE → extract → recurse
```

---

## Установка и запуск

### Требования

- Python 3.11+
- NVIDIA GPU с 8GB+ VRAM (для GPU режима)
- CUDA 12.1+ (для GPU режима)

### Установка зависимостей

```bash
pip install -r requirements.txt
```

### Запуск API сервера

```bash
# Development
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

### Запуск через Docker

```bash
# Сборка и запуск
docker compose up -d

# Просмотр логов
docker compose logs -f

# Остановка
docker compose down
```

### Проверка работоспособности

```bash
curl http://localhost:8000/api/health
# {"status":"ok","model":"Qwen2-VL-2B-Instruct"}
```

---

## API Reference

### GET /api/health

Проверка статуса сервиса.

**Response:**
```json
{
  "status": "ok",
  "model": "Qwen2-VL-2B-Instruct"
}
```

### POST /api/extract

Извлечение шагов из изображения диаграммы.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` - изображение (PNG, JPG, etc.)

**Response:**
```json
{
  "source_file": "diagram.png",
  "page_or_slide": null,
  "diagram_type": "sequence",
  "steps": [
    {
      "number": 1,
      "actor": "User",
      "action": "sends request",
      "target": "Server",
      "note": null
    }
  ],
  "confidence": 0.85,
  "error": null
}
```

**Пример:**
```bash
curl -X POST http://localhost:8000/api/extract \
  -F "file=@diagram.png"
```

### POST /api/extract/file

Извлечение из любого поддерживаемого файла (PDF, PPTX, DOCX, etc.).

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` - файл любого поддерживаемого формата

**Response:** Массив `ExtractionResult[]`

**Пример:**
```bash
curl -X POST http://localhost:8000/api/extract/file \
  -F "file=@presentation.pptx"
```

### POST /api/extract/batch

Пакетная обработка нескольких файлов.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `files` - массив файлов

**Response:**
```json
{
  "total_files": 5,
  "successful": 4,
  "failed": 1,
  "results": [...]
}
```

### POST /api/generate

Генерация PlantUML диаграммы из шагов (обратная задача).

**Request:**
```json
{
  "steps": [
    {"number": 1, "actor": "User", "action": "login", "target": "System"},
    {"number": 2, "actor": "System", "action": "validate", "target": "Database"}
  ],
  "diagram_type": "sequence",
  "title": "Login Flow"
}
```

**Response:**
```json
{
  "plantuml_code": "@startuml\ntitle Login Flow\n...\n@enduml",
  "png_base64": "iVBORw0KGgo...",
  "error": null
}
```

---

## CLI Reference

### batch_process.py

```bash
python batch_process.py [OPTIONS]
```

**Опции:**

| Опция | Короткая | Описание | По умолчанию |
|-------|----------|----------|--------------|
| `--input-dir` | `-i` | Директория с файлами | (обязательно) |
| `--output-file` | `-o` | Выходной файл | `results.json` |
| `--format` | `-f` | Формат: json, jsonl, csv | `json` |
| `--verbose` | `-v` | Подробный вывод | False |

**Примеры:**

```bash
# Базовое использование
python batch_process.py -i ./docs -o results.json

# CSV формат
python batch_process.py -i ./docs -o results.csv -f csv

# JSONL формат (по строке на результат)
python batch_process.py -i ./docs -o results.jsonl -f jsonl

# Подробный вывод
python batch_process.py -i ./docs -o results.json -v
```

---

## Модули

### app/models.py

Pydantic модели для типизации данных.

```python
from app.models import DiagramStep, ExtractionResult, FileType

# Типы файлов
FileType.IMAGE   # PNG, JPG, JPEG, BMP, GIF, WEBP
FileType.SVG
FileType.PDF
FileType.PPTX
FileType.DOCX
FileType.DRAWIO
FileType.BPMN
FileType.ARCHIVE # ZIP, RAR, 7Z

# Шаг диаграммы
step = DiagramStep(
    number=1,
    actor="User",
    action="clicks button",
    target="System",
    note="optional note"
)

# Результат извлечения
result = ExtractionResult(
    source_file="diagram.png",
    page_or_slide=None,
    diagram_type="sequence",
    steps=[step],
    confidence=0.85
)
```

### app/llm.py

Загрузка и инференс модели Qwen2-VL-2B.

```python
from app.llm import load_model, image_inference, text_inference, warmup

# Прогрев модели (загрузка в память)
warmup()

# Инференс на изображении
from PIL import Image
image = Image.open("diagram.png")
response = image_inference(image, "Describe this diagram")

# Инференс на тексте (для DrawIO/BPMN)
response = text_inference(xml_content, "Extract steps from this diagram")
```

### app/preprocessing.py

Предобработка изображений перед инференсом.

```python
from app.preprocessing import preprocess_image, load_and_preprocess

from PIL import Image

# Полный пайплайн предобработки
image = Image.open("diagram.png")
processed = preprocess_image(
    image,
    resize=True,       # Resize до max 1280px
    enhance=True,      # Улучшение контраста
    handle_dark=True,  # Инверсия тёмного фона
    max_dim=1280
)

# Загрузка и предобработка из файла
processed = load_and_preprocess("diagram.png")
```

**Функции:**
- `resize_image(image, max_dim, min_dim)` - изменение размера
- `enhance_contrast(image, factor)` - улучшение контраста
- `is_dark_background(image)` - детекция тёмного фона
- `invert_dark_background(image)` - инверсия тёмного фона
- `convert_to_rgb(image)` - конвертация в RGB

### app/prompts.py

Промпты для LLM.

```python
from app.prompts import IMAGE_PROMPT, TEXT_PROMPT, SIMPLE_IMAGE_PROMPT

# IMAGE_PROMPT - основной промпт для изображений
# TEXT_PROMPT - промпт для текстовых диаграмм (DrawIO, BPMN)
# SIMPLE_IMAGE_PROMPT - упрощённый промпт (fallback)
# SIMPLE_TEXT_PROMPT - упрощённый текстовый промпт
# PLANTUML_SEQUENCE_PROMPT - генерация sequence диаграммы
# PLANTUML_ACTIVITY_PROMPT - генерация activity диаграммы
```

### app/postprocessing.py

Парсинг ответов LLM.

```python
from app.postprocessing import parse_llm_response, validate_steps

# Парсинг ответа в ExtractionResult
result = parse_llm_response(
    llm_response_text,
    source_file="diagram.png",
    page_or_slide=None
)

# Валидация и очистка шагов
clean_steps = validate_steps(result.steps)
```

### app/router.py

Определение типа файла по расширению.

```python
from app.router import get_file_type, is_supported, get_supported_extensions

from pathlib import Path

# Определение типа
file_type = get_file_type(Path("diagram.pdf"))  # FileType.PDF

# Проверка поддержки
is_supported(Path("diagram.xyz"))  # False

# Список расширений
extensions = get_supported_extensions()
# {'.png', '.jpg', '.pdf', '.pptx', ...}
```

### app/scanner.py

Сканирование директорий.

```python
from app.scanner import scan_directory, scan_with_archives, scan_with_deduplication

# Простое сканирование
for file_input in scan_directory("./docs", recursive=True):
    print(file_input.path, file_input.file_type)

# С дедупликацией (по MD5 хешу)
unique_files = scan_with_deduplication("./docs")

# С распаковкой архивов
for file_input in scan_with_archives("./docs"):
    if file_input.parent_archive:
        print(f"From archive: {file_input.parent_archive}")
```

### app/pipeline.py

Главный оркестратор обработки.

```python
from app.pipeline import process_file, process_path, batch_process

from app.models import FileInput, FileType
from pathlib import Path

# Обработка одного файла
file_input = FileInput(path=Path("diagram.png"), file_type=FileType.IMAGE)
results = process_file(file_input)

# Обработка пути (файл или директория)
results = process_path("./docs")

# Пакетная обработка с callback
def on_progress(current, total, path, results):
    print(f"{current}/{total}: {path}")

results = batch_process(
    ["file1.png", "file2.pdf"],
    progress_callback=on_progress
)
```

### app/converters/

Конвертеры для разных форматов.

```python
# SVG → PIL Image
from app.converters.svg import render_svg
image = render_svg("diagram.svg", scale=2.0)

# PDF → список (page_num, PIL Image)
from app.converters.pdf import render_pdf_pages
pages = render_pdf_pages("document.pdf", dpi=150)

# PPTX → список (slide_num, PIL Image)
from app.converters.pptx import extract_pptx_images
images = extract_pptx_images("presentation.pptx")

# DOCX → список (index, PIL Image)
from app.converters.docx import extract_docx_images
images = extract_docx_images("document.docx")

# DrawIO → текстовое представление
from app.converters.drawio import parse_drawio
text = parse_drawio("diagram.drawio")

# BPMN → текстовое представление
from app.converters.bpmn import parse_bpmn
text = parse_bpmn("process.bpmn")

# Archive → извлечённая директория
from app.converters.archive import extract_archive
extracted_dir = extract_archive("files.zip", output_dir="./temp")
```

### app/ocr.py

OCR через Tesseract (опционально).

```python
from app.ocr import extract_text, is_tesseract_available

# Проверка доступности
if is_tesseract_available():
    text = extract_text(image, lang="eng+rus")
```

---

## Примеры использования

### Извлечение из изображения (Python)

```python
from PIL import Image
from app.llm import image_inference, warmup
from app.preprocessing import preprocess_image
from app.prompts import IMAGE_PROMPT
from app.postprocessing import parse_llm_response

# Инициализация
warmup()

# Загрузка и обработка
image = Image.open("diagram.png")
processed = preprocess_image(image)

# Инференс
response = image_inference(processed, IMAGE_PROMPT)

# Парсинг результата
result = parse_llm_response(response, "diagram.png")

# Вывод шагов
for step in result.steps:
    print(f"{step.number}. {step.actor} → {step.action} → {step.target}")
```

### Обработка PDF (Python)

```python
from app.converters.pdf import render_pdf_pages
from app.pipeline import process_image

pages = render_pdf_pages("document.pdf", dpi=150)

for page_num, image in pages:
    result = process_image(image, "document.pdf", page_or_slide=page_num)
    print(f"Page {page_num}: {len(result.steps)} steps")
```

### Пакетная обработка директории

```bash
python batch_process.py -i ./diagrams -o results.json -v
```

### curl примеры

```bash
# Health check
curl http://localhost:8000/api/health

# Извлечение из изображения
curl -X POST http://localhost:8000/api/extract \
  -F "file=@diagram.png" | jq

# Извлечение из PDF
curl -X POST http://localhost:8000/api/extract/file \
  -F "file=@document.pdf" | jq

# Генерация диаграммы
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "steps": [
      {"number": 1, "actor": "User", "action": "login", "target": "System"}
    ],
    "diagram_type": "sequence",
    "title": "Login"
  }' | jq
```

---

## Расширение функционала

### Добавление нового формата файлов

1. Создать конвертер в `app/converters/`:

```python
# app/converters/newformat.py
from pathlib import Path
from PIL import Image

def convert_newformat(path: Path) -> list[tuple[int, Image.Image]]:
    # Реализация конвертации
    images = []
    # ...
    return images
```

2. Добавить тип в `app/models.py`:

```python
class FileType(str, Enum):
    # ...
    NEWFORMAT = "newformat"
```

3. Зарегистрировать в `app/router.py`:

```python
EXTENSION_MAP = {
    # ...
    ".nf": FileType.NEWFORMAT,
}
```

4. Добавить обработку в `app/pipeline.py`:

```python
elif file_type == FileType.NEWFORMAT:
    images = convert_newformat(path)
    # ...
```

### Смена модели LLM

Изменить в `app/llm.py`:

```python
MODEL_ID = "your-model/name"
```

И адаптировать функции `image_inference` / `text_inference` под API новой модели.

### Кастомные промпты

Изменить промпты в `app/prompts.py` для улучшения качества на специфичных типах диаграмм.

---

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `CUDA_VISIBLE_DEVICES` | GPU устройства | `0` |
| `TRANSFORMERS_CACHE` | Кэш моделей | `~/.cache/huggingface` |
| `PLANTUML_JAR` | Путь к PlantUML JAR | `./plantuml.jar` |

---

## Troubleshooting

### CUDA out of memory

Уменьшить размер изображения в `app/preprocessing.py`:
```python
MAX_DIMENSION = 1024  # вместо 1280
```

### Модель не загружается

Проверить доступность HuggingFace:
```bash
python -c "from transformers import AutoProcessor; AutoProcessor.from_pretrained('Qwen/Qwen2-VL-2B-Instruct')"
```

### Tesseract не найден

```bash
# Ubuntu
apt install tesseract-ocr tesseract-ocr-rus

# Windows
# Установить с https://github.com/UB-Mannheim/tesseract/wiki
# Добавить в PATH
```

### PlantUML не генерирует PNG

Проверить наличие Java:
```bash
java -version
```

Скачать PlantUML JAR:
```bash
wget https://github.com/plantuml/plantuml/releases/download/v1.2024.0/plantuml-1.2024.0.jar -O plantuml.jar
```
