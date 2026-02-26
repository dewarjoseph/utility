
import os
import sys
import time
import shutil
import json
import random
from pathlib import Path
from dataclasses import dataclass
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.worker import Worker
from core.project import Project, ProjectSettings, BoundingBox

@dataclass
class MockProject:
    id: str = "perf-test"
    data_dir: Path = Path("tests/performance/data")
    training_data_path: Path = Path("tests/performance/data/training_dataset.jsonl")

    def save(self):
        pass

def setup_test_env():
    """Setup a clean test environment."""
    if os.path.exists("tests/performance/data"):
        shutil.rmtree("tests/performance/data")
    os.makedirs("tests/performance/data")

def benchmark_io_write(n_points=1000):
    """
    Benchmark the time taken to write points to disk.
    Now we are testing the ACTUAL methods on the Worker class.
    """
    print(f"Benchmarking I/O for {n_points} points...")

    worker = Worker(worker_id="bench-worker")
    project = MockProject()

    # Generate mock data
    points = []
    for i in range(n_points):
        lat = 37.0 + (i * 0.001)
        lon = -122.0 + (i * 0.001)
        features = {"has_water": True, "has_road": False}
        score = 5.0
        points.append((lat, lon, features, score))

    # --- METHOD 1: One-by-one (Legacy wrapper) ---
    setup_test_env()

    start_time = time.time()
    for lat, lon, features, score in points:
        worker._save_point(project, lat, lon, features, score)
    end_time = time.time()

    duration_single = end_time - start_time
    print(f"Legacy 1-by-1 (via _save_point): {duration_single:.4f} seconds ({n_points/duration_single:.2f} points/sec)")

    # verify file size/lines
    with open(project.training_data_path, 'r') as f:
        lines = len(f.readlines())
        assert lines == n_points

    # --- METHOD 2: Batched (New Implementation) ---
    setup_test_env()

    # Convert to format expected by _save_points_batch
    batch_points = [{"lat": p[0], "lon": p[1], "features": p[2], "score": p[3]} for p in points]

    start_time = time.time()
    worker._save_points_batch(project, batch_points)
    end_time = time.time()

    duration_batch = end_time - start_time
    print(f"Batched (via _save_points_batch): {duration_batch:.4f} seconds ({n_points/duration_batch:.2f} points/sec)")

    # verify file size/lines
    with open(project.training_data_path, 'r') as f:
        lines = len(f.readlines())
        assert lines == n_points

    speedup = duration_single / duration_batch
    print(f"Speedup: {speedup:.2f}x")

    # Cleanup
    if os.path.exists("tests/performance/data"):
        shutil.rmtree("tests/performance/data")

if __name__ == "__main__":
    benchmark_io_write(n_points=2000)
