from __future__ import annotations

from typing import Iterator

from .image_buffer import ImageBuffer


class PPMFormatError(RuntimeError):
    pass


def read_ppm(path: str) -> ImageBuffer:
    with open(path, "rb") as stream:
        magic, width, height, max_value = _read_header(stream)
        total_values = width * height * 3
        if magic == "P3":
            data = _read_ascii_pixels(stream, total_values, max_value)
        elif magic == "P6":
            data = _read_binary_pixels(stream, total_values, max_value)
        else:
            raise PPMFormatError(f"Unsupported PPM magic number: {magic}")
    return ImageBuffer(width, height, min(max_value, 255), data)


def write_ppm(image: ImageBuffer, path: str, binary: bool = True) -> None:
    magic = "P6" if binary else "P3"
    header = f"{magic}\n{image.width} {image.height}\n{image.max_value}\n"
    with open(path, "wb") as stream:
        stream.write(header.encode("ascii"))
        if binary:
            stream.write(bytes(image.data))
        else:
            _write_ascii_pixels(image, stream)


def _read_header(stream) -> tuple[str, int, int, int]:
    magic = stream.read(2).decode("ascii")
    if magic not in {"P3", "P6"}:
        raise PPMFormatError("File is not a valid PPM (expected P3 or P6)")
    tokens = list(_read_tokens(stream, 3))
    if len(tokens) < 3:
        raise PPMFormatError("PPM header is incomplete")
    width, height, max_value = map(int, tokens)
    return magic, width, height, max_value


def _read_tokens(stream, required: int) -> Iterator[str]:
    token = bytearray()
    comment = False
    while required:
        chunk = stream.read(1)
        if not chunk:
            break
        ch = chunk[0]
        if comment:
            if ch in (10, 13):
                comment = False
            continue
        if ch == 35:
            comment = True
            continue
        if ch in b" \t\r\n\v\f":
            if token:
                yield token.decode("ascii")
                token.clear()
                required -= 1
        else:
            token.append(ch)
    if token and required > 0:
        yield token.decode("ascii")


def _read_ascii_pixels(stream, total_values: int, max_value: int) -> bytearray:
    data = bytearray(total_values)
    idx = 0
    for token in _ascii_value_generator(stream):
        if idx >= total_values:
            break
        value = int(token)
        data[idx] = _normalize_value(value, max_value)
        idx += 1
    if idx != total_values:
        raise PPMFormatError("Unexpected end of ASCII pixel data")
    return data


def _ascii_value_generator(stream) -> Iterator[str]:
    token = bytearray()
    comment = False
    while True:
        chunk = stream.read(4096)
        if not chunk:
            break
        for ch in chunk:
            if comment:
                if ch in (10, 13):
                    comment = False
                continue
            if ch == 35:
                comment = True
                continue
            if chr(ch).isspace():
                if token:
                    yield token.decode("ascii")
                    token.clear()
            else:
                token.append(ch)
    if token:
        yield token.decode("ascii")


def _read_binary_pixels(stream, total_values: int, max_value: int) -> bytearray:
    raw = stream.read(total_values)
    if len(raw) != total_values:
        raise PPMFormatError("Binary pixel data shorter than expected")
    if max_value == 255:
        return bytearray(raw)
    scale = 255 / max_value
    return bytearray(int(round(b * scale)) for b in raw)


def _write_ascii_pixels(image: ImageBuffer, stream) -> None:
    row_length = image.width * 3
    for y in range(image.height):
        row_values = []
        offset = y * row_length
        for x in range(0, row_length, 3):
            r = image.data[offset + x]
            g = image.data[offset + x + 1]
            b = image.data[offset + x + 2]
            row_values.append(f"{r} {g} {b}")
        stream.write((" ".join(row_values) + "\n").encode("ascii"))


def _normalize_value(value: int, max_value: int) -> int:
    if max_value == 255:
        return value
    return int(round((value / max_value) * 255))

