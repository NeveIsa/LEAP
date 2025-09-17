"""Instructor-facing Monte Carlo helper functions."""

from __future__ import annotations

import math
import random
from typing import Tuple


def random_point_square() -> Tuple[float, float]:
    """Return a random point uniformly sampled from [-1, 1] x [-1, 1]."""

    return (random.uniform(-1, 1), random.uniform(-1, 1))


def is_inside_unit_circle(x: float, y: float) -> bool:
    """Check whether (x, y) lies inside the unit circle."""

    return x * x + y * y <= 1.0


def estimate_pi(samples: int = 10000) -> float:
    """Estimate pi using Monte Carlo sampling within the unit square."""

    if samples <= 0:
        raise ValueError("samples must be positive")

    inside = 0
    for _ in range(samples):
        x, y = random_point_square()
        if is_inside_unit_circle(x, y):
            inside += 1
    return 4.0 * inside / samples


def echo(value):
    """Return the input value unchanged so UIs can log arbitrary payloads."""

    return value
