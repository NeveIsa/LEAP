# state.py
"""Centralized state management for the server."""

from typing import Optional


class ServerState:
    """Centralized state management for the server."""
    
    def __init__(self):
        self.active_experiment: Optional[str] = None
        self.mounted_experiments: set[str] = set()
        
    def set_active_experiment(self, experiment_name: Optional[str]):
        """Set the active experiment."""
        self.active_experiment = experiment_name
        
    def get_active_experiment(self) -> Optional[str]:
        """Get the currently active experiment."""
        return self.active_experiment
        
    def add_mounted_experiment(self, experiment_name: str):
        """Track a mounted experiment."""
        self.mounted_experiments.add(experiment_name)
        
    def is_mounted(self, experiment_name: str) -> bool:
        """Check if an experiment is mounted."""
        return experiment_name in self.mounted_experiments


# Global state instance
server_state = ServerState()