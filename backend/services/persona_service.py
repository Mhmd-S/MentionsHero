"""Persona service for database operations."""

from typing import Any
from datetime import datetime, timezone

from backend.core.database import get_supabase, get_folder_ids_in_tree


async def get_all_personas() -> list[dict[str, Any]]:
    """Fetch all personas with their aliases."""
    supabase = get_supabase()

    # Get all personas
    personas_response = supabase.table("personas").select("*").order("name").execute()
    personas = personas_response.data if personas_response.data else []

    if not personas:
        return []

    # Get all aliases
    aliases_response = supabase.table("persona_aliases").select("*").execute()
    aliases = aliases_response.data if aliases_response.data else []

    # Group aliases by persona_id
    aliases_by_persona: dict[str, list[str]] = {}
    for alias in aliases:
        pid = alias["persona_id"]
        if pid not in aliases_by_persona:
            aliases_by_persona[pid] = []
        aliases_by_persona[pid].append(alias["alias"])

    # Attach aliases to personas
    for persona in personas:
        persona["aliases"] = aliases_by_persona.get(persona["id"], [])

    return personas


async def get_persona_by_id(persona_id: str) -> dict[str, Any] | None:
    """Fetch a single persona by ID with its aliases."""
    supabase = get_supabase()

    persona_response = (
        supabase.table("personas")
        .select("*")
        .eq("id", persona_id)
        .single()
        .execute()
    )

    if not persona_response.data:
        return None

    persona = persona_response.data

    # Get aliases for this persona
    aliases_response = (
        supabase.table("persona_aliases")
        .select("alias")
        .eq("persona_id", persona_id)
        .execute()
    )

    persona["aliases"] = [a["alias"] for a in (aliases_response.data or [])]
    return persona


async def create_persona(
    name: str,
    description: str | None = None,
    aliases: list[str] | None = None
) -> dict[str, Any]:
    """Create a new persona with optional aliases."""
    supabase = get_supabase()

    # Create the persona
    insert_data = {
        "name": name.strip(),
    }
    if description and description.strip():
        insert_data["description"] = description.strip()

    persona_response = (
        supabase.table("personas")
        .insert(insert_data)
        .execute()
    )

    if not persona_response.data:
        raise ValueError(f"Failed to create persona: {persona_response}")

    persona = persona_response.data[0]
    persona["aliases"] = []

    # Add aliases if provided
    if aliases:
        unique_aliases = list(set(a.strip() for a in aliases if a.strip()))
        if unique_aliases:
            alias_records = [
                {"persona_id": persona["id"], "alias": alias}
                for alias in unique_aliases
            ]
            supabase.table("persona_aliases").insert(alias_records).execute()
            persona["aliases"] = unique_aliases

    return persona


async def update_persona(
    persona_id: str,
    name: str | None = None,
    description: str | None = None,
) -> dict[str, Any] | None:
    """Update a persona's name and/or description."""
    supabase = get_supabase()

    updates: dict[str, Any] = {
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    if name is not None:
        updates["name"] = name.strip()

    if description is not None:
        updates["description"] = description.strip() if description else None

    response = (
        supabase.table("personas")
        .update(updates)
        .eq("id", persona_id)
        .execute()
    )

    if not response.data:
        return None

    # Get aliases
    aliases_response = (
        supabase.table("persona_aliases")
        .select("alias")
        .eq("persona_id", persona_id)
        .execute()
    )

    persona = response.data[0]
    persona["aliases"] = [a["alias"] for a in (aliases_response.data or [])]
    return persona


async def delete_persona(persona_id: str) -> bool:
    """Delete a persona (aliases cascade automatically)."""
    supabase = get_supabase()

    # Check if persona exists
    check = (
        supabase.table("personas")
        .select("id")
        .eq("id", persona_id)
        .single()
        .execute()
    )

    if not check.data:
        return False

    # Delete (aliases will cascade)
    supabase.table("personas").delete().eq("id", persona_id).execute()
    return True


async def add_aliases(persona_id: str, aliases: list[str]) -> dict[str, Any] | None:
    """Add aliases to a persona."""
    supabase = get_supabase()

    # Check if persona exists
    persona = await get_persona_by_id(persona_id)
    if not persona:
        return None

    # Filter out duplicates and empty strings
    unique_aliases = list(set(a.strip() for a in aliases if a.strip()))
    existing = set(persona["aliases"])
    new_aliases = [a for a in unique_aliases if a not in existing]

    if new_aliases:
        alias_records = [
            {"persona_id": persona_id, "alias": alias}
            for alias in new_aliases
        ]
        supabase.table("persona_aliases").insert(alias_records).execute()

    # Return updated persona
    return await get_persona_by_id(persona_id)


async def remove_aliases(persona_id: str, aliases: list[str]) -> dict[str, Any] | None:
    """Remove aliases from a persona."""
    supabase = get_supabase()

    # Check if persona exists
    persona = await get_persona_by_id(persona_id)
    if not persona:
        return None

    if aliases:
        # Remove specified aliases
        supabase.table("persona_aliases").delete().eq(
            "persona_id", persona_id
        ).in_("alias", aliases).execute()

    # Return updated persona
    return await get_persona_by_id(persona_id)


async def get_all_aliases() -> dict[str, str]:
    """Get a mapping of all aliases to their persona IDs."""
    supabase = get_supabase()

    response = supabase.table("persona_aliases").select("alias, persona_id").execute()
    aliases = response.data if response.data else []

    return {a["alias"]: a["persona_id"] for a in aliases}


async def get_transcripts_for_persona(
    persona_id: str,
    folder_id: str | None = None
) -> list[dict[str, Any]]:
    """Find transcripts containing any of the persona's aliases."""
    supabase = get_supabase()

    # Get persona aliases
    persona = await get_persona_by_id(persona_id)
    if not persona or not persona["aliases"]:
        print(f"[get_transcripts_for_persona] No persona or no aliases for persona_id={persona_id}")
        return []

    aliases = persona["aliases"]
    print(f"[get_transcripts_for_persona] persona_id={persona_id}, aliases={aliases}")

    # Get transcripts
    query = supabase.table("transcripts").select("id, name, youtube_url, created_at, folder_id")

    if folder_id:
        # Get folder tree
        folders_response = supabase.table("folders").select("*").execute()
        folders = folders_response.data if folders_response.data else []
        folder_ids = get_folder_ids_in_tree(folder_id, folders)
        query = query.in_("folder_id", folder_ids)

    response = query.order("created_at", desc=True).execute()
    transcripts = response.data if response.data else []
    print(f"[get_transcripts_for_persona] Total transcripts to check: {len(transcripts)}")

    # Filter transcripts that contain any alias in transcript text
    # We need to fetch transcripts content to search
    matching = []
    for t in transcripts:
        # Get full transcript
        full = (
            supabase.table("transcripts")
            .select("transcript")
            .eq("id", t["id"])
            .single()
            .execute()
        )
        if full.data:
            text = full.data.get("transcript", "").lower()
            for alias in aliases:
                if alias.lower() in text:
                    matching.append(t)
                    break

    print(f"[get_transcripts_for_persona] Matching transcripts: {len(matching)}")
    return matching
