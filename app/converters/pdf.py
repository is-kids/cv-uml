import logging
from pathlib import Path
from typing import Optional, Union

from PIL import Image

logger = logging.getLogger(__name__)


def render_pdf_pages(
    pdf_path: Union[str, Path],
    dpi: int = 150,
    first_page: int = 0,
    last_page: Optional[int] = None,
) -> list[tuple[int, Image.Image]]:
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        logger.error(f"PDF file not found: {pdf_path}")
        return []

    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF not installed. Install with: pip install PyMuPDF")
        return []

    pages = []

    try:
        doc = fitz.open(pdf_path)

        if last_page is None:
            last_page = len(doc) - 1

        last_page = min(last_page, len(doc) - 1)
        first_page = max(first_page, 0)

        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        for page_num in range(first_page, last_page + 1):
            try:
                page = doc[page_num]
                pix = page.get_pixmap(matrix=matrix)

                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                pages.append((page_num + 1, img))

            except Exception as e:
                logger.warning(f"Failed to render page {page_num + 1}: {e}")

        doc.close()

    except Exception as e:
        logger.error(f"Failed to process PDF {pdf_path}: {e}")

    return pages


def extract_pdf_images(pdf_path: Union[str, Path]) -> list[tuple[int, Image.Image]]:
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        logger.error(f"PDF file not found: {pdf_path}")
        return []

    try:
        import fitz
    except ImportError:
        logger.error("PyMuPDF not installed")
        return []

    images = []

    try:
        doc = fitz.open(pdf_path)

        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images()

            for img_index, img_info in enumerate(image_list):
                try:
                    xref = img_info[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]

                    import io
                    img = Image.open(io.BytesIO(image_bytes))
                    images.append((page_num + 1, img.copy()))

                except Exception as e:
                    logger.warning(f"Failed to extract image from page {page_num + 1}: {e}")

        doc.close()

    except Exception as e:
        logger.error(f"Failed to extract images from PDF: {e}")

    return images


def get_pdf_page_count(pdf_path: Union[str, Path]) -> int:
    try:
        import fitz
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return 0


def pdf_page_to_image(
    pdf_path: Union[str, Path],
    page_num: int,
    dpi: int = 150,
) -> Optional[Image.Image]:
    pages = render_pdf_pages(pdf_path, dpi=dpi, first_page=page_num, last_page=page_num)
    if pages:
        return pages[0][1]
    return None
