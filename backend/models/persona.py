"""Persona-related Pydantic models."""

from datetime import datetime

from pydantic import BaseModel


class PersonaAlias(BaseModel):
    """Persona alias model."""
    id: str
    persona_id: str
    alias: str
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class Persona(BaseModel):
    """Persona model with aliases."""
    id: str
    name: str
    description: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    aliases: list[str] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class PersonaCreate(BaseModel):
    """Request model for creating a persona."""
    name: str
    description: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    aliases: list[str] = []


class PersonaUpdate(BaseModel):
    """Request model for updating a persona."""
    name: str | None = None
    description: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None


class AddAliasesRequest(BaseModel):
    """Request model for adding aliases to a persona."""
    aliases: list[str]


class RemoveAliasesRequest(BaseModel):
    """Request model for removing aliases from a persona."""
    aliases: list[str]
