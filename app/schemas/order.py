from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

OrderStatus = Literal[
    "pending",
    "processing",
    "on-hold",
    "completed",
    "cancelled",
    "refunded",
    "failed",
    "draft",
    "checkout-draft",
]


class Order(BaseModel):
    """Validated WooCommerce order representation for Task 4."""

    model_config = ConfigDict(extra="ignore")

    order_id: int
    customer_name: str = ""
    customer_email: str = ""
    order_date: str = ""
    order_status: str
    product_names: list[str] = Field(default_factory=list)
    total_order_amount: str = "0.00"

    @model_validator(mode="before")
    @classmethod
    def extract_woocommerce_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        if "order_id" in data:
            return data

        billing = data.get("billing")
        if not isinstance(billing, dict):
            billing = {}

        first_name = str(billing.get("first_name") or "").strip()
        last_name = str(billing.get("last_name") or "").strip()
        customer_name = " ".join(part for part in (first_name, last_name) if part)

        line_items = data.get("line_items")
        product_names: list[str] = []
        if isinstance(line_items, list):
            for item in line_items:
                if isinstance(item, dict) and item.get("name"):
                    product_names.append(str(item["name"]))

        return {
            "order_id": data.get("id"),
            "customer_name": customer_name,
            "customer_email": str(billing.get("email") or "").strip(),
            "order_date": str(data.get("date_created") or ""),
            "order_status": data.get("status"),
            "product_names": product_names,
            "total_order_amount": str(data.get("total") or "0.00"),
        }
