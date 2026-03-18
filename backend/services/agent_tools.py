"""Agent tool definitions and executors for Gemini function calling."""

import json
import logging
from typing import Any

from google.genai import types

from backend.services import (
    folder_service,
    persona_service,
    speaker_service,
    transcript_service,
    kalshi_service,
    polymarket_service,
)
from backend.utils.nlp import (
    calculate_term_frequency,
    calculate_all_term_frequencies,
    extract_ngrams,
    search_term_in_context,
)

logger = logging.getLogger(__name__)


# --- Gemini Tool Declarations ---

TOOL_DECLARATIONS = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="search_term",
        description=(
            "Search for a term across press briefing transcripts. "
            "Returns frequency count, percentage of briefings mentioning it, "
            "trend direction (increasing/decreasing/stable), and per-date breakdown."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "term": types.Schema(type=types.Type.STRING, description="The term to search for"),
                "folder_id": types.Schema(type=types.Type.STRING, description="Optional folder ID to scope search to"),
                "speakers": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                    description="Optional speaker names to filter by",
                ),
            },
            required=["term"],
        ),
    ),
    types.FunctionDeclaration(
        name="search_term_in_context",
        description=(
            "Find a term in transcripts with surrounding context snippets. "
            "Returns matched text passages showing how the term was used."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "query": types.Schema(type=types.Type.STRING, description="The term or phrase to search for"),
                "folder_id": types.Schema(type=types.Type.STRING, description="Optional folder ID to scope search"),
                "speakers": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                    description="Optional speaker names to filter by",
                ),
                "context_chars": types.Schema(
                    type=types.Type.INTEGER,
                    description="Characters of context around each match (default 200)",
                ),
            },
            required=["query"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_top_terms",
        description=(
            "Get the most frequently used terms across transcripts, ranked by frequency. "
            "Useful for discovering what topics are most discussed."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "folder_id": types.Schema(type=types.Type.STRING, description="Optional folder ID to scope search"),
                "min_frequency": types.Schema(type=types.Type.INTEGER, description="Minimum frequency threshold (default 5)"),
                "max_terms": types.Schema(type=types.Type.INTEGER, description="Maximum terms to return (default 50)"),
                "speakers": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                    description="Optional speaker names to filter by",
                ),
            },
            required=[],
        ),
    ),
    types.FunctionDeclaration(
        name="get_ngrams",
        description=(
            "Extract common multi-word phrases (2 or 3 word combinations) from transcripts. "
            "Useful for discovering commonly used phrases and talking points."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "folder_id": types.Schema(type=types.Type.STRING, description="Optional folder ID to scope search"),
                "n": types.Schema(type=types.Type.INTEGER, description="N-gram size: 2 for bigrams, 3 for trigrams (default 2)"),
                "min_frequency": types.Schema(type=types.Type.INTEGER, description="Minimum frequency threshold (default 3)"),
                "speakers": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                    description="Optional speaker names to filter by",
                ),
            },
            required=[],
        ),
    ),
    types.FunctionDeclaration(
        name="list_speakers",
        description=(
            "List all speakers found across transcripts with their segment counts and "
            "number of briefings they appear in."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "folder_id": types.Schema(type=types.Type.STRING, description="Optional folder ID to filter speakers"),
            },
            required=[],
        ),
    ),
    types.FunctionDeclaration(
        name="list_personas",
        description=(
            "List all personas (tracked speaker identities) with their aliases. "
            "Personas represent specific public figures whose mentions are tracked."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={},
            required=[],
        ),
    ),
    types.FunctionDeclaration(
        name="get_persona",
        description="Get detailed information about a specific persona including their aliases.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "persona_id": types.Schema(type=types.Type.STRING, description="The persona's UUID"),
            },
            required=["persona_id"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_persona_transcripts",
        description=(
            "Get transcripts where a specific persona is an actual speaker. "
            "Uses persona aliases to match against transcript speaker names. "
            "Returns transcript metadata sorted by date (newest first)."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "persona_id": types.Schema(type=types.Type.STRING, description="The persona's UUID (from search_personas or list_personas)"),
                "folder_id": types.Schema(type=types.Type.STRING, description="Optional folder ID to scope results"),
                "limit": types.Schema(type=types.Type.INTEGER, description="Max transcripts to return (default 20)"),
            },
            required=["persona_id"],
        ),
    ),
    types.FunctionDeclaration(
        name="browse_kalshi_events",
        description=(
            "Browse currently open Kalshi prediction market events in the Mentions category, "
            "grouped by tag (Politicians, Earnings, Sports). Shows event titles, market questions, "
            "and current prices."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={},
            required=[],
        ),
    ),
    types.FunctionDeclaration(
        name="get_kalshi_event",
        description=(
            "Get detailed information about a specific Kalshi event including its markets, "
            "prices, and optionally persona-specific mention analysis."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "event_ticker": types.Schema(type=types.Type.STRING, description="The Kalshi event ticker (e.g. 'INXWH-25MAR14')"),
                "persona_id": types.Schema(type=types.Type.STRING, description="Optional persona ID for mention analysis"),
            },
            required=["event_ticker"],
        ),
    ),
    types.FunctionDeclaration(
        name="search_polymarket",
        description=(
            "Search Polymarket for prediction market events by keyword. "
            "Returns matching events with titles, volumes, and market counts."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "query": types.Schema(type=types.Type.STRING, description="Search query (e.g. 'Trump', 'tariff')"),
                "limit": types.Schema(type=types.Type.INTEGER, description="Max results to return (default 20)"),
            },
            required=["query"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_polymarket_event",
        description=(
            "Get detailed information about a specific Polymarket event including its markets, "
            "prices, and optionally persona-specific mention analysis."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "event_id": types.Schema(type=types.Type.STRING, description="The Polymarket event ID (database UUID or numeric Polymarket ID from search results)"),
                "persona_id": types.Schema(type=types.Type.STRING, description="Optional persona ID for mention analysis"),
            },
            required=["event_id"],
        ),
    ),
    types.FunctionDeclaration(
        name="list_folders",
        description="List all available transcript folders.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={},
            required=[],
        ),
    ),
    types.FunctionDeclaration(
        name="search_folders",
        description=(
            "Search for transcript folders by name (case-insensitive substring match). "
            "Use this to resolve folder names like 'PMQ' or 'White House' to folder IDs."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "query": types.Schema(type=types.Type.STRING, description="Folder name to search for"),
            },
            required=["query"],
        ),
    ),
    types.FunctionDeclaration(
        name="search_personas",
        description=(
            "Search for a persona by name or alias (case-insensitive). "
            "Use this to find a persona's ID when you know their name (e.g. 'Keir Starmer', 'Trump')."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "query": types.Schema(type=types.Type.STRING, description="Person name or alias to search for"),
            },
            required=["query"],
        ),
    ),
    types.FunctionDeclaration(
        name="list_transcripts",
        description=(
            "List transcripts with metadata (id, name, upload_date, youtube_url). "
            "Returns metadata only, not transcript text. Use get_transcript_content to read text."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "folder_id": types.Schema(type=types.Type.STRING, description="Optional folder ID to filter by"),
                "limit": types.Schema(type=types.Type.INTEGER, description="Max transcripts to return (default 5)"),
                "sort": types.Schema(type=types.Type.STRING, description="Sort order: 'latest' (default) or 'oldest'"),
            },
            required=[],
        ),
    ),
    types.FunctionDeclaration(
        name="get_transcript_content",
        description=(
            "Read the text content of a specific transcript. "
            "Returns the transcript text (truncated if very long) along with metadata. "
            "Use list_transcripts first to find the transcript ID."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "transcript_id": types.Schema(type=types.Type.STRING, description="The transcript's UUID"),
                "section": types.Schema(
                    type=types.Type.STRING,
                    description="Which part to read: 'full' (default, start+end), 'start', or 'end'",
                ),
                "max_chars": types.Schema(
                    type=types.Type.INTEGER,
                    description="Maximum characters to return (default 4000)",
                ),
            },
            required=["transcript_id"],
        ),
    ),
])


