from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _validate_price_string(value: str | None) -> str | None:
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


class Product(BaseModel):
    """Validated WooCommerce product representation for Task 2."""

    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    sku: str = ""
    regular_price: str = ""
    sale_price: str = ""
    stock_quantity: int | None = None
    stock_status: Literal["instock", "outofstock", "onbackorder"] | str = "instock"

    @field_validator("sku", "regular_price", "sale_price", mode="before")
    @classmethod
    def coerce_none_to_empty(cls, value: object) -> object:
        if value is None:
            return ""
        return value


class ProductCreate(BaseModel):
    """Request schema for creating a WooCommerce product."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="Product name")
    sku: str | None = Field(default=None, description="Unique SKU")
    regular_price: str | None = Field(default=None, description="Regular price as string")
    sale_price: str | None = Field(default=None, description="Sale price as string")
    stock_quantity: int | None = Field(default=None, ge=0, description="Stock quantity")
    stock_status: Literal["instock", "outofstock", "onbackorder"] = "instock"
    status: Literal["publish", "draft", "pending", "private"] = "publish"

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("regular_price", "sale_price")
    @classmethod
    def validate_prices(cls, value: str | None) -> str | None:
        return _validate_price_string(value)


class ProductFilterParams(BaseModel):
    """Optional filters for retrieving WooCommerce products."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, description="Partial product name filter")
    sku: str | None = Field(default=None, description="Partial SKU filter")
    min_price: Decimal | None = Field(default=None, ge=0, description="Minimum price")
    max_price: Decimal | None = Field(default=None, ge=0, description="Maximum price")

    @field_validator("name", "sku", mode="before")
    @classmethod
    def normalize_query(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @model_validator(mode="after")
    def validate_price_range(self) -> "ProductFilterParams":
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("'min_price' cannot be greater than 'max_price'.")
        return self


class ProductSearchParams(ProductFilterParams):
    """Validated query parameters for searching WooCommerce products."""

    @model_validator(mode="after")
    def require_at_least_one_filter(self) -> "ProductSearchParams":
        if (
            self.name is None
            and self.sku is None
            and self.min_price is None
            and self.max_price is None
        ):
            raise ValueError(
                "Provide at least one search parameter: 'name', 'sku', 'min_price', or 'max_price'."
            )
        return self
