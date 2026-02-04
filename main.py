import base64
import io
import logging
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, Query
from fastapi.responses import JSONResponse, PlainTextResponse, HTMLResponse
from PIL import Image

from app.llm import warmup
from app.models import (
    BatchResult,
    DiagramStep,
    ExtractionResult,
    GenerateRequest,
    GenerateResponse,
)
from app.pipeline import process_path
from app.preprocessing import preprocess_image
from app.prompts import IMAGE_PROMPT, IMAGE_PROMPT_NO_OCR
from app.postprocessing import parse_llm_response
from app.llm import image_inference
from app.ocr import extract_text, is_tesseract_available

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CV-UML",
    description="Extract diagram steps from images and documents",
    version="0.1.0",
)


@app.on_event("startup")
async def startup_event():
    logger.info("Warming up LLM model...")
    if warmup():
        logger.info("Model ready")
    else:
        logger.warning("Model warmup failed - will load on first request")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "model": "Qwen2-VL-2B-Instruct"}


def format_result_text(result: ExtractionResult) -> str:
    """Format result as readable plain text."""
    lines = []
    lines.append(f"{'='*50}")
    lines.append(f"Файл: {result.source_file}")
    if result.diagram_type:
        lines.append(f"Тип: {result.diagram_type}")
    lines.append(f"{'='*50}")
    lines.append("")

    if result.error:
        lines.append(f"ОШИБКА: {result.error}")
        return "\n".join(lines)

    if not result.steps:
        lines.append("Шаги не найдены")
        return "\n".join(lines)

    lines.append("АЛГОРИТМ:")
    lines.append("")

    for step in result.steps:
        num = step.number or "•"
        line = f"  {num}. "
        if step.actor:
            line += f"[{step.actor}] "
        line += step.action or "—"
        if step.target and step.target != step.actor:
            line += f" → {step.target}"
        lines.append(line)

    lines.append("")
    lines.append(f"Всего шагов: {len(result.steps)}")
    if result.confidence:
        lines.append(f"Уверенность: {result.confidence:.0%}")

    return "\n".join(lines)


