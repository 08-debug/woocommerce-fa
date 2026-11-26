import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app

STORE_URL = "https://store.example.com"
CONSUMER_KEY = "ck_test_secret_key"
CONSUMER_SECRET = "cs_test_secret_value"


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


def sample_woo_order(order_id: int = 501, **overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "id": order_id,
        "status": "processing",
        "date_created": "2026-11-26T10:15:00",
        "total": "149.98",
        "billing": {
            "first_name": "Varsha",
            "last_name": "M",
            "email": "varsha@example.com",
        },
        "line_items": [
            {"id": 1, "name": "Wireless Mouse", "quantity": 1},
            {"id": 2, "name": "USB Keyboard", "quantity": 1},
        ],
    }
    item.update(overrides)
    return item


def test_get_all_orders_maps_required_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/wp-json/wc/v3/orders"
        assert request.url.params["status"] == "any"
        return httpx.Response(
            200,
            json=[
                sample_woo_order(501, status="processing"),
                sample_woo_order(
                    502,
                    status="completed",
                    total="59.00",
                    billing={"first_name": "Alex", "last_name": "", "email": "alex@example.com"},
                    line_items=[{"name": "Laptop Stand"}],
                ),
            ],
        )

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        response = client.get("/orders")

    assert response.status_code == 200
    assert response.json() == [
        {
            "order_id": 501,
            "customer_name": "Varsha M",
            "customer_email": "varsha@example.com",
            "order_date": "2026-11-26T10:15:00",
            "order_status": "processing",
            "product_names": ["Wireless Mouse", "USB Keyboard"],
            "total_order_amount": "149.98",
        },
        {
            "order_id": 502,
            "customer_name": "Alex",
            "customer_email": "alex@example.com",
            "order_date": "2026-11-26T10:15:00",
            "order_status": "completed",
            "product_names": ["Laptop Stand"],
            "total_order_amount": "59.00",
        },
    ]


@pytest.mark.parametrize("status_value", ["processing", "completed", "on-hold", "pending"])
def test_get_orders_filters_by_status(
    monkeypatch: pytest.MonkeyPatch,
    status_value: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["status"] == status_value
        return httpx.Response(
            200,
            json=[
                sample_woo_order(601, status=status_value),
                sample_woo_order(602, status="cancelled"),
            ],
        )

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        response = client.get("/orders", params={"status": status_value})

    assert response.status_code == 200
    assert [o["order_id"] for o in response.json()] == [601]
    assert response.json()[0]["order_status"] == status_value


def test_get_orders_draft_filter_matches_draft_and_checkout_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["status"] == "any"
        return httpx.Response(
            200,
            json=[
                sample_woo_order(701, status="checkout-draft"),
                sample_woo_order(702, status="draft"),
                sample_woo_order(703, status="completed"),
            ],
        )

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        response = client.get("/orders", params={"status": "draft"})

    assert response.status_code == 200
    assert [o["order_id"] for o in response.json()] == [701, 702]


def test_get_orders_rejects_invalid_status_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("WooCommerce should not be called with invalid status")

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        response = client.get("/orders", params={"status": "unknown"})

    assert response.status_code == 422


def test_get_orders_handles_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_httpx(monkeypatch, lambda request: httpx.Response(200, json=[]))

    with TestClient(app) as client:
        response = client.get("/orders")

    assert response.status_code == 200
    assert response.json() == []


def test_get_orders_rejects_invalid_response_format(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_httpx(monkeypatch, lambda request: httpx.Response(200, json={"unexpected": "dict"}))

    with TestClient(app) as client:
        response = client.get("/orders")

    assert response.status_code == 502
    assert response.json()["detail"] == "The WooCommerce API returned an unexpected response format."


def test_get_orders_handles_auth_error_without_leaking_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_httpx(
        monkeypatch,
        lambda request: httpx.Response(401, json={"message": CONSUMER_SECRET}),
    )

    with TestClient(app) as client:
        response = client.get("/orders")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API credentials."
    assert CONSUMER_KEY not in response.text
    assert CONSUMER_SECRET not in response.text


def test_get_placed_orders_excludes_drafts(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["status"] == "any"
        return httpx.Response(
            200,
            json=[
                sample_woo_order(801, status="processing"),
                sample_woo_order(802, status="completed"),
                sample_woo_order(803, status="pending"),
                sample_woo_order(804, status="checkout-draft"),
                sample_woo_order(805, status="draft"),
            ],
        )

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        response = client.get("/orders/placed")

    assert response.status_code == 200
    assert [o["order_id"] for o in response.json()] == [801, 802, 803]
