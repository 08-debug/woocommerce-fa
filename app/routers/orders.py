from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.schemas.order import Order, OrderStatus
from app.services.order_service import list_orders, list_placed_orders
from app.services.woocommerce import WooCommerceAPIError, WooCommerceClient

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get(
    "",
    response_model=list[Order],
    summary="Retrieve orders with optional status filter",
)
def get_orders(
    status: OrderStatus | None = Query(
        default=None,
        description="Filter by order status (pending, processing, on-hold, completed, cancelled, refunded, failed, draft)",
    ),
) -> list[Order]:
    try:
        with WooCommerceClient(get_settings()) as client:
            return list_orders(client, order_status=status)
    except WooCommerceAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get(
    "/placed",
    response_model=list[Order],
    summary="Retrieve all placed orders",
)
def get_placed_orders() -> list[Order]:
    try:
        with WooCommerceClient(get_settings()) as client:
            return list_placed_orders(client)
    except WooCommerceAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
