import json
import logging
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from partner_catalog.config import Settings
from partner_catalog.main import create_app


def test_health_checks_database_without_key(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_create_returns_contract_location_and_utc_timestamp(client, partner_payload):
    response = client.post("/v1/partners", json=partner_payload)
    assert response.status_code == 201
    body = response.json()
    assert UUID(body["id"]).version == 4
    assert response.headers["Location"] == f"/v1/partners/{body['id']}"
    assert body["code"] == partner_payload["code"]
    assert body["active"] is True
    assert datetime.fromisoformat(body["created_at"]).utcoffset().total_seconds() == 0
    assert set(body) == {"id", "code", "display_name", "category", "active", "created_at"}


def test_read_returns_persisted_partner(client, partner):
    response = client.get(f"/v1/partners/{partner['id']}")
    assert response.status_code == 200
    assert response.json() == partner


def test_unique_code_conflict_does_not_break_later_requests(client, partner, partner_payload):
    duplicate = client.post("/v1/partners", json=partner_payload)
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "partner_code_conflict"}
    assert client.get("/v1/partners").json()["total"] == 1
    partner_payload["code"] = "DEMO-002"
    assert client.post("/v1/partners", json=partner_payload).status_code == 201


def test_patch_changes_selected_fields_and_preserves_identity(client, partner):
    response = client.patch(
        f"/v1/partners/{partner['id']}",
        json={"display_name": "Synthetic Investor", "active": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Synthetic Investor"
    assert body["active"] is False
    for field in ["id", "code", "category", "created_at"]:
        assert body[field] == partner[field]


def test_patch_duplicate_code_leaves_both_records_unchanged(client, partner, partner_payload):
    partner_payload["code"] = "DEMO-002"
    other = client.post("/v1/partners", json=partner_payload).json()
    result = client.patch(f"/v1/partners/{other['id']}", json={"code": partner["code"]})
    assert result.status_code == 409
    assert client.get(f"/v1/partners/{other['id']}").json()["code"] == "DEMO-002"


def test_delete_is_permanent_and_second_delete_is_not_found(client, partner):
    path = f"/v1/partners/{partner['id']}"
    response = client.delete(path)
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(path).status_code == 404
    assert client.delete(path).status_code == 404
    assert client.get("/v1/partners").json()["total"] == 0


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_missing_partner_returns_explicit_not_found(client, method):
    options = {"json": {"active": False}} if method == "patch" else {}
    response = getattr(client, method)(f"/v1/partners/{uuid4()}", **options)
    assert response.status_code == 404
    assert response.json() == {"detail": "partner_not_found"}


def test_invalid_uuid_is_rejected_before_database_query(client):
    assert client.get("/v1/partners/not-a-uuid").status_code == 422


@pytest.mark.parametrize(
    "change",
    [
        {"code": "lowercase"},
        {"code": "A"},
        {"code": "A" * 33},
        {"display_name": "   "},
        {"display_name": "x" * 121},
        {"category": "banking-approval"},
        {"active": "true"},
        {"active": 1},
        {"unexpected_field": "not allowed"},
        {"code": None},
    ],
)
def test_invalid_create_payload_is_rejected_without_write(client, partner_payload, change):
    response = client.post("/v1/partners", json={**partner_payload, **change})
    assert response.status_code == 422
    assert client.get("/v1/partners").json()["total"] == 0


def test_name_is_trimmed_by_contract(client, partner_payload):
    partner_payload["display_name"] = "   Synthetic Servicer   "
    response = client.post("/v1/partners", json=partner_payload)
    assert response.status_code == 201
    assert response.json()["display_name"] == "Synthetic Servicer"


@pytest.mark.parametrize("body", [{}, {"display_name": None}, {"active": None}, {"id": "x"}])
def test_invalid_patch_cannot_clear_required_fields(client, partner, body):
    response = client.patch(f"/v1/partners/{partner['id']}", json=body)
    assert response.status_code == 422
    assert client.get(f"/v1/partners/{partner['id']}").json() == partner


def test_page_is_deterministic_with_total_offset_and_active_filter(client, partner_payload):
    for code in ["DEMO-003", "DEMO-001", "DEMO-002"]:
        body = {**partner_payload, "code": code, "active": code != "DEMO-002"}
        assert client.post("/v1/partners", json=body).status_code == 201
    page = client.get("/v1/partners?limit=1&offset=1").json()
    assert page["total"] == 3 and page["limit"] == 1 and page["offset"] == 1
    assert [p["code"] for p in page["items"]] == ["DEMO-002"]
    inactive = client.get("/v1/partners?active=false").json()
    assert inactive["total"] == 1
    assert inactive["items"][0]["code"] == "DEMO-002"
    assert client.get("/v1/partners?offset=100").json()["items"] == []


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "limit=not-a-number"])
def test_pagination_boundaries_are_validated(client, query):
    assert client.get("/v1/partners?" + query).status_code == 422


