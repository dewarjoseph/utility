"""Tests for the zoning loader module."""

import pytest
from loaders.zoning import (
    ZoningLoader, ZoningData, ZoneType, ZoningConstraints,
    get_zoning_loader
)


class TestZoningLoader:
    """Tests for the zoning data loader."""

    def test_get_zoning_returns_data(self):
        loader = ZoningLoader(use_mock=True)
        zoning = loader.get_zoning(36.9741, -122.0308)
        
        assert isinstance(zoning, ZoningData)
        assert zoning.zone_code is not None
        assert zoning.zone_name is not None

    def test_zoning_is_cached(self):
        loader = ZoningLoader(use_mock=True)
        z1 = loader.get_zoning(36.9741, -122.0308)
        z2 = loader.get_zoning(36.9741, -122.0308)
        
        assert z1 is z2  # Same object from cache

    def test_different_locations_different_zones(self):
        loader = ZoningLoader(use_mock=True)
        z1 = loader.get_zoning(36.9741, -122.0308)
        z2 = loader.get_zoning(37.7749, -122.4194)
        
        # May or may not be different, but should be cached separately
        assert z1 is not z2

    def test_zoning_has_constraints(self):
        loader = ZoningLoader(use_mock=True)
        zoning = loader.get_zoning(36.9741, -122.0308)
        
        assert isinstance(zoning.constraints, ZoningConstraints)
        assert zoning.constraints.max_height_ft > 0
        assert 0 < zoning.constraints.max_lot_coverage <= 1.0

    def test_zoning_has_allowed_uses(self):
        loader = ZoningLoader(use_mock=True)
        zoning = loader.get_zoning(36.9741, -122.0308)
        
        assert isinstance(zoning.allowed_uses, list)
        assert len(zoning.allowed_uses) > 0

    def test_buildable_sqft_calculated(self):
        loader = ZoningLoader(use_mock=True)
        zoning = loader.get_zoning(36.9741, -122.0308, lot_size_sqft=10000)
        
        assert zoning.buildable_sqft is not None
        assert zoning.buildable_sqft > 0


class TestZoningValidation:
    """Tests for use validation."""

    def test_validate_allowed_use(self):
        loader = ZoningLoader(use_mock=True)
        # Get a commercial zone
        for _ in range(10):
            zoning = loader.get_zoning(37.0 + _ * 0.01, -122.0)
            if zoning.zone_type == ZoneType.COMMERCIAL:
                break
        
        if zoning.zone_type == ZoneType.COMMERCIAL:
            result = loader.validate_use(zoning, "retail store")
            assert result['allowed'] is True

    def test_validate_unknown_use(self):
        loader = ZoningLoader(use_mock=True)
        zoning = loader.get_zoning(36.9741, -122.0308)
        result = loader.validate_use(zoning, "nuclear power plant")
        
        assert result['allowed'] is False


class TestZoningData:
    """Tests for ZoningData data class."""

    def test_to_dict(self):
        zoning = ZoningData(
            zone_code="R-1",
            zone_type=ZoneType.RESIDENTIAL_SINGLE,
            zone_name="Single-Family Residential",
            constraints=ZoningConstraints(),
            allowed_uses=["Single-Family Dwelling"],
        )
        d = zoning.to_dict()
        
        assert d['zone_code'] == "R-1"
        assert d['zone_type'] == "R-1"
        assert 'max_height_ft' in d


class TestFactoryFunction:
    """Tests for factory function."""

    def test_get_zoning_loader(self):
        loader = get_zoning_loader()
        assert isinstance(loader, ZoningLoader)
        assert loader.use_mock is True

    def test_get_zoning_loader_no_mock(self):
        loader = get_zoning_loader(use_mock=False)
        assert loader.use_mock is False
