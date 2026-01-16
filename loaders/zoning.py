"""
Zoning Data Loader Module - Mock data for development.
"""

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Any


class ZoneType(Enum):
    """Common zoning classifications."""
    RESIDENTIAL_SINGLE = "R-1"
    RESIDENTIAL_MULTI = "R-M"
    COMMERCIAL = "C"
    INDUSTRIAL_LIGHT = "I-L"
    MIXED_USE = "MU"


@dataclass
class ZoningConstraints:
    """Development constraints from zoning code."""
    max_height_ft: float = 35.0
    max_lot_coverage: float = 0.50
    max_far: float = 1.0
    parking_ratio: float = 1.0
    front_setback: float = 20.0
    rear_setback: float = 15.0
    side_setback: float = 5.0


@dataclass
class ZoningData:
    """Complete zoning information for a parcel."""
    zone_code: str
    zone_type: ZoneType
    zone_name: str
    constraints: ZoningConstraints
    allowed_uses: List[str]
    overlay_districts: List[str] = field(default_factory=list)
    buildable_sqft: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'zone_code': self.zone_code,
            'zone_type': self.zone_type.value,
            'zone_name': self.zone_name,
            'max_height_ft': self.constraints.max_height_ft,
            'max_far': self.constraints.max_far,
            'allowed_uses': self.allowed_uses,
            'overlay_districts': self.overlay_districts,
        }


ZONE_CONFIGS = {
    ZoneType.RESIDENTIAL_SINGLE: ('Single-Family Residential', 
        ZoningConstraints(30, 0.4, 0.6, 2.0, 25, 20, 5),
        ['Single-Family Dwelling', 'ADU', 'Home Occupation']),
    ZoneType.RESIDENTIAL_MULTI: ('Multi-Family Residential',
        ZoningConstraints(45, 0.6, 1.5, 1.5, 15, 15, 5),
        ['Multi-Family', 'Townhouse', 'Live/Work']),
    ZoneType.COMMERCIAL: ('General Commercial',
        ZoningConstraints(50, 0.8, 2.0, 3.0, 0, 10, 0),
        ['Retail', 'Restaurant', 'Office', 'Mixed-Use']),
    ZoneType.INDUSTRIAL_LIGHT: ('Light Industrial',
        ZoningConstraints(45, 0.7, 1.5, 1.0, 20, 20, 10),
        ['Manufacturing', 'Warehouse', 'R&D']),
    ZoneType.MIXED_USE: ('Mixed-Use',
        ZoningConstraints(55, 0.85, 3.0, 1.0, 5, 10, 0),
        ['Mixed-Use', 'Residential', 'Retail', 'Office']),
}


class ZoningLoader:
    """Zoning data loader with mock data generation."""

    def __init__(self, use_mock: bool = True):
        self.use_mock = use_mock
        self._cache: Dict[str, ZoningData] = {}

    def get_zoning(self, latitude: float, longitude: float, 
                   lot_size_sqft: Optional[float] = None) -> ZoningData:
        """Get zoning data for a location."""
        cache_key = f"{latitude:.6f},{longitude:.6f}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        random.seed(int(abs(latitude * 10000) + abs(longitude * 10000)))
        zone_types = list(ZoneType)
        zone_type = random.choice(zone_types)
        
        name, constraints, uses = ZONE_CONFIGS[zone_type]
        
        overlays = []
        if random.random() < 0.2:
            overlays.append('Historic Preservation')
        if random.random() < 0.15:
            overlays.append('Transit-Oriented Development')

        buildable = None
        if lot_size_sqft:
            buildable = lot_size_sqft * constraints.max_lot_coverage * constraints.max_far

        zoning = ZoningData(
            zone_code=zone_type.value,
            zone_type=zone_type,
            zone_name=name,
            constraints=constraints,
            allowed_uses=list(uses),
            overlay_districts=overlays,
            buildable_sqft=buildable,
        )
        self._cache[cache_key] = zoning
        return zoning

    def validate_use(self, zoning: ZoningData, proposed_use: str) -> Dict[str, Any]:
        """Validate if a proposed use is allowed."""
        proposed_lower = proposed_use.lower()
        for use in zoning.allowed_uses:
            if use.lower() in proposed_lower or proposed_lower in use.lower():
                return {'allowed': True, 'matching_use': use}
        return {'allowed': False, 'matching_use': None}


def get_zoning_loader(use_mock: bool = True) -> ZoningLoader:
    """Factory function to get a zoning loader instance."""
    return ZoningLoader(use_mock=use_mock)
