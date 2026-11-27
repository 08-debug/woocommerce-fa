import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ReviewModerationStatus = Literal["approved", "hold", "spam", "unspam", "trash", "untrash"]
ReviewListStatus = Literal["all", "hold", "approved", "spam", "trash"]
ReviewOrder = Literal["asc", "desc"]
ReviewOrderBy = Literal["date", "date_gmt", "id", "slug", "include", "product"]

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_optional_email(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Invalid email address format.")
    stripped = value.strip()
    if not stripped or not _EMAIL_PATTERN.fullmatch(stripped):
        raise ValueError("Invalid email address format.")
    return stripped


class ProductReviewCreate(BaseModel):
    """Request schema for creating a WooCommerce product review."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "product_id": 22,
                "review": "Nice album!",
                "reviewer": "John Doe",
                "reviewer_email": "john.doe@example.com",
                "rating": 5,
            }
        },
    )

    product_id: int = Field(..., ge=1, description="ID of the product being reviewed.")
    review: str = Field(..., min_length=1, description="Review content.")
    reviewer: str | None = Field(default=None, description="Reviewer name.")
    reviewer_email: str | None = Field(default=None, description="Reviewer email address.")
    rating: int | None = Field(default=None, ge=0, le=5, description="Review rating (0 to 5).")
    status: ReviewModerationStatus = Field(
        default="approved",
        description="Review moderation status.",
    )

    @field_validator("review", mode="before")
    @classmethod
    def strip_review(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("reviewer_email", mode="before")
    @classmethod
    def validate_email(cls, value: object) -> str | None:
        return _validate_optional_email(value)


class ProductReviewUpdate(BaseModel):
    """Request schema for updating a WooCommerce product review."""

    model_config = ConfigDict(extra="forbid")

    product_id: int | None = Field(default=None, ge=1, description="Product ID.")
    status: ReviewModerationStatus | None = Field(default=None, description="Moderation status.")
    reviewer: str | None = Field(default=None, description="Reviewer name.")
    reviewer_email: str | None = Field(default=None, description="Reviewer email address.")
    review: str | None = Field(default=None, min_length=1, description="Review content.")
    rating: int | None = Field(default=None, ge=0, le=5, description="Review rating (0 to 5).")

    @field_validator("review", mode="before")
    @classmethod
    def strip_review(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("reviewer_email", mode="before")
    @classmethod
    def validate_email(cls, value: object) -> str | None:
        return _validate_optional_email(value)

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "ProductReviewUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        return self


class ProductReviewBatchUpdate(ProductReviewUpdate):
    """Batch update item containing review ID and editable fields."""

    id: int = Field(..., ge=1, description="Existing review ID to update.")


class ProductReviewBatchRequest(BaseModel):
    """Batch create, update, and delete request for product reviews (max 100 total)."""

    model_config = ConfigDict(extra="forbid")

    create: list[ProductReviewCreate] = Field(default_factory=list)
    update: list[ProductReviewBatchUpdate] = Field(default_factory=list)
    delete: list[int] = Field(default_factory=list)

    @field_validator("delete")
    @classmethod
    def validate_delete_ids(cls, values: list[int]) -> list[int]:
        for item_id in values:
            if item_id < 1:
                raise ValueError("All delete IDs must be positive integers.")
        return values

    @model_validator(mode="after")
    def validate_batch_totals(self) -> "ProductReviewBatchRequest":
        total = len(self.create) + len(self.update) + len(self.delete)
        if total == 0:
            raise ValueError("Provide at least one item in 'create', 'update', or 'delete'.")
        if total > 100:
            raise ValueError(
                f"Batch request exceeds WooCommerce limit of 100 total objects (got {total})."
            )
        return self


class ProductReviewResponse(BaseModel):
    """Validated WooCommerce product review resource."""

    model_config = ConfigDict(extra="ignore")

    id: int
    date_created: datetime
    date_created_gmt: datetime
    product_id: int
    status: str
    reviewer: str = ""
    reviewer_email: str = ""
    review: str = ""
    rating: int = 0
    verified: bool = False
    reviewer_avatar_urls: dict[str, str] | None = None

    @field_validator("reviewer", "reviewer_email", "review", mode="before")
    @classmethod
    def coerce_none_to_empty(cls, value: object) -> object:
        return "" if value is None else value


class ProductReviewDeleteResponse(BaseModel):
    """Response returned by WooCommerce after deleting a product review."""

    model_config = ConfigDict(extra="ignore")

    deleted: bool
    previous: ProductReviewResponse


class BatchReviewError(BaseModel):
    """Per-item error returned by WooCommerce batch endpoints."""

    model_config = ConfigDict(extra="ignore")

    id: int = 0
    error: dict[str, object]


class ProductReviewBatchResponse(BaseModel):
    """Response schema for batch product review operations."""

    model_config = ConfigDict(extra="ignore")

    create: list[ProductReviewResponse | BatchReviewError] = Field(default_factory=list)
    update: list[ProductReviewResponse | BatchReviewError] = Field(default_factory=list)
    delete: list[ProductReviewResponse | BatchReviewError | ProductReviewDeleteResponse] = Field(
        default_factory=list
    )


class ReviewListQueryParams(BaseModel):
    """Documented query parameters for listing product reviews."""

    model_config = ConfigDict(extra="forbid")

    context: Literal["view", "edit"] = "view"
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=100)
    search: str | None = None
    after: datetime | None = None
    before: datetime | None = None
    dates_are_gmt: bool | None = None
    exclude: list[int] | None = None
    include: list[int] | None = None
    offset: int | None = Field(default=None, ge=0)
    order: ReviewOrder = "desc"
    orderby: ReviewOrderBy = "date_gmt"
    reviewer: list[int] | None = None
    reviewer_exclude: list[int] | None = None
    reviewer_email: list[str] | None = None
    product: list[int] | None = None
    status: ReviewListStatus = "approved"

    @field_validator("exclude", "include", "reviewer", "reviewer_exclude", "product")
    @classmethod
    def validate_id_lists(cls, values: list[int] | None) -> list[int] | None:
        if values is not None:
            for item_id in values:
                if item_id < 1:
                    raise ValueError("Filter IDs must be positive integers.")
        return values

    @field_validator("reviewer_email")
    @classmethod
    def validate_email_list(cls, values: list[str] | None) -> list[str] | None:
        if values is not None:
            return [_validate_optional_email(email) or "" for email in values]
        return None

    def to_woo_params(self) -> dict[str, object]:
        params: dict[str, object] = {
            "context": self.context,
            "page": self.page,
            "per_page": self.per_page,
            "order": self.order,
            "orderby": self.orderby,
            "status": self.status,
        }
        if self.search is not None:
            params["search"] = self.search
        if self.after is not None:
            params["after"] = self.after.isoformat()
        if self.before is not None:
            params["before"] = self.before.isoformat()
        if self.dates_are_gmt is not None:
            params["dates_are_gmt"] = str(self.dates_are_gmt).lower()
        if self.exclude:
            params["exclude"] = ",".join(str(i) for i in self.exclude)
        if self.include:
            params["include"] = ",".join(str(i) for i in self.include)
        if self.offset is not None:
            params["offset"] = self.offset
        if self.reviewer:
            params["reviewer"] = ",".join(str(i) for i in self.reviewer)
        if self.reviewer_exclude:
            params["reviewer_exclude"] = ",".join(str(i) for i in self.reviewer_exclude)
        if self.reviewer_email:
            params["reviewer_email"] = ",".join(self.reviewer_email)
        if self.product:
            params["product"] = ",".join(str(i) for i in self.product)
        return params
