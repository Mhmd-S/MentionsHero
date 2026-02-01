"""Folder management API routes."""

from fastapi import APIRouter, HTTPException
from postgrest.exceptions import APIError

from backend.models.folder import Folder, FolderCreate, FolderUpdate
from backend.services import folder_service

router = APIRouter(prefix="/api/folders", tags=["folders"])


@router.get("")
async def list_folders() -> list[Folder]:
    """List all folders."""
    folders = await folder_service.get_all_folders()
    return folders


@router.post("")
async def create_folder(request: FolderCreate) -> Folder:
    """Create a new folder."""
    if not request.name or not request.name.strip():
        raise HTTPException(status_code=400, detail="Folder name is required")

    try:
        folder = await folder_service.create_folder(
            name=request.name,
            parent_id=request.parent_id
        )
        return folder
    except APIError as e:
        error_info = e.args[0] if e.args else {}
        if isinstance(error_info, dict) and error_info.get("code") == "23505":
            raise HTTPException(
                status_code=409,
                detail="A folder with this name already exists in this location"
            )
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{folder_id}")
async def update_folder(folder_id: str, request: FolderUpdate) -> Folder:
    """Update a folder."""
    if request.name is not None and not request.name.strip():
        raise HTTPException(status_code=400, detail="Folder name cannot be empty")

    if request.parent_id == folder_id:
        raise HTTPException(status_code=400, detail="Cannot move a folder into itself")

    try:
        folder = await folder_service.update_folder(
            folder_id=folder_id,
            name=request.name,
            parent_id=request.parent_id
        )
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")
        return folder
    except APIError as e:
        error_info = e.args[0] if e.args else {}
        if isinstance(error_info, dict) and error_info.get("code") == "23505":
            raise HTTPException(
                status_code=409,
                detail="A folder with this name already exists in this location"
            )
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{folder_id}")
async def delete_folder(folder_id: str) -> dict:
    """Delete a folder and move its contents to the parent."""
    success = await folder_service.delete_folder(folder_id)
    if not success:
        raise HTTPException(status_code=404, detail="Folder not found")
    return {"success": True}
