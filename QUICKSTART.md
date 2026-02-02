# CV-UML: Полный гайд по запуску

## 1. Подготовка окружения

### 1.1 Системные требования

- Windows 10/11 или Linux
- Python 3.11+
- NVIDIA GPU с 8GB+ VRAM (RTX 3080 laptop подходит)
- CUDA 12.1+
- ~10GB свободного места (модель + зависимости)

### 1.2 Проверка GPU

```bash
# Проверить CUDA
nvidia-smi

# Должно показать GPU и версию драйвера
# Например: NVIDIA GeForce RTX 3080 Laptop GPU, CUDA Version: 12.x
```

### 1.3 Создание виртуального окружения

```bash
# Windows
cd C:\Users\Ilya\PycharmProjects\cv-uml
python -m venv venv
venv\Scripts\activate

# Linux/Mac
cd ~/cv-uml
python -m venv venv
source venv/bin/activate
```

---

## 2. Установка зависимостей

### 2.1 Установка PyTorch с CUDA

```bash
# PyTorch с CUDA 12.1
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### 2.2 Установка остальных зависимостей

```bash
pip install -r requirements.txt
```

### 2.3 Проверка установки

```bash
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
python -c "import torch; print(f'GPU: {torch.cuda.get_device_name(0)}')"
```

Ожидаемый вывод:
```
CUDA available: True
GPU: NVIDIA GeForce RTX 3080 Laptop GPU
```

---

## 3. Загрузка и тестирование модели

### 3.1 Первая загрузка модели

Модель загрузится автоматически при первом запуске (~4GB).

```bash
python -c "from app.llm import warmup; warmup()"
```

Вывод:
```
INFO:app.llm:Loading model Qwen/Qwen2-VL-2B-Instruct...
INFO:app.llm:Using device: cuda
INFO:app.llm:Model loaded successfully
```

### 3.2 Тест инференса

Создай тестовый скрипт `test_model.py`:

```python
from PIL import Image
from app.llm import image_inference, warmup
from app.preprocessing import preprocess_image
from app.prompts import IMAGE_PROMPT

print("Loading model...")
warmup()

# Замени на путь к твоей тестовой картинке
image_path = "docs/Диаграммы. 2 часть/Диаграммы. 2 часть/Picture/1.png"

print(f"Processing {image_path}...")
image = Image.open(image_path)
processed = preprocess_image(image)

print("Running inference...")
response = image_inference(processed, IMAGE_PROMPT)

print("\n=== RESULT ===")
print(response)
```

Запуск:
```bash
python test_model.py
```

---

## 4. Запуск API сервера

### 4.1 Запуск в режиме разработки

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4.2 Проверка работы

Открой новый терминал:

```bash
# Health check
curl http://localhost:8000/api/health
```

Ответ:
```json
{"status":"ok","model":"Qwen2-VL-2B-Instruct"}
```

### 4.3 Swagger UI

Открой в браузере: http://localhost:8000/docs

Там можно тестировать все endpoints через веб-интерфейс.

---

## 5. Демонстрация работы

### 5.1 Извлечение из одного изображения

```bash
# Windows PowerShell
curl.exe -X POST http://localhost:8000/api/extract -F "file=@docs/Диаграммы. 2 часть/Диаграммы. 2 часть/Picture/1.png"

# Linux/Mac
curl -X POST http://localhost:8000/api/extract \
  -F "file=@docs/Диаграммы. 2 часть/Диаграммы. 2 часть/Picture/1.png"
```

### 5.2 Пакетная обработка через CLI

```bash
# Обработать все диаграммы в папке
python batch_process.py \
  --input-dir "docs/Диаграммы. 2 часть/Диаграммы. 2 часть/Picture" \
  --output-file results.json \
  --verbose
```

Вывод:
```
Loading model...
Processing files in docs/Диаграммы. 2 часть/Диаграммы. 2 часть/Picture...
Processing: 100%|████████████████| 155/155 [12:34<00:00, 4.87s/it]

