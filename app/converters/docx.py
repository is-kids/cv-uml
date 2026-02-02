import io
import logging
import zipfile
from pathlib import Path
from typing import Union

from PIL import Image

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".emf", ".wmf"}


def extract_docx_images(docx_path: Union[str, Path]) -> list[tuple[int, Image.Image]]:
    docx_path = Path(docx_path)

    if not docx_path.exists():
        logger.error(f"DOCX file not found: {docx_path}")
        return []

    images = []

    try:
        with zipfile.ZipFile(docx_path, "r") as zf:
            media_files = [
                name for name in zf.namelist()
                if name.startswith("word/media/") and
                Path(name).suffix.lower() in IMAGE_EXTENSIONS
            ]

            media_files.sort()

            for i, media_path in enumerate(media_files):
                try:
                    data = zf.read(media_path)
                    img = Image.open(io.BytesIO(data))
                    images.append((i + 1, img.copy()))
                except Exception as e:
                    logger.warning(f"Failed to load image {media_path}: {e}")

    except zipfile.BadZipFile as e:
        logger.error(f"Invalid DOCX file {docx_path}: {e}")
    except Exception as e:
        logger.error(f"Failed to extract DOCX images: {e}")

    return images


def extract_docx_with_context(docx_path: Union[str, Path]) -> list[dict]:
    docx_path = Path(docx_path)

    if not docx_path.exists():
        logger.error(f"DOCX file not found: {docx_path}")
        return []

    try:
        from docx import Document
        from docx.opc.constants import RELATIONSHIP_TYPE as RT
    except ImportError:
        logger.warning("python-docx not available, falling back to simple extraction")
        images = extract_docx_images(docx_path)
        return [{"index": i, "image": img} for i, img in images]

    results = []

    try:
        doc = Document(docx_path)
        image_index = 0

        for para in doc.paragraphs:
            for run in para.runs:
                if run._element.xpath(".//a:blip"):
                    for blip in run._element.xpath(".//a:blip"):
                        embed_id = blip.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
                        if embed_id:
                            try:
                                rel = doc.part.rels[embed_id]
                                image_blob = rel.target_part.blob
                                img = Image.open(io.BytesIO(image_blob))

                                context_text = para.text[:100] if para.text else ""

                                results.append({
                                    "index": image_index + 1,
                                    "image": img.copy(),
                                    "context": context_text,
                                })
                                image_index += 1
                            except Exception as e:
                                logger.warning(f"Failed to extract inline image: {e}")

    except Exception as e:
        logger.error(f"Failed to process DOCX with python-docx: {e}")
        images = extract_docx_images(docx_path)
        return [{"index": i, "image": img} for i, img in images]

    if not results:
        images = extract_docx_images(docx_path)
        return [{"index": i, "image": img} for i, img in images]

    return results
