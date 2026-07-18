from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from nursing_station import main
from nursing_station.database import Database


@pytest.fixture()
def client(tmp_path):
    main.db = Database(tmp_path / "test.db")
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture()
def token(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "amina.okafor@nursing.test", "password": "Nursing2026!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture()
def headers(token):
    return {"Authorization": f"Bearer {token}"}
