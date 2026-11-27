from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _validate_optional_price(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if stripped == "":
        return ""
    try:
        parsed = Decimal(stripped)
    except InvalidOperation as exc:
        raise ValueError("Price must be a valid decimal string.") from exc
    if parsed < 0:
        raise ValueError("Price cannot be negative.")
    return stripped


class VariationDownload(BaseModel):
    """Downloadable file entry for a product variation."""

    model_config = ConfigDict(extra="ignore")

    id: str = ""
    name: str
    file: str


class VariationDimensions(BaseModel):
    """Physical dimensions for a product variation."""

    model_config = ConfigDict(extra="ignore")

    length: str = ""
    width: str = ""
    height: str = ""


class VariationImageRequest(BaseModel):
    """Writable image fields for creating or updating a variation."""

    model_config = ConfigDict(extra="forbid")

    id: int | None = Field(default=None, ge=1, description="Media attachment ID.")
    src: str | None = Field(default=None, description="Image URL.")
    name: str | None = Field(default=None, description="Image name.")
    alt: str | None = Field(default=None, description="Image alt text.")


class VariationImageResponse(BaseModel):
    """Image object returned by WooCommerce for a variation."""

    model_config = ConfigDict(extra="ignore")

    id: int = 0
    date_created: datetime | None = None
    date_created_gmt: datetime | None = None
    date_modified: datetime | None = None
    date_modified_gmt: datetime | None = None
    src: str = ""
    name: str = ""
    alt: str = ""


class VariationAttribute(BaseModel):
    """Attribute option selected for a variation."""

    model_config = ConfigDict(extra="ignore")

    id: int = Field(default=0, ge=0, description="Attribute ID.")
    name: str = Field(default="", description="Attribute name.")
    option: str = Field(..., min_length=1, description="Selected attribute term/option.")


class VariationMetaDataInput(BaseModel):
    """Writable metadata entry for a variation."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., min_length=1, description="Metadata key.")
    value: object = Field(..., description="Metadata value.")


class VariationMetaDataResponse(BaseModel):
    """Metadata entry returned by WooCommerce for a variation."""

    model_config = ConfigDict(extra="ignore")

    id: int = 0
    key: str
    value: object


VariationStatus = Literal["publish", "private", "pending", "draft"]
VariationTaxStatus = Literal["taxable", "shipping", "none"]
VariationStockStatus = Literal["instock", "outofstock", "onbackorder"]
VariationBackorders = Literal["no", "notify", "yes"]


class ProductVariationCreate(BaseModel):
    """Request schema for creating a WooCommerce product variation."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "regular_price": "19.99",
                "sku": "TSHIRT-BLUE-L",
                "manage_stock": True,
                "stock_quantity": 10,
                "attributes": [{"id": 1, "name": "Color", "option": "Blue"}],
            }
        },
    )

    description: str | None = None
    sku: str | None = None
    mpn: str | None = None
    global_unique_id: str | None = None
    customs_commodity_code: str | None = None
    customs_country_of_origin: str | None = None
    customs_description: str | None = Field(default=None, max_length=35)
    regular_price: str | None = None
    sale_price: str | None = None
    date_on_sale_from: datetime | None = None
    date_on_sale_from_gmt: datetime | None = None
    date_on_sale_to: datetime | None = None
    date_on_sale_to_gmt: datetime | None = None
    status: VariationStatus = "publish"
    virtual: bool = False
    downloadable: bool = False
    downloads: list[VariationDownload] | None = None
    download_limit: int = Field(default=-1, ge=-1)
    download_expiry: int = Field(default=-1, ge=-1)
    tax_status: VariationTaxStatus = "taxable"
    tax_class: str | None = None
    manage_stock: bool | Literal["parent"] = False
    stock_quantity: int | None = Field(default=None, ge=0)
    stock_status: VariationStockStatus = "instock"
    backorders: VariationBackorders = "no"
    weight: str | None = None
    dimensions: VariationDimensions | None = None
    shipping_class: str | None = None
    image: VariationImageRequest | None = None
    gallery_image_ids: list[int] | None = None
    attributes: list[VariationAttribute] | None = None
    menu_order: int | None = None
    meta_data: list[VariationMetaDataInput] | None = None

    @field_validator("regular_price", "sale_price")
    @classmethod
    def validate_prices(cls, value: str | None) -> str | None:
        return _validate_optional_price(value)


