# План реализации: обработка всех форматов диаграмм

## Контекст

Три набора данных:
- `docs/Диаграммы. 2 часть/` — 155 PNG изображений + 11 тестовых с ground truth в test.txt
- `docs/Диаграммы/Диаграммы/` — смешанные форматы: .drawio(18), .puml(13), .plantuml(12), .txt(15), .bpmn(4), .svg(5), .dsl(1), .png(7), .jpg(9), .zip(10), .rar(1), .7z(1)
- Документы с встроенными диаграммами:
  - PPTX (2 файла): `презентация проекта.pptx` (6 изображений), `Workshop1.pptx` (48 изображений)
  - DOCX (3 файла, 2 с медиа): `Проект.docx` (9 изображений), остальные без медиа
  - PDF (2 файла): `Workshop2.pdf` (3MB), `презентация.pdf` (1.6MB) — нужна растеризация страниц

**Обработка архивов:** .zip/.rar/.7z распаковываются во временную папку, содержимое обрабатывается рекурсивно.

**Дедупликация:** Если существует архив `Name.zip` И папка `Name/` или `Name_Диаграммы/`, обрабатывается только папка (она уже распакована). Это устраняет дубликаты в текущем датасете.

Важное: PPTX и DOCX — это ZIP архивы. Изображения лежат в `ppt/media/` и `word/media/`. Извлекаем через stdlib `zipfile` — специальных библиотек не нужно. PDF требует PyMuPDF для растеризации страниц.

---

## Структура файлов проекта

```
cv-uml/
├── app/
│   ├── __init__.py
│   ├── models.py              # Pydantic: DiagramStep, ExtractionResult
│   ├── scanner.py             # Рекурсивный поиск файлов в папке + дедупликация архивов
│   ├── router.py              # Маршрутизация по расширению → тип обработки
│   ├── preprocessing.py       # Resize, контраст, инверсия тёмного фона
│   ├── ocr.py                 # Tesseract OCR обёртка
│   ├── prompts.py             # Два промпт-шаблона: image и text
│   ├── postprocessing.py      # Парсинг JSON из ответа LLM + regex fallback
│   ├── converters/
│   │   ├── __init__.py
│   │   ├── drawio.py          # DrawIO XML → текст меток (value attrs из mxCell)
│   │   ├── bpmn.py            # BPMN XML → текст (participants + tasks + gateways + events)
│   │   ├── svg.py             # SVG → PIL Image через cairosvg
│   │   ├── archive.py         # ZIP/RAR/7Z → распаковка во временную папку → рекурсивная обработка
│   │   ├── pptx.py            # PPTX → список PIL Images (извлечь из ZIP ppt/media/)
│   │   ├── docx.py            # DOCX → список PIL Images (извлечь из ZIP word/media/)
│   │   └── pdf.py             # PDF → список PIL Images (растеризация страниц через PyMuPDF)
│   └── pipeline.py            # Оркестратор: detect → convert → LLM → parse
├── main.py                    # FastAPI: POST /api/extract, GET /api/health
├── batch_process.py           # CLI скрипт для пакетной обработки папки
└── requirements.txt
```

---

## Схема маршрутизации

```
Входной файл
│
├─ .png / .jpg ──────────────────→ [Pipeline A] Image
├─ .svg ────────────────────────→ растеризация → [Pipeline A] Image
├─ .png + .txt (пара) ──────────→ [Pipeline A] Image (txt как контекст вместо OCR)
│
├─ .zip / .rar / .7z ───────────→ распаковка во temp → рекурсивная обработка содержимого
├─ .pptx ───────────────────────→ извлечь изображения из ZIP → каждое через [Pipeline A]
├─ .docx ───────────────────────→ извлечь изображения из ZIP → каждое через [Pipeline A]
├─ .pdf ────────────────────────→ растеризация страниц → каждая через [Pipeline A]
│
├─ .drawio ─────────────────────→ extract XML labels → [Pipeline B] Text
├─ .bpmn ───────────────────────→ extract XML structure → [Pipeline B] Text
└─ .puml / .plantuml / .txt / .dsl → [Pipeline B] Text
```

### Pipeline A — Image
```
файл → [конвертация если нужна] → preprocessing → OCR → Multimodal LLM (image + ocr_text) → postprocessing → JSON
```
Для документов: один файл → список изображений → каждое через Pipeline A отдельно.

