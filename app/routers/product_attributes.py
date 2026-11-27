from typing import Literal

from fastapi import APIRouter, Path, Query, status

from app.config import get_settings
from app.schemas.product_attribute import (
    ProductAttributeBatchRequest,
    ProductAttributeBatchResponse,
    ProductAttributeCreate,
    ProductAttributeResponse,
    ProductAttributeUpdate,
)
from app.services.product_attribute_service import (
    batch_product_attributes,
    create_product_attribute,
    delete_product_attribute,
    get_product_attribute,
    list_product_attributes,
    update_product_attribute,
)
from app.services.woocommerce import WooCommerceClient

router = APIRouter(prefix="/products/attributes", tags=["Product Attributes"])


@router.post(
    "",
    response_model=ProductAttributeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product attribute",
)
def post_product_attribute(payload: ProductAttributeCreate) -> ProductAttributeResponse:
    with WooCommerceClient(get_settings()) as client:
        return create_product_attribute(client, payload)


@router.get(
    "",
    response_model=list[ProductAttributeResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve all product attributes",
)
def get_product_attributes(
    context: Literal["view", "edit"] = Query(default="view", description="Response context"),
    slug: list[str] | None = Query(default=None, description="Filter by attribute slug(s)"),
) -> list[ProductAttributeResponse]:
    with WooCommerceClient(get_settings()) as client:
        return list_product_attributes(client, context=context, slug=slug)


@router.post(
    "/batch",
    response_model=ProductAttributeBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch create, update, and delete product attributes",
)
def post_batch_product_attributes(
    payload: ProductAttributeBatchRequest,
) -> ProductAttributeBatchResponse:
    with WooCommerceClient(get_settings()) as client:
        return batch_product_attributes(client, payload)


@router.get(
    "/{attribute_id}",
    response_model=ProductAttributeResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a product attribute by ID",
)
def get_single_product_attribute(
    attribute_id: int = Path(..., ge=1, description="WooCommerce attribute ID"),
    context: Literal["view", "edit"] = Query(default="view", description="Response context"),
) -> ProductAttributeResponse:
    with WooCommerceClient(get_settings()) as client:
        return get_product_attribute(client, attribute_id, context=context)


@router.put(
    "/{attribute_id}",
    response_model=ProductAttributeResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a product attribute",
)
def put_product_attribute(
    payload: ProductAttributeUpdate,
    attribute_id: int = Path(..., ge=1, description="WooCommerce attribute ID"),
) -> ProductAttributeResponse:
    with WooCommerceClient(get_settings()) as client:
        return update_product_attribute(client, attribute_id, payload)


@router.delete(
    "/{attribute_id}",
    response_model=ProductAttributeResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a product attribute",
)
def remove_product_attribute(
    attribute_id: int = Path(..., ge=1, description="WooCommerce attribute ID"),
    force: bool = Query(default=False, description="Must be true to delete the attribute"),
) -> ProductAttributeResponse:
    with WooCommerceClient(get_settings()) as client:
        return delete_product_attribute(client, attribute_id, force=force)
