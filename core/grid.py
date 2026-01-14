"""
Grid Engine for spatial land analysis.
Projects real-world features onto a discrete grid of LandQuantum cells.
"""

import math
from typing import List
from core.models import LandQuantum


class GridEngine:
    """
    Manages a spatial grid of LandQuantum cells.
    Converts real-world coordinates to grid positions and projects features.
    """
    
    def __init__(
        self, 
        start_lat: float, 
        start_lon: float, 
        width_cells: int = 20, 
        height_cells: int = 10, 
        cell_size_meters: int = 50
    ):
        self.start_lat = start_lat
        self.start_lon = start_lon
        self.width = width_cells
        self.height = height_cells
        self.cell_size = cell_size_meters
        self.grid: List[List[LandQuantum]] = []
        
        # Approx meters per degree at this latitude
        self.lat_step = (cell_size_meters / 111000)
        self.lon_step = (cell_size_meters / (111000 * math.cos(math.radians(start_lat))))
        
        self._init_grid()

    def _init_grid(self) -> None:
        """Initialize the grid with empty LandQuantum cells."""
        for y in range(self.height):
            row = []
            for x in range(self.width):
                # Calculate center of cell
                plat = self.start_lat + (y * self.lat_step)
                plon = self.start_lon + (x * self.lon_step)
                row.append(LandQuantum(x, y, plat, plon))
            self.grid.append(row)

    def project_feature(self, feature_type: str, lat: float, lon: float) -> bool:
        """
        Project a real-world feature onto the grid.
        
        Args:
            feature_type: One of "water", "highway", "industrial", "residential"
            lat: Latitude of the feature
            lon: Longitude of the feature
            
        Returns:
            True if feature was projected, False if out of bounds
        """
        rel_y = int((lat - self.start_lat) / self.lat_step)
        rel_x = int((lon - self.start_lon) / self.lon_step)
        
        if 0 <= rel_x < self.width and 0 <= rel_y < self.height:
            cell = self.grid[rel_y][rel_x]
            
            if feature_type == "water":
                cell.has_water_infrastructure = True
                cell.debug_notes.append("Water node projected")
            elif feature_type == "highway":
                cell.has_road_access = True
                cell.debug_notes.append("Road node projected")
            elif feature_type == "industrial":
                cell.zoning_type = "Industrial"
            elif feature_type == "residential":
                cell.zoning_type = "Residential"
            elif feature_type == "power":
                cell.has_power_infrastructure = True
                cell.debug_notes.append("Power infrastructure projected")
                
            return True
        return False

    def get_all_quanta(self) -> List[LandQuantum]:
        """Return all grid cells as a flat list."""
        quanta = []
        for row in self.grid:
            quanta.extend(row)
        return quanta
    
    def get_quantum_at(self, lat: float, lon: float) -> LandQuantum | None:
        """Get the quantum at a specific coordinate, or None if out of bounds."""
        rel_y = int((lat - self.start_lat) / self.lat_step)
        rel_x = int((lon - self.start_lon) / self.lon_step)
        
        if 0 <= rel_x < self.width and 0 <= rel_y < self.height:
            return self.grid[rel_y][rel_x]
        return None
    
    def get_bounds(self) -> tuple:
        """Return (min_lat, min_lon, max_lat, max_lon) of the grid."""
        max_lat = self.start_lat + (self.height * self.lat_step)
        max_lon = self.start_lon + (self.width * self.lon_step)
        return (self.start_lat, self.start_lon, max_lat, max_lon)
