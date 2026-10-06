import pytest
from fastapi.testclient import TestClient

from karaoke import create_app
from karaoke.config import Settings


@pytest.fixture
def client(tmp_path):
    settings = Settings(port=0, data_dir=tmp_path)
    return TestClient(create_app(settings))
