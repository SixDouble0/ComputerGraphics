from __future__ import annotations

from .image_buffer import ImageBuffer


def compute_histogram(image: ImageBuffer, channel: int = 0) -> list[int]:
    """
    Compute histogram for a single channel (0=R, 1=G, 2=B).
    Returns list of 256 integers representing pixel count for each intensity level.
    """
    hist = [0] * 256
    data = image.data
    for i in range(channel, len(data), 3):
        hist[data[i]] += 1
    return hist


def compute_histogram_grayscale(image: ImageBuffer) -> list[int]:
    """Compute histogram for grayscale image (using luminance)."""
    hist = [0] * 256
    data = image.data
    for i in range(0, len(data), 3):
        r, g, b = data[i], data[i + 1], data[i + 2]
        gray = int(0.2126 * r + 0.7152 * g + 0.0722 * b)
        hist[gray] += 1
    return hist


def histogram_stretch(image: ImageBuffer, channel: int | None = 0) -> ImageBuffer:
    """
    Normalize image by stretching histogram to full range [0, 255].
    Works on a single channel or all channels if channel is None.
    """
    if channel in (0, 1, 2):
        return _stretch_single_channel(image, channel)
    # Stretch all channels independently
    result = image.copy()
    for ch in range(3):
        result = _stretch_single_channel(result, ch)
    return result


def _stretch_single_channel(image: ImageBuffer, channel: int) -> ImageBuffer:
    """Stretch histogram for a single channel."""
    hist = compute_histogram(image, channel)
    # Find min and max non-zero values
    min_val = 0
    max_val = 255
    for i in range(256):
        if hist[i] > 0:
            min_val = i
            break
    for i in range(255, -1, -1):
        if hist[i] > 0:
            max_val = i
            break
    if min_val >= max_val:
        return image.copy()
    # Linear stretch: new = (old - min) * 255 / (max - min)
    scale = 255.0 / (max_val - min_val)
    new_data = bytearray(len(image.data))
    for i in range(channel, len(image.data), 3):
        old_val = image.data[i]
        new_val = int((old_val - min_val) * scale)
        new_data[i] = image.clamp(new_val)
    # Copy other channels
    for ch in range(3):
        if ch != channel:
            for i in range(ch, len(image.data), 3):
                new_data[i] = image.data[i]
    return ImageBuffer(image.width, image.height, image.max_value, new_data)


def histogram_equalization(image: ImageBuffer, channel: int | None = 0) -> ImageBuffer:
    """
    Equalize histogram to achieve uniform distribution.
    Works on a single channel or all channels if channel is None.
    """
    if channel in (0, 1, 2):
        return _equalize_single_channel(image, channel)
    # Equalize all channels independently
    result = image.copy()
    for ch in range(3):
        result = _equalize_single_channel(result, ch)
    return result


def _equalize_single_channel(image: ImageBuffer, channel: int) -> ImageBuffer:
    """Equalize histogram for a single channel."""
    hist = compute_histogram(image, channel)
    total_pixels = image.width * image.height
    if total_pixels == 0:
        return image.copy()
    # Compute cumulative distribution function (CDF)
    cdf = [0] * 256
    cdf[0] = hist[0]
    for i in range(1, 256):
        cdf[i] = cdf[i - 1] + hist[i]
    # Normalize CDF to [0, 255]
    cdf_min = min(cdf[i] for i in range(256) if hist[i] > 0)
    if cdf_min >= total_pixels:
        return image.copy()
    scale = 255.0 / (total_pixels - cdf_min)
    # Create lookup table
    lut = [0] * 256
    for i in range(256):
        lut[i] = int((cdf[i] - cdf_min) * scale)
    # Apply lookup table
    new_data = bytearray(len(image.data))
    for i in range(channel, len(image.data), 3):
        old_val = image.data[i]
        new_data[i] = image.clamp(lut[old_val])
    # Copy other channels
    for ch in range(3):
        if ch != channel:
            for i in range(ch, len(image.data), 3):
                new_data[i] = image.data[i]
    return ImageBuffer(image.width, image.height, image.max_value, new_data)

