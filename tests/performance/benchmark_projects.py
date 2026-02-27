"""
Performance Benchmark for Project Management

Measures the performance of list_projects() with varying numbers of projects.
"""
import time
import os
import sys
import shutil
import tempfile
import sqlite3
import random
import logging
import json
from pathlib import Path
from unittest.mock import patch

# Adjust sys.path to ensure we can import core
sys.path.append(str(Path(__file__).parent.parent.parent))

from core.project import ProjectManager, Project

# Configure logging to silence normal output during benchmark
logging.basicConfig(level=logging.ERROR)

def generate_projects(pm, num_projects, base_idx=0):
    """Generates N projects using the manager."""
    print(f"Generating batch of {num_projects} projects...")
    start = time.time()

    for i in range(num_projects):
        pm.create_project(
            name=f"Project {time.time()} {base_idx + i}",
            center_lat=37.0 + (i * 0.001),
            center_lon=-122.0 + (i * 0.001),
            description=f"Description for project {i}"
        )
    print(f"  Batch complete in {time.time() - start:.2f}s")

def benchmark_list_projects(pm, iterations=10):
    """Runs list_projects() multiple times and returns average time."""
    times = []
    projects = []
    for _ in range(iterations):
        start = time.time()
        projects = pm.list_projects()
        end = time.time()
        times.append(end - start)
        if len(projects) == 0:
            print("WARNING: list_projects() returned 0 projects!")
        else:
            assert len(projects) > 0

    avg_time = sum(times) / len(times)
    return avg_time, len(projects)

def benchmark_list_projects_files(pm, iterations=3):
    """Runs _list_projects_from_files() multiple times."""
    times = []
    for _ in range(iterations):
        start = time.time()
        projects = pm._list_projects_from_files()
        end = time.time()
        times.append(end - start)
        if len(projects) == 0:
            print("WARNING: _list_projects_from_files() returned 0 projects!")
        else:
            assert len(projects) > 0

    avg_time = sum(times) / len(times)
    return avg_time

def run_benchmark():
    # Create a temporary directory for projects
    # We must change CWD to make hardcoded Path("projects") resolve correctly
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        try:
            os.chdir(temp_dir)
            print(f"Benchmarking in {temp_dir}...")

            # Since we changed CWD, we don't need to patch paths for creating files,
            # BUT core/project.py uses INDEX_DB_PATH = Path("projects") / "index.db"
            # which is evaluated at import time. Since we imported core.project BEFORE chdir,
            # INDEX_DB_PATH points to the OLD directory.
            # We MUST patch INDEX_DB_PATH to point to the new location relative to CWD.

            projects_dir = Path("projects")
            projects_dir.mkdir()
            index_db_path = projects_dir / "index.db"

            # Patch INDEX_DB_PATH in core.project
            with patch("core.project.INDEX_DB_PATH", index_db_path):
                pm = ProjectManager()

                # 1. Small Scale
                generate_projects(pm, 50)
                t_db, count = benchmark_list_projects(pm)
                t_file = benchmark_list_projects_files(pm)
                print(f"\n[50 Projects]")
                print(f"  DB Time:   {t_db*1000:.2f} ms")
                print(f"  File Time: {t_file*1000:.2f} ms")
                print(f"  Speedup:   {t_file/t_db:.2f}x")

                # 2. Medium Scale (Total 150)
                generate_projects(pm, 100, base_idx=50)
                t_db, count = benchmark_list_projects(pm)
                t_file = benchmark_list_projects_files(pm)
                print(f"\n[150 Projects]")
                print(f"  DB Time:   {t_db*1000:.2f} ms")
                print(f"  File Time: {t_file*1000:.2f} ms")
                print(f"  Speedup:   {t_file/t_db:.2f}x")

                # 3. Large Scale (Total 500)
                generate_projects(pm, 350, base_idx=150)
                t_db, count = benchmark_list_projects(pm)

                # File based gets very slow, so reduce iterations
                if count > 300:
                    t_file = benchmark_list_projects_files(pm, iterations=1)
                else:
                    t_file = benchmark_list_projects_files(pm)

                print(f"\n[500 Projects]")
                print(f"  DB Time:   {t_db*1000:.2f} ms")
                print(f"  File Time: {t_file*1000:.2f} ms")
                print(f"  Speedup:   {t_file/t_db:.2f}x")

        finally:
            os.chdir(cwd)

if __name__ == "__main__":
    run_benchmark()
