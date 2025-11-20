from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image

from .image_buffer import ImageBuffer


def read_jpeg(path: str | Path) -> ImageBuffer:
    with Image.open(path) as img:
        return ImageBuffer.from_pillow_image(img)


def write_jpeg(image: ImageBuffer, path: str | Path, quality: int = 90) -> None:
    quality = max(1, min(95, quality))
    pil_image = image.to_pillow_image()
    pil_image.save(path, format="JPEG", quality=quality, optimize=True)

