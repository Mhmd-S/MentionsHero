"""Chat service for conversation and message persistence."""

from typing import Any
from datetime import datetime, timezone

from backend.core.database import get_supabase


async def create_conversation(title: str | None = None) -> dict[str, Any]:
    """Create a new conversation."""
    supabase = get_supabase()
    data: dict[str, Any] = {}
    if title:
        data["title"] = title
    response = supabase.table("chat_conversations").insert(data).execute()
    return response.data[0]


async def list_conversations(limit: int = 50) -> list[dict[str, Any]]:
    """List conversations ordered by most recently updated."""
    supabase = get_supabase()
    response = (
        supabase.table("chat_conversations")
        .select("*")
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


async def get_conversation(conversation_id: str) -> dict[str, Any] | None:
    """Get a single conversation by ID."""
    supabase = get_supabase()
    response = (
        supabase.table("chat_conversations")
        .select("*")
        .eq("id", conversation_id)
        .single()
        .execute()
    )
    return response.data


async def get_messages(conversation_id: str) -> list[dict[str, Any]]:
    """Get all messages for a conversation ordered by creation time."""
    supabase = get_supabase()
    response = (
        supabase.table("chat_messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
    )
    return response.data or []


async def add_message(
    conversation_id: str,
    role: str,
    content: str | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Add a message and update conversation's updated_at."""
    supabase = get_supabase()

    message_data: dict[str, Any] = {
        "conversation_id": conversation_id,
        "role": role,
    }
    if content is not None:
        message_data["content"] = content
    if tool_calls is not None:
        message_data["tool_calls"] = tool_calls

    msg_response = supabase.table("chat_messages").insert(message_data).execute()

    # Touch conversation updated_at
    supabase.table("chat_conversations").update(
        {"updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", conversation_id).execute()

    return msg_response.data[0]


async def delete_conversation(conversation_id: str) -> bool:
    """Delete a conversation and its messages (CASCADE)."""
    supabase = get_supabase()
    response = (
        supabase.table("chat_conversations")
        .delete()
        .eq("id", conversation_id)
        .execute()
    )
    return bool(response.data)


async def update_conversation_title(
    conversation_id: str, title: str
) -> dict[str, Any] | None:
    """Update a conversation's title."""
    supabase = get_supabase()
    response = (
        supabase.table("chat_conversations")
        .update({"title": title})
        .eq("id", conversation_id)
        .execute()
    )
    return response.data[0] if response.data else None
