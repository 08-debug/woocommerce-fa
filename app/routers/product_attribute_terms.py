from typing import Literal

from fastapi import APIRouter, Path, Query, status

from app.config import get_settings
from app.schemas.product_attribute_term import (
    AttributeTermListQueryParams,
    ProductAttributeTermBatchRequest,
    ProductAttributeTermBatchResponse,
    ProductAttributeTermCreate,
    ProductAttributeTermResponse,
    ProductAttributeTermUpdate,
    TermOrder,
    TermOrderBy,
)
from app.services.product_attribute_term_service import (
    batch_attribute_terms,
    create_attribute_term,
    delete_attribute_term,
    get_attribute_term,
    list_attribute_terms,
    update_attribute_term,
)
from app.services.woocommerce import WooCommerceClient

router = APIRouter(
    prefix="/products/attributes/{attribute_id}/terms",
    tags=["Product Attribute Terms"],
)


@router.post(
    "",
    response_model=ProductAttributeTermResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an attribute term",
)
def post_attribute_term(
    payload: ProductAttributeTermCreate,
    attribute_id: int = Path(..., ge=1, description="WooCommerce attribute ID"),
) -> ProductAttributeTermResponse:
    with WooCommerceClient(get_settings()) as client:
        return create_attribute_term(client, attribute_id, payload)


@router.get(
    "",
    response_model=list[ProductAttributeTermResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve all terms for an attribute",
)
def get_attribute_terms(
    attribute_id: int = Path(..., ge=1, description="WooCommerce attribute ID"),
    context: Literal["view", "edit"] = Query(default="view"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=10, ge=1, le=100),
    search: str | None = Query(default=None),
    exclude: list[int] | None = Query(default=None),
    include: list[int] | None = Query(default=None),
    order: TermOrder = Query(default="asc"),
    orderby: TermOrderBy = Query(default="name"),
    hide_empty: bool = Query(default=False),
    parent: int | None = Query(default=None, ge=0),
    product: int | None = Query(default=None, ge=1),
    slug: str | None = Query(default=None),
) -> list[ProductAttributeTermResponse]:
    query = AttributeTermListQueryParams(
        context=context,
        page=page,
        per_page=per_page,
        search=search,
        exclude=exclude,
        include=include,
        order=order,
        orderby=orderby,
        hide_empty=hide_empty,
        parent=parent,
        product=product,
        slug=slug,
    )
    with WooCommerceClient(get_settings()) as client:
        return list_attribute_terms(client, attribute_id, query)


@router.post(
    "/batch",
    response_model=ProductAttributeTermBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch create, update, and delete attribute terms",
)
def post_batch_attribute_terms(
    payload: ProductAttributeTermBatchRequest,
    attribute_id: int = Path(..., ge=1, description="WooCommerce attribute ID"),
) -> ProductAttributeTermBatchResponse:
    with WooCommerceClient(get_settings()) as client:
        return batch_attribute_terms(client, attribute_id, payload)


@router.get(
    "/{term_id}",
    response_model=ProductAttributeTermResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a specific attribute term",
)
def get_single_attribute_term(
    attribute_id: int = Path(..., ge=1, description="WooCommerce attribute ID"),
    term_id: int = Path(..., ge=1, description="WooCommerce term ID"),
    context: Literal["view", "edit"] = Query(default="view"),
) -> ProductAttributeTermResponse:
    with WooCommerceClient(get_settings()) as client:
        return get_attribute_term(client, attribute_id, term_id, context=context)


@router.put(
    "/{term_id}",
    response_model=ProductAttributeTermResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an attribute term",
)
def put_attribute_term(
    payload: ProductAttributeTermUpdate,
    attribute_id: int = Path(..., ge=1, description="WooCommerce attribute ID"),
    term_id: int = Path(..., ge=1, description="WooCommerce term ID"),
) -> ProductAttributeTermResponse:
    with WooCommerceClient(get_settings()) as client:
        return update_attribute_term(client, attribute_id, term_id, payload)


@router.delete(
    "/{term_id}",
    response_model=ProductAttributeTermResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete an attribute term",
)
def remove_attribute_term(
    attribute_id: int = Path(..., ge=1, description="WooCommerce attribute ID"),
    term_id: int = Path(..., ge=1, description="WooCommerce term ID"),
    force: bool = Query(default=False, description="Must be true to delete the term"),
) -> ProductAttributeTermResponse:
    with WooCommerceClient(get_settings()) as client:
        return delete_attribute_term(client, attribute_id, term_id, force=force)
