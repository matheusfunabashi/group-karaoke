import pytest
from fastapi.testclient import TestClient

from app import create_app
from sessions.config import Settings


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(Settings(port=0, data_dir=tmp_path)))