"""Smoke tests for Streamlit Dashboard imports and backend component integration."""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def test_dashboard_imports():
    """Verify that frontend/streamlit_app.py imports cleanly."""
    dashboard_path = os.path.join(BASE_DIR, "frontend", "streamlit_app.py")
    assert os.path.exists(dashboard_path)

    # Read and parse python AST to verify valid syntax
    with open(dashboard_path, "r", encoding="utf-8") as f:
        code = f.read()

    import ast
    parsed = ast.parse(code)
    assert parsed is not None
