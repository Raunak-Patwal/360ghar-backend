"""Pydantic schemas for the AI Agent chat feature."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    """Request body for the agent chat endpoint."""

    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[int] = None


class ConversationSummary(BaseModel):
    """Summary of a conversation for listing."""

    id: int
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class ConversationMessageOut(BaseModel):
    """A single message in a conversation."""

    id: int
    role: str
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[dict[str, Any]] = None
    tool_result: Optional[dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}
