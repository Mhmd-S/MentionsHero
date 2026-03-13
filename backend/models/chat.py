"""Chat-related Pydantic models."""

from pydantic import BaseModel


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    title: str | None = None


class UpdateConversationRequest(BaseModel):
    """Request to update a conversation."""
    title: str
