import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app

STORE_URL = "https://store.example.com"
CONSUMER_KEY = "ck_task5_secret"
CONSUMER_SECRET = "cs_task5_secret"


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


@pytest.mark.parametrize("endpoint", ["/products", "/orders", "/orders/placed"])
def test_invalid_api_credentials_across_endpoints(
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
) -> None:
    mock_httpx(
        monkeypatch,
        lambda request: httpx.Response(401, json={"message": f"bad {CONSUMER_KEY}"}),
    )

    with TestClient(app) as client:
        response = client.get(endpoint)

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API credentials.", "upstream_status": 401}
    assert CONSUMER_KEY not in response.text
    assert CONSUMER_SECRET not in response.text


@pytest.mark.parametrize("endpoint", ["/products", "/orders"])
@pytest.mark.parametrize(
    "bad_url",
    [
        "",
        "http://store.example.com",
        "https://[::1",
        "not-a-valid-url",
    ],
)
def test_incorrect_store_url_across_endpoints(
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
    bad_url: str,
) -> None:
    monkeypatch.setenv("WOOCOMMERCE_STORE_URL", bad_url)
    mock_httpx(
        monkeypatch,
        lambda request: (_ for _ in ()).throw(AssertionError("Store should not be called")),
    )

    with TestClient(app) as client:
        response = client.get(endpoint)

    assert response.status_code == 400
    assert "detail" in response.json()
    assert CONSUMER_KEY not in response.text
    assert CONSUMER_SECRET not in response.text


@pytest.mark.parametrize("endpoint", ["/products", "/orders"])
def test_api_connection_failure(monkeypatch: pytest.MonkeyPatch, endpoint: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"failed {CONSUMER_KEY}")

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        response = client.get(endpoint)

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Could not connect to the WooCommerce store.",
        "upstream_status": None,
    }
    assert CONSUMER_KEY not in response.text


@pytest.mark.parametrize("endpoint", ["/products", "/orders", "/orders/placed"])
def test_empty_product_and_order_results(
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
) -> None:
    mock_httpx(monkeypatch, lambda request: httpx.Response(200, json=[]))

    with TestClient(app) as client:
        response = client.get(endpoint)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("endpoint", ["/products", "/orders"])
def test_invalid_json_api_response(
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
) -> None:
    mock_httpx(monkeypatch, lambda request: httpx.Response(200, content=b"not-json"))

    with TestClient(app) as client:
        response = client.get(endpoint)

    assert response.status_code == 502
    assert response.json() == {
        "detail": "The WooCommerce API returned invalid JSON.",
        "upstream_status": 200,
    }


@pytest.mark.parametrize("endpoint", ["/products", "/orders"])
def test_network_timeout(monkeypatch: pytest.MonkeyPatch, endpoint: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(f"timeout {CONSUMER_SECRET}")

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        response = client.get(endpoint)

    assert response.status_code == 504
    assert response.json() == {
        "detail": "The request to the WooCommerce store timed out.",
        "upstream_status": None,
    }
    assert CONSUMER_SECRET not in response.text