# --- Tool Executors ---

async def _get_transcripts(folder_id: str | None = None) -> list[dict[str, Any]]:
    """Get transcripts, optionally filtered by folder tree."""
    if folder_id:
        return await transcript_service.get_transcripts_in_folder_tree(folder_id)
    return await transcript_service.get_all_transcripts()


def _truncate_result(result: Any, max_chars: int = 3000) -> Any:
    """Truncate large results to stay within context limits."""
    text = json.dumps(result, default=str)
    if len(text) <= max_chars:
        return result
    # For lists, truncate items
    if isinstance(result, list) and len(result) > 10:
        truncated = result[:10]
        truncated.append({"_truncated": f"Showing 10 of {len(result)} items"})
        return truncated
    # For dicts with large nested lists, truncate them
    if isinstance(result, dict):
        truncated = {}
        for k, v in result.items():
            if isinstance(v, list) and len(v) > 10:
                truncated[k] = v[:10]
                truncated[f"_{k}_truncated"] = f"Showing 10 of {len(v)} items"
            else:
                truncated[k] = v
        return truncated
    return result


async def execute_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool by name and return the result."""
    try:
        result = await _execute_tool_inner(name, args)
        return _truncate_result(result)
    except Exception as e:
        logger.error(f"Tool execution error ({name}): {e}")
        return {"error": str(e)}


async def _execute_tool_inner(name: str, args: dict[str, Any]) -> Any:
    """Inner tool execution without error handling."""

    if name == "search_term":
        transcripts = await _get_transcripts(args.get("folder_id"))
        if not transcripts:
            return {"error": "No transcripts found"}
        return calculate_term_frequency(
            transcripts,
            args["term"],
            case_sensitive=False,
            speakers=args.get("speakers"),
        )

    elif name == "search_term_in_context":
        transcripts = await _get_transcripts(args.get("folder_id"))
        if not transcripts:
            return {"error": "No transcripts found"}
        return search_term_in_context(
            transcripts,
            args["query"],
            context_chars=args.get("context_chars", 200),
            speakers=args.get("speakers"),
        )

    elif name == "get_top_terms":
        transcripts = await _get_transcripts(args.get("folder_id"))
        if not transcripts:
            return {"error": "No transcripts found"}
        return calculate_all_term_frequencies(
            transcripts,
            min_frequency=args.get("min_frequency", 5),
            max_terms=args.get("max_terms", 50),
            speakers=args.get("speakers"),
        )

    elif name == "get_ngrams":
        transcripts = await _get_transcripts(args.get("folder_id"))
        if not transcripts:
            return {"error": "No transcripts found"}
        return extract_ngrams(
            transcripts,
            n=args.get("n", 2),
            min_frequency=args.get("min_frequency", 3),
            max_ngrams=200,
            speakers=args.get("speakers"),
        )

    elif name == "list_speakers":
        return await speaker_service.get_all_speakers(args.get("folder_id"))

    elif name == "list_personas":
        return await persona_service.get_all_personas()

    elif name == "get_persona":
        persona = await persona_service.get_persona_by_id(args["persona_id"])
        if not persona:
            return {"error": "Persona not found"}
        return persona

    elif name == "get_persona_transcripts":
        transcripts = await persona_service.get_transcripts_for_persona(
            args["persona_id"],
            folder_id=args.get("folder_id"),
        )
        limit = args.get("limit", 20)
        transcripts = transcripts[:limit]
        return [
            {
                "id": t["id"],
                "name": t.get("name"),
                "upload_date": t.get("upload_date"),
                "youtube_url": t.get("youtube_url"),
                "folder_id": t.get("folder_id"),
            }
            for t in transcripts
        ]

    elif name == "browse_kalshi_events":
        return await kalshi_service.browse_events()

    elif name == "get_kalshi_event":
        result = await kalshi_service.get_event_detail_by_ticker(
            args["event_ticker"],
            persona_id=args.get("persona_id"),
        )
        if not result:
            return {"error": "Event not found"}
        return result

    elif name == "search_polymarket":
        return await polymarket_service.search_events(
            query=args["query"],
            limit=args.get("limit", 20),
        )

    elif name == "get_polymarket_event":
        result = await polymarket_service.get_event_detail(
            event_id=args["event_id"],
            persona_id=args.get("persona_id"),
        )
        if not result:
            return {"error": "Event not found"}
        return result

    elif name == "list_folders":
        return await folder_service.get_all_folders()

    elif name == "search_folders":
        query = args["query"].lower()
        all_folders = await folder_service.get_all_folders()
        matches = [
            {"id": f["id"], "name": f["name"], "parent_id": f.get("parent_id")}
            for f in all_folders
            if query in (f.get("name") or "").lower()
        ]
        if not matches:
            return {"error": f"No folders matching '{args['query']}'"}
        return matches

    elif name == "search_personas":
        results = await persona_service.search_personas(
            query=args["query"],
            limit=10,
        )
        if not results:
            return {"error": f"No personas matching '{args['query']}'"}
        return results

    elif name == "list_transcripts":
        folder_id = args.get("folder_id")
        limit = args.get("limit", 5)
        sort = args.get("sort", "latest")
        transcripts = await transcript_service.get_all_transcripts(folder_id)
        # Sort by upload_date
        transcripts.sort(
            key=lambda t: t.get("upload_date") or "",
            reverse=(sort == "latest"),
        )
        # Slice and strip transcript text
        transcripts = transcripts[:limit]
        return [
            {
                "id": t["id"],
                "name": t.get("name"),
                "upload_date": t.get("upload_date"),
                "youtube_url": t.get("youtube_url"),
                "folder_id": t.get("folder_id"),
            }
            for t in transcripts
        ]

    elif name == "get_transcript_content":
        transcript = await transcript_service.get_transcript_by_id(args["transcript_id"])
        if not transcript:
            return {"error": "Transcript not found"}
        text = transcript.get("transcript") or ""
        section = args.get("section", "full")
        max_chars = args.get("max_chars", 4000)

        # Apply section-based truncation
        if len(text) <= max_chars:
            content = text
        elif section == "start":
            content = text[:max_chars] + f"\n\n[... truncated, {len(text)} total chars]"
        elif section == "end":
            content = f"[... truncated, showing last {max_chars} of {len(text)} chars ...]\n\n" + text[-max_chars:]
        else:  # full — show start + end
            half = max_chars // 2
            content = (
                text[:half]
                + f"\n\n[... {len(text) - max_chars} chars omitted ...]\n\n"
                + text[-half:]
            )

        return {
            "id": transcript["id"],
            "name": transcript.get("name"),
            "upload_date": transcript.get("upload_date"),
            "youtube_url": transcript.get("youtube_url"),
            "total_chars": len(text),
            "content": content,
        }

    else:
        return {"error": f"Unknown tool: {name}"}
