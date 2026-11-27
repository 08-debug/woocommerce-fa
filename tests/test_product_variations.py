import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app

STORE_URL = "https://store.example.com"
CONSUMER_KEY = "ck_var_secret"
CONSUMER_SECRET = "cs_var_secret"


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


def sample_variation(variation_id: int = 201, **overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "id": variation_id,
        "date_created": "2026-11-27T10:00:00",
        "date_created_gmt": "2026-11-27T04:30:00",
        "date_modified": "2026-11-27T10:00:00",
        "date_modified_gmt": "2026-11-27T04:30:00",
        "description": "Blue Large T-Shirt",
        "permalink": "https://store.example.com/product/tshirt/?attribute_pa_color=blue",
        "sku": "TSHIRT-BLUE-L",
        "mpn": "MPN-01",
        "global_unique_id": "1234567890123",
        "customs_commodity_code": None,
        "customs_country_of_origin": None,
        "customs_description": "Cotton shirt",
        "price": "19.99",
        "regular_price": "19.99",
        "sale_price": "",
        "on_sale": False,
        "status": "publish",
        "purchasable": True,
        "virtual": False,
        "downloadable": False,
        "downloads": [{"id": "d1", "name": "Guide", "file": "https://example.com/guide.pdf"}],
        "download_limit": -1,
        "download_expiry": -1,
        "tax_status": "taxable",
        "tax_class": "",
        "manage_stock": True,
        "stock_quantity": 10,
        "stock_status": "instock",
        "backorders": "no",
        "backorders_allowed": False,
        "backordered": False,
        "weight": "0.3",
        "dimensions": {"length": "10", "width": "8", "height": "2"},
        "shipping_class": "",
        "shipping_class_id": 0,
        "image": {"id": 50, "src": "https://example.com/img.png", "name": "img", "alt": "Blue"},
        "gallery_image_ids": [51],
        "attributes": [{"id": 1, "name": "Color", "option": "Blue"}],
        "menu_order": 0,
        "meta_data": [{"id": 10, "key": "_custom", "value": "val"}],
    }
    item.update(overrides)
    return item


def test_create_variation_with_nested_fields_and_invalid_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/wp-json/wc/v3/products/100/variations":
            return httpx.Response(201, json=sample_variation(201))
        if request.url.path == "/wp-json/wc/v3/products/9999/variations":
            return httpx.Response(404, json={"code": "woocommerce_rest_product_invalid_id"})
        raise AssertionError(f"Unexpected path: {request.url.path}")

    mock_httpx(monkeypatch, handler)

    payload = {
        "regular_price": "19.99",
        "sku": "TSHIRT-BLUE-L",
        "customs_description": "Cotton shirt",
        "manage_stock": True,
        "stock_quantity": 10,
        "dimensions": {"length": "10", "width": "8", "height": "2"},
        "downloads": [{"id": "d1", "name": "Guide", "file": "https://example.com/guide.pdf"}],
        "image": {"id": 50, "src": "https://example.com/img.png"},
        "attributes": [{"id": 1, "name": "Color", "option": "Blue"}],
        "meta_data": [{"key": "_custom", "value": "val"}],
    }

    with TestClient(app) as client:
        ok = client.post("/products/100/variations", json=payload)
        missing_parent = client.post("/products/9999/variations", json=payload)
        bad_id = client.post("/products/0/variations", json=payload)

    assert ok.status_code == 201
    assert ok.json()["id"] == 201
    assert ok.json()["dimensions"]["length"] == "10"
    assert missing_parent.status_code == 404
    assert bad_id.status_code == 422


def test_get_and_list_variations_with_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/wp-json/wc/v3/products/100/variations/201":
            return httpx.Response(200, json=sample_variation(201))
        if request.url.path == "/wp-json/wc/v3/products/100/variations":
            assert request.url.params["page"] == "2"
            assert request.url.params["per_page"] == "5"
            assert request.url.params["sku"] == "TSHIRT-BLUE-L"
            assert request.url.params["stock_status"] == "instock"
            assert request.url.params["min_price"] == "10"
            assert request.url.params["max_price"] == "30"
            return httpx.Response(200, json=[sample_variation(201)])
        raise AssertionError(f"Unexpected path: {request.url.path}")

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        single = client.get("/products/100/variations/201")
        listed = client.get(
            "/products/100/variations",
            params={
                "page": 2,
                "per_page": 5,
                "sku": "TSHIRT-BLUE-L",
                "stock_status": "instock",
                "min_price": "10",
                "max_price": "30",
            },
        )

    assert single.status_code == 200
    assert single.json()["id"] == 201
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_update_delete_and_batch_variations(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT":
            return httpx.Response(200, json=sample_variation(201, regular_price="24.99"))
        if request.method == "DELETE":
            assert request.url.params["force"] == "true"
            return httpx.Response(200, json=sample_variation(201))
        if request.method == "POST" and request.url.path.endswith("/batch"):
            return httpx.Response(
                200,
                json={
                    "create": [sample_variation(202)],
                    "update": [sample_variation(201, regular_price="25.00")],
                    "delete": [sample_variation(203)],
                },
            )
        raise AssertionError("Unexpected request")

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        upd = client.put("/products/100/variations/201", json={"regular_price": "24.99"})
        no_force = client.delete("/products/100/variations/201")
        with_force = client.delete("/products/100/variations/201", params={"force": True})
        batch = client.post(
            "/products/100/variations/batch",
            json={
                "create": [{"regular_price": "19.99"}],
                "update": [{"id": 201, "regular_price": "25.00"}],
                "delete": [203],
            },
        )

    assert upd.status_code == 200
    assert upd.json()["regular_price"] == "24.99"
    assert no_force.status_code == 400
    assert with_force.status_code == 200
    assert batch.status_code == 200
    assert batch.json()["create"][0]["id"] == 202


@pytest.mark.parametrize(
    "bad_payload",
    [
        {"regular_price": "-10.00"},
        {"status": "bad_status"},
        {"stock_quantity": -1},
        {"customs_description": "x" * 36},
        {"id": 999, "regular_price": "10.00"},
        {"image": {"id": 1, "date_created": "2026-01-01T00:00:00"}},
        {"meta_data": [{"id": 5, "key": "k", "value": "v"}]},
    ],
)
def test_variation_validation_rejects_invalid_and_readonly_fields(
    monkeypatch: pytest.MonkeyPatch,
    bad_payload: dict[str, object],
) -> None:
    mock_httpx(
        monkeypatch,
        lambda request: (_ for _ in ()).throw(AssertionError("Store should not be called")),
    )

    with TestClient(app) as client:
        resp = client.post("/products/100/variations", json=bad_payload)

    assert resp.status_code == 422
