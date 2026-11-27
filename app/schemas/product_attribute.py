from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AttributeType = Literal["select"]
AttributeOrderBy = Literal["menu_order", "name", "name_num", "id"]


class ProductAttributeCreate(BaseModel):
    """Request schema for creating a WooCommerce product attribute."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "name": "Color",
                "slug": "pa_color",
                "type": "select",
                "order_by": "menu_order",
                "has_archives": False,
            }
        },
    )

    name: str = Field(..., min_length=1, description="Attribute name (mandatory).")
    slug: str | None = Field(default=None, description="Optional attribute slug.")
    type: AttributeType = Field(default="select", description="Attribute type (select).")
    order_by: AttributeOrderBy = Field(
        default="menu_order",
        description="Default sort order (menu_order, name, name_num, id).",
    )
    has_archives: bool = Field(default=False, description="Enable attribute archives.")

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class ProductAttributeUpdate(BaseModel):
    """Request schema for updating a WooCommerce product attribute."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, description="Attribute name.")
    slug: str | None = Field(default=None, description="Attribute slug.")
    type: AttributeType | None = Field(default=None, description="Attribute type (select).")
    order_by: AttributeOrderBy | None = Field(
        default=None,
        description="Default sort order (menu_order, name, name_num, id).",
    )
    has_archives: bool | None = Field(default=None, description="Enable attribute archives.")

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "ProductAttributeUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        return self


class ProductAttributeBatchUpdateItem(ProductAttributeUpdate):
    """Batch update item containing attribute ID and editable fields."""

    id: int = Field(..., ge=1, description="Existing attribute ID to update.")


class ProductAttributeBatchRequest(BaseModel):
    """Batch create, update, and delete request for product attributes (max 100 per operation)."""

    model_config = ConfigDict(extra="forbid")

    create: list[ProductAttributeCreate] = Field(default_factory=list, max_length=100)
    update: list[ProductAttributeBatchUpdateItem] = Field(default_factory=list, max_length=100)
    delete: list[int] = Field(default_factory=list, max_length=100)

    @field_validator("delete")
    @classmethod
    def validate_delete_ids(cls, values: list[int]) -> list[int]:
        for item_id in values:
            if item_id < 1:
                raise ValueError("All delete IDs must be positive integers.")
        return values

    @model_validator(mode="after")
    def require_any_operation(self) -> "ProductAttributeBatchRequest":
        if not self.create and not self.update and not self.delete:
            raise ValueError("Provide at least one item in 'create', 'update', or 'delete'.")
        return self


class ProductAttributeResponse(BaseModel):
    """Validated WooCommerce product attribute resource."""

    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    slug: str = ""
    type: str = "select"
    order_by: str = "menu_order"
    has_archives: bool = False


class BatchItemError(BaseModel):
    """Per-item error returned by WooCommerce batch endpoints."""

    model_config = ConfigDict(extra="ignore")

    id: int = 0
    error: dict[str, object]


class ProductAttributeBatchResponse(BaseModel):
    """Response schema for batch product attribute operations."""

    model_config = ConfigDict(extra="ignore")

    create: list[ProductAttributeResponse | BatchItemError] = Field(default_factory=list)
    update: list[ProductAttributeResponse | BatchItemError] = Field(default_factory=list)
    delete: list[ProductAttributeResponse | BatchItemError] = Field(default_factory=list)
