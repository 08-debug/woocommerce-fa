import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app

STORE_URL = "https://store.example.com"
CONSUMER_KEY = "ck_attr_secret"
CONSUMER_SECRET = "cs_attr_secret"


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


def sample_attribute(attr_id: int = 1, **overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "id": attr_id,
        "name": "Color",
        "slug": "pa_color",
        "type": "select",
        "order_by": "menu_order",
        "has_archives": False,
    }
    item.update(overrides)
    return item


def test_create_attribute_valid_and_missing_name(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/wp-json/wc/v3/products/attributes"
        return httpx.Response(201, json=sample_attribute(1))

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        ok = client.post("/products/attributes", json={"name": "Color"})
        missing = client.post("/products/attributes", json={})
        blank = client.post("/products/attributes", json={"name": "   "})
        with_id = client.post("/products/attributes", json={"id": 99, "name": "Color"})

    assert ok.status_code == 201
    assert ok.json()["id"] == 1
    assert missing.status_code == 422
    assert blank.status_code == 422
    assert with_id.status_code == 422


def test_get_list_and_slug_filter_attributes(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/wp-json/wc/v3/products/attributes/1":
            return httpx.Response(200, json=sample_attribute(1))
        if request.url.path == "/wp-json/wc/v3/products/attributes":
            if "slug" in request.url.params:
                assert request.url.params["slug"] == "pa_color,pa_size"
                return httpx.Response(200, json=[sample_attribute(1)])
            return httpx.Response(200, json=[sample_attribute(1), sample_attribute(2, name="Size", slug="pa_size")])
        raise AssertionError(f"Unexpected path: {request.url.path}")

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        by_id = client.get("/products/attributes/1")
        all_attrs = client.get("/products/attributes")
        by_slug = client.get("/products/attributes", params={"slug": ["pa_color", "pa_size"]})

    assert by_id.status_code == 200
    assert by_id.json()["name"] == "Color"
    assert all_attrs.status_code == 200
    assert len(all_attrs.json()) == 2
    assert by_slug.status_code == 200
    assert len(by_slug.json()) == 1


def test_update_and_delete_attribute_force_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT":
            assert json.loads(request.content) == {"name": "Colour", "order_by": "name"}
            return httpx.Response(200, json=sample_attribute(1, name="Colour", order_by="name"))
        if request.method == "DELETE":
            assert request.url.params["force"] == "true"
            return httpx.Response(200, json=sample_attribute(1))
        raise AssertionError(f"Unexpected method: {request.method}")

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        upd = client.put("/products/attributes/1", json={"name": "Colour", "order_by": "name"})
        no_force = client.delete("/products/attributes/1")
        with_force = client.delete("/products/attributes/1", params={"force": True})

    assert upd.status_code == 200
    assert upd.json()["name"] == "Colour"
    assert no_force.status_code == 400
    assert "force=true" in no_force.json()["detail"]
    assert with_force.status_code == 200


def test_batch_attributes_and_limit_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/wp-json/wc/v3/products/attributes/batch"
        sent = json.loads(request.content)
        assert len(sent["create"]) == 1
        assert len(sent["update"]) == 1
        assert sent["delete"] == [3]
        return httpx.Response(
            200,
            json={
                "create": [sample_attribute(10, name="Material")],
                "update": [sample_attribute(1, name="Updated Color")],
                "delete": [sample_attribute(3, name="Old")],
            },
        )

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        ok = client.post(
            "/products/attributes/batch",
            json={
                "create": [{"name": "Material"}],
                "update": [{"id": 1, "name": "Updated Color"}],
                "delete": [3],
            },
        )
        empty = client.post("/products/attributes/batch", json={})
        over_100 = client.post(
            "/products/attributes/batch",
            json={"create": [{"name": f"Attr {i}"} for i in range(101)]},
        )

    assert ok.status_code == 200
    assert ok.json()["create"][0]["id"] == 10
    assert empty.status_code == 422
    assert over_100.status_code == 422
