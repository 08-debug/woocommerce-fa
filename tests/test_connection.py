import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.services.woocommerce import WooCommerceClient, api_root

STORE_URL = "https://store.example.com"
CONSUMER_KEY = "ck_test"
CONSUMER_SECRET = "cs_test"


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "woocommerce_store_url": STORE_URL,
        "woocommerce_consumer_key": CONSUMER_KEY,
        "woocommerce_consumer_secret": CONSUMER_SECRET,
        "woocommerce_api_version": "wc/v3",
        "woocommerce_timeout_seconds": 5,
    }
    values.update(overrides)
    return Settings(**values)


def verify(handler, current: Settings):
    http = httpx.Client(
        transport=httpx.MockTransport(handler),
        auth=httpx.BasicAuth(
            current.woocommerce_consumer_key,
            current.woocommerce_consumer_secret,
        ),
    )
    with WooCommerceClient(current, client=http) as client:
        return client.verify_connection()


def json_response(status_code: int, payload) -> httpx.Response:
    return httpx.Response(status_code, json=payload)


def assert_credentials_hidden(message: str) -> None:
    assert CONSUMER_KEY not in message
    assert CONSUMER_SECRET not in message


def test_successful_connection() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/wp-json/wc/v3/products"
        assert request.url.params["per_page"] == "1"
        assert request.headers["authorization"].startswith("Basic ")
        assert CONSUMER_KEY not in str(request.url)
        assert CONSUMER_SECRET not in str(request.url)
        return json_response(200, [{"id": 10}])

    status = verify(handler, settings())

    assert status.success is True
    assert status.status_code == 200
    assert status.store_url == STORE_URL
    assert status.message == "Authenticated WooCommerce API connection succeeded."
    assert "id" not in status.model_dump()


def test_successful_connection_accepts_an_empty_collection() -> None:
    status = verify(lambda request: json_response(200, []), settings())
    assert status.success is True
    assert status.status_code == 200


