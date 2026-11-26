# WooCommerce Store Integration

FastAPI application that verifies a connection to a WooCommerce store. HTTPX calls the WooCommerce REST API with the consumer key and consumer secret. Task 1 is this connection check only.

## Installation

Python 3.11 or newer is required. From the project root:

```bash
uv venv
uv pip install -r requirements.txt
copy .env.example .env
```

On macOS or Linux, use `cp .env.example .env`.

## Environment

Put credentials in `.env`. `.env` is gitignored. Do not commit it.

| Variable | Required | Purpose |
| --- | --- | --- |
| `WOOCOMMERCE_STORE_URL` | Yes | Store origin, such as `https://store.example.com`. A subdirectory install such as `https://store.example.com/shop` is also valid. If the value already includes `/wp-json/wc/v3`, that API root is used as configured. |
| `WOOCOMMERCE_CONSUMER_KEY` | Yes | WooCommerce consumer key |
| `WOOCOMMERCE_CONSUMER_SECRET` | Yes | WooCommerce consumer secret |
| `WOOCOMMERCE_API_VERSION` | No | Defaults to `wc/v3` when empty |
| `WOOCOMMERCE_TIMEOUT_SECONDS` | No | Defaults to `15` when empty |

Create the key in WooCommerce under **Settings → Advanced → REST API** with Read permission. The store URL must be `https://`. The key and secret are sent with HTTP Basic authentication and are not put in the query string.

## Start the application

```bash
uv run uvicorn app.main:app --reload
```

The API listens on `http://127.0.0.1:8000`.

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- Connection check: `http://127.0.0.1:8000/connection`

## Verify the connection

`GET /connection` asks the configured API root for a single product record, checks the HTTP status and JSON shape, and returns only the connection result. It does not return product or order data.

### Success

HTTP 200 from this application:

```json
{
  "success": true,
  "message": "Authenticated WooCommerce API connection succeeded.",
  "store_url": "https://store.example.com",
  "status_code": 200
}
```

An empty product collection is still a successful connection.

### Failure

HTTP 200 from this application with `"success": false`. `status_code` is the WooCommerce status when the store responded, and `null` when the request was not sent or did not complete.

| Condition | `message` |
| --- | --- |
| Store URL is missing | `Missing store URL. Set WOOCOMMERCE_STORE_URL.` |
| Consumer key is missing | `Missing Consumer Key. Set WOOCOMMERCE_CONSUMER_KEY.` |
| Consumer secret is missing | `Missing Consumer Secret. Set WOOCOMMERCE_CONSUMER_SECRET.` |
| URL is malformed, not HTTPS, or has unexpected components | `Incorrect store URL. ...` |
| WooCommerce returns 401 | `Invalid API credentials.` |
| WooCommerce returns 403 | `Insufficient API permissions.` |
| WooCommerce returns 404 | `The WooCommerce API endpoint was not found.` |
| WooCommerce returns 500 or another server error | `The WooCommerce API returned an unexpected server error.` |
| Another unexpected HTTP status | `The WooCommerce API returned an unexpected HTTP response.` |
| Network connection failure | `Could not connect to the WooCommerce store.` |
| Timeout | `The request to the WooCommerce store timed out.` |
| Response body is not JSON | `The WooCommerce API returned invalid JSON.` |
| JSON is not a WooCommerce collection | `The WooCommerce API returned an unexpected response format.` |

Failure messages do not include the consumer key or consumer secret.

## Tests

The Task 1 suite uses mocked HTTPX responses and does not call a live store:

```bash
uv run pytest
```
