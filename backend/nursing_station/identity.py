"""The authenticated caller, shared by every route module.

Extracted so :mod:`nursing_station.national_routes` can annotate its
dependencies with the real type instead of ``Any``. That is not cosmetic:
FastAPI resolves ``Annotated[Any, Depends(...)]`` as a query parameter, so an
``Any``-typed dependency turns every route into a 422.
"""

from __future__ import annotations

from pydantic import BaseModel


class CurrentUser(BaseModel):
    id: str
    tenant_id: str
    email: str
    name: str
    role: str
    ward_id: str | None
    facility_id: str | None
