# Unified Logging System

## Overview

Created a centralized logging module (`logger.py`) that provides consistent log formatting across all project files.

## Features

- **Consistent format:** All logs follow the same structure
- **Easy to use:** Single import, simple function calls
- **Informative:** Includes timestamp, server name, script name, and action
- **Flexible:** Multiple log levels (info, warning, error, generic)
- **No dependencies:** Uses only Python standard library

## Log Format

```
[TIMESTAMP] [SERVER_NAME] [SCRIPT_NAME] ACTION
```

**Example:**
```
[2025-12-31 10:30:45] [MODEL_SERVER] [run_model_server.py] Processing image batch of size 32
```

### Components

1. **Timestamp:** `YYYY-MM-DD HH:MM:SS` format
2. **Server Name:** Identifies which server/component generated the log
3. **Script Name:** The main Python file being executed
4. **Action:** Description of what's happening

## API Reference

### `log(action, server_name=None)`

Generic logging function.

**Parameters:**
- `action` (str): Description of the action
- `server_name` (str, optional): Server identifier (defaults to hostname)

**Example:**
```python
from logger import log

log("Starting web server", "WEB_SERVER")
# Output: [2025-12-31 10:30:45] [WEB_SERVER] [run_web_server.py] Starting web server
```

### `log_info(info_message, server_name=None)`

Log informational messages.

**Example:**
```python
from logger import log_info

log_info("Connected to Redis successfully", "WEB_SERVER")
# Output: [2025-12-31 10:30:45] [WEB_SERVER] [run_web_server.py] INFO: Connected to Redis successfully
```

### `log_warning(warning_message, server_name=None)`

Log warning messages.

**Example:**
```python
from logger import log_warning

log_warning("Queue size exceeds 100 items", "MODEL_SERVER")
# Output: [2025-12-31 10:30:45] [MODEL_SERVER] [run_model_server.py] WARNING: Queue size exceeds 100 items
```

### `log_error(error_message, server_name=None)`

Log error messages.

**Example:**
```python
from logger import log_error

log_error("Failed to connect to Redis", "WEB_SERVER")
# Output: [2025-12-31 10:30:45] [WEB_SERVER] [run_web_server.py] ERROR: Failed to connect to Redis
```

## Usage Examples

### Example 1: Web Server Logging

```python
# run_web_server.py
from logger import log_info, log_warning, log_error

# At startup
log_info("Web server starting on port 5000", "WEB_SERVER")

# During request handling
@app.route("/predict", methods=["POST"])
def predict():
    log_info(f"Received prediction request with job ID: {k}", "WEB_SERVER")

    # ... processing ...

    if output is not None:
        log_info(f"Job {k} completed successfully", "WEB_SERVER")
    else:
        log_warning(f"Job {k} timed out", "WEB_SERVER")
```

### Example 2: Model Server Logging

```python
# run_model_server.py
from logger import log_info, log

# At startup
log_info("Loading ResNet50 model", "MODEL_SERVER")
model = ResNet50(weights="imagenet")
log_info("Model loaded successfully", "MODEL_SERVER")

# During processing
def classify_process():
    while True:
        queue = db.lrange(settings.IMAGE_QUEUE, 0, settings.BATCH_SIZE - 1)

        if len(queue) > 0:
            log(f"Processing batch of {len(queue)} images", "MODEL_SERVER")
            # ... process batch ...
            log(f"Batch completed: {len(imageIDs)} predictions stored", "MODEL_SERVER")
```

### Example 3: Client Logging

```python
# simple_request.py
from logger import log_info, log_error

log_info("Sending image to server", "CLIENT")

r = requests.post(KERAS_REST_API_URL, files=payload).json()

if r["success"]:
    log_info(f"Received {len(r['predictions'])} predictions", "CLIENT")
else:
    log_error("Request failed", "CLIENT")
```

## Integration with Existing Code

To add logging to existing files:

1. **Import the logger:**
   ```python
   from logger import log_info, log_warning, log_error
   ```

2. **Add logs at key points:**
   - Server startup
   - Request received
   - Work queued
   - Processing started
   - Processing completed
   - Errors encountered

3. **Use appropriate log levels:**
   - `log_info()`: Normal operations
   - `log_warning()`: Unusual but handled situations
   - `log_error()`: Errors and failures

## Sample Output

Running the system with logging enabled:

```
[2025-12-31 10:30:00] [WEB_SERVER] [run_web_server.py] INFO: Starting web service
[2025-12-31 10:30:15] [MODEL_SERVER] [run_model_server.py] INFO: Loading model
[2025-12-31 10:30:25] [MODEL_SERVER] [run_model_server.py] INFO: Model loaded
[2025-12-31 10:31:00] [CLIENT] [simple_request.py] INFO: Sending image to server
[2025-12-31 10:31:01] [WEB_SERVER] [run_web_server.py] INFO: Received prediction request with job ID: a1b2c3d4-5e6f-7890
[2025-12-31 10:31:01] [MODEL_SERVER] [run_model_server.py] Processing batch of 1 images
[2025-12-31 10:31:03] [MODEL_SERVER] [run_model_server.py] Batch completed: 1 predictions stored
[2025-12-31 10:31:03] [WEB_SERVER] [run_web_server.py] INFO: Job a1b2c3d4-5e6f-7890 completed successfully
[2025-12-31 10:31:03] [CLIENT] [simple_request.py] INFO: Received 5 predictions
```

## Benefits

1. **Debugging:** Easy to trace request flow across servers
2. **Monitoring:** Identify bottlenecks and performance issues
3. **Auditing:** Track all actions with timestamps
4. **Troubleshooting:** Quickly identify where errors occur
5. **Consistency:** Same format everywhere

## Advanced Usage

### Custom Server Names

```python
# For multiple model servers
log_info("Started processing", f"MODEL_SERVER_{worker_id}")
```

### Structured Data

```python
log(f"Batch processed: size={batch_size}, time={elapsed:.2f}s", "MODEL_SERVER")
```

### Performance Logging

```python
import time

start = time.time()
# ... do work ...
elapsed = time.time() - start
log(f"Image classification took {elapsed:.3f}s", "MODEL_SERVER")
```

## Future Enhancements

Possible improvements:

1. **File output:** Write logs to file in addition to console
2. **Log levels:** Add DEBUG level for verbose logging
3. **Log rotation:** Automatically rotate log files by size/date
4. **Structured logging:** JSON output for log aggregation tools
5. **Filtering:** Environment variable to control log level
6. **Color coding:** Colorize output based on log level

## Implementation Details

The logger is implemented in `logger.py` using:
- `datetime` for timestamps
- `sys.argv[0]` to get script name
- `socket.gethostname()` as fallback for server name
- Simple `print()` for output (easy to redirect)
