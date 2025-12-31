# Concurrency Issues and Fixes

## Overview

When running multiple web servers and/or multiple model servers simultaneously, several race conditions can occur that lead to duplicate processing, lost work, or incorrect results.

## Issue 1: Duplicate Work Processing (CRITICAL)

### Problem

**Location:** `run_model_server.py:31-79`

When multiple model servers run concurrently, they can process the same work items multiple times.

### Race Condition Flow

```
Time  Model Server 1              Redis Queue           Model Server 2
--------------------------------------------------------------------------------
t0    lrange(queue, 0, 31)    →   [job1, job2, ...]
t1                                 [job1, job2, ...]   ←  lrange(queue, 0, 31)
t2    Processing job1, job2...     [job1, job2, ...]      Processing job1, job2...
t3    predict(batch)               [job1, job2, ...]      predict(batch)
t4    set(job1, result)        →   [job1, job2, ...]
t5                                 [job1, job2, ...]   ←  set(job1, result)  [OVERWRITES!]
t6    ltrim(queue, 2, -1)      →   [job3, job4, ...]
t7                                 [job5, job6, ...]   ←  ltrim(queue, 2, -1)  [LOST WORK!]
```

### Issues

1. **`lrange` is non-atomic** - Reading items doesn't remove them from the queue
2. **Gap between read and remove** - Multiple servers can read the same items
3. **Lost work** - If both servers trim by same amount, items in the middle disappear
4. **Duplicate processing** - Same job predicted multiple times (wastes GPU)
5. **Result overwrite** - Last server to finish overwrites previous results

### Code Analysis

```python
# PROBLEMATIC CODE (run_model_server.py:31-79)
queue = db.lrange(settings.IMAGE_QUEUE, 0, settings.BATCH_SIZE - 1)  # Read items
imageIDs = []
batch = None

for q in queue:
    # ... process items ...
    imageIDs.append(q["id"])

if len(imageIDs) > 0:
    # ... predict and store results ...
    db.ltrim(settings.IMAGE_QUEUE, len(imageIDs), -1)  # Remove items
```

**Problem:** Time gap between `lrange` (t0) and `ltrim` (t6) allows race conditions.

## Issue 2: UUID Collision (Low Probability)

### Problem

**Location:** `run_web_server.py:61`

While UUID4 collisions are extremely rare (1 in 2^122), the code has no collision detection.

```python
k = str(uuid.uuid4())
# No check if 'k' already exists in Redis
db.rpush(settings.IMAGE_QUEUE, json.dumps(d))
```

### Consequences

If collision occurs:
- Two different requests use same key
- First request gets second request's results
- Data corruption and incorrect predictions returned

## Issue 3: Result Key Cleanup Failure

### Problem

**Location:** `run_web_server.py:82`

If web server crashes after model server stores results but before `db.delete(k)`:

```python
output = db.get(k)
if output is not None:
    # ... use output ...
    db.delete(k)  # <-- If crash happens before this, key remains forever
```

### Consequences

- Redis fills up with orphaned result keys
- Memory leak
- No TTL (Time To Live) set on result keys

## Solution: Atomic Queue Operations

### Fix for Issue 1: Use LPOP Instead of LRANGE + LTRIM

Replace the non-atomic read-then-delete pattern with atomic pop operations.

**Original problematic code:**
```python
queue = db.lrange(settings.IMAGE_QUEUE, 0, settings.BATCH_SIZE - 1)
# ... process ...
db.ltrim(settings.IMAGE_QUEUE, len(imageIDs), -1)
```

**Fixed code using atomic operations:**
```python
# Atomically pop items one at a time
queue = []
for _ in range(settings.BATCH_SIZE):
    item = db.lpop(settings.IMAGE_QUEUE)
    if item is None:
        break  # Queue is empty
    queue.append(item)
```

### Why This Works

- **`LPOP` is atomic** - Removes and returns in a single operation
- **No race condition** - Item is removed before another server can see it
- **Guaranteed uniqueness** - Each item processed by exactly one server
- **No lost work** - Items can't disappear during trim operations

### Implementation in run_model_server.py

