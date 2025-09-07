import sys
sys.path.append("../client")
sys.path.append("client")

from client import RPCClient, RPCError
from fire import Fire
import os

SERVER_URL = "http://localhost:9000"
STUDENT_ID = "s001" # Change to your assigned ID
TRIAL = "bisection-demo"
EXPERIMENT_NAME = os.environ.get('DEFAULT_EXPERIMENT', 'default')

def bisection(fn, a, b, xtol=1e-6):
    if fn(a)*fn(b) > 0:
        return []

    visited = []

    while abs(a-b) > xtol:
        mid = (a+b)/2
        visited.append(mid)
        fm = fn(mid)             # <-- compute once

        if fm == 0:              # <-- NEW: stop if midpoint is a root
            return visited

        if fn(a)*fm < 0:
            b = mid
            continue
        else:
            a = mid
            continue

    return visited


def square(x):
    return (x-10)*(x-30)

def main(a,b):
    try:
        client = RPCClient(server_url=SERVER_URL, student_id=STUDENT_ID, trial_name=TRIAL, experiment_name=EXPERIMENT_NAME)
    except RPCError as e:
        print(f"Failed to initialize RPC client: {e}")
        return

    try:
        root = bisection(client.square, a, b)
        if root:
            print(root[-1])
        else:
            print("No root found or invalid interval.")
    except RPCError as e:
        print(f"RPC error during remote bisection: {e}")

    print()
    root = bisection(square, a, b)
    print(root[-1])

Fire(main)