def format_result_html(result: ExtractionResult) -> str:
    """Format result as HTML page."""
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{result.source_file} - CV-UML</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               max-width: 800px; margin: 40px auto; padding: 20px; background: #1a1a2e; color: #eee; }}
        h1 {{ color: #00d4ff; margin-bottom: 5px; }}
        .type {{ color: #888; margin-bottom: 20px; }}
        .steps {{ background: #16213e; padding: 20px; border-radius: 8px; }}
        .step {{ padding: 10px 15px; margin: 8px 0; background: #0f3460; border-radius: 6px;
                 border-left: 3px solid #00d4ff; }}
        .step-num {{ color: #00d4ff; font-weight: bold; margin-right: 10px; }}
        .actor {{ color: #ffaa00; margin-right: 8px; }}
        .action {{ color: #fff; }}
        .target {{ color: #888; margin-left: 8px; }}
        .note {{ color: #666; font-style: italic; margin-top: 5px; font-size: 0.9em; }}
        .summary {{ margin-top: 20px; color: #888; }}
        .error {{ background: #4a1a1a; border-left-color: #ff4444; }}
    </style>
</head>
<body>
    <h1>{result.source_file}</h1>
    <div class="type">{result.diagram_type or 'Тип не определён'}</div>
"""

    if result.error:
        html += f'<div class="step error">Ошибка: {result.error}</div>'
    elif not result.steps:
        html += '<div class="step">Шаги не найдены</div>'
    else:
        html += '<div class="steps">'
        for step in result.steps:
            html += '<div class="step">'
            html += f'<span class="step-num">{step.number or "•"}.</span>'
            if step.actor:
                html += f'<span class="actor">[{step.actor}]</span>'
            html += f'<span class="action">{step.action or "—"}</span>'
            if step.target and step.target != step.actor:
                html += f'<span class="target">→ {step.target}</span>'
            if step.note and step.note != step.action:
                html += f'<div class="note">{step.note}</div>'
            html += '</div>'
        html += '</div>'

        conf_pct = f"{result.confidence:.0%}" if result.confidence else "—"
        html += f'<div class="summary">Шагов: {len(result.steps)} | Уверенность: {conf_pct}</div>'

    html += "</body></html>"
    return html


@app.post("/api/extract")
async def extract_from_image(
    file: UploadFile = File(...),
    format: str = Query("json", description="Output format: json, text, html")
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        processed = preprocess_image(image)

        # Run OCR if available
        ocr_text = ""
        if is_tesseract_available():
            logger.info("Running OCR...")
            ocr_text = extract_text(image) or ""
            if ocr_text:
                logger.info(f"OCR extracted {len(ocr_text)} chars")

        # Build prompt with or without OCR
        if ocr_text:
            prompt = IMAGE_PROMPT.format(ocr_text=ocr_text)
        else:
            prompt = IMAGE_PROMPT_NO_OCR

        response = image_inference(processed, prompt)
        result = parse_llm_response(response, file.filename or "uploaded_image")

        if format == "text":
            return PlainTextResponse(format_result_text(result))
        elif format == "html":
            return HTMLResponse(format_result_html(result))
        else:
            return result

    except Exception as e:
        logger.exception("Extraction failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/extract/file", response_model=list[ExtractionResult])
async def extract_from_file(file: UploadFile = File(...)):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        results = process_path(tmp_path)

        Path(tmp_path).unlink(missing_ok=True)

        return results

    except Exception as e:
        logger.exception("Extraction failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/extract/batch", response_model=BatchResult)
async def extract_batch(files: list[UploadFile] = File(...)):
    all_results = []
    failed = 0

    for file in files:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
                contents = await file.read()
                tmp.write(contents)
                tmp_path = tmp.name

            results = process_path(tmp_path)
            all_results.extend(results)

            Path(tmp_path).unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"Failed to process {file.filename}: {e}")
            failed += 1
            all_results.append(ExtractionResult(
                source_file=file.filename or "unknown",
                error=str(e),
            ))

    successful = len([r for r in all_results if not r.error])

    return BatchResult(
        total_files=len(files),
        successful=successful,
        failed=failed,
        results=all_results,
    )


@app.post("/api/generate", response_model=GenerateResponse)
async def generate_diagram(request: GenerateRequest):
    try:
        if request.diagram_type == "sequence":
            plantuml = generate_sequence_diagram(request.steps, request.title)
        elif request.diagram_type == "activity":
            plantuml = generate_activity_diagram(request.steps, request.title)
        else:
            plantuml = generate_sequence_diagram(request.steps, request.title)

        png_base64 = render_plantuml(plantuml)

        return GenerateResponse(
            plantuml_code=plantuml,
            png_base64=png_base64,
        )

    except Exception as e:
        logger.exception("Generation failed")
        return GenerateResponse(
            plantuml_code="",
            error=str(e),
        )


def generate_sequence_diagram(steps: list[DiagramStep], title: Optional[str] = None) -> str:
    lines = ["@startuml"]

    if title:
        lines.append(f"title {title}")

    participants = set()
    for step in steps:
        if step.actor:
            participants.add(step.actor)
        if step.target:
            participants.add(step.target)

    for p in sorted(participants):
        safe_name = p.replace(" ", "_")
        lines.append(f'participant "{p}" as {safe_name}')

    lines.append("")

    for step in steps:
        actor = step.actor or "User"
        target = step.target or "System"
        actor_safe = actor.replace(" ", "_")
        target_safe = target.replace(" ", "_")

        lines.append(f"{actor_safe} -> {target_safe}: {step.action}")

        if step.note:
            lines.append(f"note right: {step.note}")

    lines.append("@enduml")
    return "\n".join(lines)


def generate_activity_diagram(steps: list[DiagramStep], title: Optional[str] = None) -> str:
    lines = ["@startuml"]

    if title:
        lines.append(f"title {title}")

    lines.append("start")

    for step in steps:
        action = step.action
        if step.actor:
            action = f"{step.actor}: {action}"
        lines.append(f":{action};")

    lines.append("stop")
    lines.append("@enduml")
    return "\n".join(lines)


def render_plantuml(code: str) -> Optional[str]:
    try:
        import subprocess
        import shutil

        if not shutil.which("java"):
            logger.warning("Java not found, cannot render PlantUML")
            return None

        plantuml_jar = Path("plantuml.jar")
        if not plantuml_jar.exists():
            logger.warning("plantuml.jar not found")
            return None

        with tempfile.NamedTemporaryFile(mode="w", suffix=".puml", delete=False) as f:
            f.write(code)
            puml_path = f.name

        subprocess.run(
            ["java", "-jar", str(plantuml_jar), "-tpng", puml_path],
            check=True,
            capture_output=True,
        )

        png_path = Path(puml_path).with_suffix(".png")
        if png_path.exists():
            with open(png_path, "rb") as f:
                png_data = f.read()
            png_path.unlink()
            Path(puml_path).unlink()
            return base64.b64encode(png_data).decode()

    except Exception as e:
        logger.error(f"PlantUML rendering failed: {e}")

    return None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
