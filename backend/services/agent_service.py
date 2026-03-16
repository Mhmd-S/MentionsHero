"""Agent service — Gemini agent loop with SSE streaming."""

import asyncio
import json
import logging
import uuid
from typing import Any, AsyncGenerator

from google import genai
from google.genai import types

from backend.config import get_settings
from backend.services import chat_service
from backend.services.agent_tools import TOOL_DECLARATIONS, execute_tool

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI analyst for MentionsHero, a platform that analyzes press briefing transcripts and tracks prediction markets (Kalshi & Polymarket) tied to speaker mentions.

## Your tools

**Lookup & navigation:**
- search_folders — find a folder by name (e.g. "PMQ", "White House")
- search_personas — find a persona by name or alias (e.g. "Keir Starmer", "Trump")
- list_folders — list all folders
- list_personas — list all personas with aliases
- get_persona — get persona details by ID

**Transcript access:**
- list_transcripts — list transcripts in a folder (sorted by date, metadata only)
- get_transcript_content — read a transcript's actual text content
- list_speakers — list speakers across transcripts

**Term analysis:**
- search_term — frequency, trend, per-date breakdown for a term
- search_term_in_context — find a term with surrounding text snippets
- get_top_terms — discover most frequent terms
- get_ngrams — extract common multi-word phrases

**Markets:**
- search_polymarket — search Polymarket events by keyword
- get_polymarket_event — get event detail with optional persona mention analysis
- browse_kalshi_events — browse open Kalshi Mentions events
- get_kalshi_event — get Kalshi event detail with optional persona mention analysis

## How to handle questions

Always use tools to get real data before responding. Never say "I cannot" without first trying to look up the information.

**When a user mentions a person, folder, or market:**
1. Resolve names first: search_personas for people, search_folders for folders
2. Gather data: list_transcripts to find relevant transcripts, get_transcript_content to read them
3. Connect to markets: search_polymarket or browse_kalshi_events
4. Synthesize: combine transcript content with market data for an analytical answer

**When asked about market implications of a transcript:**
1. Find and read the transcript content
2. Identify the key topics, statements, and notable language
3. Find the relevant market and get current prices
4. Use get_polymarket_event or get_kalshi_event with persona_id to get historical mention analysis
5. Offer your analytical assessment grounded in the data

**When asked "latest" or "most recent":**
Use list_transcripts with sort="latest" and limit=1 to find it.

## Important behaviors
- Cite specific numbers from tool results (mention counts, prices, dates, percentages)
- When providing market analysis, be analytical — connect transcript content to market pricing
- You have a budget of 10 tool calls per turn. Plan your tool use efficiently
- If no folder is specified, search across all transcripts
- Keep responses concise and data-driven"""

MAX_HISTORY_MESSAGES = 20
MAX_TOOL_LOOPS = 10


def _format_sse(event: str, data: dict[str, Any]) -> str:
    """Format an SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _build_contents_from_history(messages: list[dict[str, Any]]) -> list[types.Content]:
    """Convert stored messages into Gemini Content objects."""
    contents: list[types.Content] = []

    for msg in messages:
        role = msg["role"]

        if role == "user":
            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_text(text=msg.get("content") or "")],
            ))
        elif role == "assistant":
            parts: list[types.Part] = []
            tool_calls = msg.get("tool_calls") or []

            # Add function call parts and their responses
            for tc in tool_calls:
                # The model's function call
                parts.append(types.Part(function_call=types.FunctionCall(
                    name=tc["name"],
                    args=tc.get("args", {}),
                )))

            # Add text part if present
            text = msg.get("content") or ""
            if text:
                parts.append(types.Part.from_text(text=text))

            if parts:
                contents.append(types.Content(role="model", parts=parts))

            # Add function responses as separate user-role content
            # (Gemini expects function responses in a user turn)
            response_parts = []
            for tc in tool_calls:
                if "result" in tc:
                    response_parts.append(types.Part(function_response=types.FunctionResponse(
                        name=tc["name"],
                        response=tc["result"] if isinstance(tc["result"], dict) else {"data": tc["result"]},
                    )))
            if response_parts:
                contents.append(types.Content(role="user", parts=response_parts))

    return contents


