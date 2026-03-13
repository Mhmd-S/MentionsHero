"""Chat API routes for AI agent conversations."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.models.chat import (
    CreateConversationRequest,
    SendMessageRequest,
    UpdateConversationRequest,
)
from backend.services import chat_service, agent_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/conversations")
async def list_conversations():
    """List all conversations."""
    return await chat_service.list_conversations()


@router.post("/conversations")
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation."""
    return await chat_service.create_conversation(title=request.title)


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a conversation with its messages."""
    conversation = await chat_service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = await chat_service.get_messages(conversation_id)
    return {**conversation, "messages": messages}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    deleted = await chat_service.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted"}


@router.patch("/conversations/{conversation_id}")
async def update_conversation(conversation_id: str, request: UpdateConversationRequest):
    """Update a conversation's title."""
    updated = await chat_service.update_conversation_title(conversation_id, request.title)
    if not updated:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return updated


@router.post("/conversations/{conversation_id}/messages")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """Send a message and stream the agent's response via SSE."""
    conversation = await chat_service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if not request.content.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    return StreamingResponse(
        agent_service.run_agent_stream(conversation_id, request.content),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
