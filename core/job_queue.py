"""
Job Queue - SQLite-backed queue for concurrent project processing.

This enables multiple projects to be scanned in sequence or parallel,
with persistent state that survives restarts.
"""

import os
import sqlite3
import json
import threading
import time
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from pathlib import Path
from enum import Enum
import logging

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# JOB STATUS
# ═══════════════════════════════════════════════════════════════════════════
class JobStatus:
    """Job lifecycle states."""
    PENDING = "pending"        # Waiting to be picked up
    RUNNING = "running"        # Currently being processed
    PAUSED = "paused"          # User paused
    COMPLETED = "completed"    # Successfully finished
    FAILED = "failed"          # Error occurred
    CANCELLED = "cancelled"    # User cancelled


# ═══════════════════════════════════════════════════════════════════════════
# JOB
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class Job:
    """
    A job in the queue representing a project scan task.
    
    Attributes:
        id: Unique job ID (auto-generated)
        project_id: Which project this job is for
        status: Current job status
        priority: Higher number = processed first (default 0)
        created_at: When the job was created
        started_at: When processing began (null if not started)
        completed_at: When processing finished (null if not done)
        progress_percent: How far along (0-100)
        progress_message: Current activity description
        error_message: Error details if status is FAILED
        worker_id: Which worker is processing this job
    """
    id: int
    project_id: str
    status: str = JobStatus.PENDING
    priority: int = 0
    created_at: str = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress_percent: int = 0
    progress_message: str = "Waiting to start"
    error_message: Optional[str] = None
    worker_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress_percent": self.progress_percent,
            "progress_message": self.progress_message,
            "error_message": self.error_message,
            "worker_id": self.worker_id,
        }