async def run_agent_stream(
    conversation_id: str,
    user_message: str,
) -> AsyncGenerator[str, None]:
    """Run the agent loop and yield SSE events."""
    logger.info(f"run_agent_stream START: conversation_id={conversation_id}, message={user_message[:100]!r}")

    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    logger.info("Gemini client created")

    # Load conversation history (limited)
    history = await chat_service.get_messages(conversation_id)
    history = history[-MAX_HISTORY_MESSAGES:]
    logger.info(f"Loaded {len(history)} history messages")

    # Build Gemini contents from history
    contents = _build_contents_from_history(history)
    logger.info(f"Built {len(contents)} content blocks from history")

    # Add new user message
    contents.append(types.Content(
        role="user",
        parts=[types.Part.from_text(text=user_message)],
    ))

    # Save user message to DB
    await chat_service.add_message(conversation_id, "user", content=user_message)
    logger.info("User message saved to DB")

    # Agent loop: call Gemini, handle tool calls, repeat
    all_tool_calls: list[dict[str, Any]] = []
    final_text = ""
    loop = asyncio.get_event_loop()

    for iteration in range(MAX_TOOL_LOOPS):
        logger.info(f"Agent loop iteration {iteration + 1}/{MAX_TOOL_LOOPS}")
        try:
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=[TOOL_DECLARATIONS],
            )

            logger.info("Calling Gemini API...")
            response = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=contents,
                    config=config,
                ),
            )
            logger.info("Gemini API responded")
        except Exception as e:
            logger.error(f"Gemini API error: {e}", exc_info=True)
            yield _format_sse("error", {"message": f"AI model error: {str(e)}"})
            return

        if not response.candidates:
            logger.warning(f"No candidates in response. Prompt feedback: {response.prompt_feedback}")
            yield _format_sse("error", {"message": "No response from AI model"})
            return

        candidate = response.candidates[0]
        logger.info(f"Candidate finish_reason: {candidate.finish_reason}")
        parts = candidate.content.parts if candidate.content else []
        logger.info(f"Response parts: {len(parts)} (types: {[('function_call' if p.function_call else 'text') for p in parts]})")

        # Check for function calls
        function_calls = [p for p in parts if p.function_call]
        text_parts = [p for p in parts if p.text]

        if function_calls:
            # Execute each function call
            model_parts = []
            response_parts = []

            for part in function_calls:
                fc = part.function_call
                call_id = str(uuid.uuid4())[:8]
                args = dict(fc.args) if fc.args else {}

                logger.info(f"Tool call: {fc.name}({args})")

                # Yield tool_call_start
                yield _format_sse("tool_call_start", {
                    "id": call_id,
                    "name": fc.name,
                    "args": args,
                })

                # Execute the tool
                result = await execute_tool(fc.name, args)
                logger.info(f"Tool {fc.name} returned ({type(result).__name__})")

                # Yield tool_call_result
                yield _format_sse("tool_call_result", {
                    "id": call_id,
                    "name": fc.name,
                    "result": result,
                })

                # Track for DB persistence
                all_tool_calls.append({
                    "id": call_id,
                    "name": fc.name,
                    "args": args,
                    "result": result,
                })

                # Build parts for next Gemini call
                model_parts.append(types.Part(function_call=types.FunctionCall(
                    name=fc.name,
                    args=args,
                )))
                response_parts.append(types.Part(function_response=types.FunctionResponse(
                    name=fc.name,
                    response=result if isinstance(result, dict) else {"data": result},
                )))

            # Append model's function calls to contents
            contents.append(types.Content(role="model", parts=model_parts))
            # Append function responses
            contents.append(types.Content(role="user", parts=response_parts))

            # Continue the loop — Gemini will process tool results
            continue

        # No function calls — we have the final text response
        if text_parts:
            final_text = "".join(p.text for p in text_parts)

        break

    # Stream the final text in chunks for perceived streaming
    logger.info(f"Final text length: {len(final_text)}, tool_calls: {len(all_tool_calls)}")
    if final_text:
        chunk_size = 20  # ~20 chars per chunk for smooth streaming
        for i in range(0, len(final_text), chunk_size):
            chunk = final_text[i : i + chunk_size]
            yield _format_sse("text_delta", {"text": chunk})
            await asyncio.sleep(0.02)  # Small delay for smooth streaming feel

    # Save assistant message to DB
    saved_msg = await chat_service.add_message(
        conversation_id,
        "assistant",
        content=final_text or None,
        tool_calls=all_tool_calls if all_tool_calls else None,
    )
    logger.info(f"Assistant message saved: {saved_msg['id']}")

    yield _format_sse("done", {"message_id": saved_msg["id"]})
    logger.info("run_agent_stream DONE")
