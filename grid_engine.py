from dataclasses import dataclass, field
from typing import List, Dict, Tuple
import math

@dataclass
class LandQuantum:
    x: int
    y: int
    lat: float
    lon: float
    has_water_infrastructure: bool = False
    has_road_access: bool = False
    has_power_infrastructure: bool = False
    zoning_type: str = "Unknown"
    gross_utility_score: float = 0.0
    debug_notes: List[str] = field(default_factory=list)

class GridEngine:
    def __init__(self, start_lat, start_lon, width_cells=20, height_cells=10, cell_size_meters=50):
        self.start_lat = start_lat
        self.start_lon = start_lon
        self.width = width_cells
        self.height = height_cells
        self.cell_size = cell_size_meters
        self.grid: List[List[LandQuantum]] = []
        
        # Approx meters per degree at 37 lat
        self.lat_step = (cell_size_meters / 111000)
        self.lon_step = (cell_size_meters / (111000 * math.cos(math.radians(start_lat))))
        
        self._init_grid()

    def _init_grid(self):
        for y in range(self.height):
            row = []
            for x in range(self.width):
                # Calculate center of cell
                plat = self.start_lat + (y * self.lat_step)
                plon = self.start_lon + (x * self.lon_step)
                row.append(LandQuantum(x, y, plat, plon))
            self.grid.append(row)

    def project_feature(self, feature_type: str, lat: float, lon: float):
        # Find which cell this feature falls into
        # Simple point projection - in real life needs polygon rasterization
        
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

    def get_all_quanta(self) -> List[LandQuantum]:
        quanta = []
        for row in self.grid:
            quanta.extend(row)
        return quanta
