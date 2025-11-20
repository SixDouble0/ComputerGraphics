from __future__ import annotations

from typing import Callable

from .image_buffer import ImageBuffer


def _scalar_point_op(image: ImageBuffer, func: Callable[[float], float]) -> ImageBuffer:
    new_data = bytearray(len(image.data))
    for i, value in enumerate(image.data):
        new_data[i] = image.clamp(func(value))
    return ImageBuffer(image.width, image.height, image.max_value, new_data)


def add_constant(image: ImageBuffer, value: float) -> ImageBuffer:
    return _scalar_point_op(image, lambda channel: channel + value)


def subtract_constant(image: ImageBuffer, value: float) -> ImageBuffer:
    return _scalar_point_op(image, lambda channel: channel - value)


def multiply(image: ImageBuffer, factor: float) -> ImageBuffer:
    return _scalar_point_op(image, lambda channel: channel * factor)


def divide(image: ImageBuffer, divisor: float) -> ImageBuffer:
    if divisor == 0:
        raise ZeroDivisionError("Divisor must not be zero")
    return _scalar_point_op(image, lambda channel: channel / divisor)


def change_brightness(image: ImageBuffer, delta: float) -> ImageBuffer:
    return add_constant(image, delta)


def linear_color_scale(image: ImageBuffer, scale_r: float, scale_g: float, scale_b: float) -> ImageBuffer:
    new_data = bytearray(len(image.data))
    for i in range(0, len(image.data), 3):
        new_data[i] = image.clamp(image.data[i] * scale_r)
        new_data[i + 1] = image.clamp(image.data[i + 1] * scale_g)
        new_data[i + 2] = image.clamp(image.data[i + 2] * scale_b)
    return ImageBuffer(image.width, image.height, image.max_value, new_data)


def grayscale_average(image: ImageBuffer) -> ImageBuffer:
    return image.apply_point_operation(
        lambda r, g, b: (int((r + g + b) / 3),) * 3
    )


def grayscale_luminance(image: ImageBuffer) -> ImageBuffer:
    return image.apply_point_operation(
        lambda r, g, b: (int(0.2126 * r + 0.7152 * g + 0.0722 * b),) * 3
    )

