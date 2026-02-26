import pytest
import threading
import time
from unittest.mock import MagicMock, patch, mock_open
from core.worker import Worker
from core.job_queue import Job
from core.project import Project, ProjectSettings, BoundingBox

@pytest.fixture
def mock_worker():
    with patch('core.worker.JobQueue') as mock_q, \
         patch('core.worker.ProjectManager') as mock_pm:
        worker = Worker(worker_id="test-worker")
        worker.queue = mock_q.return_value
        worker.project_manager = mock_pm.return_value
        yield worker

def test_worker_initialization(mock_worker):
    assert mock_worker.worker_id == "test-worker"
    assert not mock_worker._running

def test_process_job_success(mock_worker):
    """Verify successful job processing flow."""
    job = Job(id=1, project_id="p1")
    
    # Mock project
    project = MagicMock(spec=Project)
    project.name = "Test Project"
    project.settings = ProjectSettings()
    project.settings.max_total_points = 1
    project.settings.points_per_scan_cycle = 1
    project.bounds = BoundingBox(0, 0, 1, 1)
    project.points_collected = 0
    project.data_dir = MagicMock()
    project.training_data_path = "test.jsonl"
    project.stats = {}
    
    mock_worker.project_manager.get_project.return_value = project
    
    # Mock feature generation
    mock_worker._generate_features = MagicMock(return_value={})
    
    # Mock file writing
    with patch("builtins.open", mock_open()) as mock_file:
        mock_worker._process_job(job)
    
    # Verify status updates
    mock_worker.queue.complete.assert_called_with(job.id)
    assert project.save.call_count >= 2 # Scanning, Progress, Completed

def test_process_job_project_not_found(mock_worker):
    """Verify handling of missing project."""
    job = Job(id=1, project_id="p1")
    mock_worker.project_manager.get_project.return_value = None
    
    mock_worker._process_job(job)
    
    mock_worker.queue.fail.assert_called()

def test_calculate_score_fallback(mock_worker):
    """Verify score calculation falls back to rules if scorer fails."""
    features = {"has_water": True} # Rule based fallback logic
    # Make import fail
    with patch.dict('sys.modules', {'core.scoring': None}):
        score = mock_worker._calculate_score(features, [], "general")
        # Base 5.0, no rules matched
        assert score == 5.0

def test_worker_stop_cleanly(mock_worker):
    """
    Test that calling stop() properly terminates the worker loop.
    This simulates the worker running in a thread and being stopped from another thread.
    """
    # Configure the mock queue to return None (no jobs) so the worker enters the sleep loop
    mock_worker.queue.claim_next.return_value = None

    # Patch time.sleep in the worker module to avoid waiting
    # We use a tiny sleep to avoid busy-waiting loop in the worker thread.
    # We must capture the real sleep before patching to avoid recursion.
    real_sleep = time.sleep
    with patch('core.worker.time.sleep', side_effect=lambda x: real_sleep(0.001)) as mock_sleep:
        # Start worker in a separate thread so we can stop it
        worker_thread = threading.Thread(target=mock_worker.run)
        worker_thread.start()

        # Let it start up and enter the loop
        # We use a short sleep to ensure the thread has started
        # This sleep is NOT patched because we imported 'time' in this test file
        time.sleep(0.1)

        # Verify it's running
        assert worker_thread.is_alive()
        assert mock_worker._running

        # Trigger the stop
        mock_worker.stop()

        # Wait for the thread to finish
        worker_thread.join(timeout=3.0)

    # Verify clean shutdown
    assert not worker_thread.is_alive()
    assert mock_worker._shutdown_requested

def test_worker_stop_during_job(mock_worker):
    """
    Test that stop() works even if called while a job is being processed.
    """
    # Create a dummy job
    job = Job(id=1, project_id="p1")

    # Mock project manager to return a valid project
    project = MagicMock(spec=Project)
    project.name = "Test Project"  # Set the name attribute
    project.settings = ProjectSettings()
    # Set points high so it loops in _run_scan
    project.settings.max_total_points = 1000
    project.settings.points_per_scan_cycle = 1
    project.settings.scan_interval_seconds = 0.1
    project.points_collected = 0
    project.bounds = BoundingBox(0, 0, 1, 1)
    project.data_dir = MagicMock()
    project.stats = {}

    mock_worker.project_manager.get_project.return_value = project
    mock_worker._generate_features = MagicMock(return_value={})

    # Mock queue to return the job once, then None.
    # Important: The worker loop continues calling claim_next.
    # If we only provide 2 items, it might crash with StopIteration if the timing is off.
    # So we provide an infinite stream of None after the job.
    def mock_claim_next(worker_id):
        if hasattr(mock_claim_next, 'called'):
            return None
        mock_claim_next.called = True
        return job

    mock_worker.queue.claim_next.side_effect = mock_claim_next

    # Mock file writing to avoid IO
    with patch("builtins.open", mock_open()):
        # Start worker
        worker_thread = threading.Thread(target=mock_worker.run)
        worker_thread.start()

        # Let it pick up the job. The job scanning loop is infinite unless we stop it or it finishes.
        # We need to wait until the worker is actually processing the job.

        # Wait up to 1 second for the job to be picked up
        timeout = 1.0
        start_time = time.time()
        while mock_worker._current_job is None and time.time() - start_time < timeout:
            time.sleep(0.05)

        assert worker_thread.is_alive()
        assert mock_worker._current_job is not None
        assert mock_worker._current_job.id == job.id

        # Stop the worker
        mock_worker.stop()

        # Wait for it to finish
        worker_thread.join(timeout=2.0)

        assert not worker_thread.is_alive()
        assert mock_worker._shutdown_requested
