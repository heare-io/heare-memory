"""Heare Memory Global Service.

A RESTful memory service that provides persistent storage for agents with
automatic git versioning. The service exposes a tree-structured filesystem
interface backed by markdown files and git commits.
"""

__version__ = "0.1.0"
__author__ = "Heare Memory Team"
__email__ = "memory@heare.ai"

# Re-export main classes/functions for easier imports
from .main import create_app

__all__ = ["create_app", "__version__"]
