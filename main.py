import base64
import io
import logging
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
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
from app.prompts import IMAGE_PROMPT
from app.postprocessing import parse_llm_response
from app.llm import image_inference

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


@app.post("/api/extract", response_model=ExtractionResult)
async def extract_from_image(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        processed = preprocess_image(image)

        response = image_inference(processed, IMAGE_PROMPT)
        result = parse_llm_response(response, file.filename or "uploaded_image")

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
