from typing import Literal

from pydantic import ValidationError

from app.schemas.product_attribute_term import (
    AttributeTermListQueryParams,
    ProductAttributeTermBatchRequest,
    ProductAttributeTermBatchResponse,
    ProductAttributeTermCreate,
    ProductAttributeTermResponse,
    ProductAttributeTermUpdate,
)
from app.services.woocommerce import WooCommerceAPIError, WooCommerceClient


def _validate_positive_id(value: int, label: str) -> None:
    if isinstance(value, bool) or value < 1:
        raise WooCommerceAPIError(
            f"Invalid {label}. {label} must be a positive integer.",
            status_code=422,
        )


def _map_term_error(
    exc: WooCommerceAPIError,
    *,
    has_term_id: bool = False,
) -> WooCommerceAPIError:
    if exc.upstream_status == 404:
        return WooCommerceAPIError(
            "Product attribute or term not found."
            if has_term_id
            else "Product attribute not found.",
            status_code=404,
            upstream_status=404,
            upstream_code=exc.upstream_code,
        )
    if exc.upstream_status in (400, 409, 422):
        detail = exc.upstream_message or "The WooCommerce attribute term request was rejected."
        if exc.upstream_code:
            detail = f"{detail} ({exc.upstream_code})"
        return WooCommerceAPIError(
            detail,
            status_code=400 if exc.upstream_status == 400 else exc.upstream_status,
            upstream_status=exc.upstream_status,
            upstream_code=exc.upstream_code,
        )
    return exc


def _parse_term(payload: object, status_code: int) -> ProductAttributeTermResponse:
    if not isinstance(payload, dict) or "code" in payload:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected response format.",
            status_code=502,
            upstream_status=status_code,
        )
    try:
        return ProductAttributeTermResponse.model_validate(payload)
    except ValidationError as exc:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected attribute term format.",
            status_code=502,
            upstream_status=status_code,
        ) from exc


def create_attribute_term(
    client: WooCommerceClient,
    attribute_id: int,
    payload: ProductAttributeTermCreate,
) -> ProductAttributeTermResponse:
    """Create a term for a WooCommerce product attribute."""
    _validate_positive_id(attribute_id, "attribute ID")
    try:
        response_payload, status_code = client.request_json(
            "POST",
            f"products/attributes/{attribute_id}/terms",
            json_body=payload.model_dump(exclude_none=True),
        )
    except WooCommerceAPIError as exc:
        raise _map_term_error(exc) from exc
    return _parse_term(response_payload, status_code)


def get_attribute_term(
    client: WooCommerceClient,
    attribute_id: int,
    term_id: int,
    *,
    context: Literal["view", "edit"] = "view",
) -> ProductAttributeTermResponse:
    """Retrieve a specific term for a product attribute."""
    _validate_positive_id(attribute_id, "attribute ID")
    _validate_positive_id(term_id, "term ID")
    try:
        response_payload, status_code = client.request_json(
            "GET",
            f"products/attributes/{attribute_id}/terms/{term_id}",
            params={"context": context},
        )
    except WooCommerceAPIError as exc:
        raise _map_term_error(exc, has_term_id=True) from exc
    return _parse_term(response_payload, status_code)


def list_attribute_terms(
    client: WooCommerceClient,
    attribute_id: int,
    query: AttributeTermListQueryParams,
) -> list[ProductAttributeTermResponse]:
    """List terms for a product attribute."""
    _validate_positive_id(attribute_id, "attribute ID")
    try:
        response_payload, status_code = client.request_json(
            "GET",
            f"products/attributes/{attribute_id}/terms",
            params=query.to_woo_params(),
        )
    except WooCommerceAPIError as exc:
        raise _map_term_error(exc) from exc

    if not isinstance(response_payload, list):
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected response format.",
            status_code=502,
            upstream_status=status_code,
        )
    return [_parse_term(item, status_code) for item in response_payload]


def update_attribute_term(
    client: WooCommerceClient,
    attribute_id: int,
    term_id: int,
    payload: ProductAttributeTermUpdate,
) -> ProductAttributeTermResponse:
    """Update a term for a product attribute."""
    _validate_positive_id(attribute_id, "attribute ID")
    _validate_positive_id(term_id, "term ID")
    try:
        response_payload, status_code = client.request_json(
            "PUT",
            f"products/attributes/{attribute_id}/terms/{term_id}",
            json_body=payload.model_dump(exclude_none=True),
        )
    except WooCommerceAPIError as exc:
        raise _map_term_error(exc, has_term_id=True) from exc
    return _parse_term(response_payload, status_code)


def delete_attribute_term(
    client: WooCommerceClient,
    attribute_id: int,
    term_id: int,
    *,
    force: bool = False,
) -> ProductAttributeTermResponse:
    """Delete an attribute term (requires force=true)."""
    _validate_positive_id(attribute_id, "attribute ID")
    _validate_positive_id(term_id, "term ID")
    if not force:
        raise WooCommerceAPIError(
            "Deleting an attribute term requires 'force=true'.",
            status_code=400,
        )
    try:
        response_payload, status_code = client.request_json(
            "DELETE",
            f"products/attributes/{attribute_id}/terms/{term_id}",
            params={"force": "true"},
        )
    except WooCommerceAPIError as exc:
        raise _map_term_error(exc, has_term_id=True) from exc
    return _parse_term(response_payload, status_code)


def batch_attribute_terms(
    client: WooCommerceClient,
    attribute_id: int,
    payload: ProductAttributeTermBatchRequest,
) -> ProductAttributeTermBatchResponse:
    """Batch create, update, and delete terms for a product attribute."""
    _validate_positive_id(attribute_id, "attribute ID")
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
            f"products/attributes/{attribute_id}/terms/batch",
            json_body=body,
        )
    except WooCommerceAPIError as exc:
        raise _map_term_error(exc) from exc

    if not isinstance(response_payload, dict) or "code" in response_payload:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected response format.",
            status_code=502,
            upstream_status=status_code,
        )
    try:
        return ProductAttributeTermBatchResponse.model_validate(response_payload)
    except ValidationError as exc:
        raise WooCommerceAPIError(
            "The WooCommerce API returned an unexpected batch attribute term format.",
            status_code=502,
            upstream_status=status_code,
        ) from exc
