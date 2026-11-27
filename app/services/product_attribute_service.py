from typing import Literal

from pydantic import ValidationError

from app.schemas.product_attribute import (
    ProductAttributeBatchRequest,
    ProductAttributeBatchResponse,
    ProductAttributeCreate,
    ProductAttributeResponse,
    ProductAttributeUpdate,
)
from app.services.woocommerce import WooCommerceAPIError, WooCommerceClient


def _validate_positive_id(value: int, label: str) -> None:
    if isinstance(value, bool) or value < 1:
        raise WooCommerceAPIError(
            f"Invalid {label}. {label} must be a positive integer.",
            status_code=422,
        )


def _map_attribute_error(exc: WooCommerceAPIError) -> WooCommerceAPIError:
    if exc.upstream_status == 404:
        return WooCommerceAPIError(
            "Product attribute not found.",
            status_code=404,
            upstream_status=404,
            upstream_code=exc.upstream_code,
        )
    if exc.upstream_status in (400, 409, 422):
        detail = exc.upstream_message or "The WooCommerce product attribute request was rejected."
        if exc.upstream_code:
            detail = f"{detail} ({exc.upstream_code})"
        return WooCommerceAPIError(
            detail,
            status_code=400 if exc.upstream_status == 400 else exc.upstream_status,
            upstream_status=exc.upstream_status,
            upstream_code=exc.upstream_code,
        )
    return exc


def _parse_attribute(payload: object, status_code: int) -> ProductAttributeResponse:
    if not isinstance(payload, dict) or "code" in payload:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected response format.",
            status_code=502,
            upstream_status=status_code,
        )
    try:
        return ProductAttributeResponse.model_validate(payload)
    except ValidationError as exc:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected product attribute format.",
            status_code=502,
            upstream_status=status_code,
        ) from exc


def create_product_attribute(
    client: WooCommerceClient,
    payload: ProductAttributeCreate,
) -> ProductAttributeResponse:
    """Create a product attribute in WooCommerce."""
    try:
        response_payload, status_code = client.request_json(
            "POST",
            "products/attributes",
            json_body=payload.model_dump(exclude_none=True),
        )
    except WooCommerceAPIError as exc:
        raise _map_attribute_error(exc) from exc
    return _parse_attribute(response_payload, status_code)


def get_product_attribute(
    client: WooCommerceClient,
    attribute_id: int,
    *,
    context: Literal["view", "edit"] = "view",
) -> ProductAttributeResponse:
    """Retrieve a product attribute by ID."""
    _validate_positive_id(attribute_id, "attribute ID")
    try:
        response_payload, status_code = client.request_json(
            "GET",
            f"products/attributes/{attribute_id}",
            params={"context": context},
        )
    except WooCommerceAPIError as exc:
        raise _map_attribute_error(exc) from exc
    return _parse_attribute(response_payload, status_code)


def list_product_attributes(
    client: WooCommerceClient,
    *,
    context: Literal["view", "edit"] = "view",
    slug: list[str] | None = None,
) -> list[ProductAttributeResponse]:
    """Retrieve all product attributes, optionally filtered by slug."""
    params: dict[str, object] = {"context": context}
    if slug:
        cleaned = [s.strip() for s in slug if s.strip()]
        if cleaned:
            params["slug"] = ",".join(cleaned)
    try:
        response_payload, status_code = client.request_json(
            "GET",
            "products/attributes",
            params=params,
        )
    except WooCommerceAPIError as exc:
        raise _map_attribute_error(exc) from exc

    if not isinstance(response_payload, list):
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected response format.",
            status_code=502,
            upstream_status=status_code,
        )
    return [_parse_attribute(item, status_code) for item in response_payload]


def update_product_attribute(
    client: WooCommerceClient,
    attribute_id: int,
    payload: ProductAttributeUpdate,
) -> ProductAttributeResponse:
    """Update a product attribute by ID."""
    _validate_positive_id(attribute_id, "attribute ID")
    try:
        response_payload, status_code = client.request_json(
            "PUT",
            f"products/attributes/{attribute_id}",
            json_body=payload.model_dump(exclude_none=True),
        )
    except WooCommerceAPIError as exc:
        raise _map_attribute_error(exc) from exc
    return _parse_attribute(response_payload, status_code)


def delete_product_attribute(
    client: WooCommerceClient,
    attribute_id: int,
    *,
    force: bool = False,
) -> ProductAttributeResponse:
    """Delete a product attribute by ID (requires force=true)."""
    _validate_positive_id(attribute_id, "attribute ID")
    if not force:
        raise WooCommerceAPIError(
            "Deleting a product attribute requires 'force=true'.",
            status_code=400,
        )
    try:
        response_payload, status_code = client.request_json(
            "DELETE",
            f"products/attributes/{attribute_id}",
            params={"force": "true"},
        )
    except WooCommerceAPIError as exc:
        raise _map_attribute_error(exc) from exc
    return _parse_attribute(response_payload, status_code)


def batch_product_attributes(
    client: WooCommerceClient,
    payload: ProductAttributeBatchRequest,
) -> ProductAttributeBatchResponse:
    """Batch create, update, and delete product attributes."""
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
            "products/attributes/batch",
            json_body=body,
        )
    except WooCommerceAPIError as exc:
        raise _map_attribute_error(exc) from exc

    if not isinstance(response_payload, dict) or "code" in response_payload:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected response format.",
            status_code=502,
            upstream_status=status_code,
        )
    try:
        return ProductAttributeBatchResponse.model_validate(response_payload)
    except ValidationError as exc:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected batch attribute format.",
            status_code=502,
            upstream_status=status_code,
        ) from exc
