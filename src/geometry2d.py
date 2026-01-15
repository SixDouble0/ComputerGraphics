from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin
from typing import Iterable, Sequence


Mat3 = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
Vec2 = tuple[float, float]


def mat3_identity() -> Mat3:
    return (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    )


def mat3_mul(a: Mat3, b: Mat3) -> Mat3:
    return (
        (
            a[0][0] * b[0][0] + a[0][1] * b[1][0] + a[0][2] * b[2][0],
            a[0][0] * b[0][1] + a[0][1] * b[1][1] + a[0][2] * b[2][1],
            a[0][0] * b[0][2] + a[0][1] * b[1][2] + a[0][2] * b[2][2],
        ),
        (
            a[1][0] * b[0][0] + a[1][1] * b[1][0] + a[1][2] * b[2][0],
            a[1][0] * b[0][1] + a[1][1] * b[1][1] + a[1][2] * b[2][1],
            a[1][0] * b[0][2] + a[1][1] * b[1][2] + a[1][2] * b[2][2],
        ),
        (
            a[2][0] * b[0][0] + a[2][1] * b[1][0] + a[2][2] * b[2][0],
            a[2][0] * b[0][1] + a[2][1] * b[1][1] + a[2][2] * b[2][1],
            a[2][0] * b[0][2] + a[2][1] * b[1][2] + a[2][2] * b[2][2],
        ),
    )


def mat3_apply_to_point(m: Mat3, p: Vec2) -> Vec2:
    x, y = p
    hx = m[0][0] * x + m[0][1] * y + m[0][2] * 1.0
    hy = m[1][0] * x + m[1][1] * y + m[1][2] * 1.0
    hw = m[2][0] * x + m[2][1] * y + m[2][2] * 1.0
    if abs(hw) < 1e-12:
        return (hx, hy)
    return (hx / hw, hy / hw)


def mat3_translate(dx: float, dy: float) -> Mat3:
    return (
        (1.0, 0.0, dx),
        (0.0, 1.0, dy),
        (0.0, 0.0, 1.0),
    )


def mat3_rotate_degrees(angle_deg: float) -> Mat3:
    a = radians(angle_deg)
    c = cos(a)
    s = sin(a)
    return (
        (c, -s, 0.0),
        (s, c, 0.0),
        (0.0, 0.0, 1.0),
    )


def mat3_scale(sx: float, sy: float) -> Mat3:
    return (
        (sx, 0.0, 0.0),
        (0.0, sy, 0.0),
        (0.0, 0.0, 1.0),
    )


def around_point(point: Vec2, transform: Mat3) -> Mat3:
    """Builds T(p) * transform * T(-p)."""
    px, py = point
    return mat3_mul(mat3_translate(px, py), mat3_mul(transform, mat3_translate(-px, -py)))


def distance2(a: Vec2, b: Vec2) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def point_in_polygon(point: Vec2, polygon: Sequence[Vec2]) -> bool:
    """Ray casting algorithm. Polygon may be convex or concave."""
    x, y = point
    inside = False
    n = len(polygon)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersect = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi)
        if intersect:
            inside = not inside
        j = i
    return inside


@dataclass
class Polygon:
    points: list[Vec2]
    name: str = "Polygon"

    def transformed(self, m: Mat3) -> "Polygon":
        return Polygon(points=[mat3_apply_to_point(m, p) for p in self.points], name=self.name)

    def apply(self, m: Mat3) -> None:
        self.points = [mat3_apply_to_point(m, p) for p in self.points]

    def centroid(self) -> Vec2:
        if not self.points:
            return (0.0, 0.0)
        sx = sum(p[0] for p in self.points)
        sy = sum(p[1] for p in self.points)
        n = len(self.points)
        return (sx / n, sy / n)

    def hit_test(self, p: Vec2, radius: float = 8.0) -> bool:
        if point_in_polygon(p, self.points):
            return True
        r2 = radius * radius
        return any(distance2(p, v) <= r2 for v in self.points)

    def nearest_vertex(self, p: Vec2, radius: float = 10.0) -> int | None:
        if not self.points:
            return None
        r2 = radius * radius
        best_i = None
        best_d2 = 1e30
        for i, v in enumerate(self.points):
            d2 = distance2(p, v)
            if d2 <= r2 and d2 < best_d2:
                best_i = i
                best_d2 = d2
        return best_i

    def to_dict(self) -> dict:
        return {"type": "polygon", "name": self.name, "points": [{"x": x, "y": y} for x, y in self.points]}

    @staticmethod
    def from_dict(data: dict) -> "Polygon":
        pts = [(float(p["x"]), float(p["y"])) for p in data.get("points", [])]
        return Polygon(points=pts, name=str(data.get("name", "Polygon")))


