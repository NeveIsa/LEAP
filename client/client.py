
import requests
import json

class RPCClient:
    """A client for the Classroom RPC Server."""

    def __init__(self, server_url: str, student_id: str):
        """Initializes the client with the server URL and student ID."""
        self.server_url = server_url.rstrip('/')
        self.student_id = student_id
        self._function_cache = {}
        self._discover_functions()

    def _discover_functions(self):
        """Fetches the list of available functions from the server."""
        try:
            response = requests.get(f"{self.server_url}/functions")
            response.raise_for_status()  # Raise an exception for bad status codes
            self._function_cache = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error discovering functions: {e}")

    def __getattr__(self, name: str):
        """
        Dynamically creates a method to call a remote function if it exists.
        This method is called only when an attribute is not found in the usual places.
        """
        if name in self._function_cache:
            func_info = self._function_cache[name]

            def rpc_method(*args, **kwargs):
                # Basic validation to prevent calling with kwargs if not supported
                if kwargs:
                    raise TypeError(f"Remote function '{name}' does not support keyword arguments.")

                payload = {
                    "student_id": self.student_id,
                    "func_name": name,
                    "args": args,
                }
                try:
                    response = requests.post(f"{self.server_url}/call", json=payload)
                    response.raise_for_status()
                    return response.json().get("result")
                except requests.exceptions.RequestException as e:
                    print(f"Error calling function '{name}': {e}")
                    if e.response and e.response.text:
                        try:
                            detail = e.response.json().get('detail', e.response.text)
                            print(f"Server error: {detail}")
                        except json.JSONDecodeError:
                            print(f"Server error: {e.response.text}")
                    return None

            # Set the docstring for the dynamically created method
            rpc_method.__doc__ = (
                f"Dynamically generated method to call the remote function '{name}'.\n\n"
                f"Original docstring:\n{func_info.get('doc', 'No documentation available.')}\n\n"
                f"Signature: {func_info.get('signature', 'N/A')}"
            )
            rpc_method.__name__ = name

            # Cache the method on the instance to avoid re-creation
            setattr(self, name, rpc_method)
            return rpc_method
        else:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'. "
                                 f"No such remote function discovered.")

    def help(self):
        """Prints a list of available remote functions and their signatures."""
        if not self._function_cache:
            print("Could not retrieve function list from the server.")
            return
        print("Available remote functions:")
        for name, info in self._function_cache.items():
            print(f"- {name}{info.get('signature', '()')}")


if __name__ == '__main__':
    SERVER_URL = "http://localhost:9000"
    STUDENT_ID = "s001"  # Make sure this student ID is registered on the server

    print(f"Initializing client for student '{STUDENT_ID}' at {SERVER_URL}\n")
    client = RPCClient(server_url=SERVER_URL, student_id=STUDENT_ID)

    # --- Example Usage ---

    # 1. List available functions
    client.help()
    print("\n" + "-"*30 + "\n")

    # 2. Call a simple function
    print("Calling 'square' with argument 7...")
    result = client.square(7)
    print(f"Result of square(7): {result}\n")

    # 3. Call a function with multiple arguments
    print("Calling 'rosenbrock' with arguments (1, 2, 1.0, 100.0)...")
    result = client.rosenbrock(1, 2, 1.0, 100.0)
    print(f"Result of rosenbrock(1, 2, 1.0, 100.0): {result}\n")

    # 4. Get help on a specific function
    print("Getting help for the 'quadratic' function:")
    # help() is a built-in, so we access the docstring directly
    if hasattr(client, 'quadratic'):
        print(client.quadratic.__doc__)
    print("\n" + "-"*30 + "\n")

    # 5. Example of calling a non-existent function
    print("Attempting to call a non-existent function 'multiply'...")
    try:
        client.multiply(2, 3)
    except AttributeError as e:
        print(f"Caught expected error: {e}")
