import math

def f(a: list) -> float:    

    print(a)
    x,y = a
    return (x ** 3) * math.exp(-2 * x) - 2.0 * y
    # return 1

def initial_condition() -> tuple:
    """Return the initial condition (x0, y0) = (0, 1)."""
    return (0.0, 1.0)
