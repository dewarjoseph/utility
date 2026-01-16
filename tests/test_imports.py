import pytest
import importlib

def test_imports():
    """Verify that critical modules can be imported without error."""
    modules_to_test = [
        "app",
        "core",
        "loaders",
        "inference",
        # "tools", # tools might have extra dependencies or side effects, uncomment if safe
    ]
    
    for module_name in modules_to_test:
        try:
            importlib.import_module(module_name)
        except Exception as e:
            pytest.fail(f"Failed to import {module_name}: {e}")
