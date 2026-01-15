"""
Project Model and Manager

A Project represents a land utility analysis for a specific geographic area.
Each project has its own data, models, and configuration.
"""

import os
import json
import uuid
import sqlite3
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Any
from pathlib import Path
import logging

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# BOUNDING BOX
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class BoundingBox:
    """
    Geographic bounding box for a project area.
    
    All coordinates are in decimal degrees (WGS84).
    """
    min_latitude: float   # Southern edge (e.g., 36.95)
    max_latitude: float   # Northern edge (e.g., 37.05)
    min_longitude: float  # Western edge (e.g., -122.10)
    max_longitude: float  # Eastern edge (e.g., -121.95)
    
    @property
    def center_latitude(self) -> float:
        """Center point latitude."""
        return (self.min_latitude + self.max_latitude) / 2
    
    @property
    def center_longitude(self) -> float:
        """Center point longitude."""
        return (self.min_longitude + self.max_longitude) / 2
    
    @property
    def area_sq_km(self) -> float:
        """Approximate area in square kilometers."""
        # Rough approximation using lat/lon differences
        lat_km = (self.max_latitude - self.min_latitude) * 111  # 1 degree ≈ 111 km
        lon_km = (self.max_longitude - self.min_longitude) * 85  # varies by latitude
        return lat_km * lon_km
    
    def contains(self, lat: float, lon: float) -> bool:
        """Check if a point is inside this bounding box."""
        return (self.min_latitude <= lat <= self.max_latitude and
                self.min_longitude <= lon <= self.max_longitude)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "BoundingBox":
        return cls(**data)
    
    @classmethod
    def from_center_and_radius(cls, lat: float, lon: float, radius_km: float) -> "BoundingBox":
        """Create a bounding box from a center point and radius."""
        # Approximate degrees from km
        lat_offset = radius_km / 111
        lon_offset = radius_km / 85
        return cls(
            min_latitude=lat - lat_offset,
            max_latitude=lat + lat_offset,
            min_longitude=lon - lon_offset,
            max_longitude=lon + lon_offset
        )


# ═══════════════════════════════════════════════════════════════════════════
# SCORING RULES (User-Friendly, No Magic Numbers)
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class ScoringRule:
    """
    A single scoring rule that affects utility calculations.
    
    All values are explicit - no hidden defaults or magic numbers.
    """
    name: str                    # Human-readable name: "Water Access Bonus"
    description: str             # What this rule does
    feature_key: str             # Which feature triggers this: "has_water"
    points_when_true: float      # Points added when feature is present: +3.0
    points_when_false: float     # Points added when feature is absent: 0.0
    enabled: bool = True         # Can be toggled on/off
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ScoringRule":
        return cls(**data)


