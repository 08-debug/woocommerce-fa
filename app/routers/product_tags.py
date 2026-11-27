from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import ValidationError

from app.config import get_settings
from app.schemas.product_tag import (
    ProductTagBatchRequest,
    ProductTagBatchResponse,
    ProductTagCreate,
    ProductTagResponse,
    ProductTagUpdate,
    TagListQueryParams,
    TagOrder,
    TagOrderBy,
)
from app.services.product_tag_service import (
    batch_product_tags,
    create_product_tag,
    delete_product_tag,
    get_product_tag,
    list_product_tags,
    update_product_tag,
)
from app.services.woocommerce import WooCommerceClient

router = APIRouter(prefix="/products/tags", tags=["Product Tags"])


@router.post(
    "",
    response_model=ProductTagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product tag",
)
def post_product_tag(payload: ProductTagCreate) -> ProductTagResponse:
    with WooCommerceClient(get_settings()) as client:
        return create_product_tag(client, payload)


@router.get(
    "",
    response_model=list[ProductTagResponse],
    status_code=status.HTTP_200_OK,
    summary="List product tags",
)
def get_product_tags() -> list[ProductTagResponse]:
    with WooCommerceClient(get_settings()) as client:
        return list_product_tags(client)


@router.post(
    "/batch",
    response_model=ProductTagBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch create, update, and delete product tags",
)
def post_batch_product_tags(
    payload: ProductTagBatchRequest,
) -> ProductTagBatchResponse:
    with WooCommerceClient(get_settings()) as client:
        return batch_product_tags(client, payload)


@router.get(
    "/{tag_id}",
    response_model=ProductTagResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a product tag by ID",
)
def get_single_product_tag(
    tag_id: int = Path(..., ge=1, description="WooCommerce product tag ID"),
    context: Literal["view", "edit"] = Query(default="view"),
) -> ProductTagResponse:
    with WooCommerceClient(get_settings()) as client:
        return get_product_tag(client, tag_id, context=context)


@router.put(
    "/{tag_id}",
    response_model=ProductTagResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a product tag",
)
def put_product_tag(
    payload: ProductTagUpdate,
    tag_id: int = Path(..., ge=1, description="WooCommerce product tag ID"),
) -> ProductTagResponse:
    with WooCommerceClient(get_settings()) as client:
        return update_product_tag(client, tag_id, payload)


@router.delete(
    "/{tag_id}",
    response_model=ProductTagResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a product tag",
)
def remove_product_tag(
    tag_id: int = Path(..., ge=1, description="WooCommerce product tag ID"),
    force: bool = Query(default=False, description="Must be true to delete the product tag"),
) -> ProductTagResponse:
    with WooCommerceClient(get_settings()) as client:
        return delete_product_tag(client, tag_id, force=force)
