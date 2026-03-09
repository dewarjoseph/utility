import time
import os
import shutil
from pathlib import Path
from core.worker import Worker
from core.project import Project, ProjectSettings, BoundingBox
from core.job_queue import Job

def setup_test_env():
    """Setup a clean test environment."""
    if os.path.exists("tests/performance/data"):
        shutil.rmtree("tests/performance/data")
    os.makedirs("tests/performance/data")

def run_benchmark():
    worker = Worker(worker_id="bench-worker")

    # Setup test project
    setup_test_env()
    settings = ProjectSettings(max_total_points=5, points_per_scan_cycle=5, scan_interval_seconds=0)

    # Just mock the project to avoid property issues
    from unittest.mock import MagicMock
    project = MagicMock(spec=Project)
    project.name = "Performance Test Project"
    project.settings = settings
    project.bounds = BoundingBox(
        min_latitude=36.9600,
        max_latitude=36.9800,
        min_longitude=-122.0500,
        max_longitude=-122.0200
    )
    project.points_collected = 0
    project.data_dir = Path("tests/performance/data")
    project.training_data_path = project.data_dir / "training_dataset.jsonl"
    project.stats = {}

    # Clear caches
    for f in ["osm_cache.db", "elevation_cache.db", "flood_cache.db"]:
        if os.path.exists(f): os.remove(f)

    print("Running baseline benchmark (N=5 points, real network calls)...")

    # Mock queue to avoid DB errors
    worker.queue = MagicMock()
    project.save = MagicMock()

    start_time = time.time()
    job = Job(id=1, project_id="bench-perf-test")
    worker._run_scan(job, project)
    end_time = time.time()

    duration = end_time - start_time
    print(f"Baseline (N+1): {duration:.4f} seconds ({5/duration:.2f} points/sec)")

    print("Running baseline benchmark (N=5 points, cached)...")
    project.points_collected = 0
    start_time2 = time.time()
    worker._run_scan(job, project)
    end_time2 = time.time()

    duration2 = end_time2 - start_time2
    print(f"Baseline (Cached): {duration2:.4f} seconds ({5/duration2:.2f} points/sec)")

    # Cleanup
    if os.path.exists("tests/performance/data"):
        shutil.rmtree("tests/performance/data")

if __name__ == "__main__":
    run_benchmark()