```python
def classify_process():
    print("* Loading model...")
    model = ResNet50(weights="imagenet")
    print("* Model loaded")

    while True:
        # Atomically pop items from queue
        queue = []
        for _ in range(settings.BATCH_SIZE):
            item = db.lpop(settings.IMAGE_QUEUE)
            if item is None:
                break
            queue.append(item)

        imageIDs = []
        batch = None

        # Process the atomically-acquired items
        for q in queue:
            q = json.loads(q.decode("utf-8"))
            image = helpers.base64_decode_image(q["image"],
                settings.IMAGE_DTYPE,
                (1, settings.IMAGE_HEIGHT, settings.IMAGE_WIDTH,
                    settings.IMAGE_CHANS))

            if batch is None:
                batch = image
            else:
                batch = np.vstack([batch, image])

            imageIDs.append(q["id"])

        # Process batch (same as before)
        if len(imageIDs) > 0:
            print("* Batch size: {}".format(batch.shape))
            preds = model.predict(batch)
            results = imagenet_utils.decode_predictions(preds)

            for (imageID, resultSet) in zip(imageIDs, results):
                output = []
                for (imagenetID, label, prob) in resultSet:
                    r = {"label": label, "probability": float(prob)}
                    output.append(r)

                db.set(imageID, json.dumps(output))

            # No ltrim needed - items already removed by lpop!

        time.sleep(settings.SERVER_SLEEP)
```

### Key Changes

1. **Removed `lrange`** - No longer reads without removing
2. **Added atomic `lpop` loop** - Pops up to BATCH_SIZE items
3. **Removed `ltrim`** - No longer needed since lpop already removed items
4. **Break on None** - Stops when queue is empty

## Alternative Solution: BRPOP for Blocking

For better efficiency, use `BRPOP` (Blocking Right Pop):

```python
# Blocking pop with timeout
item = db.brpop(settings.IMAGE_QUEUE, timeout=settings.SERVER_SLEEP)
if item is not None:
    queue_name, data = item
    # Process data
```

**Benefits:**
- No busy-waiting/polling
- More efficient (event-driven)
- Reduces CPU usage

## Solution for Issue 2: Check for Existing Keys

Add collision detection:

```python
k = str(uuid.uuid4())
# Check if key already exists (very unlikely but safe)
while db.exists(k):
    k = str(uuid.uuid4())  # Generate new UUID
```

## Solution for Issue 3: Set TTL on Result Keys

Add expiration to result keys:

```python
# In run_model_server.py:76
db.setex(imageID, 3600, json.dumps(output))  # Expires in 1 hour
```

Or:
```python
db.set(imageID, json.dumps(output))
db.expire(imageID, 3600)  # Set 1 hour TTL
```

## Testing the Fix

### Test Scenario 1: Multiple Model Servers

1. Start 3 model servers simultaneously:
   ```bash
   python run_model_server.py &
   python run_model_server.py &
   python run_model_server.py &
   ```

2. Run stress test:
   ```bash
   python stress_test.py
   ```

3. **Without fix:** Check Redis for duplicate processing (same job ID processed multiple times)
4. **With fix:** Each job processed exactly once

### Test Scenario 2: Work Distribution

1. Queue 100 jobs
2. Start 2 model servers
3. **Without fix:** Jobs may be duplicated or lost
4. **With fix:** All 100 jobs processed exactly once, distributed across servers

## Summary Table

| Issue | Location | Problem | Solution | Status |
|-------|----------|---------|----------|--------|
| Duplicate processing | run_model_server.py:31-79 | Non-atomic lrange + ltrim | Use atomic lpop | ✓ Fixed |
| UUID collision | run_web_server.py:61 | No collision check | Check exists() | Optional |
| Memory leak | run_model_server.py:76 | No TTL on results | Use setex() | Recommended |

## Performance Impact

**Before (with lrange + ltrim):**
- 2 servers process same batch → 2× redundant work
- ltrim race condition → lost jobs

**After (with lpop):**
- Each server gets unique items
- Perfect work distribution
- No redundant processing
- Linear scalability

## Diagram: Atomic vs Non-Atomic

### Non-Atomic (BROKEN)
```
Server 1: READ [A,B,C] → PROCESS → DELETE [A,B,C]
                ↓
Server 2:     READ [A,B,C] → PROCESS → DELETE [A,B,C]
                ↓
Result: A, B, C processed twice!
```

### Atomic (FIXED)
```
Server 1: POP A → POP B → POP C → PROCESS [A,B,C]
Server 2: POP D → POP E → POP F → PROCESS [D,E,F]

Result: Each item processed exactly once!
```
