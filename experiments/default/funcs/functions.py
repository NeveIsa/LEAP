# functions.py
# Put any functions you want to expose to students here.
# All public functions (not starting with "_") will be auto-registered
# and callable by name via POST /call/{func_name}.

def square(x: float) -> float:
    """Return (x-30)*(x-10)."""
    return (x-10)*(x-30)

def cubic(x: float) -> float:
    """Return x^3."""
    return x * x * x

def rosenbrock(x: float, y: float, a: float = 1.0, b: float = 100.0) -> float:
    """Classic Rosenbrock function f(x, y) = (a-x)^2 + b(y - x^2)^2."""
    return (a - x) ** 2 + b * (y - x * x) ** 2

def quadratic(a: float, b: float, c: float, x: float) -> float:
    """Evaluate a*x^2 + b*x + c at x."""
    return a * x * x + b * x + c

# Utility function(s) for logging arbitrary values from UI
def echo(value):
    """Return the input value unchanged. Useful for logging arbitrary payloads via /call."""
    return value
