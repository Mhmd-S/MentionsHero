"""Folder service for database operations."""

from typing import Any
from datetime import datetime, timezone

from backend.core.database import get_supabase, get_folder_ids_in_tree


async def get_all_folders() -> list[dict[str, Any]]:
    """Fetch all folders from the database."""
    supabase = get_supabase()
    response = supabase.table("folders").select("*").order("name", desc=False).execute()
    return response.data if response.data else []


async def get_folder_by_id(folder_id: str) -> dict[str, Any] | None:
    """Fetch a single folder by ID."""
    supabase = get_supabase()
    response = (
        supabase.table("folders")
        .select("*")
        .eq("id", folder_id)
        .single()
        .execute()
    )
    return response.data


async def create_folder(name: str, parent_id: str | None = None) -> dict[str, Any]:
    """Create a new folder."""
    supabase = get_supabase()
    response = (
        supabase.table("folders")
        .insert({
            "name": name.strip(),
            "parent_id": parent_id
        })
        .select()
        .single()
        .execute()
    )
    return response.data


async def update_folder(
    folder_id: str,
    name: str | None = None,
    parent_id: str | None = None
) -> dict[str, Any] | None:
    """Update a folder."""
    supabase = get_supabase()

    updates: dict[str, Any] = {
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    if name is not None:
        updates["name"] = name.strip()

    if parent_id is not None:
        updates["parent_id"] = parent_id

    response = (
        supabase.table("folders")
        .update(updates)
        .eq("id", folder_id)
        .select()
        .single()
        .execute()
    )
    return response.data


async def delete_folder(folder_id: str) -> bool:
    """
    Delete a folder and move its children to the parent folder.

    Returns True if successful.
    """
    supabase = get_supabase()

    # Get the folder to find its parent
    folder_response = (
        supabase.table("folders")
        .select("parent_id")
        .eq("id", folder_id)
        .single()
        .execute()
    )

    if not folder_response.data:
        return False

    parent_id = folder_response.data.get("parent_id")

    # Move all child folders to the parent
    supabase.table("folders").update({
        "parent_id": parent_id,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }).eq("parent_id", folder_id).execute()

    # Move all transcripts in this folder to the parent
    supabase.table("transcripts").update({
        "folder_id": parent_id
    }).eq("folder_id", folder_id).execute()

    # Delete the folder
    supabase.table("folders").delete().eq("id", folder_id).execute()

    return True


async def get_folder_descendants(folder_id: str) -> list[str]:
    """Get all descendant folder IDs for a folder."""
    folders = await get_all_folders()
    return get_folder_ids_in_tree(folder_id, folders)
