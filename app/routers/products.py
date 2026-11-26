from fastapi import APIRouter, HTTPException, status

from app.config import get_settings
from app.schemas.product import Product, ProductCreate
from app.services.product_service import create_product, list_published_products
from app.services.woocommerce import WooCommerceAPIError, WooCommerceClient

router = APIRouter(prefix="/products", tags=["products"])


@router.get(
    "",
    response_model=list[Product],
    summary="Retrieve all published products",
)
def get_products() -> list[Product]:
    try:
        with WooCommerceClient(get_settings()) as client:
            return list_published_products(client)
    except WooCommerceAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post(
    "",
    response_model=Product,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product",
)
def post_product(payload: ProductCreate) -> Product:
    try:
        with WooCommerceClient(get_settings()) as client:
            return create_product(client, payload)
    except WooCommerceAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