# ═══════════════════════════════════════════════════════════════════════════
# JOB QUEUE
# ═══════════════════════════════════════════════════════════════════════════
class JobQueue:
    """
    SQLite-backed job queue for reliable, persistent task processing.
    
    Features:
    - Survives restarts
    - Thread-safe
    - Priority ordering
    - Progress tracking
    
    Usage:
        queue = JobQueue()
        job_id = queue.enqueue("project-abc")
        job = queue.claim_next("worker-1")
        queue.update_progress(job_id, 50, "Processing...")
        queue.complete(job_id)
    """
    
    DEFAULT_DB_PATH = "job_queue.db"
    
    def __init__(self, db_path: str = None):
        """
        Initialize the job queue.
        
        Args:
            db_path: Path to SQLite database. Defaults to 'job_queue.db'
        """
        self.db_path = db_path or self.DEFAULT_DB_PATH
        self._lock = threading.RLock()
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a thread-local database connection."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Initialize database schema."""
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS jobs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending',
                        priority INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL,
                        started_at TEXT,
                        completed_at TEXT,
                        progress_percent INTEGER DEFAULT 0,
                        progress_message TEXT DEFAULT 'Waiting to start',
                        error_message TEXT,
                        worker_id TEXT
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_project ON jobs(project_id)")
                conn.commit()
                log.info(f"Job queue initialized at {self.db_path}")
            finally:
                conn.close()
    
    def enqueue(self, project_id: str, priority: int = 0) -> int:
        """
        Add a new job to the queue.
        
        Args:
            project_id: The project to process
            priority: Higher priority jobs are processed first
            
        Returns:
            The new job's ID
        """
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO jobs (project_id, priority, created_at, status)
                    VALUES (?, ?, ?, ?)
                    """,
                    (project_id, priority, datetime.now().isoformat(), JobStatus.PENDING)
                )
                conn.commit()
                job_id = cursor.lastrowid
                log.info(f"Enqueued job {job_id} for project {project_id}")
                return job_id
            finally:
                conn.close()
    
    def claim_next(self, worker_id: str) -> Optional[Job]:
        """
        Claim the next available job for processing.
        
        This atomically marks the job as RUNNING so no other worker takes it.
        
        Args:
            worker_id: Identifier for the worker claiming the job
            
        Returns:
            The claimed Job, or None if queue is empty
        """
        with self._lock:
            conn = self._get_connection()
            try:
                # Find the highest priority pending job
                row = conn.execute(
                    """
                    SELECT * FROM jobs 
                    WHERE status = ? 
                    ORDER BY priority DESC, created_at ASC 
                    LIMIT 1
                    """,
                    (JobStatus.PENDING,)
                ).fetchone()
                
                if not row:
                    return None
                
                # Claim it
                now = datetime.now().isoformat()
                conn.execute(
                    """
                    UPDATE jobs 
                    SET status = ?, started_at = ?, worker_id = ?, 
                        progress_message = 'Starting...'
                    WHERE id = ?
                    """,
                    (JobStatus.RUNNING, now, worker_id, row["id"])
                )
                conn.commit()
                
                job = Job(
                    id=row["id"],
                    project_id=row["project_id"],
                    status=JobStatus.RUNNING,
                    priority=row["priority"],
                    created_at=row["created_at"],
                    started_at=now,
                    worker_id=worker_id,
                )
                log.info(f"Worker {worker_id} claimed job {job.id}")
                return job
            finally:
                conn.close()
    
    def update_progress(self, job_id: int, percent: int, message: str):
        """
        Update job progress.
        
        Args:
            job_id: The job to update
            percent: Progress percentage (0-100)
            message: Human-readable status message
        """
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    UPDATE jobs 
                    SET progress_percent = ?, progress_message = ?
                    WHERE id = ?
                    """,
                    (percent, message, job_id)
                )
                conn.commit()
            finally:
                conn.close()
    
    def complete(self, job_id: int):
        """Mark a job as successfully completed."""
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    UPDATE jobs 
                    SET status = ?, completed_at = ?, progress_percent = 100,
                        progress_message = 'Completed'
                    WHERE id = ?
                    """,
                    (JobStatus.COMPLETED, datetime.now().isoformat(), job_id)
                )
                conn.commit()
                log.info(f"Job {job_id} completed")
            finally:
                conn.close()
    
    def fail(self, job_id: int, error_message: str):
        """Mark a job as failed with an error message."""
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    UPDATE jobs 
                    SET status = ?, completed_at = ?, error_message = ?,
                        progress_message = 'Failed'
                    WHERE id = ?
                    """,
                    (JobStatus.FAILED, datetime.now().isoformat(), error_message, job_id)
                )
                conn.commit()
                log.error(f"Job {job_id} failed: {error_message}")
            finally:
                conn.close()
    
    def pause(self, job_id: int):
        """Pause a running job."""
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    "UPDATE jobs SET status = ?, progress_message = 'Paused' WHERE id = ?",
                    (JobStatus.PAUSED, job_id)
                )
                conn.commit()
            finally:
                conn.close()
    
    def resume(self, job_id: int):
        """Resume a paused job (puts it back in pending)."""
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    "UPDATE jobs SET status = ?, worker_id = NULL WHERE id = ?",
                    (JobStatus.PENDING, job_id)
                )
                conn.commit()
            finally:
                conn.close()
    
    def cancel(self, job_id: int):
        """Cancel a job."""
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    UPDATE jobs SET status = ?, completed_at = ?,
                        progress_message = 'Cancelled'
                    WHERE id = ?
                    """,
                    (JobStatus.CANCELLED, datetime.now().isoformat(), job_id)
                )
                conn.commit()
            finally:
                conn.close()
    
    def get_job(self, job_id: int) -> Optional[Job]:
        """Get a specific job by ID."""
        conn = self._get_connection()
        try:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row:
                return Job(**dict(row))
            return None
        finally:
            conn.close()
    
    def get_project_jobs(self, project_id: str) -> List[Job]:
        """Get all jobs for a project."""
        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,)
            ).fetchall()
            return [Job(**dict(row)) for row in rows]
        finally:
            conn.close()
    
    def get_active_jobs(self) -> List[Job]:
        """Get all pending or running jobs."""
        conn = self._get_connection()
        try:
            rows = conn.execute(
                """
                SELECT * FROM jobs 
                WHERE status IN (?, ?)
                ORDER BY priority DESC, created_at ASC
                """,
                (JobStatus.PENDING, JobStatus.RUNNING)
            ).fetchall()
            return [Job(**dict(row)) for row in rows]
        finally:
            conn.close()
    
    def get_queue_stats(self) -> Dict[str, int]:
        """Get counts of jobs by status."""
        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT status, COUNT(*) as count FROM jobs GROUP BY status"
            ).fetchall()
            return {row["status"]: row["count"] for row in rows}
        finally:
            conn.close()
    
    def cleanup_stale_jobs(self, max_age_hours: int = 24):
        """
        Reset jobs that have been running too long (crashed workers).
        
        Args:
            max_age_hours: Jobs running longer than this are reset to pending
        """
        with self._lock:
            conn = self._get_connection()
            try:
                # Find stale running jobs
                cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
                conn.execute(
                    """
                    UPDATE jobs 
                    SET status = ?, worker_id = NULL,
                        progress_message = 'Reset after timeout'
                    WHERE status = ? AND started_at < ?
                    """,
                    (JobStatus.PENDING, JobStatus.RUNNING, 
                     datetime.fromtimestamp(cutoff).isoformat())
                )
                conn.commit()
            finally:
                conn.close()
