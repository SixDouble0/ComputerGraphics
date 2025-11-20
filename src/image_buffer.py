from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Iterator, Tuple

Pixel = Tuple[int, int, int]


@dataclass
class ImageBuffer:
    """Simple RGB image container backed by a flat bytearray."""

    width: int
    height: int
    max_value: int
    data: bytearray

    @classmethod
    def from_dimensions(
        cls,
        width: int,
        height: int,
        color: Pixel | None = None,
        max_value: int = 255,
    ) -> "ImageBuffer":
        if width <= 0 or height <= 0:
            raise ValueError("Image dimensions must be positive")
        color = color or (0, 0, 0)
        data = bytearray(width * height * 3)
        r, g, b = color
        for i in range(0, len(data), 3):
            data[i] = r
            data[i + 1] = g
            data[i + 2] = b
        return cls(width, height, max_value, data)

    @classmethod
    def from_pixels(
        cls,
        width: int,
        height: int,
        pixels: Iterable[Pixel],
        max_value: int = 255,
    ) -> "ImageBuffer":
        data = bytearray()
        for r, g, b in pixels:
            data.extend([r, g, b])
        if len(data) != width * height * 3:
            raise ValueError("Pixel data does not match provided dimensions")
        return cls(width, height, max_value, data)

    def copy(self) -> "ImageBuffer":
        return ImageBuffer(self.width, self.height, self.max_value, bytearray(self.data))

    def clamp(self, value: float) -> int:
        return max(0, min(self.max_value, int(round(value))))

    def get_pixel(self, x: int, y: int) -> Pixel:
        self._validate_coordinates(x, y)
        idx = self._offset(x, y)
        return self.data[idx], self.data[idx + 1], self.data[idx + 2]

    def set_pixel(self, x: int, y: int, color: Pixel) -> None:
        self._validate_coordinates(x, y)
        idx = self._offset(x, y)
        r, g, b = color
        self.data[idx] = self.clamp(r)
        self.data[idx + 1] = self.clamp(g)
        self.data[idx + 2] = self.clamp(b)

    def iter_pixels(self) -> Iterator[Pixel]:
        for i in range(0, len(self.data), 3):
            yield self.data[i], self.data[i + 1], self.data[i + 2]

    def apply_point_operation(self, func: Callable[[int, int, int], Pixel]) -> "ImageBuffer":
        new_data = bytearray(len(self.data))
        for i in range(0, len(self.data), 3):
            r, g, b = func(self.data[i], self.data[i + 1], self.data[i + 2])
            new_data[i] = self.clamp(r)
            new_data[i + 1] = self.clamp(g)
            new_data[i + 2] = self.clamp(b)
        return ImageBuffer(self.width, self.height, self.max_value, new_data)

    def to_pillow_image(self):
        from PIL import Image

        return Image.frombytes("RGB", (self.width, self.height), bytes(self.data))

    @classmethod
    def from_pillow_image(cls, image) -> "ImageBuffer":
        rgb_image = image.convert("RGB")
        return cls(rgb_image.width, rgb_image.height, 255, bytearray(rgb_image.tobytes()))

    def _validate_coordinates(self, x: int, y: int) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError("Pixel coordinates out of bounds")

    def _offset(self, x: int, y: int) -> int:
        return (y * self.width + x) * 3

