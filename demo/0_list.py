import sys
sys.path.append("../client")
sys.path.append("client")

from client import RPCClient, RPCError


SERVER_URL = "http://localhost:9000"
STUDENT_ID = "s001" # Change to your assigned ID
EXPERIMENT = "listing-demo"

try:
    client = RPCClient(server_url=SERVER_URL, student_id=STUDENT_ID, experiment_name=EXPERIMENT)
    # Get a list of available functions
    client.help()
except RPCError as e:
    print(f"RPC error while initializing or listing functions: {e}")

