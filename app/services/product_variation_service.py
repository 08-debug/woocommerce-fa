from typing import Literal

from pydantic import ValidationError

from app.schemas.product_variation import (
    ProductVariationBatchRequest,
    ProductVariationBatchResponse,
    ProductVariationCreate,
    ProductVariationResponse,
    ProductVariationUpdate,
    VariationListQueryParams,
)
from app.services.woocommerce import WooCommerceAPIError, WooCommerceClient


def _validate_positive_id(value: int, label: str) -> None:
    if isinstance(value, bool) or value < 1:
        raise WooCommerceAPIError(
            f"Invalid {label}. {label} must be a positive integer.",
            status_code=422,
        )


def _map_variation_error(
    exc: WooCommerceAPIError,
    *,
    has_variation_id: bool = False,
) -> WooCommerceAPIError:
    if exc.upstream_status == 404:
        return WooCommerceAPIError(
            "Parent product or variation not found."
            if has_variation_id
            else "Parent product not found.",
            status_code=404,
            upstream_status=404,
            upstream_code=exc.upstream_code,
        )
    if exc.upstream_status in (400, 409, 422):
        detail = exc.upstream_message or "The WooCommerce product variation request was rejected."
        if exc.upstream_code:
            detail = f"{detail} ({exc.upstream_code})"
        return WooCommerceAPIError(
            detail,
            status_code=400 if exc.upstream_status == 400 else exc.upstream_status,
            upstream_status=exc.upstream_status,
            upstream_code=exc.upstream_code,
        )
    return exc


def _parse_variation(payload: object, status_code: int) -> ProductVariationResponse:
    if not isinstance(payload, dict) or "code" in payload:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected response format.",
            status_code=502,
            upstream_status=status_code,
        )
    try:
        return ProductVariationResponse.model_validate(payload)
    except ValidationError as exc:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected product variation format.",
            status_code=502,
            upstream_status=status_code,
        ) from exc


def create_product_variation(
    client: WooCommerceClient,
    product_id: int,
    payload: ProductVariationCreate,
) -> ProductVariationResponse:
    """Create a variation for a parent variable product."""
    _validate_positive_id(product_id, "product ID")
    try:
        response_payload, status_code = client.request_json(
            "POST",
            f"products/{product_id}/variations",
            json_body=payload.model_dump(mode="json", exclude_none=True),
        )
    except WooCommerceAPIError as exc:
        raise _map_variation_error(exc) from exc
    return _parse_variation(response_payload, status_code)


def get_product_variation(
    client: WooCommerceClient,
    product_id: int,
    variation_id: int,
    *,
    context: Literal["view", "edit"] = "view",
) -> ProductVariationResponse:
    """Retrieve a specific variation for a parent product."""
    _validate_positive_id(product_id, "product ID")
    _validate_positive_id(variation_id, "variation ID")
    try:
        response_payload, status_code = client.request_json(
            "GET",
            f"products/{product_id}/variations/{variation_id}",
            params={"context": context},
        )
    except WooCommerceAPIError as exc:
        raise _map_variation_error(exc, has_variation_id=True) from exc
    return _parse_variation(response_payload, status_code)


def list_product_variations(
    client: WooCommerceClient,
    product_id: int,
    query: VariationListQueryParams,
) -> list[ProductVariationResponse]:
    """List variations for a parent product with documented query parameters."""
    _validate_positive_id(product_id, "product ID")
    try:
        response_payload, status_code = client.request_json(
            "GET",
            f"products/{product_id}/variations",
            params=query.to_woo_params(),
        )
    except WooCommerceAPIError as exc:
        raise _map_variation_error(exc) from exc

    if not isinstance(response_payload, list):
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected response format.",
            status_code=502,
            upstream_status=status_code,
        )
    return [_parse_variation(item, status_code) for item in response_payload]


def update_product_variation(
    client: WooCommerceClient,
    product_id: int,
    variation_id: int,
    payload: ProductVariationUpdate,
) -> ProductVariationResponse:
    """Update a specific variation for a parent product."""
    _validate_positive_id(product_id, "product ID")
    _validate_positive_id(variation_id, "variation ID")
    try:
        response_payload, status_code = client.request_json(
            "PUT",
            f"products/{product_id}/variations/{variation_id}",
            json_body=payload.model_dump(mode="json", exclude_none=True),
        )
    except WooCommerceAPIError as exc:
        raise _map_variation_error(exc, has_variation_id=True) from exc
    return _parse_variation(response_payload, status_code)


def delete_product_variation(
    client: WooCommerceClient,
    product_id: int,
    variation_id: int,
    *,
    force: bool = False,
) -> ProductVariationResponse:
    """Delete a product variation (requires force=true)."""
    _validate_positive_id(product_id, "product ID")
    _validate_positive_id(variation_id, "variation ID")
    if not force:
        raise WooCommerceAPIError(
            "Deleting a product variation requires 'force=true'.",
            status_code=400,
        )
    try:
        response_payload, status_code = client.request_json(
            "DELETE",
            f"products/{product_id}/variations/{variation_id}",
            params={"force": "true"},
        )
    except WooCommerceAPIError as exc:
        raise _map_variation_error(exc, has_variation_id=True) from exc
    return _parse_variation(response_payload, status_code)


def batch_product_variations(
    client: WooCommerceClient,
    product_id: int,
    payload: ProductVariationBatchRequest,
) -> ProductVariationBatchResponse:
    """Batch create, update, and delete variations for a parent product."""
    _validate_positive_id(product_id, "product ID")
    body: dict[str, object] = {}
    if payload.create:
        body["create"] = [item.model_dump(mode="json", exclude_none=True) for item in payload.create]
    if payload.update:
        body["update"] = [item.model_dump(mode="json", exclude_none=True) for item in payload.update]
    if payload.delete:
        body["delete"] = payload.delete

    try:
        response_payload, status_code = client.request_json(
            "POST",
            f"products/{product_id}/variations/batch",
            json_body=body,
        )
    except WooCommerceAPIError as exc:
        raise _map_variation_error(exc) from exc

    if not isinstance(response_payload, dict) or "code" in response_payload:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected response format.",
            status_code=502,
            upstream_status=status_code,
        )
    try:
        return ProductVariationBatchResponse.model_validate(response_payload)
    except ValidationError as exc:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected batch variation format.",
            status_code=502,
            upstream_status=status_code,
        ) from exc
