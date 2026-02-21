"""
AI Agent chat endpoints.

POST /agent/chat              — Stream a chat response via SSE
GET  /agent/conversations     — List the user's conversations
GET  /agent/conversations/{id}/messages — Get messages for a conversation
DELETE /agent/conversations/{id}       — Delete a conversation
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.api_v1.dependencies.auth import get_current_active_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.schemas.ai_agent import (
    AgentChatRequest,
    ConversationMessageOut,
    ConversationSummary,
)
from app.services.ai_agent import get_agent_service
from app.services.ai_agent import conversation_store

logger = get_logger(__name__)

router = APIRouter()


@router.post("/chat")
async def agent_chat(
    body: AgentChatRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream an AI agent response via Server-Sent Events."""
    service = get_agent_service()

    # Get or create conversation
    conversation = await conversation_store.get_or_create_conversation(
        db, user_id=current_user.id, conversation_id=body.conversation_id,
    )

    # Persist the user message
    await conversation_store.add_message(
        db, conversation_id=conversation.id, role="user", content=body.message,
    )
    await db.commit()

    # Load conversation history for context
    history_rows = await conversation_store.get_history(db, conversation.id, limit=50)
    history = [
        {
            "role": m.role,
            "content": m.content,
            "tool_name": m.tool_name,
            "tool_args": m.tool_args,
            "tool_result": m.tool_result,
        }
        for m in history_rows
    ]

    async def event_stream():
        full_response = ""
        try:
            async for event in service.stream_response(
                user_message=body.message,
                conversation_id=conversation.id,
                conversation_history=history[:-1],  # exclude the message we just stored
                user=current_user,
                db=db,
            ):
                # Extract response text from done event to persist
                if '"response_text"' in event:
                    import json as _json
                    try:
                        line = event.split("data: ", 1)[1].split("\n")[0]
                        data = _json.loads(line)
                        full_response = data.get("response_text", "")
                    except Exception:
                        pass
                yield event
        except Exception as exc:
            logger.error("SSE stream error: %s", exc, exc_info=True)
            import json as _json
            yield f"event: error\ndata: {_json.dumps({'code': 'STREAM_ERROR', 'message': str(exc)[:200]})}\n\n"
        finally:
            # Persist assistant response
            if full_response:
                try:
                    await conversation_store.add_message(
                        db, conversation_id=conversation.id,
                        role="assistant", content=full_response,
                    )
                    await db.commit()
                except Exception as exc:
                    logger.error("Failed to persist assistant message: %s", exc)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    """List the authenticated user's AI conversations."""
    return await conversation_store.list_conversations(
        db, user_id=current_user.id, limit=limit, offset=offset,
    )


@router.get("/conversations/{conversation_id}/messages",
            response_model=list[ConversationMessageOut])
async def get_conversation_messages(
    conversation_id: int,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 100,
):
    """Get messages for a specific conversation."""
    # Verify ownership
    from app.models.ai_conversations import AIConversation
    from sqlalchemy import select

    conv = (await db.execute(
        select(AIConversation).where(
            AIConversation.id == conversation_id,
            AIConversation.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Conversation not found")

    messages = await conversation_store.get_history(db, conversation_id, limit=limit)
    return [ConversationMessageOut.model_validate(m) for m in messages]


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: int,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation and all its messages."""
    deleted = await conversation_store.delete_conversation(
        db, conversation_id=conversation_id, user_id=current_user.id,
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Conversation not found")
    await db.commit()


@router.get("/widgets/{widget_name}")
async def get_widget_html(widget_name: str) -> Response:
    """Serve a pre-built HTML widget bundle by name.

    No auth required — widget HTML is static and data is injected
    client-side via postMessage after loading.
    """
    from app.mcp.chatgpt import load_widget_html

    html = load_widget_html(widget_name)
    if not html:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget not found",
        )
    return Response(
        content=html,
        media_type="text/html",
        headers={"Cache-Control": "public, max-age=3600"},
    )
