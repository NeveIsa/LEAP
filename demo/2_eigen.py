import sys
import numpy as np
sys.path.append("../client")
sys.path.append("client")

from client import RPCClient, RPCError
from fire import Fire

SERVER_URL = "http://localhost:9000"
STUDENT_ID = "s001" # Change to your assigned ID
EXPERIMENT = "eigen"

def powerMethod(A, maxIterations = 1000, tol = 1e-10):
    n = A.shape[0]
    x = np.random.randn(n)
    x /= np.linalg.norm(x)
    previousLam = 0

    for _ in range(maxIterations):
        y = A @ x
        normY = np.linalg.norm(y)
        if normY == 0:
            return 0, x
        x = y / normY
        lam = x @ (A @ x)
        if abs(lam - previousLam) < tol * (1 + abs(lam)):
            return lam, x
        previousLam = lam

    return lam, x

def deflation(A, lam, v):
    v = v/np.linalg.norm(v)
    return A - lam * np.outer(v,v)

A = np.array([[-1.0, -3.0], [-3.0, -1.0]], dtype=float)

k, v1 = powerMethod(A)
print("Eigenvalue 1: ", k)
print("Eigenvector 1: ", v1)

B = deflation(A, k, v1)

u, v2 = powerMethod(B)
print("Eigenvalue 2: ", u)
print("Eigenvector 2: ", v2)
