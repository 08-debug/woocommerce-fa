from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
