"""
Moduł do obliczania krzywych Béziera.
Implementuje krzywe wielomianowe i wymierne (NURBS).
"""
from __future__ import annotations

import math
from typing import Sequence


def binomial_coefficient(n: int, k: int) -> int:
    """
    Oblicza symbol Newtona (n nad k) = n! / (k! * (n-k)!)
    """
    if k < 0 or k > n:
        return 0
    if k == 0 or k == n:
        return 1
    # Optymalizacja: wykorzystaj symetrię
    k = min(k, n - k)
    result = 1
    for i in range(k):
        result = result * (n - i) // (i + 1)
    return result


def bernstein_polynomial(n: int, i: int, t: float) -> float:
    """
    Oblicza wartość wielomianu Bernsteina B_{i,n}(t).
    B_{i,n}(t) = (n nad i) * t^i * (1-t)^(n-i)
    
    Args:
        n: stopień wielomianu
        i: indeks wielomianu
        t: parametr z przedziału [0, 1]
    """
    if t < 0.0 or t > 1.0:
        return 0.0
    return binomial_coefficient(n, i) * (t ** i) * ((1 - t) ** (n - i))


def bezier_curve_point(control_points: Sequence[tuple[float, float]], t: float) -> tuple[float, float]:
    """
    Oblicza punkt na krzywej Béziera dla parametru t.
    
    Args:
        control_points: lista punktów kontrolnych [(x0, y0), (x1, y1), ...]
        t: parametr z przedziału [0, 1]
    
    Returns:
        (x, y) - współrzędne punktu na krzywej
    """
    if not control_points:
        return (0.0, 0.0)
    
    n = len(control_points) - 1
    x = 0.0
    y = 0.0
    
    for i, (px, py) in enumerate(control_points):
        b = bernstein_polynomial(n, i, t)
        x += b * px
        y += b * py
    
    return (x, y)


def rational_bezier_curve_point(
    control_points: Sequence[tuple[float, float]],
    weights: Sequence[float],
    t: float
) -> tuple[float, float]:
    """
    Oblicza punkt na wymiernej krzywej Béziera (NURBS) dla parametru t.
    
    Args:
        control_points: lista punktów kontrolnych [(x0, y0), (x1, y1), ...]
        weights: lista wag dla każdego punktu kontrolnego
        t: parametr z przedziału [0, 1]
    
    Returns:
        (x, y) - współrzędne punktu na krzywej
    """
    if not control_points or len(control_points) != len(weights):
        return (0.0, 0.0)
    
    n = len(control_points) - 1
    numerator_x = 0.0
    numerator_y = 0.0
    denominator = 0.0
    
    for i, ((px, py), w) in enumerate(zip(control_points, weights)):
        b = bernstein_polynomial(n, i, t)
        wb = w * b
        numerator_x += wb * px
        numerator_y += wb * py
        denominator += wb
    
    if abs(denominator) < 1e-10:
        return (0.0, 0.0)
    
    return (numerator_x / denominator, numerator_y / denominator)


def generate_bezier_curve(
    control_points: Sequence[tuple[float, float]],
    num_samples: int = 100,
    weights: Sequence[float] | None = None
) -> list[tuple[float, float]]:
    """
    Generuje listę punktów reprezentujących krzywą Béziera.
    
    Args:
        control_points: lista punktów kontrolnych
        num_samples: liczba punktów do wygenerowania
        weights: opcjonalne wagi dla wymiernej krzywej Béziera
    
    Returns:
        lista punktów na krzywej
    """
    if len(control_points) < 2:
        return list(control_points)
    
    curve_points = []
    is_rational = weights is not None and len(weights) == len(control_points)
    
    for i in range(num_samples + 1):
        t = i / num_samples
        if is_rational:
            point = rational_bezier_curve_point(control_points, weights, t)  # type: ignore
        else:
            point = bezier_curve_point(control_points, t)
        curve_points.append(point)
    
    return curve_points