@pytest.mark.parametrize("supplied", [None, "incorrect-key", b"invalid-high-byte-\xff"])
def test_missing_or_invalid_api_key_cannot_read_catalog(settings, supplied):
    with TestClient(create_app(settings)) as client:
        headers = {"X-API-Key": supplied} if supplied else {}
        response = client.get("/v1/partners", headers=headers)
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_api_key"}


def test_missing_key_cannot_create_update_or_delete(settings, partner_payload):
    with TestClient(create_app(settings)) as client:
        assert client.post("/v1/partners", json=partner_payload).status_code == 401
        path = f"/v1/partners/{uuid4()}"
        assert client.patch(path, json={"active": False}).status_code == 401
        assert client.delete(path).status_code == 401


def test_data_survives_new_application_and_engine(settings, partner_payload):
    with TestClient(create_app(settings)) as first:
        first.headers["X-API-Key"] = settings.api_key
        created = first.post("/v1/partners", json=partner_payload).json()
    with TestClient(create_app(settings)) as second:
        second.headers["X-API-Key"] = settings.api_key
        assert second.get(f"/v1/partners/{created['id']}").json() == created


def test_independent_database_files_do_not_share_partner_records(
    client, partner, tmp_path, settings
):
    other = Settings(api_key=settings.api_key, database_url=f"sqlite:///{tmp_path / 'isolated.db'}")
    with TestClient(create_app(other)) as isolated:
        isolated.headers["X-API-Key"] = settings.api_key
        assert isolated.get("/v1/partners").json()["total"] == 0
    assert client.get("/v1/partners").json()["total"] == 1


def test_parameter_binding_stores_sql_like_text_without_executing_it(client, partner_payload):
    partner_payload["display_name"] = "Synthetic'); DROP TABLE partners; --"
    response = client.post("/v1/partners", json=partner_payload)
    assert response.status_code == 201
    assert response.json()["display_name"] == partner_payload["display_name"]
    assert client.get("/v1/partners").json()["total"] == 1


def test_database_constraint_blocks_invalid_category_even_without_api(settings):
    app = create_app(settings)
    with pytest.raises(IntegrityError), app.state.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO partners (id, code, display_name, category, active, created_at) "
                "VALUES (:id, :code, :name, :category, :active, :created)"
            ),
            {
                "id": str(uuid4()),
                "code": "DEMO-001",
                "name": "Synthetic Organization",
                "category": "invalid",
                "active": True,
                "created": "2026-01-01T00:00:00+00:00",
            },
        )
    app.state.engine.dispose()


def test_request_id_and_structured_log_do_not_contain_credentials_or_payload(
    client, partner_payload, caplog, settings
):
    with caplog.at_level(logging.INFO, logger="partner_catalog.http"):
        response = client.post(
            "/v1/partners", json=partner_payload, headers={"X-Request-ID": "synthetic-request-001"}
        )
    assert response.headers["X-Request-ID"] == "synthetic-request-001"
    records = [json.loads(r.message) for r in caplog.records if r.name == "partner_catalog.http"]
    assert records[-1]["status"] == 201
    assert records[-1]["request_id"] == "synthetic-request-001"
    assert settings.api_key not in caplog.text
    assert partner_payload["display_name"] not in caplog.text


def test_untrusted_request_id_is_replaced(client):
    response = client.get("/health", headers={"X-Request-ID": "contains spaces"})
    UUID(response.headers["X-Request-ID"])


def test_openapi_describes_api_key_scheme_and_bounded_list(client):
    schema = client.get("/openapi.json").json()
    assert schema["components"]["securitySchemes"]["APIKeyHeader"]["name"] == "X-API-Key"
    params = schema["paths"]["/v1/partners"]["get"]["parameters"]
    assert next(p for p in params if p["name"] == "limit")["schema"]["maximum"] == 100


def test_exported_openapi_matches_current_application_contract(client):
    exported = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"
    assert json.loads(exported.read_text(encoding="utf-8")) == client.get("/openapi.json").json()
