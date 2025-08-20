import requests
from typing import Optional, List, Dict, Any, Literal

class LogsClient:
    """A client for fetching logs from the classroom RPC server."""

    def __init__(self, server_url: str):
        """Initializes the client with the server URL.

        Args:
            server_url: The base URL of the server (e.g., http://localhost:9000).
        """
        self.server_url = server_url.rstrip('/')

    def fetch_logs(
        self, 
        student_id: Optional[str] = None,
        experiment_name: Optional[str] = None,
        n: int = 100,
        order: Literal["latest", "earliest"] = "latest",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetches logs from the server with optional filters.

        Args:
            student_id: Optional student ID to filter by.
            experiment_name: Optional experiment name to filter by.
            n: Maximum number of logs to return.
            order: Order of logs to return ('latest' or 'earliest').
            start_time: Optional start time in ISO 8601 format (e.g., 2023-01-01T00:00:00).
            end_time: Optional end time in ISO 8601 format (e.g., 2023-01-01T12:00:00).

        Returns:
            A list of log dictionaries.

        Raises:
            requests.exceptions.RequestException: For network errors.
            ValueError: If the server returns an invalid response.
        """
        params = {
            "sid": student_id,
            "exp": experiment_name,
            "n": n,
            "order": order,
            "start_time": start_time,
            "end_time": end_time,
        }
        # Remove None values so they are not sent as empty query parameters
        params = {k: v for k, v in params.items() if v is not None}

        response = requests.get(f"{self.server_url}/logs", params=params)
        response.raise_for_status()  # Raise an exception for bad status codes

        try:
            data = response.json()
            return data.get("logs", [])
        except ValueError:
            raise ValueError("Invalid JSON response from server")

if __name__ == '__main__':
    # Example usage:
    client = LogsClient("http://localhost:9000")

    print("Fetching latest 10 logs for student s001:")
    try:
        logs = client.fetch_logs(student_id="s001", n=10)
        for log in logs:
            print(log)
    except Exception as e:
        print(f"Error: {e}")

    print("\nFetching all logs from the last hour:")
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    one_hour_ago = now - timedelta(hours=1)
    try:
        logs = client.fetch_logs(start_time=one_hour_ago.isoformat(), end_time=now.isoformat())
        for log in logs:
            print(log)
    except Exception as e:
        print(f"Error: {e}")
