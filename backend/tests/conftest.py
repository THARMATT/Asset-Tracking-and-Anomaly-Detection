# ==========================================
# PYTEST CONFIGURATION & TEST FIXTURES
# ==========================================

import os
import sys
from pathlib import Path
import pytest

# Ensure backend root is on Python module search path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from database import initialize_database
from app import create_app


@pytest.fixture
def temp_db(tmp_path):
    """Provide a fresh, isolated temporary database with seeded demo data."""
    db_file = tmp_path / "test_asset_tracking.db"
    db_path = str(db_file)

    initialize_database(db_path=db_path, seed=True)
    yield db_path


@pytest.fixture
def empty_db(tmp_path):
    """Provide a fresh, isolated temporary database WITHOUT initial seed data."""
    db_file = tmp_path / "test_empty_tracking.db"
    db_path = str(db_file)

    initialize_database(db_path=db_path, seed=False)
    yield db_path


@pytest.fixture
def client(tmp_path):
    """Provide a Flask test client using an isolated temporary database."""
    db_file = tmp_path / "test_flask_app.db"
    db_path = str(db_file)

    app = create_app({"DATABASE_PATH": db_path})
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client
