import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app

STORE_URL = "https://store.example.com"
CONSUMER_KEY = "ck_tag_secret"
CONSUMER_SECRET = "cs_tag_secret"


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


def sample_tag(tag_id: int = 34, **overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "id": tag_id,
        "name": "Leather Shoes",
        "slug": "leather-shoes",
        "description": "Genuine leather footwear",
        "count": 2,
    }
    item.update(overrides)
    return item


def test_create_product_tag_and_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_httpx(monkeypatch, lambda request: httpx.Response(201, json=sample_tag(34)))

    with TestClient(app) as client:
        name_only = client.post("/products/tags", json={"name": "Leather Shoes"})
        full = client.post(
            "/products/tags",
            json={"name": "Leather Shoes", "slug": "leather-shoes", "description": "Genuine leather footwear"},
        )
        missing = client.post("/products/tags", json={})
        blank = client.post("/products/tags", json={"name": "   "})
        readonly_count = client.post("/products/tags", json={"name": "Leather", "count": 5})

    assert name_only.status_code == 201
    assert full.status_code == 201
    assert missing.status_code == 422
    assert blank.status_code == 422
    assert readonly_count.status_code == 422


def test_get_and_list_product_tags_with_all_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/wp-json/wc/v3/products/tags/34":
            return httpx.Response(200, json=sample_tag(34))
        if request.url.path == "/wp-json/wc/v3/products/tags":
            assert request.url.params["context"] == "edit"
            assert request.url.params["page"] == "2"
            assert request.url.params["per_page"] == "5"
            assert request.url.params["search"] == "leather"
            assert request.url.params["include"] == "34,35"
            assert request.url.params["exclude"] == "10"
            assert request.url.params["offset"] == "1"
            assert request.url.params["order"] == "desc"
            assert request.url.params["orderby"] == "count"
            assert request.url.params["hide_empty"] == "true"
            assert request.url.params["product"] == "100"
            assert request.url.params["slug"] == "leather-shoes"
            return httpx.Response(200, json=[sample_tag(34)])
        raise AssertionError(f"Unexpected path: {request.url.path}")

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        single = client.get("/products/tags/34")
        listed = client.get(
            "/products/tags",
            params={
                "context": "edit",
                "page": 2,
                "per_page": 5,
                "search": "leather",
                "include": [34, 35],
                "exclude": [10],
                "offset": 1,
                "order": "desc",
                "orderby": "count",
                "hide_empty": True,
                "product": 100,
                "slug": "leather-shoes",
            },
        )
        bad_id = client.get("/products/tags/0")

    assert single.status_code == 200
    assert single.json()["id"] == 34
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert bad_id.status_code == 422


def test_update_and_delete_product_tag_requires_force(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT":
            return httpx.Response(200, json=sample_tag(34, description="Genuine leather."))
        if request.method == "DELETE":
            assert request.url.params["force"] == "true"
            return httpx.Response(200, json=sample_tag(34))
        raise AssertionError("Unexpected method")

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        upd = client.put("/products/tags/34", json={"description": "Genuine leather."})
        empty_upd = client.put("/products/tags/34", json={})
        no_force = client.delete("/products/tags/34")
        false_force = client.delete("/products/tags/34", params={"force": False})
        with_force = client.delete("/products/tags/34", params={"force": True})

    assert upd.status_code == 200
    assert upd.json()["description"] == "Genuine leather."
    assert empty_upd.status_code == 422
    assert no_force.status_code == 400
    assert false_force.status_code == 400
    assert with_force.status_code == 200


def test_batch_product_tags_total_limit_and_partial_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/wp-json/wc/v3/products/tags/batch"
        sent = json.loads(request.content)
        assert len(sent["create"]) == 2
        assert sent["update"] == [{"id": 34, "description": "Genuine leather."}]
        assert sent["delete"] == [35]
        return httpx.Response(
            200,
            json={
                "create": [
                    sample_tag(40, name="Round toe"),
                    {"id": 0, "error": {"code": "term_exists", "message": "Exists"}},
                ],
                "update": [sample_tag(34, description="Genuine leather.")],
                "delete": [sample_tag(35)],
            },
        )

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        ok = client.post(
            "/products/tags/batch",
            json={
                "create": [{"name": "Round toe"}, {"name": "Flat"}],
                "update": [{"id": 34, "description": "Genuine leather."}],
                "delete": [35],
            },
        )
        over_100 = client.post(
            "/products/tags/batch",
            json={
                "create": [{"name": f"Tag {i}"} for i in range(60)],
                "delete": list(range(1, 42)),
            },
        )

    assert ok.status_code == 200
    assert ok.json()["create"][1]["error"]["code"] == "term_exists"
    assert over_100.status_code == 422


def test_product_tags_errors_and_swagger(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_httpx(monkeypatch, lambda request: httpx.Response(401, json={"message": CONSUMER_KEY}))
    with TestClient(app) as client:
        auth_err = client.get("/products/tags")
        schema = client.get("/openapi.json").json()

    assert auth_err.status_code == 401
    assert CONSUMER_KEY not in auth_err.text
    assert schema["paths"]["/products/tags"]["get"]["tags"] == ["Product Tags"]
    assert schema["paths"]["/products/tags/batch"]["post"]["tags"] == ["Product Tags"]
