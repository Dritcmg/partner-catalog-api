"""Public API contract. Synthetic organization names, no personal identifiers."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

PartnerCode = Annotated[
    str,
    StringConstraints(strict=True, min_length=3, max_length=32, pattern=r"^[A-Z0-9][A-Z0-9_-]+$"),
]
DisplayName = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=3, max_length=120)
]
Category = Literal["originator", "investor", "servicer"]


class PartnerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    code: PartnerCode
    display_name: DisplayName
    category: Category
    active: bool = True


class PartnerPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    code: PartnerCode | None = None
    display_name: DisplayName | None = None
    category: Category | None = None
    active: bool | None = None

    @model_validator(mode="after")
    def at_least_one_non_null_field(self) -> "PartnerPatch":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Explicit null is not accepted for partner fields")
        return self


class PartnerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    display_name: str
    category: Category
    active: bool
    created_at: str


class PartnerPage(BaseModel):
    items: list[PartnerRead]
    total: int
    limit: int
    offset: int