### Pipeline B — Text
```
файл → [извлечение текста из XML или read] → Text LLM prompt → postprocessing → JSON
```

---

## Извлечение изображений из документов

### PPTX и DOCX
Оба формата — ZIP архивы. Изображения лежат в:
- PPTX: `ppt/media/image*.png|jpg`
- DOCX: `word/media/image*.png|jpg`

Извлекаем через stdlib `zipfile`. Специальных библиотек не нужно.

Фильтр: пропускаем файлы < 10KB (иконки/логотипы) и изображения < 100x100px.

### PDF
PDF нельзя распаковать как ZIP. Используем PyMuPDF (fitz):
растеризация каждой страницы в PNG с resolution 200 DPI → список PIL Images.

### Фильтрация
Из документов извлекаются все изображения. Не все они диаграммы.
Простой фильтр: < 10KB или < 100x100px — пропускаем.
Если изображение пропустилось, но не является процессом — модель выдаст пустой steps, и мы это фиксируем в результате.

---

## Детали каждого модуля

### models.py
```python
class DiagramStep(BaseModel):
    step: int
    role: str | None = None
    action: str

class ExtractionResult(BaseModel):
    source_file: str
    diagram_type: str
    title: str
    steps: list[DiagramStep]
    pipeline_used: str  # "image" или "text"
```

### scanner.py
- Принимает путь к папке
- Рекурсивно собирает все файлы
- Фильтрует по допустимым расширениям: {.png, .jpg, .jpeg, .svg, .drawio, .bpmn, .puml, .plantuml, .txt, .dsl, .pptx, .docx, .pdf, .zip, .rar, .7z}
- **Дедупликация архивов:** если существует `Name.zip` И папка `Name/` или `Name_Диаграммы/`, пропускаем архив
- Обнаруживает парные файлы (png + txt с тем же именем) → объединяет в один FileInput
- Возвращает список FileInput объектов

### router.py
Маппинг расширение → тип:
- IMAGE: .png, .jpg, .jpeg
- SVG: .svg
- ARCHIVE: .zip, .rar, .7z
- XML_DRAWIO: .drawio
- XML_BPMN: .bpmn
- TEXT: .puml, .plantuml, .txt, .dsl
- DOCUMENT_PPTX: .pptx
- DOCUMENT_DOCX: .docx
- DOCUMENT_PDF: .pdf

### converters/drawio.py
DrawIO — это XML с `<mxCell>` элементами. Метки лежат в атрибуте `value`:
```xml
<mxCell value="Создать новую страницу" .../>
```
Парсим: итерируем по всем mxCell, берём value, убираем HTML-теги (в value бывает `<div>`, `<br>`), собираем в список строк.

### converters/bpmn.py
BPMN — XML с namespace `bpmn:`. Ключевые элементы с именами:
- `<bpmn:participant name="Backend">` — роли (swim lanes)
- `<bpmn:task name="Включить клапан">` — задачи
- `<bpmn:exclusiveGateway name="Показания в норме?">` — решения
- `<bpmn:endEvent name="...">` / `<bpmn:startEvent name="...">` — события
- `<bpmn:messageFlow name="...">` — связи

Парсим: собираем participants как роли, tasks+gateways+events как элементы потока. Формируем текст:
```
Участники: Backend, Controller, User
Поток:
- User: Просмотр показаний влажности почвы
- User: [решение] Показания в норме?
- User: Отправить команду
```

### converters/svg.py
Используем cairosvg.svg2png() для растеризации в PNG, потом Image.open(). Результат — PIL Image, далее через Pipeline A.

### converters/archive.py
Обработка архивов: .zip, .rar, .7z

**Логика:**
1. Создаём временную папку в `scratchpad/archives/{hash}`
2. Распаковываем архив:
   - .zip → stdlib `zipfile`
   - .rar → библиотека `rarfile`
   - .7z → библиотека `py7zr`
3. Рекурсивно сканируем содержимое через scanner.py
4. Обрабатываем каждый файл через соответствующий pipeline
5. Очищаем временную папку после обработки

**Дедупликация на уровне scanner.py:** если для архива `Name.zip` существует папка `Name/` или `Name_Диаграммы/`, архив пропускается.

