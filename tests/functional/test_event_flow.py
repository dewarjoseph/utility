import pytest
import time
import threading
import random
from concurrent.futures import ThreadPoolExecutor
from core.event_buffer import EventBuffer

@pytest.fixture
def event_buffer(tmp_path):
    # Use a file-based DB for tests to support multi-threading
    # :memory: is unique per connection/thread, so threads see empty DBs
    db_file = tmp_path / "test_events.db"
    buffer = EventBuffer(db_path=str(db_file))
    yield buffer
    buffer.close()

def test_high_throughput_insert(event_buffer):
    """Verify that the buffer can handle high-speed insertions without error."""
    start_time = time.time()
    count = 1000
    
    for _ in range(count):
        success = event_buffer.insert_event(
            quantum_data={'lat': 36.97, 'lon': -122.02, 'is_surprise': False},
            score=random.uniform(0, 10),
            ml_error=random.uniform(0, 1)
        )
        assert success, "Insertion failed"
        
    duration = time.time() - start_time
    stats = event_buffer.get_stats()
    
    assert stats['total_events'] == count
    print(f"\nThroughput: {count / duration:.2f} events/sec")

def test_concurrency_thread_safety(event_buffer):
    """Verify thread safety with concurrent writers."""
    def worker(worker_id):
        for i in range(100):
            event_buffer.insert_event(
                quantum_data={'lat': 36.0, 'lon': -122.0},
                score=5.0,
                mismatches=[{'mismatch_type': 'test', 'severity': 1}]
            )
            
    num_threads = 5
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        for f in futures:
            f.result()  # Wait for completion and raise exceptions if any
            
    stats = event_buffer.get_stats()
    # 5 threads * 100 events = 500 total
    assert stats['total_events'] == 500

def test_pruning_logic(event_buffer):
    """Verify that the buffer prunes old events when MAX_EVENTS is exceeded."""
    # Temporarily lower limits for testing
    event_buffer.MAX_EVENTS = 50
    event_buffer.PRUNE_BATCH_SIZE = 10
    # Provide a shorter prune interval to force check
    event_buffer._last_prune_time = 0 
    
    # Insert more than max
    total_insert = 70
    for i in range(total_insert):
        event_buffer.insert_event(
            quantum_data={'lat': 0, 'lon': 0},
            score=0.0
        )
        # Artificially age the prune timer so it runs every time
        event_buffer._last_prune_time = 0
        
    stats = event_buffer.get_stats()
    assert stats['total_events'] <= event_buffer.MAX_EVENTS + event_buffer.PRUNE_BATCH_SIZE
    # Ideally should be close to MAX_EVENTS

def test_aggregations(event_buffer):
    """Verify velocity and mismatch summary calculations."""
    # Insert high value events
    for _ in range(5):
        event_buffer.insert_event(
            quantum_data={'lat': 0, 'lon': 0},
            score=8.0 # Above default threshold 5.0
        )
    
    # Insert low value events
    for _ in range(5):
        event_buffer.insert_event(
            quantum_data={'lat': 0, 'lon': 0},
            score=2.0
        )
        
    # Check velocity
    velocity = event_buffer.get_high_value_velocity()
    assert velocity == 5
    
    # Insert mismatches
    event_buffer.insert_event(
        quantum_data={'lat': 0, 'lon': 0},
        score=5.0,
        mismatches=[{'mismatch_type': 'slope', 'severity': 0.8}]
    )
    
    summary = event_buffer.get_mismatch_summary()
    assert summary['slope'] >= 1