@pytest.mark.parametrize(
    ("store_url", "version", "expected_path"),
    [
        ("https://store.example.com", "wc/v3", "/wp-json/wc/v3/products"),
        ("https://store.example.com/wp-json/wc/v3", "wc/v3", "/wp-json/wc/v3/products"),
        ("https://store.example.com/shop", "wc/v3", "/shop/wp-json/wc/v3/products"),
        ("https://store.example.com/wp-json", "wc/v2", "/wp-json/wc/v2/products"),
    ],
)
def test_configured_api_root_is_used(store_url: str, version: str, expected_path: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == expected_path
        return json_response(200, [])

    status = verify(
        handler,
        settings(woocommerce_store_url=store_url, woocommerce_api_version=version),
    )
    assert status.success is True


def test_api_root_helper_does_not_duplicate_the_configured_root() -> None:
    assert api_root("https://store.example.com/wp-json/wc/v3", "wc/v3") == (
        "https://store.example.com/wp-json/wc/v3"
    )


@pytest.mark.parametrize(
    ("overrides", "expected_message"),
    [
        (
            {"woocommerce_store_url": ""},
            "Missing store URL. Set WOOCOMMERCE_STORE_URL.",
        ),
        (
            {"woocommerce_consumer_key": "  "},
            "Missing Consumer Key. Set WOOCOMMERCE_CONSUMER_KEY.",
        ),
        (
            {"woocommerce_consumer_secret": ""},
            "Missing Consumer Secret. Set WOOCOMMERCE_CONSUMER_SECRET.",
        ),
    ],
)
def test_missing_configuration_does_not_call_the_store(overrides: dict, expected_message: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("The store should not be called")

    status = verify(handler, settings(**overrides))
    assert status.success is False
    assert status.status_code is None
    assert status.message == expected_message
    assert_credentials_hidden(status.message)


@pytest.mark.parametrize(
    "store_url",
    [
        "not-a-url",
        "http://store.example.com",
        "ftp://store.example.com",
        "https://",
        "https://[::1",
        "https://user:secret@store.example.com",
        "https://store.example.com/shop?consumer_key=ck_test",
        "https://store.example.com/shop#fragment",
        "https://store.example.com:99999",
        "https://-invalid.example.com",
        "https://256.256.256.256",
        "https://store.example.com/../admin",
    ],
)
def test_invalid_store_url(store_url: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("The store should not be called")

    status = verify(handler, settings(woocommerce_store_url=store_url))
    assert status.success is False
    assert status.status_code is None
    assert status.message.startswith("Incorrect store URL.")
    assert_credentials_hidden(status.message)


def test_http_store_url_is_rejected_before_credentials_are_sent() -> None:
    status = verify(
        lambda request: json_response(200, []),
        settings(woocommerce_store_url="http://store.example.com"),
    )
    assert status.success is False
    assert "HTTPS" in status.message


def test_invalid_credentials() -> None:
    status = verify(
        lambda request: json_response(401, {"code": "woocommerce_rest_authentication_error", "message": CONSUMER_KEY}),
        settings(),
    )
    assert status.success is False
    assert status.status_code == 401
    assert status.message == "Invalid API credentials."
    assert_credentials_hidden(status.message)


def test_insufficient_permissions() -> None:
    status = verify(
        lambda request: json_response(403, {"code": "woocommerce_rest_cannot_view", "message": "Sorry"}),
        settings(),
    )
    assert status.success is False
    assert status.status_code == 403
    assert status.message == "Insufficient API permissions."


def test_api_endpoint_not_found() -> None:
    status = verify(lambda request: json_response(404, {"code": "rest_no_route"}), settings())
    assert status.success is False
    assert status.status_code == 404
    assert status.message == "The WooCommerce API endpoint was not found."


def test_server_error() -> None:
    status = verify(
        lambda request: json_response(500, {"code": "internal_server_error", "message": CONSUMER_SECRET}),
        settings(),
    )
    assert status.success is False
    assert status.status_code == 500
    assert status.message == "The WooCommerce API returned an unexpected server error."
    assert_credentials_hidden(status.message)


def test_unexpected_http_response() -> None:
    status = verify(lambda request: httpx.Response(302, headers={"Location": "http://elsewhere"}), settings())
    assert status.success is False
    assert status.status_code == 302
    assert status.message == "The WooCommerce API returned an unexpected HTTP response."


def test_network_connection_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"connection failed for {CONSUMER_KEY}")

    status = verify(handler, settings())
    assert status.success is False
    assert status.status_code is None
    assert status.message == "Could not connect to the WooCommerce store."
    assert_credentials_hidden(status.message)


def test_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(f"timed out {CONSUMER_SECRET}")

    status = verify(handler, settings())
    assert status.success is False
    assert status.message == "The request to the WooCommerce store timed out."
    assert_credentials_hidden(status.message)


def test_invalid_json_response() -> None:
    status = verify(
        lambda request: httpx.Response(200, content=b"<html>not json</html>"),
        settings(),
    )
    assert status.success is False
    assert status.status_code == 200
    assert status.message == "The WooCommerce API returned invalid JSON."


def test_unexpected_json_shape() -> None:
    status = verify(
        lambda request: json_response(200, {"namespace": "wc/v3", "routes": {}}),
        settings(),
    )
    assert status.success is False
    assert status.status_code == 200
    assert status.message == "The WooCommerce API returned an unexpected response format."



def test_local_http_uses_oauth1_authorization_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WOOCOMMERCE_STORE_URL", "http://localhost:8080")
    monkeypatch.setenv("WOOCOMMERCE_CONSUMER_KEY", CONSUMER_KEY)
    monkeypatch.setenv("WOOCOMMERCE_CONSUMER_SECRET", CONSUMER_SECRET)

    def handler(request: httpx.Request) -> httpx.Response:
        auth_header = request.headers.get("authorization", "")
        assert auth_header.startswith("OAuth ")
        assert f'oauth_consumer_key="{CONSUMER_KEY}"' in auth_header
        assert 'oauth_signature_method="HMAC-SHA256"' in auth_header
        assert CONSUMER_SECRET not in auth_header
        assert CONSUMER_KEY not in str(request.url)
        return json_response(200, [])

    real_client = httpx.Client

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr("app.services.woocommerce.httpx.Client", client_factory)

    with TestClient(app) as client:
        response = client.get("/connection")

    assert response.status_code == 200
    assert response.json()["success"] is True
