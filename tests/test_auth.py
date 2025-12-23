import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client_with_api_key(repo_root, monkeypatch):
    monkeypatch.setenv("DM_API_KEY", "secret")
    from service.app import app
    with TestClient(app) as test_client:
        yield test_client


def test_post_allowed_without_key_when_disabled(client):
    payload = {"slug": "auth-no-key", "template_slug": "example-rogue"}
    response = client.post("/api/sessions", json=payload)
    assert response.status_code == 201


def test_post_rejected_without_header_when_key_set(client_with_api_key):
    payload = {"slug": "auth-missing", "template_slug": "example-rogue"}
    response = client_with_api_key.post("/api/sessions", json=payload)
    assert response.status_code == 401


def test_post_allowed_with_header_when_key_set(client_with_api_key):
    payload = {"slug": "auth-with-header", "template_slug": "example-rogue"}
    response = client_with_api_key.post("/api/sessions", json=payload, headers={"X-API-Key": "secret"})
    assert response.status_code == 201


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_mutating_methods_rejected_without_header_when_key_set(client_with_api_key, method):
    request_fn = getattr(client_with_api_key, method)
    if method == "delete":
        response = request_fn("/api/unknown")
    else:
        response = request_fn("/api/unknown", json={"noop": True})
    assert response.status_code == 401
    assert response.json()["detail"] == "unauthorized"


def test_llm_routes_require_key_when_enabled(client_with_api_key):
    response = client_with_api_key.get("/api/llm/config")
    assert response.status_code == 401
    assert response.json()["detail"] == "unauthorized"

    response = client_with_api_key.post("/api/llm/narrate", json={"prompt": "hello"})
    assert response.status_code == 401
    assert response.json()["detail"] == "unauthorized"
