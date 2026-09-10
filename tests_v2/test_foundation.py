from fastapi.testclient import TestClient

from loyalty_v2.api.app import app
from loyalty_v2.db.base import Base
from loyalty_v2.db import models  # noqa: F401


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_foundation_tables_registered() -> None:
    expected = {
        "organizations",
        "locations",
        "customers",
        "staff",
        "loyalty_tiers",
        "customer_loyalty_states",
        "points_accounts",
        "points_ledger_entries",
    }
    assert expected.issubset(Base.metadata.tables.keys())
