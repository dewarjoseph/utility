import pytest
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