# Default rules - BALANCED to create score variety
DEFAULT_SCORING_RULES = [
    ScoringRule(
        name="Water Access",
        description="Properties with water utility access score higher",
        feature_key="has_water",
        points_when_true=1.5,
        points_when_false=-1.0,  # Penalty for no water
        enabled=True
    ),
    ScoringRule(
        name="Road Access",
        description="Properties with road access are more accessible",
        feature_key="has_road",
        points_when_true=1.0,
        points_when_false=-2.0,  # Significant penalty for no road
        enabled=True
    ),
    ScoringRule(
        name="Industrial Zoning",
        description="Industrial zones have higher development potential",
        feature_key="is_industrial",
        points_when_true=2.0,
        points_when_false=0.0,
        enabled=True
    ),
    ScoringRule(
        name="Commercial Zone",
        description="Commercial zones have business potential",
        feature_key="is_commercial",
        points_when_true=1.5,
        points_when_false=0.0,
        enabled=True
    ),
    ScoringRule(
        name="Residential Area",
        description="Residential areas have use constraints",
        feature_key="is_residential",
        points_when_true=-0.5,  # Slight penalty - more constrained
        points_when_false=0.5,
        enabled=True
    ),
    ScoringRule(
        name="Agricultural Land",
        description="Agricultural land has limited development potential",
        feature_key="is_agricultural",
        points_when_true=-1.5,
        points_when_false=0.0,
        enabled=True
    ),
    ScoringRule(
        name="Elevation Penalty",
        description="Very high elevation areas are harder to develop",
        feature_key="high_elevation",
        points_when_true=-2.0,
        points_when_false=0.0,
        enabled=True
    ),
    ScoringRule(
        name="Low Elevation Bonus",
        description="Low coastal areas have utility potential",
        feature_key="low_elevation",
        points_when_true=1.0,
        points_when_false=0.0,
        enabled=True
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# PROJECT SETTINGS (User-Friendly, Verbose)
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class ProjectSettings:
    """
    All configurable settings for a project.
    
    IMPORTANT: Every value has an explicit meaning. No magic numbers.
    """
    
    # Scanning Settings
    points_per_scan_cycle: int = 50
    """How many random points to evaluate each time the daemon runs a cycle."""
    
    scan_interval_seconds: float = 5.0
    """How many seconds to wait between scan cycles."""
    
    max_total_points: int = 10000
    """Maximum points to collect before stopping. Set to -1 for unlimited."""
    
    # Scoring Thresholds
    high_value_threshold: float = 7.0
    """Score at or above this value is considered 'high value' (scale 0-10)."""
    
    low_value_threshold: float = 3.0
    """Score at or below this value is considered 'low value' (scale 0-10)."""
    
    # Machine Learning Settings
    online_learning_enabled: bool = True
    """If True, the ML model learns from each new data point in real-time."""
    
    ml_model_tree_count: int = 15
    """Number of decision trees in the ML model. More = slower but more accurate."""
    
    surprise_detection_multiplier: float = 2.0
    """A prediction error this many times the average is flagged as 'surprise'."""
    
    # Scoring Rules
    scoring_rules: List[ScoringRule] = field(default_factory=lambda: DEFAULT_SCORING_RULES.copy())
    """List of rules that affect utility scoring."""
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data["scoring_rules"] = [r.to_dict() for r in self.scoring_rules]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ProjectSettings":
        rules_data = data.pop("scoring_rules", [])
        rules = [ScoringRule.from_dict(r) for r in rules_data]
        return cls(**data, scoring_rules=rules)


# ═══════════════════════════════════════════════════════════════════════════
# PROJECT STATUS
# ═══════════════════════════════════════════════════════════════════════════
class ProjectStatus:
    """Project lifecycle states."""
    CREATED = "created"        # Just created, not yet started
    QUEUED = "queued"          # Waiting in job queue
    SCANNING = "scanning"      # Actively being processed
    PAUSED = "paused"          # User paused the scan
    COMPLETED = "completed"    # Reached max points or user stopped
    ERROR = "error"            # Something went wrong


# ═══════════════════════════════════════════════════════════════════════════
# PROJECT
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class Project:
    """
    A land utility analysis project for a specific geographic area.
    
    Each project has:
    - A unique ID
    - A name and description
    - A geographic bounding box
    - Configuration settings
    - Its own data files (database, model)
    """
    
    id: str
    """Unique identifier (UUID)."""
    
    name: str
    """Human-readable project name, e.g., 'Santa Cruz Downtown'."""
    
    description: str
    """Optional longer description of what this project analyzes."""
    
    bounds: BoundingBox
    """Geographic area to analyze."""
    
    settings: ProjectSettings
    """All configurable project settings."""
    
    status: str = ProjectStatus.CREATED
    """Current project status."""
    
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    """When this project was created."""
    
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    """When this project was last modified."""
    
    points_collected: int = 0
    """Number of data points collected so far."""
    
    error_message: Optional[str] = None
    """If status is ERROR, this contains the error details."""
    
    # Derived paths
    @property
    def data_dir(self) -> Path:
        """Directory containing all project data."""
        return Path("projects") / self.id
    
    @property
    def database_path(self) -> Path:
        """Path to this project's event database."""
        return self.data_dir / "events.db"
    
    @property
    def model_path(self) -> Path:
        """Path to this project's ML model file."""
        return self.data_dir / "model.pkl"
    
    @property
    def training_data_path(self) -> Path:
        """Path to this project's training dataset."""
        return self.data_dir / "training_dataset.jsonl"
    
    @property
    def config_path(self) -> Path:
        """Path to this project's saved configuration."""
        return self.data_dir / "project.json"
    
    def to_dict(self) -> Dict:
        """Serialize project to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "bounds": self.bounds.to_dict(),
            "settings": self.settings.to_dict(),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "points_collected": self.points_collected,
            "error_message": self.error_message,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Project":
        """Deserialize project from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            bounds=BoundingBox.from_dict(data["bounds"]),
            settings=ProjectSettings.from_dict(data.get("settings", {})),
            status=data.get("status", ProjectStatus.CREATED),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            points_collected=data.get("points_collected", 0),
            error_message=data.get("error_message"),
        )
    
    def save(self):
        """Save project to disk."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.updated_at = datetime.now().isoformat()
        with open(self.config_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        log.info(f"Saved project {self.id} to {self.config_path}")
    
    @classmethod
    def load(cls, project_id: str) -> Optional["Project"]:
        """Load project from disk."""
        config_path = Path("projects") / project_id / "project.json"
        if not config_path.exists():
            return None
        with open(config_path, "r") as f:
            return cls.from_dict(json.load(f))


# ═══════════════════════════════════════════════════════════════════════════
# PROJECT MANAGER
# ═══════════════════════════════════════════════════════════════════════════
class ProjectManager:
    """
    Manages all projects - create, list, load, delete.
    
    Projects are stored in the 'projects/' directory.
    """
    
    PROJECTS_DIR = Path("projects")
    
    def __init__(self):
        self.PROJECTS_DIR.mkdir(exist_ok=True)
    
    def create_project(
        self,
        name: str,
        center_lat: float,
        center_lon: float,
        radius_km: float = 2.0,
        description: str = ""
    ) -> Project:
        """
        Create a new project centered on a location.
        
        Args:
            name: Human-readable name for the project
            center_lat: Center latitude of the area to analyze
            center_lon: Center longitude of the area to analyze
            radius_km: Radius of the analysis area in kilometers (default 2km)
            description: Optional description
            
        Returns:
            The created Project object
        """
        project = Project(
            id=str(uuid.uuid4())[:8],  # Short ID for readability
            name=name,
            description=description,
            bounds=BoundingBox.from_center_and_radius(center_lat, center_lon, radius_km),
            settings=ProjectSettings(),
        )
        project.save()
        log.info(f"Created project '{name}' with ID {project.id}")
        return project
    
    def list_projects(self) -> List[Project]:
        """List all projects."""
        projects = []
        for folder in self.PROJECTS_DIR.iterdir():
            if folder.is_dir():
                project = Project.load(folder.name)
                if project:
                    projects.append(project)
        return sorted(projects, key=lambda p: p.created_at, reverse=True)
    
    def get_project(self, project_id: str) -> Optional[Project]:
        """Get a specific project by ID."""
        return Project.load(project_id)
    
    def delete_project(self, project_id: str) -> bool:
        """Delete a project and all its data."""
        project_dir = self.PROJECTS_DIR / project_id
        if project_dir.exists():
            import shutil
            shutil.rmtree(project_dir)
            log.info(f"Deleted project {project_id}")
            return True
        return False
    
    def update_project_status(self, project_id: str, status: str, error: str = None):
        """Update a project's status."""
        project = self.get_project(project_id)
        if project:
            project.status = status
            project.error_message = error
            project.save()
