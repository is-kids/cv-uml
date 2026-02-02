import io
import logging
from pathlib import Path
from typing import Optional, Union

from PIL import Image

logger = logging.getLogger(__name__)

try:
    import cairosvg
    CAIROSVG_AVAILABLE = True
except (ImportError, OSError):
    CAIROSVG_AVAILABLE = False
    logger.warning("cairosvg not available - SVG rendering disabled")


def render_svg(
    source: Union[str, Path, bytes],
    scale: float = 2.0,
    background_color: str = "white",
) -> Optional[Image.Image]:
    if not CAIROSVG_AVAILABLE:
        logger.error("cairosvg not available - install Cairo library")
        return None

    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            logger.error(f"SVG file not found: {path}")
            return None
        svg_data = path.read_bytes()
    else:
        svg_data = source

    try:
        png_data = cairosvg.svg2png(
            bytestring=svg_data,
            scale=scale,
            background_color=background_color,
        )
        return Image.open(io.BytesIO(png_data))
    except Exception as e:
        logger.error(f"Failed to render SVG: {e}")
        return None


def get_svg_dimensions(svg_path: Union[str, Path]) -> Optional[tuple[int, int]]:
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(svg_path)
        root = tree.getroot()

        width = root.get("width", "").replace("px", "")
        height = root.get("height", "").replace("px", "")

        if width and height:
            return int(float(width)), int(float(height))

        viewbox = root.get("viewBox")
        if viewbox:
            parts = viewbox.split()
            if len(parts) == 4:
                return int(float(parts[2])), int(float(parts[3]))
    except Exception as e:
        logger.error(f"Failed to get SVG dimensions: {e}")

    return None
