from typing import Literal

from pydantic import ValidationError

from app.schemas.product_review import (
    ProductReviewBatchRequest,
    ProductReviewBatchResponse,
    ProductReviewCreate,
    ProductReviewDeleteResponse,
    ProductReviewResponse,
    ProductReviewUpdate,
    ReviewListQueryParams,
)
from app.services.woocommerce import WooCommerceAPIError, WooCommerceClient


def _validate_positive_id(value: int, label: str) -> None:
    if isinstance(value, bool) or value < 1:
        raise WooCommerceAPIError(
            f"Invalid {label}. {label} must be a positive integer.",
            status_code=422,
        )


def _map_review_error(exc: WooCommerceAPIError) -> WooCommerceAPIError:
    if exc.upstream_status == 404:
        return WooCommerceAPIError(
            "Product review not found.",
            status_code=404,
            upstream_status=404,
            upstream_code=exc.upstream_code,
        )
    if exc.upstream_status in (400, 409, 422):
        detail = exc.upstream_message or "The WooCommerce product review request was rejected."
        if exc.upstream_code:
            detail = f"{detail} ({exc.upstream_code})"
        return WooCommerceAPIError(
            detail,
            status_code=400 if exc.upstream_status == 400 else exc.upstream_status,
            upstream_status=exc.upstream_status,
            upstream_code=exc.upstream_code,
        )
    return exc


def _parse_review(payload: object, status_code: int) -> ProductReviewResponse:
    if not isinstance(payload, dict) or "code" in payload:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected response format.",
            status_code=502,
            upstream_status=status_code,
        )
    try:
        return ProductReviewResponse.model_validate(payload)
    except ValidationError as exc:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected product review format.",
            status_code=502,
            upstream_status=status_code,
        ) from exc


def create_product_review(
    client: WooCommerceClient,
    payload: ProductReviewCreate,
) -> ProductReviewResponse:
    """Create a product review in WooCommerce."""
    try:
        response_payload, status_code = client.request_json(
            "POST",
            "products/reviews",
            json_body=payload.model_dump(exclude_none=True),
        )
    except WooCommerceAPIError as exc:
        raise _map_review_error(exc) from exc
    return _parse_review(response_payload, status_code)


def get_product_review(
    client: WooCommerceClient,
    review_id: int,
    *,
    context: Literal["view", "edit"] = "view",
) -> ProductReviewResponse:
    """Retrieve a product review by ID."""
    _validate_positive_id(review_id, "review ID")
    try:
        response_payload, status_code = client.request_json(
            "GET",
            f"products/reviews/{review_id}",
            params={"context": context},
        )
    except WooCommerceAPIError as exc:
        raise _map_review_error(exc) from exc
    return _parse_review(response_payload, status_code)


def list_product_reviews(
    client: WooCommerceClient,
    query: ReviewListQueryParams | None = None,
) -> list[ProductReviewResponse]:
    """List all product reviews."""
    try:
        if query is None:
            raw_items, status_code = client.fetch_paginated("products/reviews")
            return [_parse_review(item, status_code) for item in raw_items]
        response_payload, status_code = client.request_json(
            "GET",
            "products/reviews",
            params=query.to_woo_params(),
        )
    except WooCommerceAPIError as exc:
        raise _map_review_error(exc) from exc

    if not isinstance(response_payload, list):
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected response format.",
            status_code=502,
            upstream_status=status_code,
        )
    return [_parse_review(item, status_code) for item in response_payload]


def update_product_review(
    client: WooCommerceClient,
    review_id: int,
    payload: ProductReviewUpdate,
) -> ProductReviewResponse:
    """Update a product review by ID."""
    _validate_positive_id(review_id, "review ID")
    try:
        response_payload, status_code = client.request_json(
            "PUT",
            f"products/reviews/{review_id}",
            json_body=payload.model_dump(exclude_none=True),
        )
    except WooCommerceAPIError as exc:
        raise _map_review_error(exc) from exc
    return _parse_review(response_payload, status_code)


def delete_product_review(
    client: WooCommerceClient,
    review_id: int,
    *,
    force: bool = False,
) -> ProductReviewDeleteResponse:
    """Delete a product review by ID (requires force=true)."""
    _validate_positive_id(review_id, "review ID")
    if not force:
        raise WooCommerceAPIError(
            "Deleting a product review requires 'force=true'.",
            status_code=400,
        )
    try:
        response_payload, status_code = client.request_json(
            "DELETE",
            f"products/reviews/{review_id}",
            params={"force": "true"},
        )
    except WooCommerceAPIError as exc:
        raise _map_review_error(exc) from exc

    if not isinstance(response_payload, dict) or "code" in response_payload:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected response format.",
            status_code=502,
            upstream_status=status_code,
        )
    try:
        return ProductReviewDeleteResponse.model_validate(response_payload)
    except ValidationError as exc:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected product review delete format.",
            status_code=502,
            upstream_status=status_code,
        ) from exc


def batch_product_reviews(
    client: WooCommerceClient,
    payload: ProductReviewBatchRequest,
) -> ProductReviewBatchResponse:
    """Batch create, update, and delete product reviews."""
    body: dict[str, object] = {}
    if payload.create:
        body["create"] = [item.model_dump(exclude_none=True) for item in payload.create]
    if payload.update:
        body["update"] = [item.model_dump(exclude_none=True) for item in payload.update]
    if payload.delete:
        body["delete"] = payload.delete

    try:
        response_payload, status_code = client.request_json(
            "POST",
            "products/reviews/batch",
            json_body=body,
        )
    except WooCommerceAPIError as exc:
        raise _map_review_error(exc) from exc

    if not isinstance(response_payload, dict) or "code" in response_payload:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected response format.",
            status_code=502,
            upstream_status=status_code,
        )
    try:
        return ProductReviewBatchResponse.model_validate(response_payload)
    except ValidationError as exc:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected batch review format.",
            status_code=502,
            upstream_status=status_code,
        ) from exc
