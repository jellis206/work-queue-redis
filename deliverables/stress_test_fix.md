# Stress Test Thread Joining Fix

## Problem

The original `stress_test.py` had a critical bug where threads were started but not properly joined before the program terminated.

### Original Code (Lines 41-51)
```python
# loop over the number of threads
for i in range(0, NUM_REQUESTS):
    # start a new thread to call the API
    t = Thread(target=call_predict_endpoint, args=(i,))
    t.daemon = True
    t.start()
    time.sleep(SLEEP_COUNT)

# insert a long sleep so we can wait until the server is finished
# processing the images
time.sleep(300)
```

### Issues

1. **No thread tracking:** Thread objects were not stored, so they couldn't be joined later
2. **Daemon threads:** `t.daemon = True` means threads are killed when main exits
3. **Fixed timeout:** `time.sleep(300)` waits exactly 5 minutes regardless of actual completion
4. **Silent failures:** If threads take longer than 300 seconds, they're killed without notification
5. **Early exit:** Program could exit before threads finish if sleep duration is too short
6. **Wasteful waiting:** If all threads finish in 10 seconds, still waits full 300 seconds

## Solution

### Fixed Code (Lines 41-58)
```python
# store all threads in a list
threads = []

# loop over the number of threads
for i in range(0, NUM_REQUESTS):
    # start a new thread to call the API
    t = Thread(target=call_predict_endpoint, args=(i,))
    t.daemon = True
    t.start()
    threads.append(t)
    time.sleep(SLEEP_COUNT)

# wait for all threads to complete before exiting
print(f"[INFO] Waiting for {len(threads)} threads to complete...")
for t in threads:
    t.join()

print("[INFO] All threads completed!")
```

### Changes Made

1. **Thread list:** Created `threads = []` to store all thread references (line 42)
2. **Store threads:** Added `threads.append(t)` after starting each thread (line 50)
3. **Proper joining:** Replaced fixed `time.sleep(300)` with proper `t.join()` loop (lines 54-56)
4. **User feedback:** Added informative print statements to show progress (lines 54, 58)

### How It Works

**Thread.join() explained:**
- `t.join()` blocks the calling thread until thread `t` completes
- If thread is already finished, `join()` returns immediately
- No timeout is specified, so it waits indefinitely for completion
- All threads are joined sequentially, but since they run in parallel, total wait time ≈ longest thread duration

**Flow:**
1. Create empty list to track threads
2. Start all threads with small delays (SLEEP_COUNT = 0.05s between starts)
3. Once all threads are started, begin joining
4. Main thread blocks until each thread completes
5. Print completion message only after ALL threads finish
6. Program exits cleanly

## Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Reliability** | May exit before threads finish | Guaranteed to wait for all threads |
| **Efficiency** | Always waits 300 seconds | Waits only as long as needed |
| **Debugging** | Silent failures | Clear progress indicators |
| **Thread safety** | Potential data corruption | Clean shutdown |
| **User feedback** | No indication of progress | Shows thread count and completion |

## Testing

To verify the fix works:

1. **Start servers:**
   ```bash
   python run_web_server.py   # Terminal 1
   python run_model_server.py # Terminal 2
   ```

2. **Run stress test:**
   ```bash
   python stress_test.py      # Terminal 3
   ```

3. **Expected output:**
   ```
   [INFO] Waiting for 500 threads to complete...
   [INFO] thread 0 OK
   [INFO] thread 1 OK
   ...
   [INFO] thread 499 OK
   [INFO] All threads completed!
   ```

## Additional Improvements (Optional)

For even better stress testing, consider:

1. **Timeout per join:**
   ```python
   for t in threads:
       t.join(timeout=30.0)  # Max 30s per thread
       if t.is_alive():
           print(f"[WARNING] Thread {t} timed out!")
   ```

2. **Success/failure tracking:**
   ```python
   results = {"success": 0, "failed": 0}
   # Update in call_predict_endpoint using a lock
   ```

3. **Progress bar:**
   ```python
   from tqdm import tqdm
   for t in tqdm(threads, desc="Waiting for threads"):
       t.join()
   ```

## Key Takeaway

**Always join threads before program exit** to ensure:
- All work completes
- Resources are properly cleaned up
- Results are captured
- No silent failures occur

The fixed code uses the proper threading pattern of **create → start → join**.
