from fastapi import FastAPI

from app.config import get_settings
from app.routers import orders, products
from app.services.woocommerce import ConnectionStatus, WooCommerceClient

app = FastAPI(title="WooCommerce Store Integration")
app.include_router(products.router)
app.include_router(orders.router)


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
