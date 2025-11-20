from __future__ import annotations

import math
from typing import List, Sequence

from .image_buffer import ImageBuffer


def mean_filter(image: ImageBuffer, size: int = 3) -> ImageBuffer:
    kernel = [[1.0 for _ in range(size)] for _ in range(size)]
    divisor = size * size
    return _convolve(image, kernel, divisor=divisor)


def median_filter(image: ImageBuffer, size: int = 3) -> ImageBuffer:
    radius = size // 2
    width, height = image.width, image.height
    src = image.data
    new_data = bytearray(len(src))
    for y in range(height):
        for x in range(width):
            neighbors_r = []
            neighbors_g = []
            neighbors_b = []
            for ky in range(-radius, radius + 1):
                for kx in range(-radius, radius + 1):
                    nx = _clamp(x + kx, 0, width - 1)
                    ny = _clamp(y + ky, 0, height - 1)
                    idx = (ny * width + nx) * 3
                    neighbors_r.append(src[idx])
                    neighbors_g.append(src[idx + 1])
                    neighbors_b.append(src[idx + 2])
            neighbors_r.sort()
            neighbors_g.sort()
            neighbors_b.sort()
            idx = len(neighbors_r) // 2
            idx_data = (y * width + x) * 3
            new_data[idx_data] = neighbors_r[idx]
            new_data[idx_data + 1] = neighbors_g[idx]
            new_data[idx_data + 2] = neighbors_b[idx]
    return ImageBuffer(width, height, image.max_value, new_data)


def sobel_edge(image: ImageBuffer) -> ImageBuffer:
    gx_kernel = [
        [-1, 0, 1],
        [-2, 0, 2],
        [-1, 0, 1],
    ]
    gy_kernel = [
        [-1, -2, -1],
        [0, 0, 0],
        [1, 2, 1],
    ]
    radius = 1
    width, height = image.width, image.height
    src = image.data
    new_data = bytearray(len(src))
    for y in range(height):
        for x in range(width):
            accum_r = accum_g = accum_b = 0.0
            accum_r_y = accum_g_y = accum_b_y = 0.0
            for ky in range(-radius, radius + 1):
                for kx in range(-radius, radius + 1):
                    nx = _clamp(x + kx, 0, width - 1)
                    ny = _clamp(y + ky, 0, height - 1)
                    weight_x = gx_kernel[ky + radius][kx + radius]
                    weight_y = gy_kernel[ky + radius][kx + radius]
                    base = (ny * width + nx) * 3
                    r = src[base]
                    g = src[base + 1]
                    b = src[base + 2]
                    accum_r += weight_x * r
                    accum_g += weight_x * g
                    accum_b += weight_x * b
                    accum_r_y += weight_y * r
                    accum_g_y += weight_y * g
                    accum_b_y += weight_y * b
            magnitude = (
                math.sqrt(accum_r**2 + accum_r_y**2),
                math.sqrt(accum_g**2 + accum_g_y**2),
                math.sqrt(accum_b**2 + accum_b_y**2),
            )
            idx = (y * width + x) * 3
            new_data[idx] = image.clamp(magnitude[0])
            new_data[idx + 1] = image.clamp(magnitude[1])
            new_data[idx + 2] = image.clamp(magnitude[2])
    return ImageBuffer(width, height, image.max_value, new_data)


def high_pass_sharpen(image: ImageBuffer) -> ImageBuffer:
    kernel = [
        [0, -1, 0],
        [-1, 5, -1],
        [0, -1, 0],
    ]
    return _convolve(image, kernel)


def gaussian_blur(image: ImageBuffer, sigma: float = 1.0) -> ImageBuffer:
    if sigma <= 0:
        raise ValueError("Sigma must be positive")
    radius = max(1, int(3 * sigma))
    kernel = _gaussian_kernel(radius, sigma)
    temp = _apply_separable(image, kernel, axis="x")
    return _apply_separable(temp, kernel, axis="y")


def custom_convolution(
    image: ImageBuffer,
    kernel: Sequence[Sequence[float]],
    divisor: float | None = None,
    offset: float = 0.0,
) -> ImageBuffer:
    return _convolve(image, kernel, divisor=divisor, offset=offset)


def _convolve(
    image: ImageBuffer,
    kernel: Sequence[Sequence[float]],
    divisor: float | None = None,
    offset: float = 0.0,
) -> ImageBuffer:
    size = len(kernel)
    if size % 2 == 0 or any(len(row) != size for row in kernel):
        raise ValueError("Kernel must be a square matrix with odd dimensions")
    radius = size // 2
    divisor = divisor or sum(sum(row) for row in kernel)
    if divisor == 0:
        divisor = 1
    width, height = image.width, image.height
    src = image.data
    new_data = bytearray(len(src))
    for y in range(height):
        for x in range(width):
            acc = [0.0, 0.0, 0.0]
            for ky in range(size):
                for kx in range(size):
                    nx = _clamp(x + kx - radius, 0, width - 1)
                    ny = _clamp(y + ky - radius, 0, height - 1)
                    weight = kernel[ky][kx]
                    base = (ny * width + nx) * 3
                    acc[0] += weight * src[base]
                    acc[1] += weight * src[base + 1]
                    acc[2] += weight * src[base + 2]
            idx = (y * width + x) * 3
            new_data[idx] = image.clamp(acc[0] / divisor + offset)
            new_data[idx + 1] = image.clamp(acc[1] / divisor + offset)
            new_data[idx + 2] = image.clamp(acc[2] / divisor + offset)
    return ImageBuffer(width, height, image.max_value, new_data)


def _apply_separable(image: ImageBuffer, kernel: Sequence[float], axis: str) -> ImageBuffer:
    radius = len(kernel) // 2
    width, height = image.width, image.height
    src = image.data
    new_data = bytearray(len(src))
    for y in range(height):
        for x in range(width):
            acc = [0.0, 0.0, 0.0]
            for k, weight in enumerate(kernel):
                offset = k - radius
                if axis == "x":
                    nx = _clamp(x + offset, 0, width - 1)
                    ny = y
                else:
                    nx = x
                    ny = _clamp(y + offset, 0, height - 1)
                base = (ny * width + nx) * 3
                acc[0] += weight * src[base]
                acc[1] += weight * src[base + 1]
                acc[2] += weight * src[base + 2]
            idx = (y * width + x) * 3
            new_data[idx] = image.clamp(acc[0])
            new_data[idx + 1] = image.clamp(acc[1])
            new_data[idx + 2] = image.clamp(acc[2])
    return ImageBuffer(width, height, image.max_value, new_data)


def _gaussian_kernel(radius: int, sigma: float) -> List[float]:
    kernel = []
    total = 0.0
    for i in range(-radius, radius + 1):
        weight = math.exp(-(i**2) / (2 * sigma**2))
        kernel.append(weight)
        total += weight
    return [w / total for w in kernel]


def _clamp(value: int, lower: int, upper: int) -> int:
    return max(lower, min(upper, value))