Results saved to results.json
Total: 155 files, 142 successful, 13 failed
Total steps extracted: 847
```

### 5.3 Просмотр результатов

```bash
# Первые 5 результатов
python -c "
import json
with open('results.json') as f:
    data = json.load(f)
    for r in data['results'][:5]:
        print(f\"File: {r['source_file']}\")
        print(f\"Steps: {len(r['steps'])}\")
        for s in r['steps'][:3]:
            print(f\"  {s['number']}. {s.get('actor', '?')} -> {s['action']}\")
        print()
"
```

### 5.4 Генерация диаграммы (обратная задача)

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "steps": [
      {"number": 1, "actor": "Клиент", "action": "Отправляет заказ", "target": "Система"},
      {"number": 2, "actor": "Система", "action": "Проверяет данные", "target": "База данных"},
      {"number": 3, "actor": "База данных", "action": "Возвращает результат", "target": "Система"},
      {"number": 4, "actor": "Система", "action": "Подтверждает заказ", "target": "Клиент"}
    ],
    "diagram_type": "sequence",
    "title": "Оформление заказа"
  }'
```

---

## 6. Демо-скрипт для презентации

Создай `demo.py`:

```python
import json
import sys
from pathlib import Path

from PIL import Image
from app.llm import warmup
from app.pipeline import process_path
from app.preprocessing import preprocess_image

def demo_single_image(image_path: str):
    """Демо обработки одного изображения."""
    print(f"\n{'='*60}")
    print(f"DEMO: Processing single image")
    print(f"{'='*60}")
    print(f"Input: {image_path}")

    results = process_path(image_path)

    for result in results:
        print(f"\nDiagram type: {result.diagram_type or 'unknown'}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Steps found: {len(result.steps)}")
        print("\nExtracted steps:")
        for step in result.steps:
            actor = step.actor or "?"
            target = step.target or "?"
            print(f"  {step.number}. [{actor}] {step.action} -> [{target}]")

def demo_batch(directory: str, limit: int = 5):
    """Демо пакетной обработки."""
    print(f"\n{'='*60}")
    print(f"DEMO: Batch processing")
    print(f"{'='*60}")
    print(f"Directory: {directory}")
    print(f"Limit: {limit} files")

    results = process_path(directory)

    total_steps = 0
    successful = 0

    for i, result in enumerate(results[:limit]):
        if not result.error:
            successful += 1
            total_steps += len(result.steps)

        print(f"\n[{i+1}] {Path(result.source_file).name}")
        if result.error:
            print(f"    ERROR: {result.error}")
        else:
            print(f"    Type: {result.diagram_type or 'unknown'}")
            print(f"    Steps: {len(result.steps)}")

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Processed: {min(limit, len(results))} files")
    print(f"Successful: {successful}")
    print(f"Total steps: {total_steps}")

def demo_comparison(image_path: str, ground_truth: str):
    """Демо сравнения с ground truth."""
    print(f"\n{'='*60}")
    print(f"DEMO: Comparison with ground truth")
    print(f"{'='*60}")

    results = process_path(image_path)

    print(f"\nExtracted ({len(results[0].steps)} steps):")
    for step in results[0].steps:
        print(f"  {step.number}. {step.action}")

    print(f"\nGround truth:")
    print(ground_truth)

if __name__ == "__main__":
    print("CV-UML Demo")
    print("="*60)

    # Загрузка модели
    print("\nLoading model (first time may take a while)...")
    warmup()
    print("Model ready!\n")

    # Путь к тестовым изображениям
    test_dir = "docs/Диаграммы. 2 часть/Диаграммы. 2 часть/Picture"

    # Демо 1: Одно изображение
    demo_single_image(f"{test_dir}/1.png")

    # Демо 2: Пакетная обработка
    demo_batch(test_dir, limit=5)

    print("\n" + "="*60)
    print("Demo completed!")
    print("="*60)
```

Запуск:
```bash
python demo.py
```

---

## 7. Запуск в Docker

### 7.1 Сборка образа

```bash
docker compose build
```

### 7.2 Запуск контейнера

```bash
docker compose up -d
```

### 7.3 Проверка логов

```bash
docker compose logs -f
```

### 7.4 Тестирование

```bash
curl http://localhost:8000/api/health
```

### 7.5 Остановка

```bash
docker compose down
```

---

## 8. Оценка качества на ground truth

### 8.1 Формат test.txt

Файл `test.txt` содержит ground truth для 11 изображений в формате:
```
1.png
1. Шаг первый
2. Шаг второй
...

2.png
1. Другой шаг
...
```

### 8.2 Скрипт оценки

Создай `evaluate.py`:

```python
import json
import re
from pathlib import Path
from app.pipeline import process_path

def parse_ground_truth(test_file: str) -> dict:
    """Парсинг test.txt в словарь {filename: [steps]}."""
    ground_truth = {}
    current_file = None
    current_steps = []

    with open(test_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                if current_file and current_steps:
                    ground_truth[current_file] = current_steps
                current_file = None
                current_steps = []
            elif line.endswith('.png') or line.endswith('.jpg'):
                current_file = line
            elif re.match(r'^\d+\.', line):
                current_steps.append(line)

    if current_file and current_steps:
        ground_truth[current_file] = current_steps

    return ground_truth

def evaluate(results_file: str, ground_truth_file: str):
    """Оценка результатов против ground truth."""

    # Загрузка результатов
    with open(results_file) as f:
        results = json.load(f)

    # Парсинг ground truth
    gt = parse_ground_truth(ground_truth_file)

    print(f"Ground truth files: {len(gt)}")
    print(f"Result files: {len(results['results'])}")

    # Метрики
    total_gt_steps = 0
    total_extracted_steps = 0
    matched_files = 0

    for filename, gt_steps in gt.items():
        total_gt_steps += len(gt_steps)

        # Найти соответствующий результат
        for result in results['results']:
            if filename in result['source_file']:
                matched_files += 1
                total_extracted_steps += len(result['steps'])

                print(f"\n{filename}:")
                print(f"  Ground truth: {len(gt_steps)} steps")
                print(f"  Extracted: {len(result['steps'])} steps")
                break

    print(f"\n{'='*40}")
    print(f"METRICS")
    print(f"{'='*40}")
    print(f"Files matched: {matched_files}/{len(gt)}")
    print(f"Total GT steps: {total_gt_steps}")
    print(f"Total extracted: {total_extracted_steps}")
    print(f"Step coverage: {total_extracted_steps/total_gt_steps*100:.1f}%")

if __name__ == "__main__":
    evaluate("results.json", "docs/test.txt")
```

Запуск:
```bash
python evaluate.py
```

---

## 9. Типичные проблемы и решения

### CUDA out of memory

```bash
# Уменьшить batch size / размер изображения
# В app/preprocessing.py:
MAX_DIMENSION = 1024  # вместо 1280
```

### Модель долго загружается

Первая загрузка качает ~4GB. После этого модель кэшируется в:
- Windows: `C:\Users\<user>\.cache\huggingface`
- Linux: `~/.cache/huggingface`

### Низкое качество распознавания

1. Проверь препроцессинг изображения
2. Попробуй другой промпт в `app/prompts.py`
3. Включи OCR как fallback

### API не отвечает

```bash
# Проверь что сервер запущен
curl http://localhost:8000/api/health

# Проверь логи
# Ctrl+C на терминале с uvicorn покажет ошибки
```

---

## 10. Чеклист для презентации

- [ ] GPU работает (`nvidia-smi`)
- [ ] Зависимости установлены (`pip list | grep torch`)
- [ ] Модель загружена (первый запуск)
- [ ] API сервер запускается
- [ ] Health check проходит
- [ ] Одно изображение обрабатывается
- [ ] Пакетная обработка работает
- [ ] Результаты сохраняются в JSON
- [ ] Swagger UI доступен (http://localhost:8000/docs)

---

## Быстрый старт (TL;DR)

```bash
# 1. Активировать venv
venv\Scripts\activate

# 2. Установить зависимости (первый раз)
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt

# 3. Запустить API
uvicorn main:app --reload

# 4. Тестировать
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/extract -F "file=@image.png"

# 5. Пакетная обработка
python batch_process.py -i ./docs -o results.json -v
```
