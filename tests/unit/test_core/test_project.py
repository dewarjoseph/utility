"""Tests for the project module."""

import json
import pytest
from pathlib import Path
from datetime import datetime
import os

from core.project import (
    Project, ProjectSettings, BoundingBox, ProjectStatus, ProjectManager
)

@pytest.fixture
def temp_projects_dir(tmp_path):
    """Fixture to provide a temporary projects directory."""
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    return projects_dir

class TestProject:
    """Tests for the Project class."""

    def test_save(self, temp_projects_dir):
        """Test saving a project to disk."""
        # Setup
        project_id = "test-project-1"
        settings = ProjectSettings()
        bounds = BoundingBox(0, 0, 1, 1)
        project = Project(
            id=project_id,
            name="Test Project",
            description="A test description",
            bounds=bounds,
            settings=settings
        )

        # Change current working directory to parent of temp_projects_dir
        # so that "projects/" resolves correctly
        old_cwd = os.getcwd()
        os.chdir(temp_projects_dir.parent)

        try:
            # Execute
            project.save()

            expected_path = temp_projects_dir / project_id

            # Verify directory created
            assert expected_path.exists()
            assert expected_path.is_dir()

            # Verify file created
            config_path = expected_path / "project.json"
            assert config_path.exists()

            # Verify content
            with open(config_path, "r") as f:
                data = json.load(f)
                assert data["id"] == project_id
                assert data["name"] == "Test Project"
                assert data["description"] == "A test description"
                assert data["status"] == ProjectStatus.CREATED
                assert "settings" in data
                assert "bounds" in data
        finally:
            os.chdir(old_cwd)

    def test_load(self, temp_projects_dir):
        """Test loading a project from disk."""
        project_id = "test-project-2"
        project_dir = temp_projects_dir / project_id
        project_dir.mkdir(parents=True)
        config_path = project_dir / "project.json"

        data = {
            "id": project_id,
            "name": "Loaded Project",
            "description": "Loaded description",
            "bounds": {"min_latitude": 0, "max_latitude": 1, "min_longitude": 0, "max_longitude": 1},
            "settings": {},
            "status": ProjectStatus.COMPLETED,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "points_collected": 100
        }

        with open(config_path, "w") as f:
            json.dump(data, f)

        old_cwd = os.getcwd()
        os.chdir(temp_projects_dir.parent) # Parent of "projects"

        try:
            loaded_project = Project.load(project_id)

            assert loaded_project is not None
            assert loaded_project.id == project_id
            assert loaded_project.name == "Loaded Project"
            assert loaded_project.status == ProjectStatus.COMPLETED
            assert loaded_project.points_collected == 100

        finally:
            os.chdir(old_cwd)


class TestProjectManager:
    """Tests for the ProjectManager class."""

    def test_create_project(self, temp_projects_dir):
        """Test creating a new project."""
        # Use chdir approach for consistency with Project.save/load behavior which uses relative paths
        old_cwd = os.getcwd()
        os.chdir(temp_projects_dir.parent)

        try:
            manager = ProjectManager()
            # Verify PROJECTS_DIR resolved correctly
            # ProjectManager.PROJECTS_DIR is initialized as Path("projects")
            # Since we changed CWD, it should point to temp_projects_dir

            project = manager.create_project(
                name="New Project",
                center_lat=10.0,
                center_lon=20.0,
                radius_km=1.0,
                description="Created via manager"
            )

            assert project.id is not None
            assert project.name == "New Project"
            assert (temp_projects_dir / project.id).exists()
            assert (temp_projects_dir / project.id / "project.json").exists()

        finally:
            os.chdir(old_cwd)

    def test_list_projects(self, temp_projects_dir):
        """Test listing projects."""
        old_cwd = os.getcwd()
        os.chdir(temp_projects_dir.parent)

        try:
            manager = ProjectManager()

            # Create two projects
            p1 = manager.create_project("Project A", 0, 0)
            p2 = manager.create_project("Project B", 1, 1)

            projects = manager.list_projects()

            assert len(projects) == 2
            ids = [p.id for p in projects]
            assert p1.id in ids
            assert p2.id in ids

        finally:
            os.chdir(old_cwd)

    def test_delete_project(self, temp_projects_dir):
        """Test deleting a project."""
        old_cwd = os.getcwd()
        os.chdir(temp_projects_dir.parent)

        try:
            manager = ProjectManager()
            project = manager.create_project("To Delete", 0, 0)

            project_path = temp_projects_dir / project.id
            assert project_path.exists()

            result = manager.delete_project(project.id)
            assert result is True
            assert not project_path.exists()

            # Test deleting non-existent
            assert manager.delete_project("non-existent") is False

        finally:
            os.chdir(old_cwd)
