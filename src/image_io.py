from __future__ import annotations

from pathlib import Path
from typing import Callable

from .image_buffer import ImageBuffer
from .jpeg_io import read_jpeg, write_jpeg
from .ppm import PPMFormatError, read_ppm, write_ppm


class ImageFormatError(RuntimeError):
    pass


def load_image(path: str | Path) -> ImageBuffer:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() in {".ppm"}:
        return read_ppm(path)
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        return read_jpeg(path)
    raise ImageFormatError(f"Unsupported file extension: {path.suffix}")


def save_as_ppm(image: ImageBuffer, path: str | Path, binary: bool = True) -> None:
    write_ppm(image, path, binary=binary)


def save_as_jpeg(image: ImageBuffer, path: str | Path, quality: int = 90) -> None:
    write_jpeg(image, path, quality=quality)