class ProductVariationUpdate(BaseModel):
    """Request schema for updating a WooCommerce product variation."""

    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    sku: str | None = None
    mpn: str | None = None
    global_unique_id: str | None = None
    customs_commodity_code: str | None = None
    customs_country_of_origin: str | None = None
    customs_description: str | None = Field(default=None, max_length=35)
    regular_price: str | None = None
    sale_price: str | None = None
    date_on_sale_from: datetime | None = None
    date_on_sale_from_gmt: datetime | None = None
    date_on_sale_to: datetime | None = None
    date_on_sale_to_gmt: datetime | None = None
    status: VariationStatus | None = None
    virtual: bool | None = None
    downloadable: bool | None = None
    downloads: list[VariationDownload] | None = None
    download_limit: int | None = Field(default=None, ge=-1)
    download_expiry: int | None = Field(default=None, ge=-1)
    tax_status: VariationTaxStatus | None = None
    tax_class: str | None = None
    manage_stock: bool | Literal["parent"] | None = None
    stock_quantity: int | None = Field(default=None, ge=0)
    stock_status: VariationStockStatus | None = None
    backorders: VariationBackorders | None = None
    weight: str | None = None
    dimensions: VariationDimensions | None = None
    shipping_class: str | None = None
    image: VariationImageRequest | None = None
    gallery_image_ids: list[int] | None = None
    attributes: list[VariationAttribute] | None = None
    menu_order: int | None = None
    meta_data: list[VariationMetaDataInput] | None = None

    @field_validator("regular_price", "sale_price")
    @classmethod
    def validate_prices(cls, value: str | None) -> str | None:
        return _validate_optional_price(value)

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "ProductVariationUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        return self


class ProductVariationBatchUpdateItem(ProductVariationUpdate):
    """Batch update item containing variation ID and editable fields."""

    id: int = Field(..., ge=1, description="Existing variation ID to update.")


class ProductVariationBatchRequest(BaseModel):
    """Batch create, update, and delete request for product variations (max 100 per operation)."""

    model_config = ConfigDict(extra="forbid")

    create: list[ProductVariationCreate] = Field(default_factory=list, max_length=100)
    update: list[ProductVariationBatchUpdateItem] = Field(default_factory=list, max_length=100)
    delete: list[int] = Field(default_factory=list, max_length=100)

    @field_validator("delete")
    @classmethod
    def validate_delete_ids(cls, values: list[int]) -> list[int]:
        for item_id in values:
            if item_id < 1:
                raise ValueError("All delete IDs must be positive integers.")
        return values

    @model_validator(mode="after")
    def require_any_operation(self) -> "ProductVariationBatchRequest":
        if not self.create and not self.update and not self.delete:
            raise ValueError("Provide at least one item in 'create', 'update', or 'delete'.")
        return self


class ProductVariationResponse(BaseModel):
    """Validated WooCommerce product variation response."""

    model_config = ConfigDict(extra="ignore")

    id: int
    date_created: datetime | None = None
    date_created_gmt: datetime | None = None
    date_modified: datetime | None = None
    date_modified_gmt: datetime | None = None
    description: str = ""
    permalink: str = ""
    sku: str = ""
    mpn: str = ""
    global_unique_id: str = ""
    customs_commodity_code: str | None = None
    customs_country_of_origin: str | None = None
    customs_description: str | None = None
    price: str = ""
    regular_price: str = ""
    sale_price: str = ""
    date_on_sale_from: datetime | None = None
    date_on_sale_from_gmt: datetime | None = None
    date_on_sale_to: datetime | None = None
    date_on_sale_to_gmt: datetime | None = None
    on_sale: bool = False
    status: str = "publish"
    purchasable: bool = True
    virtual: bool = False
    downloadable: bool = False
    downloads: list[VariationDownload] = Field(default_factory=list)
    download_limit: int = -1
    download_expiry: int = -1
    tax_status: str = "taxable"
    tax_class: str = ""
    manage_stock: bool | str = False
    stock_quantity: int | None = None
    stock_status: str = "instock"
    backorders: str = "no"
    backorders_allowed: bool = False
    backordered: bool = False
    weight: str = ""
    dimensions: VariationDimensions = Field(default_factory=VariationDimensions)
    shipping_class: str = ""
    shipping_class_id: int = 0
    image: VariationImageResponse | None = None
    gallery_image_ids: list[int] = Field(default_factory=list)
    attributes: list[VariationAttribute] = Field(default_factory=list)
    menu_order: int = 0
    meta_data: list[VariationMetaDataResponse] = Field(default_factory=list)

    @field_validator(
        "description",
        "permalink",
        "sku",
        "mpn",
        "global_unique_id",
        "price",
        "regular_price",
        "sale_price",
        "tax_class",
        "weight",
        "shipping_class",
        mode="before",
    )
    @classmethod
    def coerce_none_to_empty(cls, value: object) -> object:
        return "" if value is None else value


