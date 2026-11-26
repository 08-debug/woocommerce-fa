from pydantic import ValidationError

from app.schemas.order import Order, OrderStatus
from app.services.woocommerce import WooCommerceAPIError, WooCommerceClient

_DRAFT_STATUSES = {"draft", "checkout-draft", "auto-draft"}


def list_orders(
    client: WooCommerceClient,
    order_status: OrderStatus | None = None,
    *,
    page: int | None = None,
    per_page: int = 100,
) -> list[Order]:
    """Retrieve WooCommerce orders in batches, optionally filtered by order status."""
    woo_status = "any" if order_status in (None, "draft") else order_status
    raw_items, status_code = client.fetch_paginated(
        "orders",
        params={"status": woo_status},
        page=page,
        per_page=per_page,
    )

    orders: list[Order] = []
    for item in raw_items:
        try:
            orders.append(Order.model_validate(item))
        except ValidationError as exc:
            raise WooCommerceAPIError(
                "The WooCommerce API returned an unexpected order format.",
                status_code=502,
                upstream_status=status_code,
            ) from exc

    if order_status == "draft":
        return [o for o in orders if o.order_status in {"draft", "checkout-draft"}]
    if order_status is not None:
        return [o for o in orders if o.order_status == order_status]
    return orders


def list_placed_orders(
    client: WooCommerceClient,
    *,
    page: int | None = None,
    per_page: int = 100,
) -> list[Order]:
    """Retrieve all placed WooCommerce orders in batches (excluding draft orders)."""
    return [
        order
        for order in list_orders(client, page=page, per_page=per_page)
        if order.order_status not in _DRAFT_STATUSES
    ]
