import time
import os
import shutil
import sqlite3
from pathlib import Path
import logging
from core.project import ProjectManager, Project, INDEX_DB_PATH

# Disable logging to focus on performance
logging.basicConfig(level=logging.ERROR)

def setup_projects(num_projects):
    pm = ProjectManager()
    # Ensure projects dir is clean
    if pm.PROJECTS_DIR.exists():
        shutil.rmtree(pm.PROJECTS_DIR)
    pm.PROJECTS_DIR.mkdir()

    # Remove index db if it exists
    if INDEX_DB_PATH.exists():
        os.remove(INDEX_DB_PATH)

    print(f"Creating {num_projects} projects...")
    for i in range(num_projects):
        pm.create_project(f"Project {i}", 37.0, -122.0)

    # Close any connections that might be open
    # (ProjectManager doesn't keep persistent connection)

def benchmark_sync():
    # Remove index db to force sync
    if INDEX_DB_PATH.exists():
        os.remove(INDEX_DB_PATH)

    start_time = time.time()
    pm = ProjectManager() # This calls _sync_index_if_needed
    end_time = time.time()

    return end_time - start_time

if __name__ == "__main__":
    num_projects = 100
    setup_projects(num_projects)

    # Run benchmark multiple times
    durations = []
    for i in range(5):
        duration = benchmark_sync()
        durations.append(duration)
        print(f"Sync {i+1} took {duration:.4f} seconds")

    avg_duration = sum(durations) / len(durations)
    print(f"Average sync time for {num_projects} projects: {avg_duration:.4f} seconds")
