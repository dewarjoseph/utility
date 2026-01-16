"""Tests for the chat module."""

import pytest
from core.chat import (
    Intent, IntentClassifier, SlotExtractor, ChatSession,
    SlotStatus, get_create_project_schema
)


class TestIntentClassifier:
    """Tests for intent classification."""

    def test_classify_create_project(self):
        classifier = IntentClassifier()
        assert classifier.classify("create a new project") == Intent.CREATE_PROJECT
        assert classifier.classify("I want to analyze a lot") == Intent.CREATE_PROJECT
        assert classifier.classify("start a new analysis") == Intent.CREATE_PROJECT

    def test_classify_zoning(self):
        classifier = IntentClassifier()
        assert classifier.classify("what's the zoning here") == Intent.ANALYZE_ZONING
        assert classifier.classify("check the setback requirements") == Intent.ANALYZE_ZONING

    def test_classify_proforma(self):
        classifier = IntentClassifier()
        assert classifier.classify("calculate the pro forma") == Intent.CALCULATE_PROFORMA
        assert classifier.classify("what's the ROI") == Intent.CALCULATE_PROFORMA

    def test_classify_help(self):
        classifier = IntentClassifier()
        assert classifier.classify("help") == Intent.GET_HELP
        assert classifier.classify("how do I use this") == Intent.GET_HELP


    def test_classify_unknown(self):
        classifier = IntentClassifier()
        assert classifier.classify("random gibberish xyz") == Intent.UNKNOWN


class TestSlotExtractor:
    """Tests for slot value extraction."""

    def test_extract_use_case(self):
        extractor = SlotExtractor()
        assert extractor.extract("build a warehouse", "use_case") == "warehouse_distribution"
        assert extractor.extract("food coop project", "use_case") == "food_coop"
        assert extractor.extract("housing development", "use_case") == "housing"

    def test_extract_radius(self):
        extractor = SlotExtractor()
        assert extractor.extract("within 2 km", "radius_km") == 2.0
        assert extractor.extract("3.5 kilometer radius", "radius_km") == 3.5

    def test_extract_no_match(self):
        extractor = SlotExtractor()
        assert extractor.extract("no useful info here", "use_case") is None


class TestSlotSchema:
    """Tests for slot schema management."""

    def test_schema_status_empty(self):
        schema = get_create_project_schema()
        assert schema.status == SlotStatus.EMPTY

    def test_schema_status_partial(self):
        schema = get_create_project_schema()
        schema.slots['address'].value = "123 Main St"
        assert schema.status == SlotStatus.PARTIAL

    def test_schema_status_complete(self):
        schema = get_create_project_schema()
        schema.slots['address'].value = "123 Main St"
        schema.slots['project_name'].value = "Test Project"
        assert schema.status == SlotStatus.COMPLETE

    def test_get_next_empty_slot(self):
        schema = get_create_project_schema()
        next_slot = schema.get_next_empty_slot()
        assert next_slot is not None
        assert next_slot.name == 'address'


class TestChatSession:
    """Tests for chat session management."""

    def test_session_creation(self):
        session = ChatSession()
        assert len(session.messages) == 0
        assert session.current_intent is None

    def test_process_help_message(self):
        session = ChatSession()
        response = session.process_message("help")
        assert response.role == 'assistant'
        assert 'Welcome' in response.content

    def test_process_create_project(self):
        session = ChatSession()
        response = session.process_message("create a new project for 123 Pacific Ave")
        assert response.role == 'assistant'
        assert session.current_intent == Intent.CREATE_PROJECT or session.current_schema is not None

    def test_conversation_flow(self):
        session = ChatSession()
        # Start project creation
        session.process_message("I want to analyze a property")
        # Should ask for address
        assert session.current_schema is not None
        
        # Provide address
        session.process_message("123 Main Street")
        
        # Should ask for project name or complete
        assert len(session.messages) >= 2
