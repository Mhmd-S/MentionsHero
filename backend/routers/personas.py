"""Persona management API routes."""

from fastapi import APIRouter, HTTPException
from postgrest.exceptions import APIError

from backend.models.persona import (
    Persona,
    PersonaCreate,
    PersonaUpdate,
    AddAliasesRequest,
    RemoveAliasesRequest,
)
from backend.services import persona_service

router = APIRouter(prefix="/api/personas", tags=["personas"])


@router.get("")
async def list_personas() -> list[Persona]:
    """List all personas with their aliases."""
    personas = await persona_service.get_all_personas()
    return personas


@router.get("/{persona_id}")
async def get_persona(persona_id: str) -> Persona:
    """Get a single persona by ID."""
    persona = await persona_service.get_persona_by_id(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    return persona


@router.post("")
async def create_persona(request: PersonaCreate) -> Persona:
    """Create a new persona."""
    if not request.name or not request.name.strip():
        raise HTTPException(status_code=400, detail="Persona name is required")

    try:
        persona = await persona_service.create_persona(
            name=request.name,
            description=request.description,
            aliases=request.aliases
        )
        return persona
    except APIError as e:
        error_info = e.args[0] if e.args else {}
        if isinstance(error_info, dict) and error_info.get("code") == "23505":
            raise HTTPException(
                status_code=409,
                detail="An alias already exists for another persona"
            )
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{persona_id}")
async def update_persona(persona_id: str, request: PersonaUpdate) -> Persona:
    """Update a persona's name and/or description."""
    if request.name is not None and not request.name.strip():
        raise HTTPException(status_code=400, detail="Persona name cannot be empty")

    try:
        persona = await persona_service.update_persona(
            persona_id=persona_id,
            name=request.name,
            description=request.description
        )
        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found")
        return persona
    except APIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{persona_id}")
async def delete_persona(persona_id: str) -> dict:
    """Delete a persona and all its aliases."""
    success = await persona_service.delete_persona(persona_id)
    if not success:
        raise HTTPException(status_code=404, detail="Persona not found")
    return {"success": True}


@router.post("/{persona_id}/aliases")
async def add_aliases(persona_id: str, request: AddAliasesRequest) -> Persona:
    """Add aliases to a persona."""
    if not request.aliases:
        raise HTTPException(status_code=400, detail="At least one alias is required")

    try:
        persona = await persona_service.add_aliases(persona_id, request.aliases)
        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found")
        return persona
    except APIError as e:
        error_info = e.args[0] if e.args else {}
        if isinstance(error_info, dict) and error_info.get("code") == "23505":
            raise HTTPException(
                status_code=409,
                detail="An alias already exists for another persona"
            )
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{persona_id}/aliases")
async def remove_aliases(persona_id: str, request: RemoveAliasesRequest) -> Persona:
    """Remove aliases from a persona."""
    if not request.aliases:
        raise HTTPException(status_code=400, detail="At least one alias is required")

    persona = await persona_service.remove_aliases(persona_id, request.aliases)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    return persona


@router.get("/{persona_id}/transcripts")
async def get_persona_transcripts(
    persona_id: str,
    folder_id: str | None = None
) -> list[dict]:
    """Get transcripts containing any of the persona's aliases."""
    persona = await persona_service.get_persona_by_id(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    transcripts = await persona_service.get_transcripts_for_persona(
        persona_id, folder_id
    )
    return transcripts
