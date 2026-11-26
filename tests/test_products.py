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


def sample_woo_product(product_id: int = 101, **overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "id": product_id,
        "name": f"Product {product_id}",
        "sku": f"SKU-{product_id}",
        "regular_price": "29.99",
        "sale_price": "24.99",
        "stock_quantity": 12,
        "stock_status": "instock",
        "permalink": "https://store.example.com/product/sample",
        "description": "<p>Extra field ignored by schema</p>",
    }
    item.update(overrides)
    return item



def test_get_products_returns_published_products_in_schema_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/wp-json/wc/v3/products"
        assert request.url.params["status"] == "publish"
        assert request.url.params["per_page"] == "100"
        assert request.url.params["page"] == "1"
        return httpx.Response(
            200,
            json=[
                sample_woo_product(101),
                sample_woo_product(102, sale_price="", stock_quantity=None, stock_status="outofstock"),
            ],
        )

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        response = client.get("/products")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 101,
            "name": "Product 101",
            "sku": "SKU-101",
            "regular_price": "29.99",
            "sale_price": "24.99",
            "stock_quantity": 12,
            "stock_status": "instock",
        },
        {
            "id": 102,
            "name": "Product 102",
            "sku": "SKU-102",
            "regular_price": "29.99",
            "sale_price": "",
            "stock_quantity": None,
            "stock_status": "outofstock",
        },
    ]


def test_get_products_handles_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_httpx(monkeypatch, lambda request: httpx.Response(200, json=[]))

    with TestClient(app) as client:
        response = client.get("/products")

    assert response.status_code == 200
    assert response.json() == []


def test_get_products_fetches_subsequent_pages_when_batch_is_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages_requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params["page"]
        pages_requested.append(page)
        if page == "1":
            return httpx.Response(200, json=[sample_woo_product(i) for i in range(1, 101)])
        return httpx.Response(200, json=[sample_woo_product(101)])

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        response = client.get("/products")

    assert response.status_code == 200
    assert pages_requested == ["1", "2"]
    assert len(response.json()) == 101


