import pytest
from unittest.mock import MagicMock, patch
import sys

# Pre-mock streamlit before importing core.theme
mock_st = MagicMock()
sys.modules['streamlit'] = mock_st

from core.theme import get_page_config, inject_theme, section_header, SHARED_CSS

def test_get_page_config():
    """Test get_page_config returns correct dictionary."""
    title = "Dashboard"
    config = get_page_config(title)

    assert config['page_title'] == "Dashboard | Land Utility Engine"
    assert config['page_icon'] == "🏗️"
    assert config['layout'] == "wide"

def test_get_page_config_different_title():
    """Test get_page_config with a different title."""
    title = "Analytics"
    config = get_page_config(title)

    assert config['page_title'] == "Analytics | Land Utility Engine"

def test_inject_theme():
    """Test inject_theme calls st.html with SHARED_CSS."""
    mock_st.reset_mock()
    inject_theme()
    mock_st.html.assert_called_once_with(SHARED_CSS)

def test_section_header_no_description():
    """Test section_header without description."""
    mock_st.reset_mock()
    section_header("Title")
    mock_st.header.assert_called_once_with("Title")
    mock_st.caption.assert_not_called()

def test_section_header_with_description():
    """Test section_header with description."""
    mock_st.reset_mock()
    section_header("Title", "Description")
    mock_st.header.assert_called_once_with("Title")
    mock_st.caption.assert_called_once_with("Description")
