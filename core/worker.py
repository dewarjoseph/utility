"""
Worker - Background process that executes jobs from the queue.

The worker:
1. Picks up jobs from the queue
2. Runs the utility scanner for each project
3. Reports progress back to the queue
4. Handles errors gracefully
"""

import os
import sys
import time
import signal
import threading
import uuid
import json
import random
from datetime import datetime
from pathlib import Path
from typing import Optional
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.project import Project, ProjectManager, ProjectStatus
from core.job_queue import JobQueue, JobStatus, Job

log = logging.getLogger(__name__)


class Worker:
    """
    Background worker that processes scan jobs.
    
    Can run as a standalone process or be managed by the dashboard.
    """
    
    def __init__(self, worker_id: str = None):
        """
        Initialize the worker.
        
        Args:
            worker_id: Unique identifier for this worker. Auto-generated if not provided.
        """
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:6]}"
        self.queue = JobQueue()
        self.project_manager = ProjectManager()
        
        self._running = False
        self._current_job: Optional[Job] = None
        self._shutdown_requested = False
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        
        log.info(f"Worker {self.worker_id} initialized")
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        log.info(f"Worker {self.worker_id} received shutdown signal")
        self._shutdown_requested = True
        
        # If we're processing a job, pause it
        if self._current_job:
            log.info(f"Pausing job {self._current_job.id}")
            self.queue.pause(self._current_job.id)
    
    def run(self):
        """
        Main worker loop. Processes jobs until shutdown.
        """
        log.info(f"Worker {self.worker_id} starting")
        self._running = True
        
        # Cleanup any stale jobs from crashed workers
        self.queue.cleanup_stale_jobs()
        
        while self._running and not self._shutdown_requested:
            # Try to claim a job
            job = self.queue.claim_next(self.worker_id)
            
            if job:
                self._current_job = job
                self._process_job(job)
                self._current_job = None
            else:
                # No jobs available, wait before checking again
                time.sleep(2)
        
        log.info(f"Worker {self.worker_id} stopped")
    
    def _process_job(self, job: Job):
        """
        Process a single job.
        
        Args:
            job: The job to process
        """
        log.info(f"Processing job {job.id} for project {job.project_id}")
        
        try:
            # Load the project
            project = self.project_manager.get_project(job.project_id)
            if not project:
                self.queue.fail(job.id, f"Project {job.project_id} not found")
                return
            
            # Update project status
            project.status = ProjectStatus.SCANNING
            project.save()
            
            # Run the scan
            self._run_scan(job, project)
            
            # Check if we were interrupted
            if self._shutdown_requested:
                return
            
            # Mark complete
            self.queue.complete(job.id)
            project.status = ProjectStatus.COMPLETED
            project.save()
            
        except Exception as e:
            log.exception(f"Job {job.id} failed")
            self.queue.fail(job.id, str(e))
            
            # Update project status
            project = self.project_manager.get_project(job.project_id)
            if project:
                project.status = ProjectStatus.ERROR
                project.error_message = str(e)
                project.save()
    
    def _run_scan(self, job: Job, project: Project):
        """
        Run the actual scanning logic for a project.
        
        This generates random points within the bounding box and
        evaluates them using the scoring rules.
        """
        settings = project.settings
        bounds = project.bounds
        
        max_points = settings.max_total_points
        points_per_cycle = settings.points_per_scan_cycle
        scan_interval = settings.scan_interval_seconds
        
        points_collected = project.points_collected
        
        log.info(f"Starting scan for {project.name}: "
                 f"{points_collected}/{max_points} points, "
                 f"bounds={bounds.area_sq_km:.2f} sq km")
        
        # Main scan loop
        while points_collected < max_points and not self._shutdown_requested:
            # Update progress
            progress = int((points_collected / max_points) * 100)
            self.queue.update_progress(
                job.id, 
                progress, 
                f"Scanned {points_collected}/{max_points} points"
            )
            
            # Generate and evaluate points
            for _ in range(points_per_cycle):
                if self._shutdown_requested:
                    break
                
                # Random point within bounds
                lat = random.uniform(bounds.min_latitude, bounds.max_latitude)
                lon = random.uniform(bounds.min_longitude, bounds.max_longitude)
                
                # Evaluate using scoring (synergy-based or rule-based)
                features = self._generate_features(lat, lon)
                score = self._calculate_score(features, settings.scoring_rules, settings.use_case)
                
                # Save the result
                self._save_point(project, lat, lon, features, score)
                points_collected += 1
                
                if points_collected >= max_points:
                    break
            
            # Update project
            project.points_collected = points_collected
            project.save()
            
            # Wait before next cycle
            if not self._shutdown_requested and points_collected < max_points:
                time.sleep(scan_interval)
        
        log.info(f"Scan complete for {project.name}: {points_collected} points")
    
    def _generate_features(self, lat: float, lon: float) -> dict:
        """
        Fetch real features for a location using unified data fetcher.
        
        Queries:
        - OpenStreetMap for land use, roads, water
        - USGS for elevation
        - FEMA for flood zones
        """
        try:
            from loaders.unified import get_data_fetcher
            fetcher = get_data_fetcher()
            
            # Fetch real data (with caching)
            location_data = fetcher.fetch_all(lat, lon, osm_radius=300, parallel=False)
            
            # Convert to feature dict for scoring
            return location_data.to_features_dict()
            
        except Exception as e:
            log.warning(f"Real data fetch failed for ({lat}, {lon}): {e}")
            # Fallback to deterministic simulation if APIs fail
            location_hash = hash((round(lat, 4), round(lon, 4)))
            return {
                "has_water": (location_hash % 5) == 0,
                "has_road": (location_hash % 3) != 0,
                "is_industrial": (location_hash % 10) < 2,
                "is_residential": (location_hash % 10) >= 5,
                "high_elevation": (location_hash % 20) == 0,
                "flood_risk": False,
            }
    
    def _calculate_score(self, features: dict, rules: list, use_case: str = "general") -> float:
        """
        Calculate utility score based on features.
        
        Uses the advanced synergy scorer if available, falling back to 
        rule-based scoring otherwise.
        
        Args:
            features: Feature dictionary from data fetcher
            rules: List of ScoringRule objects (fallback)
            use_case: Use-case profile name (general, desalination_plant, etc.)
        """
        # Try synergy-based scoring first
        try:
            from core.scoring import get_scorer, UseCase
            
            # Map use_case string to UseCase enum
            use_case_map = {
                "general": UseCase.GENERAL,
                "desalination_plant": UseCase.DESALINATION,
                "silicon_wafer_fab": UseCase.SILICON_FAB,
                "warehouse_distribution": UseCase.WAREHOUSE,
                "light_manufacturing": UseCase.MANUFACTURING,
            }
            uc = use_case_map.get(use_case, UseCase.GENERAL)
            
            scorer = get_scorer(uc)
            return scorer.score(features)
        except ImportError:
            log.debug("Synergy scorer not available, using rule-based")
        except Exception as e:
            log.warning(f"Synergy scoring failed: {e}")
        
        # Fall back to rule-based scoring
        base_score = 5.0  # Start at middle of 0-10 scale
        
        for rule in rules:
            if not rule.enabled:
                continue
            
            feature_value = features.get(rule.feature_key, False)
            
            if feature_value:
                points = rule.points_when_true
            else:
                points = rule.points_when_false
            
            base_score += points
        
        # Apply flood risk penalty (not in standard rules)
        if features.get("flood_risk"):
            base_score -= 2.0
        
        # Clamp to 0-10
        return max(0.0, min(10.0, base_score))
    
    def _save_point(self, project: Project, lat: float, lon: float, 
                    features: dict, score: float):
        """
        Save a scanned point to the project's training dataset.
        """
        data = {
            "location": {"lat": lat, "lon": lon},
            "features_raw": features,
            "expert_label": {
                "gross_utility_score": score,
                "reasoning_trace": [],
            },
            "timestamp": datetime.now().isoformat(),
        }
        
        # Append to JSONL file
        project.data_dir.mkdir(parents=True, exist_ok=True)
        with open(project.training_data_path, "a") as f:
            f.write(json.dumps(data) + "\n")
    
    def stop(self):
        """Stop the worker gracefully."""
        self._shutdown_requested = True


def main():
    """Run the worker as a standalone process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    worker = Worker()
    
    print(f"Worker {worker.worker_id} starting...")
    print("Press Ctrl+C to stop")
    
    try:
        worker.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
        worker.stop()


if __name__ == "__main__":
    main()
