import sys
sys.path.append("../client")
sys.path.append("client")

from client import RPCClient


SERVER_URL = "http://localhost:9000"
STUDENT_ID = "s001" # Change to your assigned ID

client = RPCClient(server_url=SERVER_URL, student_id=STUDENT_ID)

# Get a list of available functions
client.help()



