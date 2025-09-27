import jax.numpy as jnp
from jax import jit, grad

zero = 20

def f(x, y):
    """
    2D function for gradient descent optimization.
    f(x,y) = ((x-20)^2 + 10*(y-20)^2) * (5*(x+20)^2 + (y+20)^2) / 100
    """
    v = ((x - zero)**2 + 10*(y - zero)**2) * (5*(x + zero)**2 + (y + zero)**2)
    return v / 100

# Gradient function using JAX
_df_compiled = jit(grad(f, argnums=(0, 1)))

def df(x, y):
    """
    Gradient of the 2D function f(x, y).
    Returns tuple (df/dx, df/dy) at point (x, y).
    """
    # Convert to JAX arrays and ensure float type
    x_jax = jnp.float32(x)
    y_jax = jnp.float32(y)
    grad_result = _df_compiled(x_jax, y_jax)
    return (float(grad_result[0]), float(grad_result[1]))
