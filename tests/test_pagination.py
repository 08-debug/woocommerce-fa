import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app

STORE_URL = "https://store.example.com"
CONSUMER_KEY = "ck_task6_secret"
CONSUMER_SECRET = "cs_task6_secret"


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


def woo_product(product_id: int) -> dict[str, object]:
    return {
        "id": product_id,
        "name": f"Product {product_id}",
        "sku": f"SKU-{product_id}",
        "regular_price": "10.00",
        "sale_price": "",
        "stock_quantity": 5,
        "stock_status": "instock",
    }


def woo_order(order_id: int) -> dict[str, object]:
    return {
        "id": order_id,
        "status": "processing",
        "date_created": "2026-11-26T12:00:00",
        "total": "25.00",
        "billing": {"first_name": "Test", "last_name": "User", "email": "test@example.com"},
        "line_items": [{"name": "Item A"}],
    }


def test_products_paginated_defaults_to_page_1_and_limit_10(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append((request.url.params["page"], request.url.params["per_page"]))
        return httpx.Response(200, json=[woo_product(i) for i in range(1, 11)])

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        response = client.get("/products/paginated")

    assert response.status_code == 200
    assert requested == [("1", "10")]
    assert len(response.json()) == 10


def test_products_paginated_custom_page_and_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append((request.url.params["page"], request.url.params["per_page"]))
        return httpx.Response(200, json=[woo_product(3), woo_product(4)])

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        response = client.get("/products/paginated", params={"page": 2, "per_page": 2})

    assert response.status_code == 200
    assert requested == [("2", "2")]
    assert [item["id"] for item in response.json()] == [3, 4]


def test_orders_paginated_defaults_to_page_1_and_limit_10(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append((request.url.params["page"], request.url.params["per_page"]))
        return httpx.Response(200, json=[woo_order(i) for i in range(1, 11)])

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        response = client.get("/orders/paginated")

    assert response.status_code == 200
    assert requested == [("1", "10")]
    assert len(response.json()) == 10


def test_orders_paginated_custom_page_and_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append((request.url.params["page"], request.url.params["per_page"]))
        return httpx.Response(200, json=[woo_order(11), woo_order(12)])

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        response = client.get("/orders/paginated", params={"page": 2, "per_page": 2})

    assert response.status_code == 200
    assert requested == [("2", "2")]
    assert [item["order_id"] for item in response.json()] == [11, 12]


@pytest.mark.parametrize("endpoint", ["/products/paginated", "/orders/paginated"])
@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": -1},
        {"per_page": 0},
        {"per_page": 101},
    ],
)
def test_invalid_pagination_parameters_return_422(
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
    params: dict[str, int],
) -> None:
    mock_httpx(
        monkeypatch,
        lambda request: (_ for _ in ()).throw(AssertionError("Store should not be called")),
    )

    with TestClient(app) as client:
        response = client.get(endpoint, params=params)

    assert response.status_code == 422
