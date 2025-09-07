import sys
sys.path.append("../client")
sys.path.append("client")

from client import RPCClient, RPCError
import os


SERVER_URL = "http://localhost:9000"
STUDENT_ID = "s001" # Change to your assigned ID
TRIAL = "listing-demo"
EXPERIMENT_NAME = os.environ.get('DEFAULT_EXPERIMENT', 'default')

try:
    client = RPCClient(server_url=SERVER_URL, student_id=STUDENT_ID, trial_name=TRIAL, experiment_name=EXPERIMENT_NAME)
    # Get a list of available functions
    client.help()
except RPCError as e:
    print(f"RPC error while initializing or listing functions: {e}")
