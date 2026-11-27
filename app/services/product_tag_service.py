from typing import Literal

from pydantic import ValidationError

from app.schemas.product_tag import (
    ProductTagBatchRequest,
    ProductTagBatchResponse,
    ProductTagCreate,
    ProductTagResponse,
    ProductTagUpdate,
    TagListQueryParams,
)
from app.services.woocommerce import WooCommerceAPIError, WooCommerceClient


def _validate_positive_id(value: int, label: str) -> None:
    if isinstance(value, bool) or value < 1:
        raise WooCommerceAPIError(
            f"Invalid {label}. {label} must be a positive integer.",
            status_code=422,
        )


def _map_tag_error(exc: WooCommerceAPIError) -> WooCommerceAPIError:
    if exc.upstream_status == 404:
        return WooCommerceAPIError(
            "Product tag not found.",
            status_code=404,
            upstream_status=404,
            upstream_code=exc.upstream_code,
        )
    if exc.upstream_status in (400, 409, 422):
        detail = exc.upstream_message or "The WooCommerce product tag request was rejected."
        if exc.upstream_code:
            detail = f"{detail} ({exc.upstream_code})"
        return WooCommerceAPIError(
            detail,
            status_code=400 if exc.upstream_status == 400 else exc.upstream_status,
            upstream_status=exc.upstream_status,
            upstream_code=exc.upstream_code,
        )
    return exc


def _parse_tag(payload: object, status_code: int) -> ProductTagResponse:
    if not isinstance(payload, dict) or "code" in payload:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected response format.",
            status_code=502,
            upstream_status=status_code,
        )
    try:
        return ProductTagResponse.model_validate(payload)
    except ValidationError as exc:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected product tag format.",
            status_code=502,
            upstream_status=status_code,
        ) from exc


def create_product_tag(
    client: WooCommerceClient,
    payload: ProductTagCreate,
) -> ProductTagResponse:
    """Create a product tag in WooCommerce."""
    try:
        response_payload, status_code = client.request_json(
            "POST",
            "products/tags",
            json_body=payload.model_dump(exclude_none=True),
        )
    except WooCommerceAPIError as exc:
        raise _map_tag_error(exc) from exc
    return _parse_tag(response_payload, status_code)


def get_product_tag(
    client: WooCommerceClient,
    tag_id: int,
    *,
    context: Literal["view", "edit"] = "view",
) -> ProductTagResponse:
    """Retrieve a product tag by ID."""
    _validate_positive_id(tag_id, "tag ID")
    try:
        response_payload, status_code = client.request_json(
            "GET",
            f"products/tags/{tag_id}",
            params={"context": context},
        )
    except WooCommerceAPIError as exc:
        raise _map_tag_error(exc) from exc
    return _parse_tag(response_payload, status_code)


def list_product_tags(
    client: WooCommerceClient,
    query: TagListQueryParams | None = None,
) -> list[ProductTagResponse]:
    """List all product tags."""
    try:
        if query is None:
            raw_items, status_code = client.fetch_paginated("products/tags")
            return [_parse_tag(item, status_code) for item in raw_items]
        response_payload, status_code = client.request_json(
            "GET",
            "products/tags",
            params=query.to_woo_params(),
        )
    except WooCommerceAPIError as exc:
        raise _map_tag_error(exc) from exc

    if not isinstance(response_payload, list):
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected response format.",
            status_code=502,
            upstream_status=status_code,
        )
    return [_parse_tag(item, status_code) for item in response_payload]


def update_product_tag(
    client: WooCommerceClient,
    tag_id: int,
    payload: ProductTagUpdate,
) -> ProductTagResponse:
    """Update a product tag by ID."""
    _validate_positive_id(tag_id, "tag ID")
    try:
        response_payload, status_code = client.request_json(
            "PUT",
            f"products/tags/{tag_id}",
            json_body=payload.model_dump(exclude_none=True),
        )
    except WooCommerceAPIError as exc:
        raise _map_tag_error(exc) from exc
    return _parse_tag(response_payload, status_code)


def delete_product_tag(
    client: WooCommerceClient,
    tag_id: int,
    *,
    force: bool = False,
) -> ProductTagResponse:
    """Delete a product tag by ID (requires force=true)."""
    _validate_positive_id(tag_id, "tag ID")
    if not force:
        raise WooCommerceAPIError(
            "Deleting a product tag requires 'force=true'.",
            status_code=400,
        )
    try:
        response_payload, status_code = client.request_json(
            "DELETE",
            f"products/tags/{tag_id}",
            params={"force": "true"},
        )
    except WooCommerceAPIError as exc:
        raise _map_tag_error(exc) from exc
    return _parse_tag(response_payload, status_code)


def batch_product_tags(
    client: WooCommerceClient,
    payload: ProductTagBatchRequest,
) -> ProductTagBatchResponse:
    """Batch create, update, and delete product tags."""
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
            "products/tags/batch",
            json_body=body,
        )
    except WooCommerceAPIError as exc:
        raise _map_tag_error(exc) from exc

    if not isinstance(response_payload, dict) or "code" in response_payload:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected response format.",
            status_code=502,
            upstream_status=status_code,
        )
    try:
        return ProductTagBatchResponse.model_validate(response_payload)
    except ValidationError as exc:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected batch tag format.",
            status_code=502,
            upstream_status=status_code,
        ) from exc
