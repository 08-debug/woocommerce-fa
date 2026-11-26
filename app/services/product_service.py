from pydantic import ValidationError

from app.schemas.product import Product, ProductCreate
from app.services.woocommerce import WooCommerceAPIError, WooCommerceClient


def list_published_products(client: WooCommerceClient) -> list[Product]:
    """Retrieve all published products from WooCommerce and validate against Product schema."""
    raw_items, status_code = client.fetch_paginated(
        "products",
        params={"status": "publish"},
    )
    products: list[Product] = []
    for item in raw_items:
        try:
            products.append(Product.model_validate(item))
        except ValidationError as exc:
            raise WooCommerceAPIError(
                "The WooCommerce API returned an unexpected product format.",
                status_code=502,
                upstream_status=status_code,
            ) from exc
    return products


def create_product(client: WooCommerceClient, product_in: ProductCreate) -> Product:
    """Create a product in WooCommerce and validate the response against Product schema."""
    payload, status_code = client.request_json(
        "POST",
        "products",
        json_body=product_in.model_dump(exclude_none=True),
    )
    if not isinstance(payload, dict):
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected response format.",
            status_code=502,
            upstream_status=status_code,
        )

    try:
        return Product.model_validate(payload)
    except ValidationError as exc:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected product format.",
            status_code=502,
            upstream_status=status_code,
        ) from exc
