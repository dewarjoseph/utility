import pytest
import sqlite3
import time
from core.job_queue import JobQueue, JobStatus

@pytest.fixture
def job_queue(tmp_path):
    db_file = tmp_path / "test_queue.db"
    return JobQueue(db_path=str(db_file))

def test_enqueue_and_claim(job_queue):
    """Verify adding and picking up jobs."""
    job_id = job_queue.enqueue("project-1", priority=10)
    assert job_id > 0
    
    job = job_queue.claim_next("worker-1")
    assert job is not None
    assert job.id == job_id
    assert job.project_id == "project-1"
    assert job.status == JobStatus.RUNNING
    assert job.worker_id == "worker-1"

def test_priority_ordering(job_queue):
    """Verify higher priority jobs are claimed first."""
    id_low = job_queue.enqueue("low", priority=1)
    id_high = job_queue.enqueue("high", priority=100)
    
    job1 = job_queue.claim_next("worker-1")
    assert job1.id == id_high
    
    job2 = job_queue.claim_next("worker-1")
    assert job2.id == id_low

def test_complete_job(job_queue):
    """Verify job lifecycle: complete."""
    job_id = job_queue.enqueue("project-1")
    job_queue.claim_next("worker-1")
    
    job_queue.update_progress(job_id, 50, "Halfway")
    job = job_queue.get_job(job_id)
    assert job.progress_percent == 50
    
    job_queue.complete(job_id)
    job = job_queue.get_job(job_id)
    assert job.status == JobStatus.COMPLETED
    assert job.progress_percent == 100

def test_fail_job(job_queue):
    """Verify job lifecycle: fail."""
    job_id = job_queue.enqueue("project-1")
    job_queue.claim_next("worker-1")
    
    job_queue.fail(job_id, "Something exploded")
    job = job_queue.get_job(job_id)
    assert job.status == JobStatus.FAILED
    assert job.error_message == "Something exploded"

def test_pause_resume(job_queue):
    """Verify pause and resume functionality."""
    job_id = job_queue.enqueue("project-1")
    job_queue.claim_next("worker-1")
    
    job_queue.pause(job_id)
    job = job_queue.get_job(job_id)
    assert job.status == JobStatus.PAUSED
    
    # Resume puts it back to pending
    job_queue.resume(job_id)
    job = job_queue.get_job(job_id)
    assert job.status == JobStatus.PENDING
    assert job.worker_id is None
    
    # Can claim again
    claimed = job_queue.claim_next("worker-2")
    assert claimed.id == job_id
    assert claimed.worker_id == "worker-2"

def test_cleanup_stale_jobs(job_queue):
    """Verify stale job cleanup."""
    job_id = job_queue.enqueue("project-1")
    job_queue.claim_next("worker-1")
    
    # Verify it's running
    assert job_queue.get_job(job_id).status == JobStatus.RUNNING
    
    # Clean up with max_age=0 hours (should reset immediately)
    job_queue.cleanup_stale_jobs(max_age_hours=0)
    
    job = job_queue.get_job(job_id)
    assert job.status == JobStatus.PENDING
    assert "Reset after timeout" in job.progress_message
    assert job.worker_id is None

def test_get_project_jobs(job_queue):
    """Verify filtering by project."""
    job_queue.enqueue("p1")
    job_queue.enqueue("p1")
    job_queue.enqueue("p2")
    
    jobs_p1 = job_queue.get_project_jobs("p1")
    assert len(jobs_p1) == 2
    
    jobs_p2 = job_queue.get_project_jobs("p2")
    assert len(jobs_p2) == 1

def test_get_queue_stats(job_queue):
    """Verify queue statistics."""
    job_queue.enqueue("p1")
    jid = job_queue.enqueue("p2")
    job_queue.claim_next("w1") # Claims one, p2 is newer but priority 0? Wait, sort is priority DESC, created_at ASC
    # p1 created first, so p1 claimed
    
    stats = job_queue.get_queue_stats()
    # 1 running, 1 pending
    assert stats.get("running") == 1
    assert stats.get("pending") == 1
