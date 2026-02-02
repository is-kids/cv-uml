"""Image preprocessing utilities."""

import logging
from typing import Optional

from PIL import Image, ImageEnhance, ImageOps

logger = logging.getLogger(__name__)

# Default max dimension for resizing
MAX_DIMENSION = 1280
MIN_DIMENSION = 224


def resize_image(
    image: Image.Image,
    max_dim: int = MAX_DIMENSION,
    min_dim: int = MIN_DIMENSION,
) -> Image.Image:
    """
    Resize image to fit within max dimensions while maintaining aspect ratio.

    Args:
        image: PIL Image to resize
        max_dim: Maximum dimension (width or height)
        min_dim: Minimum dimension (will upscale if smaller)

    Returns:
        Resized PIL Image
    """
    width, height = image.size

    # Check if resize is needed
    max_current = max(width, height)
    min_current = min(width, height)

    if max_current <= max_dim and min_current >= min_dim:
        return image

    # Calculate new size
    if max_current > max_dim:
        scale = max_dim / max_current
    elif min_current < min_dim:
        scale = min_dim / min_current
    else:
        return image

    new_width = int(width * scale)
    new_height = int(height * scale)

    logger.debug(f"Resizing image from {width}x{height} to {new_width}x{new_height}")
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)


def enhance_contrast(image: Image.Image, factor: float = 1.3) -> Image.Image:
    """
    Enhance image contrast.

    Args:
        image: PIL Image to enhance
        factor: Contrast enhancement factor (1.0 = no change)

    Returns:
        Enhanced PIL Image
    """
    enhancer = ImageEnhance.Contrast(image)
    return enhancer.enhance(factor)


def enhance_sharpness(image: Image.Image, factor: float = 1.2) -> Image.Image:
    """
    Enhance image sharpness.

    Args:
        image: PIL Image to enhance
        factor: Sharpness enhancement factor (1.0 = no change)

    Returns:
        Enhanced PIL Image
    """
    enhancer = ImageEnhance.Sharpness(image)
    return enhancer.enhance(factor)


def is_dark_background(image: Image.Image, threshold: float = 0.4) -> bool:
    """
    Detect if image has a dark background.

    Args:
        image: PIL Image to analyze
        threshold: Brightness threshold (0-1), below which is considered dark

    Returns:
        True if image has dark background
    """
    # Convert to grayscale
    gray = image.convert("L")

    # Sample corners and edges
    width, height = gray.size
    samples = []

    # Sample corners (10% inset)
    margin_x = int(width * 0.1)
    margin_y = int(height * 0.1)

    corners = [
        (margin_x, margin_y),
        (width - margin_x, margin_y),
        (margin_x, height - margin_y),
        (width - margin_x, height - margin_y),
    ]

    for x, y in corners:
        x = max(0, min(x, width - 1))
        y = max(0, min(y, height - 1))
        samples.append(gray.getpixel((x, y)))

    # Calculate average brightness (0-255 -> 0-1)
    avg_brightness = sum(samples) / len(samples) / 255.0
    return avg_brightness < threshold


def invert_dark_background(image: Image.Image) -> Image.Image:
    """
    Invert image if it has a dark background.

    Args:
        image: PIL Image to potentially invert

    Returns:
        Original or inverted PIL Image
    """
    if is_dark_background(image):
        logger.debug("Dark background detected, inverting image")
        # Handle RGBA images
        if image.mode == "RGBA":
            r, g, b, a = image.split()
            rgb = Image.merge("RGB", (r, g, b))
            rgb_inverted = ImageOps.invert(rgb)
            r, g, b = rgb_inverted.split()
            return Image.merge("RGBA", (r, g, b, a))
        elif image.mode == "RGB":
            return ImageOps.invert(image)
        else:
            # Convert to RGB, invert, convert back
            rgb = image.convert("RGB")
            inverted = ImageOps.invert(rgb)
            return inverted.convert(image.mode)
    return image


def convert_to_rgb(image: Image.Image) -> Image.Image:
    """
    Convert image to RGB mode if necessary.

    Args:
        image: PIL Image

    Returns:
        RGB PIL Image
    """
    if image.mode == "RGBA":
        # Create white background
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        return background
    elif image.mode != "RGB":
        return image.convert("RGB")
    return image


def preprocess_image(
    image: Image.Image,
    resize: bool = True,
    enhance: bool = True,
    handle_dark: bool = True,
    max_dim: int = MAX_DIMENSION,
) -> Image.Image:
    """
    Apply full preprocessing pipeline to an image.

    Args:
        image: PIL Image to preprocess
        resize: Whether to resize the image
        enhance: Whether to enhance contrast/sharpness
        handle_dark: Whether to invert dark backgrounds
        max_dim: Maximum dimension for resizing

    Returns:
        Preprocessed PIL Image
    """
    result = image.copy()

    # Handle dark backgrounds first (before other processing)
    if handle_dark:
        result = invert_dark_background(result)

    # Convert to RGB
    result = convert_to_rgb(result)

    # Resize
    if resize:
        result = resize_image(result, max_dim=max_dim)

    # Enhance
    if enhance:
        result = enhance_contrast(result, factor=1.2)
        result = enhance_sharpness(result, factor=1.1)

    return result


def load_and_preprocess(
    path: str,
    **kwargs,
) -> Optional[Image.Image]:
    """
    Load an image from path and preprocess it.

    Args:
        path: Path to image file
        **kwargs: Additional arguments for preprocess_image

    Returns:
        Preprocessed PIL Image or None if loading failed
    """
    try:
        image = Image.open(path)
        return preprocess_image(image, **kwargs)
    except Exception as e:
        logger.error(f"Failed to load/preprocess image {path}: {e}")
        return None
