"""Folder-related Pydantic models."""

from datetime import datetime

from pydantic import BaseModel


class Folder(BaseModel):
    """Folder model."""
    id: str
    name: str
    parent_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class FolderCreate(BaseModel):
    """Request model for creating a folder."""
    name: str
    parent_id: str | None = None


class FolderUpdate(BaseModel):
    """Request model for updating a folder."""
    name: str | None = None
    parent_id: str | None = None
