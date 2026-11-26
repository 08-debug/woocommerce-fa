from fastapi import APIRouter, Query

from app.config import get_settings
from app.schemas.order import Order, OrderStatus
from app.services.order_service import list_orders, list_placed_orders
from app.services.woocommerce import WooCommerceClient

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
    with WooCommerceClient(get_settings()) as client:
        return list_orders(client, order_status=status)


@router.get(
    "/placed",
    response_model=list[Order],
    summary="Retrieve all placed orders",
)
def get_placed_orders() -> list[Order]:
    with WooCommerceClient(get_settings()) as client:
        return list_placed_orders(client)
