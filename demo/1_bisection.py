import sys
sys.path.append("../client")
sys.path.append("client")

from client import RPCClient
from fire import Fire

SERVER_URL = "http://localhost:9000"
STUDENT_ID = "s001" # Change to your assigned ID

client = RPCClient(server_url=SERVER_URL, student_id=STUDENT_ID)

def bisection(fn,a,b, xtol=1e-6):
    if fn(a)*fn(b) > 0:
        return []
    
    visited = []

    while abs(a-b) > xtol:
        mid = (a+b)/2
        visited.append(mid)

        if fn(a)*fn(mid) < 0:
            b = mid
            continue
        else:
            a = mid
            continue

    return visited


def square(x):
    return (x-10)*(x-30)

def main(a,b):
    root = bisection(client.square, a, b)
    print(root[-1])
    print(client.square(20),client.square(35))
    print()
    root = bisection(square, a, b)
    print(root[-1])
    print(square(20),square(35))

Fire(main)
