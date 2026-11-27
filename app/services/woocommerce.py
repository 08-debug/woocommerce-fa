import base64
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import time
from urllib.parse import quote, unquote, urlparse, urlunparse

import httpx
from pydantic import BaseModel

from app.config import Settings

_API_VERSION = re.compile(r"^wc/v[1-9][0-9]*$")
_HOSTNAME_LABEL = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$")
_LOCAL_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


class ConnectionStatus(BaseModel):
    success: bool
    message: str
    store_url: str
    status_code: int | None = None


class WooCommerceAPIError(Exception):
    """Safe domain exception for WooCommerce API failures without exposing credentials."""

    def __init__(
        self,
        message: str,
        status_code: int = 502,
        upstream_status: int | None = None,
        upstream_code: str | None = None,
        upstream_message: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.upstream_status = upstream_status
        self.upstream_code = upstream_code
        self.upstream_message = upstream_message


class _WooCommerceAuth(httpx.Auth):
    """Use HTTP Basic Auth over HTTPS and OAuth 1.0a over local HTTP."""

    def __init__(self, consumer_key: str, consumer_secret: str) -> None:
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret

    def auth_flow(self, request: httpx.Request):
        if request.url.scheme == "https":
            token = base64.b64encode(
                f"{self.consumer_key}:{self.consumer_secret}".encode("utf-8")
            ).decode("ascii")
            request.headers["Authorization"] = f"Basic {token}"
        else:
            request.headers["Authorization"] = _build_oauth1_header(
                request,
                self.consumer_key,
                self.consumer_secret,
            )
        yield request


class WooCommerceClient:
    """HTTPX client for the WooCommerce REST API."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self._owns_client = client is None
        self.client = client or httpx.Client(
            auth=_WooCommerceAuth(
                settings.woocommerce_consumer_key,
                settings.woocommerce_consumer_secret,
            ),
            timeout=settings.woocommerce_timeout_seconds,
            headers={"Accept": "application/json"},
            follow_redirects=False,
        )

    def __enter__(self) -> "WooCommerceClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _validated_config(self) -> tuple[str, str]:
        store_url = self.settings.woocommerce_store_url.strip()
        consumer_key = self.settings.woocommerce_consumer_key.strip()
        consumer_secret = self.settings.woocommerce_consumer_secret.strip()

        if not store_url:
            raise WooCommerceAPIError(
                "Missing store URL. Set WOOCOMMERCE_STORE_URL.",
                status_code=400,
            )
        if not consumer_key:
            raise WooCommerceAPIError(
                "Missing Consumer Key. Set WOOCOMMERCE_CONSUMER_KEY.",
                status_code=400,
            )
        if not consumer_secret:
            raise WooCommerceAPIError(
                "Missing Consumer Secret. Set WOOCOMMERCE_CONSUMER_SECRET.",
                status_code=400,
            )

        url_error = validate_store_url(store_url)
        if url_error:
            raise WooCommerceAPIError(url_error, status_code=400)

        version = self.settings.woocommerce_api_version.strip() or "wc/v3"
        if not _API_VERSION.fullmatch(version):
            raise WooCommerceAPIError(
                "Incorrect WooCommerce API version. Use a value such as wc/v3.",
                status_code=400,
            )

        timeout = self.settings.woocommerce_timeout_seconds
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise WooCommerceAPIError(
                "Request timeout configuration is invalid.",
                status_code=400,
            )

        return store_url, version

    def request_json(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, object] | None = None,
        json_body: dict[str, object] | None = None,
        data: dict[str, object] | None = None,
        files: dict[str, object] | None = None,
    ) -> tuple[object, int]:
        """Send an authenticated request to a WooCommerce endpoint and return parsed JSON and status."""
        store_url, version = self._validated_config()
        url = f"{api_root(store_url, version)}/{endpoint.lstrip('/')}"
        try:
            response = self.client.request(
                method,
                url,
                params=params,
                json=json_body,
                data=data,
                files=files,
            )
        except httpx.TimeoutException as exc:
            raise WooCommerceAPIError(
                "The request to the WooCommerce store timed out.",
                status_code=504,
            ) from exc
        except httpx.RequestError as exc:
            raise WooCommerceAPIError(
                "Could not connect to the WooCommerce store.",
                status_code=502,
            ) from exc

        _raise_for_http_error(response)

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise WooCommerceAPIError(
                "The WooCommerce API returned invalid JSON.",
                status_code=502,
                upstream_status=response.status_code,
            ) from exc

        return payload, response.status_code

    def fetch_paginated(
        self,
        endpoint: str,
        *,
        params: dict[str, object] | None = None,
        page: int | None = None,
        per_page: int = 100,
    ) -> tuple[list[object], int]:
        """Retrieve a single page or all pages in batches of `per_page`."""
        base_params = dict(params or {})
        if page is not None:
            payload, status_code = self.request_json(
                "GET",
                endpoint,
                params={**base_params, "per_page": per_page, "page": page},
            )
            if not isinstance(payload, list):
                raise WooCommerceAPIError(
                    "The WooCommerce API returned an unexpected response format.",
                    status_code=502,
                    upstream_status=status_code,
                )
            return payload, status_code

        items: list[object] = []
        current_page = 1
        last_status = 200

        while True:
            payload, last_status = self.request_json(
                "GET",
                endpoint,
                params={**base_params, "per_page": per_page, "page": current_page},
            )
            if not isinstance(payload, list):
                raise WooCommerceAPIError(
                    "The WooCommerce API returned an unexpected response format.",
                    status_code=502,
                    upstream_status=last_status,
                )

            items.extend(payload)
            if len(payload) < per_page:
                break
            current_page += 1

        return items, last_status

    def verify_connection(self) -> ConnectionStatus:
        store_url = self.settings.woocommerce_store_url.strip()
        try:
            payload, status_code = self.request_json(
                "GET",
                "products",
                params={"per_page": 1},
            )
        except WooCommerceAPIError as exc:
            return _failure(exc.message, store_url, exc.upstream_status)

        if not isinstance(payload, list):
            return _failure(
                "The WooCommerce API returned an unexpected response format.",
                store_url,
                status_code,
            )

        return ConnectionStatus(
            success=True,
            message="Authenticated WooCommerce API connection succeeded.",
            store_url=store_url,
            status_code=status_code,
        )


def api_root(store_url: str, api_version: str) -> str:
    parsed = urlparse(store_url.strip())
    version = api_version.strip().strip("/")
    path = unquote(parsed.path).rstrip("/")
    marker = f"/wp-json/{version}"
    index = path.find(marker)
    if index != -1 and _marker_is_api_root(path, index, marker):
        new_path = path[: index + len(marker)]
    elif path == "/wp-json" or path.endswith("/wp-json"):
        new_path = f"{path}/{version}"
    else:
        new_path = f"{path}{marker}" if path else marker
    return urlunparse(parsed._replace(path=new_path, params="", query="", fragment=""))


def validate_store_url(store_url: str) -> str | None:
    candidate = store_url.strip()
    if not candidate or any(character.isspace() for character in candidate) or "\\" in candidate:
        return _invalid_url_message()

    try:
        parsed = urlparse(candidate)
    except ValueError:
        return _invalid_url_message()
    if parsed.scheme == "http":
        if (parsed.hostname or "").lower() not in _LOCAL_LOOPBACK_HOSTS:
            return (
                "Incorrect store URL. Use HTTPS so API credentials are not sent in clear text."
            )
    elif parsed.scheme != "https":
        return _invalid_url_message()
    if parsed.username is not None or parsed.password is not None:
        return _invalid_url_message()
    if parsed.query or parsed.fragment or parsed.params:
        return _invalid_url_message()

    try:
        port = parsed.port
    except ValueError:
        return _invalid_url_message()
    if port is not None and not 1 <= port <= 65535:
        return _invalid_url_message()

    hostname = parsed.hostname
    if hostname is None or not _valid_hostname(hostname):
        return _invalid_url_message()

    path = unquote(parsed.path)
    if any(part == ".." for part in path.split("/")):
        return _invalid_url_message()
    return None


def _extract_upstream_error_info(response: httpx.Response) -> tuple[str | None, str | None]:
    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError):
        return None, None
    if not isinstance(payload, dict):
        return None, None
    code = payload.get("code")
    message = payload.get("message")
    return (
        str(code) if isinstance(code, str) else None,
        str(message) if isinstance(message, str) else None,
    )


def _raise_for_http_error(response: httpx.Response) -> None:
    status_code = response.status_code
    if status_code in (400, 409, 413, 422):
        upstream_code, upstream_message = _extract_upstream_error_info(response)
        raise WooCommerceAPIError(
            "The WooCommerce API rejected the request.",
            status_code=status_code,
            upstream_status=status_code,
            upstream_code=upstream_code,
            upstream_message=upstream_message,
        )
    if status_code == 401:
        raise WooCommerceAPIError("Invalid API credentials.", status_code=401, upstream_status=status_code)
    if status_code == 403:
        raise WooCommerceAPIError("Insufficient API permissions.", status_code=403, upstream_status=status_code)
    if status_code == 404:
        upstream_code, upstream_message = _extract_upstream_error_info(response)
        raise WooCommerceAPIError(
            "The WooCommerce API endpoint was not found.",
            status_code=404,
            upstream_status=status_code,
            upstream_code=upstream_code,
            upstream_message=upstream_message,
        )
    if status_code >= 500:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected server error.",
            status_code=502,
            upstream_status=status_code,
        )
    if not 200 <= status_code < 300:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected HTTP response.",
            status_code=502,
            upstream_status=status_code,
        )


def _marker_is_api_root(path: str, index: int, marker: str) -> bool:
    remainder = path[index + len(marker) :]
    return remainder == "" or remainder.startswith("/")


def _valid_hostname(hostname: str) -> bool:
    if hostname.endswith("."):
        hostname = hostname[:-1]
    if not hostname or len(hostname) > 253:
        return False
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        pass
    labels = hostname.split(".")
    if len(labels) == 4 and all(label.isdigit() for label in labels):
        return False
    return all(_HOSTNAME_LABEL.fullmatch(label) is not None for label in labels)


def _invalid_url_message() -> str:
    return (
        "Incorrect store URL. The URL is malformed or uses an unsupported "
        "hostname or component."
    )


def _failure(
    message: str,
    store_url: str,
    status_code: int | None = None,
) -> ConnectionStatus:
    return ConnectionStatus(
        success=False,
        message=message,
        store_url=store_url,
        status_code=status_code,
    )


def _oauth_percent_encode(value: object) -> str:
    return quote(str(value), safe="~")


def _build_oauth1_header(
    request: httpx.Request,
    consumer_key: str,
    consumer_secret: str,
) -> str:
    oauth_params = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA256",
        "oauth_timestamp": str(int(time.time())),
        "oauth_version": "1.0",
    }

    host = request.url.host.lower()
    port = request.url.port
    default_port = 80 if request.url.scheme == "http" else 443
    netloc = host if port is None or port == default_port else f"{host}:{port}"
    base_uri = f"{request.url.scheme}://{netloc}{request.url.path}"

    all_params: list[tuple[str, str]] = list(request.url.params.multi_items())
    all_params.extend(oauth_params.items())
    encoded_params = sorted(
        (_oauth_percent_encode(k), _oauth_percent_encode(v)) for k, v in all_params
    )
    param_string = "&".join(f"{k}={v}" for k, v in encoded_params)

    base_string = "&".join(
        [
            request.method.upper(),
            _oauth_percent_encode(base_uri),
            _oauth_percent_encode(param_string),
        ]
    )
    signing_key = f"{_oauth_percent_encode(consumer_secret)}&"
    digest = hmac.new(
        signing_key.encode("ascii"),
        base_string.encode("ascii"),
        hashlib.sha256,
    ).digest()
    oauth_params["oauth_signature"] = base64.b64encode(digest).decode("ascii")

    header_parts = ", ".join(
        f'{k}="{_oauth_percent_encode(v)}"' for k, v in sorted(oauth_params.items())
    )
    return f"OAuth {header_parts}"
