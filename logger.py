"""
Unified logging utility for the work queue project.
Provides consistent logging format across all servers.
"""

import os
import sys
from datetime import datetime


def log(action, server_name=None):
    """
    Log an action with consistent formatting.

    Args:
        action (str): Description of the action being logged
        server_name (str, optional): Name of the server (e.g., "WEB_SERVER", "MODEL_SERVER").
                                     If not provided, uses hostname.

    Format:
        [TIMESTAMP] [SERVER_NAME] [SCRIPT_NAME] ACTION

    Example:
        >>> log("Processing image batch of size 32", "MODEL_SERVER")
        [2025-12-31 10:30:45] [MODEL_SERVER] [run_model_server.py] Processing image batch of size 32
    """
    # Get timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Get the script name from the main module
    script_name = os.path.basename(sys.argv[0]) if sys.argv else "unknown"

    # Use provided server name or hostname as fallback
    if server_name is None:
        import socket
        server_name = socket.gethostname()

    # Format and print log message
    log_message = f"[{timestamp}] [{server_name}] [{script_name}] {action}"
    print(log_message)

    return log_message


def log_error(error_message, server_name=None):
    """
    Log an error message.

    Args:
        error_message (str): Description of the error
        server_name (str, optional): Name of the server

    Example:
        >>> log_error("Failed to connect to Redis", "WEB_SERVER")
        [2025-12-31 10:30:45] [WEB_SERVER] [run_web_server.py] ERROR: Failed to connect to Redis
    """
    return log(f"ERROR: {error_message}", server_name)


def log_info(info_message, server_name=None):
    """
    Log an informational message.

    Args:
        info_message (str): Information to log
        server_name (str, optional): Name of the server

    Example:
        >>> log_info("Server started successfully", "WEB_SERVER")
        [2025-12-31 10:30:45] [WEB_SERVER] [run_web_server.py] INFO: Server started successfully
    """
    return log(f"INFO: {info_message}", server_name)


def log_warning(warning_message, server_name=None):
    """
    Log a warning message.

    Args:
        warning_message (str): Warning to log
        server_name (str, optional): Name of the server

    Example:
        >>> log_warning("Queue size exceeds 100 items", "MODEL_SERVER")
        [2025-12-31 10:30:45] [MODEL_SERVER] [run_model_server.py] WARNING: Queue size exceeds 100 items
    """
    return log(f"WARNING: {warning_message}", server_name)
