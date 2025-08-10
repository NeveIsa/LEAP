
import requests
import json

class RPCError(Exception):
    """Base exception for RPC client errors."""


class RPCServerError(RPCError):
    """Raised when the server returns a non-2xx response with an error."""


class RPCNetworkError(RPCError):
    """Raised when there is a network/transport error reaching the server."""


class RPCProtocolError(RPCError):
    """Raised when the server responds successfully but the payload is invalid."""


class RPCNotRegisteredError(RPCServerError):
    """Raised when the server indicates the student_id is not registered (HTTP 403)."""

class RPCClient:
    """A client for the Classroom RPC Server."""

    def __init__(self, server_url: str, student_id: str, experiment_name: str | None = None):
        """Initializes the client with the server URL, student ID, and optional experiment name."""
        self.server_url = server_url.rstrip('/')
        self.student_id = student_id
        self.experiment_name = experiment_name
        self._function_cache = {}
        self._discover_functions()

    def _discover_functions(self):
        """Fetches the list of available functions from the server."""
        try:
            response = requests.get(f"{self.server_url}/functions")
            response.raise_for_status()  # Raise an exception for bad status codes
            self._function_cache = response.json()
        except requests.exceptions.RequestException as e:
            raise RPCNetworkError(f"Error discovering functions: {e}") from e

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
                    "experiment": self.experiment_name,
                }
                try:
                    response = requests.post(f"{self.server_url}/call", json=payload)
                except requests.exceptions.RequestException as e:
                    raise RPCNetworkError(f"Network error calling '{name}': {e}") from e

                # Non-2xx means server rejected/execution failed
                if not response.ok:
                    status = response.status_code
                    server_detail = None
                    try:
                        server_json = response.json()
                        server_detail = server_json.get("detail")
                    except Exception:
                        server_detail = response.text or response.reason

                    # Friendlier guidance for common cases
                    if status == 403:
                        raise RPCNotRegisteredError(
                            (
                                f"Forbidden: student_id '{self.student_id}' is not registered. "
                                "Please add the student via the Admin UI (" 
                                f"{self.server_url}/ui/students.html) or the admin API, then retry."
                            )
                        )
                    if status == 404 and (server_detail or '').lower().startswith("function"):
                        raise RPCServerError(
                            (
                                f"Function not found: '{name}'. Check available functions via "
                                f"{self.server_url}/functions or client.help()."
                            )
                        )

                    msg = f"Server error calling '{name}': {server_detail or 'unknown error'} (HTTP {status})"
                    raise RPCServerError(msg)

                # Parse success payload and validate presence of result
                try:
                    payload = response.json()
                except json.JSONDecodeError as e:
                    raise RPCProtocolError(f"Invalid JSON response for '{name}': {e}") from e

                if "result" not in payload:
                    raise RPCProtocolError(f"Missing 'result' in server response for '{name}'.")

                return payload["result"]

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
        print("Available remote functions:\n")
        for name, info in self._function_cache.items():
            print(f"- {name}{info.get('signature', '()')}\n")

    def fetch_logs(self, n: int = 100, student_id: str | None = None, order: str = "latest"):
        """Fetch logs from the public logs endpoint.

        Args:
            n: number of logs (1..1000).
            student_id: optional filter.
            order: 'latest' or 'earliest'.

        Returns:
            A list of log dicts.
        """
        params = {"n": n, "order": order}
        if student_id:
            params["student_id"] = student_id
        try:
            resp = requests.get(f"{self.server_url}/logs", params=params)
        except requests.exceptions.RequestException as e:
            raise RPCNetworkError(f"Network error fetching logs: {e}") from e
        if not resp.ok:
            if resp.status_code == 403:
                raise RPCNotRegisteredError(
                    (
                        f"Forbidden: student_id '{student_id or self.student_id}' is not registered. "
                        "Add the student via the Admin UI or admin API."
                    )
                )
            raise RPCServerError(f"Server error fetching logs: HTTP {resp.status_code}")
        try:
            data = resp.json()
        except json.JSONDecodeError as e:
            raise RPCProtocolError(f"Invalid JSON response from /logs: {e}") from e
        return data.get("logs", [])

    def is_registered(self) -> bool:
        """Return True if this client's student_id is registered.

        Strategy (zero side-effects):
        1) Try GET /is-registered?student_id=... and return its boolean.
        2) If the endpoint is unavailable or fails, fall back to a benign
           probe via /call against a simple function (may create one log entry).
        """
        # 1) Zero-side-effect check via public endpoint
        try:
            resp = requests.get(f"{self.server_url}/is-registered", params={"student_id": self.student_id}, timeout=5)
            if resp.ok:
                data = resp.json()
                if isinstance(data, dict) and "registered" in data:
                    return bool(data["registered"])
        except requests.exceptions.RequestException:
            # Ignore and fall back
            pass
        # Preferred simple functions and args
        preferred: list[tuple[str, tuple]] = []
        if "quadratic" in self._function_cache:
            preferred.append(("quadratic", (0, 0, 0, 0)))
        if "square" in self._function_cache:
            preferred.append(("square", (0,)))
        if "cubic" in self._function_cache:
            preferred.append(("cubic", (0,)))
        if "rosenbrock" in self._function_cache:
            preferred.append(("rosenbrock", (0, 0)))

        tried = set(name for name, _ in preferred)

        # For any other functions, attempt zeros for required args inferred from signature
        for name, info in self._function_cache.items():
            if name in tried:
                continue
            sig = str(info.get("signature", "()"))
            # crude parse: count commas for params not having '=' (required)
            params = sig.strip()
            if params.startswith("(") and params.endswith(")"):
                params = params[1:-1].strip()
            required = 0
            if params:
                for part in [p.strip() for p in params.split(",")]:
                    if not part:
                        continue
                    # skip var-args or kwargs markers
                    if part.startswith("*"):
                        continue
                    if "=" in part:
                        continue
                    required += 1
            # Cap at 4 zeros to avoid huge arg lists
            args = tuple(0 for _ in range(min(required, 4)))
            preferred.append((name, args))

        # Try each candidate function until we can decide
        for fname, args in preferred:
            try:
                getattr(self, fname)(*args)
                return True
            except RPCNotRegisteredError:
                return False
            except RPCNetworkError:
                # Propagate network problems to caller
                raise
            except RPCServerError:
                # Any non-403 server error implies the student gate did not trigger
                return True
            except RPCProtocolError:
                # Unexpected payload still implies gate pass
                return True

        # If we couldn't test any function, conservatively raise
        raise RPCError("Cannot determine registration: no callable functions available to probe.")


