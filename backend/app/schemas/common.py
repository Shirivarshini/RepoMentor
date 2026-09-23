"""Shared response schemas. Mirrors API_CONTRACT.md."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
