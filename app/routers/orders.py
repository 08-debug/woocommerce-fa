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


@router.get(
    "/paginated",
    response_model=list[Order],
    summary="Retrieve orders with pagination",
)
def get_orders_paginated(
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(default=10, ge=1, le=100, description="Orders per page (default 10)"),
) -> list[Order]:
    with WooCommerceClient(get_settings()) as client:
        return list_orders(client, page=page, per_page=per_page)
