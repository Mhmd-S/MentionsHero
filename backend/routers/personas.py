"""Persona management API routes."""

import io
import re
import zipfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from postgrest.exceptions import APIError

from backend.core.database import get_supabase
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
            meta_title=request.meta_title,
            meta_description=request.meta_description,
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
            slug=request.slug,
            description=request.description,
            meta_title=request.meta_title,
            meta_description=request.meta_description,
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


@router.get("/{persona_id}/transcripts/download")
async def download_persona_transcripts(persona_id: str):
    """Download all transcripts for a persona as a ZIP of .txt files."""
    persona = await persona_service.get_persona_by_id(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    transcripts = await persona_service.get_transcripts_for_persona(persona_id)
    if not transcripts:
        raise HTTPException(status_code=404, detail="No transcripts found for this persona")

    supabase = get_supabase()
    ids = [t["id"] for t in transcripts]
    rows = supabase.table("transcripts").select("id, name, upload_date, transcript").in_("id", ids).execute()
    full_map = {r["id"]: r for r in (rows.data or [])}

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for meta in transcripts:
            row = full_map.get(meta["id"])
            if not row or not row.get("transcript"):
                continue
            raw_name = meta.get("name") or meta["id"]
            safe_name = re.sub(r'[^\w\s\-.]', '_', raw_name).strip()[:80]
            date_prefix = meta.get("upload_date") or ""
            filename = f"{date_prefix}_{safe_name}.txt".lstrip("_")
            zf.writestr(filename, row["transcript"])

    buf.seek(0)
    persona_slug = re.sub(r'[^\w\-]', '_', persona["name"]).lower()
    zip_name = f"{persona_slug}_transcripts.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}"'},
    )


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
