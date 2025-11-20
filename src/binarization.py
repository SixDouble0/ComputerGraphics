from __future__ import annotations

import math

from .image_buffer import ImageBuffer
from .histogram import compute_histogram_grayscale


def threshold_manual(image: ImageBuffer, threshold: int) -> ImageBuffer:
    """
    Binaryzacja z ręcznie ustawionym progiem.
    Piksele >= threshold -> 255 (biały), < threshold -> 0 (czarny).
    """
    if not (0 <= threshold <= 255):
        raise ValueError("Threshold must be in range [0, 255]")
    new_data = bytearray(len(image.data))
    for i in range(0, len(image.data), 3):
        r, g, b = image.data[i], image.data[i + 1], image.data[i + 2]
        gray = int(0.2126 * r + 0.7152 * g + 0.0722 * b)
        value = 255 if gray >= threshold else 0
        new_data[i] = value
        new_data[i + 1] = value
        new_data[i + 2] = value
    return ImageBuffer(image.width, image.height, image.max_value, new_data)


def threshold_percent_black(image: ImageBuffer, percent: float) -> ImageBuffer:
    """
    Procentowa selekcja czarnego (Percent Black Selection).
    Ustawia próg tak, aby określony procent pikseli było czarnych.
    """
    if not (0.0 <= percent <= 100.0):
        raise ValueError("Percent must be in range [0, 100]")
    hist = compute_histogram_grayscale(image)
    total_pixels = image.width * image.height
    target_black = int(total_pixels * percent / 100.0)
    cumulative = 0
    threshold = 0
    for i in range(256):
        cumulative += hist[i]
        if cumulative >= target_black:
            threshold = i
            break
    return threshold_manual(image, threshold)


def threshold_mean_iterative(image: ImageBuffer, max_iterations: int = 100) -> ImageBuffer:
    """
    Selekcja iteratywna średniej (Mean Iterative Selection).
    Iteracyjnie wyznacza próg jako średnią wartości pikseli po obu stronach progu.
    """
    hist = compute_histogram_grayscale(image)
    # Initial threshold: średnia wszystkich wartości
    total_sum = sum(i * hist[i] for i in range(256))
    total_pixels = image.width * image.height
    if total_pixels == 0:
        return threshold_manual(image, 128)
    threshold = int(total_sum / total_pixels)
    for _ in range(max_iterations):
        # Oblicz średnie po obu stronach progu
        sum_below = sum(i * hist[i] for i in range(threshold))
        count_below = sum(hist[i] for i in range(threshold))
        sum_above = sum(i * hist[i] for i in range(threshold, 256))
        count_above = sum(hist[i] for i in range(threshold, 256))
        if count_below == 0 or count_above == 0:
            break
        mean_below = sum_below / count_below
        mean_above = sum_above / count_above
        new_threshold = int((mean_below + mean_above) / 2)
        if new_threshold == threshold:
            break
        threshold = new_threshold
    return threshold_manual(image, threshold)


def threshold_entropy(image: ImageBuffer) -> ImageBuffer:
    """
    Selekcja entropii (Entropy Selection).
    Wybiera próg maksymalizujący entropię po obu stronach progu.
    """
    hist = compute_histogram_grayscale(image)
    total_pixels = image.width * image.height
    if total_pixels == 0:
        return threshold_manual(image, 128)
    # Normalize histogram to probabilities
    prob = [h / total_pixels for h in hist]
    best_threshold = 128
    max_entropy = -float("inf")
    for t in range(1, 255):
        # Probability of background and foreground
        p_bg = sum(prob[i] for i in range(t))
        p_fg = sum(prob[i] for i in range(t, 256))
        if p_bg == 0 or p_fg == 0:
            continue
        # Entropy of background
        entropy_bg = 0.0
        for i in range(t):
            if prob[i] > 0:
                p_i_bg = prob[i] / p_bg
                entropy_bg -= p_i_bg * math.log2(p_i_bg)
        # Entropy of foreground
        entropy_fg = 0.0
        for i in range(t, 256):
            if prob[i] > 0:
                p_i_fg = prob[i] / p_fg
                entropy_fg -= p_i_fg * math.log2(p_i_fg)
        total_entropy = entropy_bg + entropy_fg
        if total_entropy > max_entropy:
            max_entropy = total_entropy
            best_threshold = t
    return threshold_manual(image, best_threshold)


