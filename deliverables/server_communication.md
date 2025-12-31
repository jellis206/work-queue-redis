# Web Server to Model Server Communication

## Architecture Overview

The web server and model server communicate asynchronously through Redis using a **producer-consumer pattern** with a work queue and result store.

```
Client → Web Server → Redis Queue → Model Server → Redis Results → Web Server → Client
```

## Communication Flow

### Phase 1: Work Submission (Web Server → Model Server)

1. **Client sends request** to web server's `/predict` endpoint (run_web_server.py:39)
   - HTTP POST with image file

2. **Web server processes image** (run_web_server.py:50-63)
   - Reads image from request
   - Prepares image (resize to 224x224, preprocess for ResNet50)
   - Generates unique job ID: `k = str(uuid.uuid4())`
   - Base64-encodes the numpy array
   - Creates work package: `{"id": k, "image": base64_image}`

3. **Web server enqueues work** (run_web_server.py:64)
   ```python
   db.rpush(settings.IMAGE_QUEUE, json.dumps(d))
   ```
   - Pushes to Redis LIST "image_queue"
   - Non-blocking operation (returns immediately)

4. **Model server dequeues work** (run_model_server.py:31)
   ```python
   queue = db.lrange(settings.IMAGE_QUEUE, 0, settings.BATCH_SIZE - 1)
   ```
   - Continuously polls the queue in a loop (run_model_server.py:28)
   - Reads up to BATCH_SIZE (32) items at once
   - Processes in batches for efficiency

### Phase 2: Processing (Model Server)

5. **Model server processes batch** (run_model_server.py:36-60)
   - Deserializes each work item
   - Decodes base64 images back to numpy arrays
   - Stacks into batch for parallel inference
   - Runs predictions: `model.predict(batch)`
   - Decodes predictions to human-readable labels

### Phase 3: Result Delivery (Model Server → Web Server)

6. **Model server stores results** (run_model_server.py:76)
   ```python
   db.set(imageID, json.dumps(output))
   ```
   - Stores predictions as JSON string
   - Uses the job UUID as the key
   - No expiration set

7. **Model server cleans queue** (run_model_server.py:79)
   ```python
   db.ltrim(settings.IMAGE_QUEUE, len(imageIDs), -1)
   ```
   - Removes processed items from queue
   - Prevents reprocessing

8. **Web server polls for results** (run_web_server.py:68-87)
   ```python
   while True:
       output = db.get(k)
       if output is not None:
           # Process and return results
           db.delete(k)
           break
       time.sleep(settings.CLIENT_SLEEP)  # 0.25 seconds
   ```
   - **Busy-wait polling loop** (inefficient!)
   - Checks every 0.25 seconds
   - Blocks the web server thread until complete

9. **Web server returns response** (run_web_server.py:93)
   - Returns JSON with predictions to client
   - HTTP response completes

## How Web Server Responds to Requests

The web server uses **synchronous blocking** with polling:

1. **Request arrives** → Flask handler invoked
2. **Work submitted** → Non-blocking Redis push
3. **Polling begins** → Thread blocks in while loop
4. **Result found** → Decode, delete, return
5. **Response sent** → HTTP request completes

**Key Issue:** Each web server thread is blocked waiting for results. With Flask's default threading model, this limits concurrency.

## Communication Characteristics

| Aspect | Implementation | Issue |
|--------|---------------|-------|
| **Work handoff** | Redis LIST (queue) | ✓ Good: Decoupled, scalable |
| **Result delivery** | Redis STRING (key-value) | ✓ Good: Simple lookup |
| **Web server wait** | Busy-wait polling | ✗ Bad: CPU waste, latency |
| **Synchronization** | UUID matching | ✓ Good: Ensures correct results |
| **Batching** | Model server batches | ✓ Good: Efficient GPU usage |
| **Error handling** | None | ✗ Bad: No timeouts or retries |

## Timing Diagram

```
Time  Web Server              Redis                   Model Server
-------------------------------------------------------------------
t0    Generate UUID (k)
t1    rpush(queue, work)  →   [work added to queue]
t2    get(k) → None
t3    sleep(0.25s)
t4    get(k) → None                                   lrange(queue) →
t5    sleep(0.25s)                                    predict(batch)
t6    get(k) → None
t7    sleep(0.25s)                                    set(k, result)
t8    get(k) → result     ←   [result retrieved]
t9    delete(k)               [result deleted]
t10   return to client
```

## Scalability Considerations

**Advantages:**
- Multiple model servers can process from same queue
- Work distribution is automatic (first-come-first-served)
- Web servers are stateless (any can handle any request)

**Disadvantages:**
- Polling wastes CPU and adds latency
- No timeout mechanism (requests can hang forever)
- No dead-letter queue for failed jobs
- Results stored forever if client disconnects
