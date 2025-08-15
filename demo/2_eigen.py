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
    n = 2 #finding the number of rows within the matrix
    x = np.random.randn(n) #nonzero random vector
    x /= np.linalg.norm(x) #normaliing vector to have length 1
    previousLam = 0 #used as reference to check if eigenvalue is close enough to the tol

    for _ in range(maxIterations):
        y = np.array(A(x)) #applying transformation to x
        normY = np.linalg.norm(y) #normalizing vector to have lenght 1 (scaling purposes)
        if normY == 0: #if length of y is already equal to zero 
            return 0, x #eigen value is 0 @ this x
        x = y / normY #setting x to normalized length y (for finding the next approximation)
        lam = x @ np.array(A(x)) #computing the rayleigh quotient to find the eigenvalue
        if abs(lam - previousLam) < tol * (1 + abs(lam)): #comparing the change in the eigenvalue to see if it has converged, then we can assume the vector is stabilized
            return lam, x
        previousLam = lam

    return lam, x

# def deflation(A, lam, v): #deflation formula
#     v = v/np.linalg.norm(v)
#     return (A - lam * np.outer(v,v)).tolist()

def deflation(A, lam, v):
    v = np.asarray(v, dtype=float) 
    v = v / np.linalg.norm(v)

    def B(x):
        x = np.asarray(x, dtype=float).reshape(-1)
        Ax = np.asarray(A(x), dtype=float)
        return (Ax - lam * v * (v @ x)).tolist()
    return B

k, v1 = powerMethod(client.linear)
print("Eigenvalue 1: ", k)
print("Eigenvector 1: ", v1)

B = deflation(client.linear, k, v1)

u, v2 = powerMethod(B)
print("Eigenvalue 2: ", u)
print("Eigenvector 2: ", v2)

