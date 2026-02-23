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
    aliases: list[str] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class PublicPersona(BaseModel):
    """Persona as exposed to public clients."""
    id: str
    name: str
    slug: str | None = None
    image_url: str | None = None
    description: str | None = None
    transcript_count: int = 0


class PublicPersonaTranscript(BaseModel):
    """Transcript metadata for public persona detail page (no full text)."""
    id: str
    name: str | None = None
    youtube_url: str | None = None
    upload_date: str | None = None
    created_at: datetime | None = None


class PublicPersonaDetail(BaseModel):
    """Full persona detail for public viewers."""
    id: str
    name: str
    slug: str | None = None
    image_url: str | None = None
    description: str | None = None
    transcripts: list[PublicPersonaTranscript] = []


class PersonaCreate(BaseModel):
    """Request model for creating a persona."""
    name: str
    description: str | None = None
    aliases: list[str] = []
    slug: str | None = None
    image_url: str | None = None


class PersonaUpdate(BaseModel):
    """Request model for updating a persona."""
    name: str | None = None
    description: str | None = None
    slug: str | None = None
    image_url: str | None = None


class AddAliasesRequest(BaseModel):
    """Request model for adding aliases to a persona."""
    aliases: list[str]


class RemoveAliasesRequest(BaseModel):
    """Request model for removing aliases from a persona."""
    aliases: list[str]
