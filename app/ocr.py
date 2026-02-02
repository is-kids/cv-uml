import logging
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)

_tesseract_available = None


def is_tesseract_available() -> bool:
    global _tesseract_available

    if _tesseract_available is not None:
        return _tesseract_available

    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        _tesseract_available = True
    except Exception:
        _tesseract_available = False

    return _tesseract_available


def extract_text(image: Image.Image, lang: str = "eng+rus") -> Optional[str]:
    if not is_tesseract_available():
        logger.warning("Tesseract not available")
        return None

    try:
        import pytesseract

        if image.mode != "RGB":
            image = image.convert("RGB")

        text = pytesseract.image_to_string(image, lang=lang)
        return text.strip() if text else None

    except Exception as e:
        logger.error(f"OCR failed: {e}")
        return None


def extract_text_with_boxes(image: Image.Image, lang: str = "eng+rus") -> list[dict]:
    if not is_tesseract_available():
        return []

    try:
        import pytesseract

        if image.mode != "RGB":
            image = image.convert("RGB")

        data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)

        results = []
        n_boxes = len(data["text"])

        for i in range(n_boxes):
            text = data["text"][i].strip()
            conf = int(data["conf"][i])

            if text and conf > 0:
                results.append({
                    "text": text,
                    "confidence": conf / 100.0,
                    "x": data["left"][i],
                    "y": data["top"][i],
                    "width": data["width"][i],
                    "height": data["height"][i],
                })

        return results

    except Exception as e:
        logger.error(f"OCR with boxes failed: {e}")
        return []


def enhance_for_ocr(image: Image.Image) -> Image.Image:
    from PIL import ImageEnhance, ImageFilter

    img = image.convert("L")

    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)

    img = img.filter(ImageFilter.SHARPEN)

    threshold = 128
    img = img.point(lambda p: 255 if p > threshold else 0)

    return img
