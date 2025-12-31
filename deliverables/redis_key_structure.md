# Redis Key Structure Analysis

## Overview
The system uses Redis as both a work queue and a result store, using two distinct key patterns.

## Key Structure 1: Work Queue

**Key Name:** `"image_queue"` (stored in `settings.IMAGE_QUEUE`)

**Data Type:** Redis LIST

**Structure:**
- The web server pushes work items using `rpush` (right push) at run_web_server.py:64
- Each item is a JSON string containing:
  ```json
  {
    "id": "uuid-string",
    "image": "base64-encoded-numpy-array"
  }
  ```

**Flow:**
1. Web server generates UUID: `k = str(uuid.uuid4())` (run_web_server.py:61)
2. Image is base64-encoded: `helpers.base64_encode_image(image)` (run_web_server.py:62)
3. Dictionary created: `d = {"id": k, "image": image}` (run_web_server.py:63)
4. Pushed to queue: `db.rpush(settings.IMAGE_QUEUE, json.dumps(d))` (run_web_server.py:64)
5. Model server reads: `db.lrange(settings.IMAGE_QUEUE, 0, settings.BATCH_SIZE - 1)` (run_model_server.py:31)
6. Model server removes processed items: `db.ltrim(settings.IMAGE_QUEUE, len(imageIDs), -1)` (run_model_server.py:79)

**Purpose:** Acts as a FIFO queue for pending classification jobs

---

## Key Structure 2: Result Store

**Key Name:** UUID string (e.g., `"a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6"`)

**Data Type:** Redis STRING

**Structure:**
- Each UUID key stores a JSON string containing classification results:
  ```json
  [
    {
      "label": "castle",
      "probability": 0.8543
    },
    {
      "label": "palace",
      "probability": 0.0234
    },
    ...
  ]
  ```

**Flow:**
1. Web server generates UUID for each request (run_web_server.py:61)
2. Web server polls for result: `output = db.get(k)` (run_web_server.py:70)
3. Model server stores result: `db.set(imageID, json.dumps(output))` (run_model_server.py:76)
4. Web server retrieves, decodes, and deletes: `db.delete(k)` (run_web_server.py:82)

**Purpose:** Temporary storage for classification results, keyed by job ID

---

## Redis Operations Summary

| Operation | Command | Location | Purpose |
|-----------|---------|----------|---------|
| Enqueue work | `rpush` | run_web_server.py:64 | Add job to queue |
| Dequeue work | `lrange` | run_model_server.py:31 | Read pending jobs |
| Remove processed | `ltrim` | run_model_server.py:79 | Clear completed jobs |
| Store result | `set` | run_model_server.py:76 | Save predictions |
| Check result | `get` | run_web_server.py:70 | Poll for completion |
| Clean up | `delete` | run_web_server.py:82 | Remove result after retrieval |

## Key Characteristics

1. **Work Queue (LIST)**
   - Persistent until explicitly trimmed
   - Supports batch processing via `lrange`
   - FIFO ordering guaranteed

2. **Result Store (STRING)**
   - Temporary (deleted after retrieval)
   - One-to-one mapping with work items
   - No TTL set (could be a memory leak if client disconnects)
