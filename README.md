# WooCommerce Store Integration

FastAPI application that connects to a WooCommerce store using the WooCommerce REST API and HTTPX. It supports store connection verification, product retrieval and creation, product search/filtering, order retrieval and status filtering, centralized error handling, and paginated batch endpoints.

## Installation

Python 3.11 or newer is required. From the project root:

```bash
uv venv
uv pip install -r requirements.txt
copy .env.example .env
```

On macOS or Linux, use `cp .env.example .env`.

## Environment

Put your store credentials in `.env`. `.env` is gitignored and must not be committed.

| Variable | Required | Purpose |
| --- | --- | --- |
| `WOOCOMMERCE_STORE_URL` | Yes | Store origin, such as `https://store.example.com` (or `http://localhost:8080` for local development). Subdirectory installs and explicit `/wp-json/wc/v3` roots are also supported. |
| `WOOCOMMERCE_CONSUMER_KEY` | Yes | WooCommerce REST API consumer key |
| `WOOCOMMERCE_CONSUMER_SECRET` | Yes | WooCommerce REST API consumer secret |
| `WOOCOMMERCE_API_VERSION` | No | Defaults to `wc/v3` when empty |
| `WOOCOMMERCE_TIMEOUT_SECONDS` | No | Defaults to `15` when empty |

Create the REST API key in WooCommerce under **Settings → Advanced → REST API**. Remote stores must use `https://` (HTTP Basic Auth). Local loopback URLs (`localhost`, `127.0.0.1`, `::1`) over `http://` are signed with OAuth 1.0a (`HMAC-SHA256`). Credentials are never placed in the query string or exposed in error messages.

## Start the Application

```bash
uv run uvicorn app.main:app --reload
```

If port `8000` is reserved or blocked on Windows (`WinError 10013`), specify another port such as `8001`:

```bash
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001
```

- **Swagger UI (interactive):** `http://127.0.0.1:8001/docs`
- **ReDoc (read-only docs):** `http://127.0.0.1:8001/redoc`

## API Endpoints

### Task 1 — Store Connection
- `GET /connection`: Verifies store URL, credentials, HTTP status, and JSON response shape without returning product or order data.

### Task 2 — Products
- `GET /products`: Retrieves all published products (`id`, `name`, `sku`, `regular_price`, `sale_price`, `stock_quantity`, `stock_status`).
- `POST /products`: Validates input with `ProductCreate` and creates a product in WooCommerce.

### Task 3 — Search & Filter Products
- `GET /products/search`: Search published products by:
  - `name` (partial, case-insensitive)
  - `sku` (partial or exact, case-insensitive)
  - `min_price` / `max_price` (uses effective price: `sale_price` if set, otherwise `regular_price`)

### Task 4 — Orders
- `GET /orders`: Retrieves orders (`order_id`, `customer_name`, `customer_email`, `order_date`, `order_status`, `product_names`, `total_order_amount`) with optional `status` filter (`pending`, `processing`, `on-hold`, `completed`, `cancelled`, `refunded`, `failed`, `draft`).
- `GET /orders/placed`: Retrieves all placed orders (excluding draft orders).

### Task 5 — Error Handling
All endpoints validate inputs via Pydantic schemas and handle:
- Missing or invalid store URL / credentials (`400`, `401`, `403`)
- Endpoint not found (`404`)
- Network connection failures & invalid JSON/schema responses (`502`)
- Request timeouts (`504`)
- Empty product or order collections (`200` with `[]`)

### Task 6 — Pagination
- `GET /products/paginated?page=1&per_page=10`: Retrieves published products in pages (default `page=1`, `per_page=10`, max `100`).
- `GET /orders/paginated?page=1&per_page=10`: Retrieves orders in pages (default `page=1`, `per_page=10`, max `100`).

## Tests

The test suite uses `pytest` with mocked HTTPX responses and does not call a live WooCommerce store:

```bash
.venv\Scripts\python.exe -m pytest -v
```