if __name__ == '__main__':
    SERVER_URL = "http://localhost:9000"
    STUDENT_ID = "s001"  # Make sure this student ID is registered on the server
    EXPERIMENT = "bisection-demo"  # Optional experiment label

    print(f"Initializing client for student '{STUDENT_ID}' at {SERVER_URL}\n")
    try:
        client = RPCClient(server_url=SERVER_URL, student_id=STUDENT_ID, experiment_name=EXPERIMENT)
    except RPCError as e:
        print(f"Failed to initialize RPC client: {e}")
        raise

    # --- Example Usage ---

    # 1. List available functions
    client.help()
    print("\n" + "-"*30 + "\n")

    # 2. Call a simple function
    print("Calling 'square' with argument 7...")
    try:
        result = client.square(7)
        print(f"Result of square(7): {result}\n")
    except RPCError as e:
        print(f"RPC error during square(7): {e}\n")

    # 3. Call a function with multiple arguments
    print("Calling 'rosenbrock' with arguments (1, 2, 1.0, 100.0)...")
    try:
        result = client.rosenbrock(1, 2, 1.0, 100.0)
        print(f"Result of rosenbrock(1, 2, 1.0, 100.0): {result}\n")
    except RPCError as e:
        print(f"RPC error during rosenbrock(...): {e}\n")

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
