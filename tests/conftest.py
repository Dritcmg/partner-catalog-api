import pytest
from fastapi.testclient import TestClient

from partner_catalog.config import Settings
from partner_catalog.main import create_app

SYNTHETIC_TEST_KEY = "synthetic-test-key-used-only-in-local-tests-0000"


@pytest.fixture
def settings(tmp_path):
    return Settings(
        api_key=SYNTHETIC_TEST_KEY, database_url=f"sqlite:///{tmp_path / 'partners.db'}"
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as test_client:
        test_client.headers["X-API-Key"] = settings.api_key
        yield test_client


@pytest.fixture
def partner_payload():
    return {"code": "DEMO-001", "display_name": "Synthetic Originator", "category": "originator"}


@pytest.fixture
def partner(client, partner_payload):
    response = client.post("/v1/partners", json=partner_payload)
    assert response.status_code == 201
    return response.json()