def threshold_minimum_error(image: ImageBuffer) -> ImageBuffer:
    """
    Błąd minimalny (Minimum Error).
    Wybiera próg minimalizujący błąd klasyfikacji przy założeniu rozkładu normalnego.
    """
    hist = compute_histogram_grayscale(image)
    total_pixels = image.width * image.height
    if total_pixels == 0:
        return threshold_manual(image, 128)
    # Compute mean and variance for all pixels
    mean_all = sum(i * hist[i] for i in range(256)) / total_pixels
    variance_all = sum((i - mean_all) ** 2 * hist[i] for i in range(256)) / total_pixels
    best_threshold = 128
    min_error = float("inf")
    for t in range(1, 255):
        # Background (below threshold)
        count_bg = sum(hist[i] for i in range(t))
        if count_bg == 0:
            continue
        mean_bg = sum(i * hist[i] for i in range(t)) / count_bg
        variance_bg = sum((i - mean_bg) ** 2 * hist[i] for i in range(t)) / count_bg if count_bg > 0 else 0
        # Foreground (above threshold)
        count_fg = sum(hist[i] for i in range(t, 256))
        if count_fg == 0:
            continue
        mean_fg = sum(i * hist[i] for i in range(t, 256)) / count_fg
        variance_fg = sum((i - mean_fg) ** 2 * hist[i] for i in range(t, 256)) / count_fg if count_fg > 0 else 0
        # Error function (simplified minimum error criterion)
        if variance_bg <= 0 or variance_fg <= 0:
            continue
        p_bg = count_bg / total_pixels
        p_fg = count_fg / total_pixels
        error = p_bg * math.log(variance_bg) + p_fg * math.log(variance_fg) - 2 * (p_bg * math.log(p_bg) + p_fg * math.log(p_fg)) if p_bg > 0 and p_fg > 0 else float("inf")
        if error < min_error:
            min_error = error
            best_threshold = t
    return threshold_manual(image, best_threshold)


def threshold_fuzzy_minimum_error(image: ImageBuffer) -> ImageBuffer:
    """
    Metoda rozmytego błędu minimalnego (Fuzzy Minimum Error).
    Używa rozmytej klasyfikacji pikseli do wyznaczenia progu.
    """
    hist = compute_histogram_grayscale(image)
    total_pixels = image.width * image.height
    if total_pixels == 0:
        return threshold_manual(image, 128)
    best_threshold = 128
    min_error = float("inf")
    for t in range(1, 255):
        # Fuzzy membership functions (simplified)
        # Background membership: decreases as value increases
        # Foreground membership: increases as value increases
        sum_bg = 0.0
        sum_fg = 0.0
        weighted_sum_bg = 0.0
        weighted_sum_fg = 0.0
        for i in range(256):
            if i < t:
                # Background membership (higher for lower values)
                mu_bg = 1.0 - (i / t) if t > 0 else 1.0
                mu_fg = 0.0
            else:
                # Foreground membership (higher for higher values)
                mu_bg = 0.0
                mu_fg = (i - t) / (255 - t) if t < 255 else 1.0
            count = hist[i]
            sum_bg += mu_bg * count
            sum_fg += mu_fg * count
            weighted_sum_bg += mu_bg * i * count
            weighted_sum_fg += mu_fg * i * count
        if sum_bg == 0 or sum_fg == 0:
            continue
        mean_bg = weighted_sum_bg / sum_bg
        mean_fg = weighted_sum_fg / sum_fg
        # Compute fuzzy error
        error = 0.0
        for i in range(256):
            if i < t:
                mu_bg = 1.0 - (i / t) if t > 0 else 1.0
                error += mu_bg * (i - mean_bg) ** 2 * hist[i]
            else:
                mu_fg = (i - t) / (255 - t) if t < 255 else 1.0
                error += mu_fg * (i - mean_fg) ** 2 * hist[i]
        error /= total_pixels
        if error < min_error:
            min_error = error
            best_threshold = t
    return threshold_manual(image, best_threshold)


