from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TagOrder = Literal["asc", "desc"]
TagOrderBy = Literal["id", "include", "name", "slug", "term_group", "description", "count"]


class ProductTagCreate(BaseModel):
    """Request schema for creating a WooCommerce product tag."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "name": "Leather Shoes",
                "slug": "leather-shoes",
                "description": "Genuine leather footwear",
            }
        },
    )

    name: str = Field(..., min_length=1, description="Mandatory product tag name.")
    slug: str | None = Field(default=None, description="Optional alphanumeric tag slug.")
    description: str | None = Field(default=None, description="Optional HTML description.")

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class ProductTagUpdate(BaseModel):
    """Request schema for updating a WooCommerce product tag."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, description="Product tag name.")
    slug: str | None = Field(default=None, description="Alphanumeric tag slug.")
    description: str | None = Field(default=None, description="HTML description.")

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "ProductTagUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        return self


class ProductTagBatchUpdate(ProductTagUpdate):
    """Batch update item containing tag ID and editable fields."""

    id: int = Field(..., ge=1, description="Existing tag ID to update.")


class ProductTagBatchRequest(BaseModel):
    """Batch create, update, and delete request for product tags (max 100 total objects)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "create": [{"name": "Round toe"}, {"name": "Flat"}],
                "update": [{"id": 34, "description": "Genuine leather."}],
                "delete": [35],
            }
        },
    )

    create: list[ProductTagCreate] = Field(default_factory=list)
    update: list[ProductTagBatchUpdate] = Field(default_factory=list)
    delete: list[int] = Field(default_factory=list)

    @field_validator("delete")
    @classmethod
    def validate_delete_ids(cls, values: list[int]) -> list[int]:
        for item_id in values:
            if item_id < 1:
                raise ValueError("All delete IDs must be positive integers.")
        return values

    @model_validator(mode="after")
    def validate_batch_totals(self) -> "ProductTagBatchRequest":
        total = len(self.create) + len(self.update) + len(self.delete)
        if total == 0:
            raise ValueError("Provide at least one item in 'create', 'update', or 'delete'.")
        if total > 100:
            raise ValueError(
                f"Batch request exceeds WooCommerce limit of 100 total objects (got {total})."
            )
        return self


class ProductTagResponse(BaseModel):
    """Validated WooCommerce product tag resource."""

    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    slug: str = ""
    description: str = ""
    count: int = 0

    @field_validator("slug", "description", mode="before")
    @classmethod
    def coerce_none_to_empty(cls, value: object) -> object:
        return "" if value is None else value


class BatchTagError(BaseModel):
    """Per-item error returned by WooCommerce batch endpoints."""

    model_config = ConfigDict(extra="ignore")

    id: int = 0
    error: dict[str, object]


class ProductTagBatchResponse(BaseModel):
    """Response schema for batch product tag operations."""

    model_config = ConfigDict(extra="ignore")

    create: list[ProductTagResponse | BatchTagError] = Field(default_factory=list)
    update: list[ProductTagResponse | BatchTagError] = Field(default_factory=list)
    delete: list[ProductTagResponse | BatchTagError] = Field(default_factory=list)


class TagListQueryParams(BaseModel):
    """Documented query parameters for listing product tags."""

    model_config = ConfigDict(extra="forbid")

    context: Literal["view", "edit"] = "view"
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=100)
    search: str | None = None
    exclude: list[int] | None = None
    include: list[int] | None = None
    offset: int | None = Field(default=None, ge=0)
    order: TagOrder = "asc"
    orderby: TagOrderBy = "name"
    hide_empty: bool = False
    product: int | None = Field(default=None, ge=1)
    slug: str | None = None

    @field_validator("exclude", "include")
    @classmethod
    def validate_id_lists(cls, values: list[int] | None) -> list[int] | None:
        if values is not None:
            for item_id in values:
                if item_id < 1:
                    raise ValueError("Filter IDs must be positive integers.")
        return values

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
        if self.offset is not None:
            params["offset"] = self.offset
        if self.product is not None:
            params["product"] = self.product
        if self.slug is not None:
            params["slug"] = self.slug
        return params
