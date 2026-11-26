from decimal import Decimal, InvalidOperation

from pydantic import ValidationError

from app.schemas.product import (
    Product,
    ProductCreate,
    ProductFilterParams,
    ProductSearchParams,
)
from app.services.woocommerce import WooCommerceAPIError, WooCommerceClient


def _fetch_products(
    client: WooCommerceClient,
    base_params: dict[str, object],
    *,
    page: int | None = None,
    per_page: int = 100,
) -> list[Product]:
    """Fetch WooCommerce product batches and validate each item."""
    raw_items, status_code = client.fetch_paginated(
        "products",
        params=base_params,
        page=page,
        per_page=per_page,
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


def _effective_price(product: Product) -> Decimal | None:
    raw = product.sale_price.strip() or product.regular_price.strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _apply_product_filters(
    products: list[Product],
    filters: ProductFilterParams,
) -> list[Product]:
    filtered = products

    if filters.name is not None:
        name_needle = filters.name.lower()
        filtered = [p for p in filtered if name_needle in p.name.lower()]

    if filters.sku is not None:
        sku_needle = filters.sku.lower()
        filtered = [p for p in filtered if sku_needle in p.sku.lower()]

    if filters.min_price is not None or filters.max_price is not None:
        price_filtered: list[Product] = []
        for product in filtered:
            price = _effective_price(product)
            if price is None:
                continue
            if filters.min_price is not None and price < filters.min_price:
                continue
            if filters.max_price is not None and price > filters.max_price:
                continue
            price_filtered.append(product)
        filtered = price_filtered

    return filtered


def list_published_products(
    client: WooCommerceClient,
    filters: ProductFilterParams | None = None,
    *,
    page: int | None = None,
    per_page: int = 100,
) -> list[Product]:
    """Retrieve published products in batches with optional name, partial SKU, and price filters."""
    params: dict[str, object] = {"status": "publish"}
    if filters is not None and filters.name is not None:
        params["search"] = filters.name

    products = _fetch_products(client, params, page=page, per_page=per_page)
    if filters is not None:
        return _apply_product_filters(products, filters)
    return products


def search_products(
    client: WooCommerceClient,
    query: ProductSearchParams,
    *,
    page: int | None = None,
    per_page: int = 100,
) -> list[Product]:
    """Search published WooCommerce products by name, partial SKU, and/or price range."""
    return list_published_products(client, query, page=page, per_page=per_page)


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
