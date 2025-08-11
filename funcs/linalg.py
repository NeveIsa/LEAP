import numpy as np

def linear(x):
    x = np.array(x).reshape(-1)
    A = np.array([[-1, -3], [-3, -1]])
    out = A @ x
    return out.tolist()
