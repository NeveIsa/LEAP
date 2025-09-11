import math

def f(x: float, y: float) -> float:
    """
    Right-hand side for the textbook IVP:

        y' + 2y = x^3 e^{-2x},   y(0) = 1

    Rewritten as an explicit first-order ODE for Euler's method:

        y' = f(x, y) = x^3 e^{-2x} - 2y

    Args:
        x: Independent variable
        y: Dependent variable value at x

    Returns:
        The derivative dy/dx evaluated at (x, y).
    """
    return (x ** 3) * math.exp(-2 * x) - 2.0 * y

def initial_condition() -> tuple:
    """Return the initial condition (x0, y0) = (0, 1)."""
    return (0.0, 1.0)
