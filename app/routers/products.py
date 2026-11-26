from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import ValidationError

from app.config import get_settings
from app.schemas.product import (
    Product,
    ProductCreate,
    ProductSearchParams,
)
from app.services.product_service import (
    create_product,
    list_published_products,
    search_products,
)
from app.services.woocommerce import WooCommerceClient

router = APIRouter(prefix="/products", tags=["products"])


@router.get(
    "",
    response_model=list[Product],
    summary="Retrieve all published products",
)
def get_products() -> list[Product]:
    with WooCommerceClient(get_settings()) as client:
        return list_published_products(client)


@router.get(
    "/search",
    response_model=list[Product],
    summary="Search products by name, partial SKU, or price range",
)
def get_products_search(
    name: str | None = Query(default=None, description="Product name to search for"),
    sku: str | None = Query(default=None, description="Partial or exact product SKU"),
    min_price: Decimal | None = Query(default=None, description="Minimum price"),
    max_price: Decimal | None = Query(default=None, description="Maximum price"),
) -> list[Product]:
    try:
        search_params = ProductSearchParams(
            name=name,
            sku=sku,
            min_price=min_price,
            max_price=max_price,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors()[0]["msg"],
        ) from exc

    with WooCommerceClient(get_settings()) as client:
        return search_products(client, search_params)


@router.post(
    "",
    response_model=Product,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product",
)
def post_product(payload: ProductCreate) -> Product:
    with WooCommerceClient(get_settings()) as client:
        return create_product(client, payload)
