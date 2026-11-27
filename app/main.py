from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import (
    orders,
    product_attribute_terms,
    product_attributes,
    product_variations,
    products,
)
from app.services.woocommerce import (
    ConnectionStatus,
    WooCommerceAPIError,
    WooCommerceClient,
)

app = FastAPI(title="WooCommerce Store Integration")
app.include_router(product_attribute_terms.router)
app.include_router(product_attributes.router)
app.include_router(product_variations.router)
app.include_router(products.router)
app.include_router(orders.router)


@app.exception_handler(WooCommerceAPIError)
def woocommerce_api_error_handler(
    request: Request,
    exc: WooCommerceAPIError,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message,
            "upstream_status": exc.upstream_status,
        },
    )


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "WooCommerce store integration",
        "connection_check": "/connection",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get(
    "/connection",
    response_model=ConnectionStatus,
    summary="Verify the WooCommerce store connection",
)
def connection() -> ConnectionStatus:
    with WooCommerceClient(get_settings()) as client:
        return client.verify_connection()
