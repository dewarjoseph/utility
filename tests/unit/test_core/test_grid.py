import pytest
from core.grid import GridEngine
from core.models import LandQuantum

def test_grid_initialization():
    """Verify grid creation and coordinate calculations."""
    grid = GridEngine(start_lat=37.0, start_lon=-122.0, width_cells=10, height_cells=10)
    assert len(grid.grid) == 10
    assert len(grid.grid[0]) == 10
    
    # Verify origin cell
    cell_0_0 = grid.grid[0][0]
    assert cell_0_0.lat == 37.0
    assert cell_0_0.lon == -122.0

def test_project_feature():
    """Verify mapping features to grid cells."""
    grid = GridEngine(start_lat=37.0, start_lon=-122.0, width_cells=10, height_cells=10, cell_size_meters=100)
    
    # Project a feature at origin
    assert grid.project_feature("water", 37.0, -122.0)
    assert grid.grid[0][0].has_water_infrastructure
    
    # Project feature slightly offset (should still fall in 0,0 or near)
    # 1 degree lat is approx 111km. 100m is very small fraction.
    # Lat step approx 0.0009
    
    # Project out of bounds
    assert not grid.project_feature("water", 38.0, -122.0)

def test_get_quantum_at():
    """Verify coordinate lookup."""
    grid = GridEngine(start_lat=37.0, start_lon=-122.0, width_cells=10, height_cells=10)
    
    # Exactly matching a cell center logic
    q = grid.get_quantum_at(37.0, -122.0)
    assert q is not None
    assert q.x == 0
    assert q.y == 0
    
    # Out of bounds
    assert grid.get_quantum_at(0.0, 0.0) is None

def test_get_bounds():
    """Verify bounds calculation."""
    grid = GridEngine(start_lat=37.0, start_lon=-122.0, width_cells=10, height_cells=10)
    min_lat, min_lon, max_lat, max_lon = grid.get_bounds()
    
    assert min_lat == 37.0
    assert min_lon == -122.0
    assert max_lat > 37.0
    assert max_lon > -122.0