def test_get_products_rejects_invalid_response_format(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_httpx(monkeypatch, lambda request: httpx.Response(200, json={"unexpected": "dict"}))

    with TestClient(app) as client:
        response = client.get("/products")

    assert response.status_code == 502
    assert response.json()["detail"] == "The WooCommerce API returned an unexpected response format."


def test_get_products_rejects_invalid_product_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_httpx(monkeypatch, lambda request: httpx.Response(200, json=[{"sku": "NO-ID-OR-NAME"}]))

    with TestClient(app) as client:
        response = client.get("/products")

    assert response.status_code == 502
    assert response.json()["detail"] == "The WooCommerce API returned an unexpected product format."


@pytest.mark.parametrize(
    ("upstream_status", "expected_status", "expected_detail"),
    [
        (401, 401, "Invalid API credentials."),
        (403, 403, "Insufficient API permissions."),
        (404, 404, "The WooCommerce API endpoint was not found."),
        (500, 502, "The WooCommerce API returned an unexpected server error."),
    ],
)
def test_get_products_maps_upstream_http_errors_safely(
    monkeypatch: pytest.MonkeyPatch,
    upstream_status: int,
    expected_status: int,
    expected_detail: str,
) -> None:
    mock_httpx(
        monkeypatch,
        lambda request: httpx.Response(upstream_status, json={"message": CONSUMER_SECRET}),
    )

    with TestClient(app) as client:
        response = client.get("/products")

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail
    assert CONSUMER_KEY not in response.text
    assert CONSUMER_SECRET not in response.text


def test_get_products_handles_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(f"timeout {CONSUMER_SECRET}")

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        response = client.get("/products")

    assert response.status_code == 504
    assert response.json()["detail"] == "The request to the WooCommerce store timed out."
    assert CONSUMER_SECRET not in response.text


def test_post_product_validates_request_and_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/wp-json/wc/v3/products"
        return httpx.Response(
            201,
            json=sample_woo_product(
                205,
                name="Wireless Mouse",
                sku="WM-01",
                regular_price="39.99",
                sale_price="29.99",
                stock_quantity=50,
                stock_status="instock",
            ),
        )

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        response = client.post(
            "/products",
            json={
                "name": "Wireless Mouse",
                "sku": "WM-01",
                "regular_price": "39.99",
                "sale_price": "29.99",
                "stock_quantity": 50,
                "stock_status": "instock",
            },
        )

    assert response.status_code == 201
    assert response.json() == {
        "id": 205,
        "name": "Wireless Mouse",
        "sku": "WM-01",
        "regular_price": "39.99",
        "sale_price": "29.99",
        "stock_quantity": 50,
        "stock_status": "instock",
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "   "},
        {"name": "Mouse", "regular_price": "not-a-price"},
        {"name": "Mouse", "regular_price": "-5.00"},
        {"name": "Mouse", "stock_quantity": -1},
        {"name": "Mouse", "stock_status": "invalid_status"},
        {"name": "Mouse", "unknown_field": "rejected"},
    ],
)
def test_post_product_rejects_invalid_input_schema(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("WooCommerce should not be called on invalid input")

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        response = client.post("/products", json=payload)

    assert response.status_code == 422


def test_post_product_rejects_invalid_upstream_response(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_httpx(monkeypatch, lambda request: httpx.Response(201, json=["not-a-dict"]))

    with TestClient(app) as client:
        response = client.post("/products", json={"name": "Valid Name"})

    assert response.status_code == 502
    assert response.json()["detail"] == "The WooCommerce API returned an unexpected response format."


def test_search_products_by_name_filters_and_validates(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/wp-json/wc/v3/products"
        assert request.url.params["status"] == "publish"
        assert request.url.params["search"] == "Mouse"
        return httpx.Response(
            200,
            json=[
                sample_woo_product(301, name="Wireless Mouse", sku="WM-01"),
                sample_woo_product(302, name="USB Keyboard", sku="UK-01"),
            ],
        )

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        response = client.get("/products/search", params={"name": "  Mouse  "})

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 301,
            "name": "Wireless Mouse",
            "sku": "WM-01",
            "regular_price": "29.99",
            "sale_price": "24.99",
            "stock_quantity": 12,
            "stock_status": "instock",
        }
    ]


def test_search_products_by_partial_sku(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["status"] == "publish"
        assert "sku" not in request.url.params
        return httpx.Response(
            200,
            json=[
                sample_woo_product(301, name="Wireless Mouse", sku="WM-01"),
                sample_woo_product(302, name="Wired Mouse", sku="wm-02"),
                sample_woo_product(303, name="USB Keyboard", sku="UK-01"),
            ],
        )

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        response = client.get("/products/search", params={"sku": "WM"})

    assert response.status_code == 200
    assert [item["sku"] for item in response.json()] == ["WM-01", "wm-02"]


def test_search_products_by_name_and_sku(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["search"] == "Mouse"
        return httpx.Response(
            200,
            json=[
                sample_woo_product(301, name="Wireless Mouse", sku="WM-01"),
                sample_woo_product(302, name="Gaming Mouse", sku="GM-01"),
            ],
        )

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        response = client.get("/products/search", params={"name": "Mouse", "sku": "WM"})

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == 301


def test_search_products_empty_result(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_httpx(monkeypatch, lambda request: httpx.Response(200, json=[]))

    with TestClient(app) as client:
        response = client.get("/products/search", params={"sku": "NO-SUCH-SKU"})

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "query",
    [
        {},
        {"name": "   "},
        {"sku": ""},
        {"name": " ", "sku": "  "},
    ],
)
def test_search_products_requires_name_or_sku(
    monkeypatch: pytest.MonkeyPatch,
    query: dict[str, str],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("WooCommerce should not be called without search parameters")

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        response = client.get("/products/search", params=query)

    assert response.status_code == 422


def test_get_products_filters_by_partial_sku_and_price_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_httpx(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json=[
                sample_woo_product(401, name="Wireless Mouse", sku="WM-100", regular_price="35.00", sale_price="25.00"),
                sample_woo_product(402, name="Pro Mouse", sku="WM-200", regular_price="50.00", sale_price=""),
                sample_woo_product(403, name="Budget Mouse", sku="WM-300", regular_price="", sale_price=""),
                sample_woo_product(404, name="Keyboard", sku="KB-100", regular_price="25.00", sale_price=""),
            ],
        ),
    )

    with TestClient(app) as client:
        response = client.get(
            "/products/search",
            params={"sku": "wm", "min_price": "20", "max_price": "30"},
        )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [401]


def test_search_products_by_price_range(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_httpx(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json=[
                sample_woo_product(501, regular_price="19.99", sale_price=""),
                sample_woo_product(502, regular_price="49.99", sale_price="29.99"),
                sample_woo_product(503, regular_price="10.00", sale_price=""),
            ],
        ),
    )

    with TestClient(app) as client:
        response = client.get("/products/search", params={"min_price": "15", "max_price": "30"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [501, 502]


@pytest.mark.parametrize(
    "params",
    [
        {"min_price": "50", "max_price": "10"},
        {"min_price": "-1"},
        {"max_price": "-5"},
    ],
)
def test_get_products_rejects_invalid_price_range(
    monkeypatch: pytest.MonkeyPatch,
    params: dict[str, str],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("WooCommerce should not be called on invalid price range")

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        response = client.get("/products/search", params=params)

    assert response.status_code == 422
