import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app

STORE_URL = "https://store.example.com"
CONSUMER_KEY = "ck_term_secret"
CONSUMER_SECRET = "cs_term_secret"


@pytest.fixture(autouse=True)
def configure_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WOOCOMMERCE_STORE_URL", STORE_URL)
    monkeypatch.setenv("WOOCOMMERCE_CONSUMER_KEY", CONSUMER_KEY)
    monkeypatch.setenv("WOOCOMMERCE_CONSUMER_SECRET", CONSUMER_SECRET)


def mock_httpx(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    real_client = httpx.Client

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr("app.services.woocommerce.httpx.Client", client_factory)


def sample_term(term_id: int = 11, **overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "id": term_id,
        "name": "Blue",
        "slug": "blue",
        "description": "Blue color",
        "menu_order": 1,
        "count": 4,
    }
    item.update(overrides)
    return item


def test_create_term_and_reject_invalid_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_httpx(
        monkeypatch,
        lambda request: httpx.Response(201, json=sample_term(11)),
    )

    with TestClient(app) as client:
        ok = client.post("/products/attributes/1/terms", json={"name": "Blue", "menu_order": 1})
        missing = client.post("/products/attributes/1/terms", json={})
        blank = client.post("/products/attributes/1/terms", json={"name": "   "})
        with_readonly = client.post("/products/attributes/1/terms", json={"name": "Blue", "count": 99})
        bad_attr = client.post("/products/attributes/0/terms", json={"name": "Blue"})

    assert ok.status_code == 201
    assert ok.json()["id"] == 11
    assert missing.status_code == 422
    assert blank.status_code == 422
    assert with_readonly.status_code == 422
    assert bad_attr.status_code == 422


def test_get_and_list_attribute_terms_with_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/wp-json/wc/v3/products/attributes/1/terms/11":
            return httpx.Response(200, json=sample_term(11))
        if request.url.path == "/wp-json/wc/v3/products/attributes/1/terms":
            assert request.url.params["order"] == "desc"
            assert request.url.params["orderby"] == "count"
            assert request.url.params["hide_empty"] == "true"
            assert request.url.params["search"] == "bl"
            return httpx.Response(200, json=[sample_term(11)])
        raise AssertionError(f"Unexpected path: {request.url.path}")

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        single = client.get("/products/attributes/1/terms/11")
        listed = client.get(
            "/products/attributes/1/terms",
            params={"order": "desc", "orderby": "count", "hide_empty": True, "search": "bl"},
        )

    assert single.status_code == 200
    assert single.json()["name"] == "Blue"
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_update_delete_and_batch_attribute_terms(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT":
            return httpx.Response(200, json=sample_term(11, name="Navy Blue"))
        if request.method == "DELETE":
            assert request.url.params["force"] == "true"
            return httpx.Response(200, json=sample_term(11))
        if request.method == "POST" and request.url.path.endswith("/batch"):
            return httpx.Response(
                200,
                json={
                    "create": [sample_term(12, name="Red")],
                    "update": [sample_term(11, name="Navy Blue")],
                    "delete": [sample_term(13, name="Old")],
                },
            )
        raise AssertionError("Unexpected request")

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        upd = client.put("/products/attributes/1/terms/11", json={"name": "Navy Blue"})
        no_force = client.delete("/products/attributes/1/terms/11")
        with_force = client.delete("/products/attributes/1/terms/11", params={"force": True})
        batch = client.post(
            "/products/attributes/1/terms/batch",
            json={
                "create": [{"name": "Red"}],
                "update": [{"id": 11, "name": "Navy Blue"}],
                "delete": [13],
            },
        )
        over_100 = client.post(
            "/products/attributes/1/terms/batch",
            json={"create": [{"name": f"Term {i}"} for i in range(101)]},
        )

    assert upd.status_code == 200
    assert upd.json()["name"] == "Navy Blue"
    assert no_force.status_code == 400
    assert with_force.status_code == 200
    assert batch.status_code == 200
    assert batch.json()["create"][0]["id"] == 12
    assert over_100.status_code == 422
