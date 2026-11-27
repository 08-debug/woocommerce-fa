from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import ValidationError

from app.config import get_settings
from app.schemas.product_review import (
    ProductReviewBatchRequest,
    ProductReviewBatchResponse,
    ProductReviewCreate,
    ProductReviewDeleteResponse,
    ProductReviewResponse,
    ProductReviewUpdate,
    ReviewListQueryParams,
    ReviewListStatus,
    ReviewOrder,
    ReviewOrderBy,
)
from app.services.product_review_service import (
    batch_product_reviews,
    create_product_review,
    delete_product_review,
    get_product_review,
    list_product_reviews,
    update_product_review,
)
from app.services.woocommerce import WooCommerceClient

router = APIRouter(prefix="/products/reviews", tags=["Product Reviews"])


@router.post(
    "",
    response_model=ProductReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product review",
)
def post_product_review(payload: ProductReviewCreate) -> ProductReviewResponse:
    with WooCommerceClient(get_settings()) as client:
        return create_product_review(client, payload)


@router.get(
    "",
    response_model=list[ProductReviewResponse],
    status_code=status.HTTP_200_OK,
    summary="List product reviews",
)
def get_product_reviews() -> list[ProductReviewResponse]:
    with WooCommerceClient(get_settings()) as client:
        return list_product_reviews(client)


@router.post(
    "/batch",
    response_model=ProductReviewBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch create, update, and delete product reviews",
)
def post_batch_product_reviews(
    payload: ProductReviewBatchRequest,
) -> ProductReviewBatchResponse:
    with WooCommerceClient(get_settings()) as client:
        return batch_product_reviews(client, payload)


@router.get(
    "/{review_id}",
    response_model=ProductReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a product review by ID",
)
def get_single_product_review(
    review_id: int = Path(..., ge=1, description="WooCommerce product review ID"),
    context: Literal["view", "edit"] = Query(default="view"),
) -> ProductReviewResponse:
    with WooCommerceClient(get_settings()) as client:
        return get_product_review(client, review_id, context=context)


@router.put(
    "/{review_id}",
    response_model=ProductReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a product review",
)
def put_product_review(
    payload: ProductReviewUpdate,
    review_id: int = Path(..., ge=1, description="WooCommerce product review ID"),
) -> ProductReviewResponse:
    with WooCommerceClient(get_settings()) as client:
        return update_product_review(client, review_id, payload)


@router.delete(
    "/{review_id}",
    response_model=ProductReviewDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a product review",
)
def remove_product_review(
    review_id: int = Path(..., ge=1, description="WooCommerce product review ID"),
    force: bool = Query(default=False, description="Must be true to delete the product review"),
) -> ProductReviewDeleteResponse:
    with WooCommerceClient(get_settings()) as client:
        return delete_product_review(client, review_id, force=force)
