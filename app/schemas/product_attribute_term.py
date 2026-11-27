from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TermOrder = Literal["asc", "desc"]
TermOrderBy = Literal["id", "include", "name", "slug", "term_group", "description", "count"]


class ProductAttributeTermCreate(BaseModel):
    """Request schema for creating a WooCommerce product attribute term."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "name": "Blue",
                "slug": "blue",
                "description": "Blue color option",
                "menu_order": 1,
            }
        },
    )

    name: str = Field(..., min_length=1, description="Term name (mandatory).")
    slug: str | None = Field(default=None, description="Optional term slug.")
    description: str | None = Field(default=None, description="Optional term description.")
    menu_order: int | None = Field(default=None, description="Menu order (integer).")

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class ProductAttributeTermUpdate(BaseModel):
    """Request schema for updating a WooCommerce product attribute term."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, description="Term name.")
    slug: str | None = Field(default=None, description="Term slug.")
    description: str | None = Field(default=None, description="Term description.")
    menu_order: int | None = Field(default=None, description="Menu order (integer).")

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "ProductAttributeTermUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        return self


class ProductAttributeTermBatchUpdateItem(ProductAttributeTermUpdate):
    """Batch update item containing term ID and editable fields."""

    id: int = Field(..., ge=1, description="Existing term ID to update.")


class ProductAttributeTermBatchRequest(BaseModel):
    """Batch create, update, and delete request for attribute terms (max 100 per operation)."""

    model_config = ConfigDict(extra="forbid")

    create: list[ProductAttributeTermCreate] = Field(default_factory=list, max_length=100)
    update: list[ProductAttributeTermBatchUpdateItem] = Field(default_factory=list, max_length=100)
    delete: list[int] = Field(default_factory=list, max_length=100)

    @field_validator("delete")
    @classmethod
    def validate_delete_ids(cls, values: list[int]) -> list[int]:
        for item_id in values:
            if item_id < 1:
                raise ValueError("All delete IDs must be positive integers.")
        return values

    @model_validator(mode="after")
    def require_any_operation(self) -> "ProductAttributeTermBatchRequest":
        if not self.create and not self.update and not self.delete:
            raise ValueError("Provide at least one item in 'create', 'update', or 'delete'.")
        return self


class ProductAttributeTermResponse(BaseModel):
    """Validated WooCommerce product attribute term resource."""

    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    slug: str = ""
    description: str = ""
    menu_order: int = 0
    count: int = 0

    @field_validator("slug", "description", mode="before")
    @classmethod
    def coerce_none_to_empty(cls, value: object) -> object:
        return "" if value is None else value


class BatchItemError(BaseModel):
    """Per-item error returned by WooCommerce batch endpoints."""

    model_config = ConfigDict(extra="ignore")

    id: int = 0
    error: dict[str, object]


class ProductAttributeTermBatchResponse(BaseModel):
    """Response schema for batch attribute term operations."""

    model_config = ConfigDict(extra="ignore")

    create: list[ProductAttributeTermResponse | BatchItemError] = Field(default_factory=list)
    update: list[ProductAttributeTermResponse | BatchItemError] = Field(default_factory=list)
    delete: list[ProductAttributeTermResponse | BatchItemError] = Field(default_factory=list)


class AttributeTermListQueryParams(BaseModel):
    """Documented query parameters for listing attribute terms."""

    model_config = ConfigDict(extra="forbid")

    context: Literal["view", "edit"] = "view"
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=100)
    search: str | None = None
    exclude: list[int] | None = None
    include: list[int] | None = None
    order: TermOrder = "asc"
    orderby: TermOrderBy = "name"
    hide_empty: bool = False
    parent: int | None = Field(default=None, ge=0)
    product: int | None = Field(default=None, ge=1)
    slug: str | None = None

    def to_woo_params(self) -> dict[str, object]:
        params: dict[str, object] = {
            "context": self.context,
            "page": self.page,
            "per_page": self.per_page,
            "order": self.order,
            "orderby": self.orderby,
            "hide_empty": str(self.hide_empty).lower(),
        }
        if self.search is not None:
            params["search"] = self.search
        if self.exclude:
            params["exclude"] = ",".join(str(i) for i in self.exclude)
        if self.include:
            params["include"] = ",".join(str(i) for i in self.include)
        if self.parent is not None:
            params["parent"] = self.parent
        if self.product is not None:
            params["product"] = self.product
        if self.slug is not None:
            params["slug"] = self.slug
        return params
