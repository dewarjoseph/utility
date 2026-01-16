"""Tests for the bylaws generator module."""

import pytest
from core.bylaws import (
    BylawsGenerator, BylawsConfig, GeneratedBylaws,
    EntityType, VotingStructure, BoardElection, SurplusDistribution,
    MemberClass, get_bylaws_generator
)


class TestBylawsConfig:
    """Tests for bylaws configuration."""

    def test_default_config(self):
        config = BylawsConfig(
            cooperative_name="Test Coop",
            entity_type=EntityType.REIC,
            state="California",
            purpose="Test purpose"
        )
        assert config.voting_structure == VotingStructure.ONE_MEMBER_ONE_VOTE
        assert config.board_size == 5
        assert config.reserve_percentage == 0.20


class TestBylawsGenerator:
    """Tests for bylaws generation."""

    def test_generate_basic_bylaws(self):
        generator = BylawsGenerator()
        config = BylawsConfig(
            cooperative_name="Santa Cruz Housing Coop",
            entity_type=EntityType.REIC,
            state="California",
            purpose="Provide affordable cooperative housing"
        )
        
        bylaws = generator.generate(config)
        assert isinstance(bylaws, GeneratedBylaws)
        assert len(bylaws.sections) > 0

    def test_bylaws_contain_required_sections(self):
        generator = BylawsGenerator()
        config = BylawsConfig(
            cooperative_name="Test Coop",
            entity_type=EntityType.LLC_COOP,
            state="New York",
            purpose="Test"
        )
        
        bylaws = generator.generate(config)
        section_titles = list(bylaws.sections.keys())
        
        assert any("PURPOSE" in t for t in section_titles)
        assert any("MEMBERSHIP" in t for t in section_titles)
        assert any("VOTING" in t for t in section_titles)
        assert any("BOARD" in t for t in section_titles)

    def test_to_markdown(self):
        generator = BylawsGenerator()
        config = BylawsConfig(
            cooperative_name="Test Coop",
            entity_type=EntityType.REIC,
            state="California",
            purpose="Test"
        )
        
        bylaws = generator.generate(config)
        md = bylaws.to_markdown()
        
        assert "# BYLAWS OF TEST COOP" in md
        assert "California" in md

    def test_anti_speculation_clause(self):
        generator = BylawsGenerator()
        config = BylawsConfig(
            cooperative_name="Test",
            entity_type=EntityType.REIC,
            state="CA",
            purpose="Test",
            appreciation_cap=0.03,
            transfer_restrictions=True
        )
        
        bylaws = generator.generate(config)
        md = bylaws.to_markdown()
        
        assert "3%" in md or "PRESERVATION" in md

    def test_member_classes(self):
        generator = BylawsGenerator()
        config = BylawsConfig(
            cooperative_name="Test",
            entity_type=EntityType.LCA,
            state="Minnesota",
            purpose="Test",
            member_classes=[
                MemberClass("Resident", "Live in the building"),
                MemberClass("Investor", "Provide capital"),
            ]
        )
        
        bylaws = generator.generate(config)
        md = bylaws.to_markdown()
        
        assert "Resident" in md


class TestFactoryFunction:
    """Tests for factory function."""

    def test_get_bylaws_generator(self):
        gen = get_bylaws_generator()
        assert isinstance(gen, BylawsGenerator)
