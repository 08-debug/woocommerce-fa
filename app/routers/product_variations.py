from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import ValidationError

from app.config import get_settings
from app.schemas.product_variation import (
    ProductVariationBatchRequest,
    ProductVariationBatchResponse,
    ProductVariationCreate,
    ProductVariationResponse,
    ProductVariationUpdate,
    VariationListQueryParams,
    VariationStockStatus,
)
from app.services.product_variation_service import (
    batch_product_variations,
    create_product_variation,
    delete_product_variation,
    get_product_variation,
    list_product_variations,
    update_product_variation,
)
from app.services.woocommerce import WooCommerceClient

router = APIRouter(prefix="/products/{product_id}/variations", tags=["Product Variations"])


@router.post(
    "",
    response_model=ProductVariationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product variation",
)
def post_product_variation(
    payload: ProductVariationCreate,
    product_id: int = Path(..., ge=1, description="Parent WooCommerce product ID"),
) -> ProductVariationResponse:
    with WooCommerceClient(get_settings()) as client:
        return create_product_variation(client, product_id, payload)


@router.get(
    "",
    response_model=list[ProductVariationResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve all variations of a product",
)
def get_product_variations(
    product_id: int = Path(..., ge=1, description="Parent WooCommerce product ID"),
    context: Literal["view", "edit"] = Query(default="view"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=10, ge=1, le=100),
    search: str | None = Query(default=None),
    after: datetime | None = Query(default=None),
    before: datetime | None = Query(default=None),
    dates_are_gmt: bool = Query(default=False),
    exclude: list[int] | None = Query(default=None),
    include: list[int] | None = Query(default=None),
    offset: int | None = Query(default=None, ge=0),
    order: Literal["asc", "desc"] = Query(default="desc"),
    orderby: Literal["date", "id", "include", "title", "slug", "modified", "menu_order"] = Query(
        default="date"
    ),
    parent: list[int] | None = Query(default=None),
    parent_exclude: list[int] | None = Query(default=None),
    slug: str | None = Query(default=None),
    status_filter: Literal["any", "draft", "pending", "private", "publish", "trash"] | None = Query(
        default=None,
        alias="status",
    ),
    include_status: list[str] | None = Query(default=None),
    exclude_status: list[str] | None = Query(default=None),
    sku: str | None = Query(default=None),
    mpn: str | None = Query(default=None),
    tax_class: str | None = Query(default=None),
    on_sale: bool | None = Query(default=None),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    stock_status: VariationStockStatus | None = Query(default=None),
    virtual: bool | None = Query(default=None),
    downloadable: bool | None = Query(default=None),
    image_size: str | None = Query(default=None),
) -> list[ProductVariationResponse]:
    try:
        query = VariationListQueryParams(
            context=context,
            page=page,
            per_page=per_page,
            search=search,
            after=after,
            before=before,
            dates_are_gmt=dates_are_gmt,
            exclude=exclude,
            include=include,
            offset=offset,
            order=order,
            orderby=orderby,
            parent=parent,
            parent_exclude=parent_exclude,
            slug=slug,
            status=status_filter,
            include_status=include_status,
            exclude_status=exclude_status,
            sku=sku,
            mpn=mpn,
            tax_class=tax_class,
            on_sale=on_sale,
            min_price=min_price,
            max_price=max_price,
            stock_status=stock_status,
            virtual=virtual,
            downloadable=downloadable,
            image_size=image_size,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.errors()[0]["msg"],
        ) from exc

    with WooCommerceClient(get_settings()) as client:
        return list_product_variations(client, product_id, query)


@router.post(
    "/batch",
    response_model=ProductVariationBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch create, update, and delete variations",
)
def post_batch_product_variations(
    payload: ProductVariationBatchRequest,
    product_id: int = Path(..., ge=1, description="Parent WooCommerce product ID"),
) -> ProductVariationBatchResponse:
    with WooCommerceClient(get_settings()) as client:
        return batch_product_variations(client, product_id, payload)


@router.get(
    "/{variation_id}",
    response_model=ProductVariationResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a specific variation",
)
def get_single_product_variation(
    product_id: int = Path(..., ge=1, description="Parent WooCommerce product ID"),
    variation_id: int = Path(..., ge=1, description="WooCommerce variation ID"),
    context: Literal["view", "edit"] = Query(default="view"),
) -> ProductVariationResponse:
    with WooCommerceClient(get_settings()) as client:
        return get_product_variation(client, product_id, variation_id, context=context)


@router.put(
    "/{variation_id}",
    response_model=ProductVariationResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a product variation",
)
def put_product_variation(
    payload: ProductVariationUpdate,
    product_id: int = Path(..., ge=1, description="Parent WooCommerce product ID"),
    variation_id: int = Path(..., ge=1, description="WooCommerce variation ID"),
) -> ProductVariationResponse:
    with WooCommerceClient(get_settings()) as client:
        return update_product_variation(client, product_id, variation_id, payload)


@router.delete(
    "/{variation_id}",
    response_model=ProductVariationResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a product variation",
)
def remove_product_variation(
    product_id: int = Path(..., ge=1, description="Parent WooCommerce product ID"),
    variation_id: int = Path(..., ge=1, description="WooCommerce variation ID"),
    force: bool = Query(default=False, description="Must be true to delete the variation"),
) -> ProductVariationResponse:
    with WooCommerceClient(get_settings()) as client:
        return delete_product_variation(client, product_id, variation_id, force=force)