### preprocessing.py
1. Конвертация в RGB (убираем RGBA/palette)
2. Проверка средней яркости — если < 128, инвертируем (для тёмных фонов как 72.png)
3. Resize с сохранением аспект-ратио до max 1024px по длинной стороне
4. Enhance контраст x1.5

### ocr.py
Обёртка над pytesseract.image_to_string(image, lang="rus+eng"). Возвращает строку текста.

### prompts.py
Два шаблона:

**IMAGE_PROMPT** — для Pipeline A:
```
Ты анализируешь изображение диаграммы процесса (может быть BPMN, flowchart, UML, схема от руки и т.д.).

Текст, извлечённый OCR:
{ocr_text}

Извлеки пошаговый алгоритм. Ответь ТОЛЬКО в формате JSON:
{"diagram_type": "...", "title": "...", "steps": [{"step": 1, "role": "роль или null", "action": "действие"}, ...]}
```

**TEXT_PROMPT** — для Pipeline B:
```
Ты анализируешь описание диаграммы (PlantUML код, Structurizr DSL, метки из XML или текстовое описание).

Содержимое:
{content}

Извлеки пошаговый алгоритм процесса. Ответь ТОЛЬКО в формате JSON:
{"diagram_type": "...", "title": "...", "steps": [{"step": 1, "role": "роль или null", "action": "действие"}, ...]}
```

### postprocessing.py
1. Попытка json.loads() на ответе модели
2. Если не парсится — ищем JSON блок через regex: `\{[\s\S]*"steps"[\s\S]*\}`
3. Если всё равно не парсится — regex fallback: извлекаем строки вида "число. текст" как шаги
4. Валидация через Pydantic ExtractionResult

### scanner.py — парные файлы
В папке ДодоПицца каждый .txt имеет парный .png с тем же именем (например, `С1.txt` + `С1.png`).
scanner.py при сборе файлов обнаруживает такие пары и возвращает их как один объект `FileInput(png_path, txt_path)`.
Если пара найдена — обрабатываем через image pipeline, но txt_content подставляем как контекст вместо OCR.

### pipeline.py
Главный оркестратор. Принимает FileInput, возвращает список ExtractionResult (один документ может содержать несколько диаграмм):

1. router.py определяет тип файла
2. **ARCHIVE (.zip/.rar/.7z)** → archive.py → распаковка → рекурсивная обработка содержимого
3. **SVG** → svg.py (растеризация) → далее как image
4. **PPTX** → pptx.py → список изображений → каждое через image pipeline
5. **DOCX** → docx.py → список изображений → каждое через image pipeline
6. **PDF** → pdf.py → список страниц → каждая через image pipeline
7. **DrawIO** → drawio.py → текст меток → text pipeline
8. **BPMN** → bpmn.py → текст структуры → text pipeline
9. **Text (.puml/.plantuml/.txt/.dsl)** → read() → text pipeline
10. **Парные (png + txt)** → preprocessing(png) → контекст из txt → multimodal LLM с IMAGE_PROMPT
11. **Image (.png/.jpg)** → preprocessing → ocr → multimodal LLM с IMAGE_PROMPT
12. postprocessing.py парсит JSON ответ

### main.py (FastAPI)
- POST /api/extract — принимает multipart файл любого формата, запускает pipeline, возвращает JSON (массив результатов для документов)
- GET /api/health — {"status": "ok"}

### batch_process.py
CLI скрипт:
```
python batch_process.py --input-dir docs/ --output-file results.json
```
- scanner.py находит все файлы
- Для каждого вызывает pipeline.py
- Собирает все ExtractionResult в список
- Сохраняет в results.json

---

## requirements.txt
```
fastapi
uvicorn
Pillow
pytesseract
transformers
torch
pydantic
cairosvg
lxml
PyMuPDF
rarfile
py7zr
```
Примечания:
- PPTX и DOCX обрабатываются через stdlib `zipfile` (не требуют доп. библиотек)
- .zip архивы — stdlib `zipfile`
- .rar архивы — библиотека `rarfile`
- .7z архивы — библиотека `py7zr`

---

## Верификация
1. `python batch_process.py --input-dir docs/ --output-file results.json` — должен обработать все файлы без ошибок
2. Проверить results.json — каждый файл должен иметь pipeline_used: "image" или "text"
3. Для 11 test/*.png сравнить steps с ground truth из test.txt
4. `uvicorn main:app` → curl POST с тестовым PNG → получить JSON ответ