class BatchItemError(BaseModel):
    """Per-item error returned by WooCommerce batch endpoints."""

    model_config = ConfigDict(extra="ignore")

    id: int = 0
    error: dict[str, object]


class ProductVariationBatchResponse(BaseModel):
    """Response schema for batch product variation operations."""

    model_config = ConfigDict(extra="ignore")

    create: list[ProductVariationResponse | BatchItemError] = Field(default_factory=list)
    update: list[ProductVariationResponse | BatchItemError] = Field(default_factory=list)
    delete: list[ProductVariationResponse | BatchItemError] = Field(default_factory=list)


class VariationListQueryParams(BaseModel):
    """Documented query parameters for listing product variations."""

    model_config = ConfigDict(extra="forbid")

    context: Literal["view", "edit"] = "view"
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=100)
    search: str | None = None
    after: datetime | None = None
    before: datetime | None = None
    dates_are_gmt: bool = False
    exclude: list[int] | None = None
    include: list[int] | None = None
    offset: int | None = Field(default=None, ge=0)
    order: Literal["asc", "desc"] = "desc"
    orderby: Literal["date", "id", "include", "title", "slug", "modified", "menu_order"] = "date"
    parent: list[int] | None = None
    parent_exclude: list[int] | None = None
    slug: str | None = None
    status: Literal["any", "draft", "pending", "private", "publish", "trash"] | None = None
    include_status: list[str] | None = None
    exclude_status: list[str] | None = None
    sku: str | None = None
    mpn: str | None = None
    tax_class: str | None = None
    on_sale: bool | None = None
    min_price: Decimal | None = Field(default=None, ge=0)
    max_price: Decimal | None = Field(default=None, ge=0)
    stock_status: VariationStockStatus | None = None
    virtual: bool | None = None
    downloadable: bool | None = None
    image_size: str | None = None

    @model_validator(mode="after")
    def validate_price_range(self) -> "VariationListQueryParams":
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("'min_price' cannot be greater than 'max_price'.")
        return self

    def to_woo_params(self) -> dict[str, object]:
        params: dict[str, object] = {
            "context": self.context,
            "page": self.page,
            "per_page": self.per_page,
            "dates_are_gmt": str(self.dates_are_gmt).lower(),
            "order": self.order,
            "orderby": self.orderby,
        }
        if self.search is not None:
            params["search"] = self.search
        if self.after is not None:
            params["after"] = self.after.isoformat()
        if self.before is not None:
            params["before"] = self.before.isoformat()
        if self.exclude:
            params["exclude"] = ",".join(str(i) for i in self.exclude)
        if self.include:
            params["include"] = ",".join(str(i) for i in self.include)
        if self.offset is not None:
            params["offset"] = self.offset
        if self.parent:
            params["parent"] = ",".join(str(i) for i in self.parent)
        if self.parent_exclude:
            params["parent_exclude"] = ",".join(str(i) for i in self.parent_exclude)
        if self.slug is not None:
            params["slug"] = self.slug
        if self.status is not None:
            params["status"] = self.status
        if self.include_status:
            params["include_status"] = ",".join(self.include_status)
        if self.exclude_status:
            params["exclude_status"] = ",".join(self.exclude_status)
        if self.sku is not None:
            params["sku"] = self.sku
        if self.mpn is not None:
            params["mpn"] = self.mpn
        if self.tax_class is not None:
            params["tax_class"] = self.tax_class
        if self.on_sale is not None:
            params["on_sale"] = str(self.on_sale).lower()
        if self.min_price is not None:
            params["min_price"] = str(self.min_price)
        if self.max_price is not None:
            params["max_price"] = str(self.max_price)
        if self.stock_status is not None:
            params["stock_status"] = self.stock_status
        if self.virtual is not None:
            params["virtual"] = str(self.virtual).lower()
        if self.downloadable is not None:
            params["downloadable"] = str(self.downloadable).lower()
        if self.image_size is not None:
            params["image_size"] = self.image_size
        return params
