"""ML data processing service — extracts persona speech segments and writes JSONL splits."""

import asyncio
import json
import os
from typing import Any, Callable

from backend.core.database import get_supabase, get_folder_ids_in_tree
from backend.utils.nlp import parse_transcript_segments


def _prepare_training_data_sync(
    persona_id: str,
    output_dir: str,
    folder_id: str | None,
    min_word_count: int,
    max_tokens: int,
    on_progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """
    Synchronous data preparation (Supabase + file I/O). Run from a thread to avoid
    blocking the event loop so the training stream and API stay responsive.
    """
    supabase = get_supabase()

    # Persona + aliases
    persona_res = supabase.table("personas").select("*").eq("id", persona_id).single().execute()
    if not persona_res.data:
        raise ValueError(f"Persona {persona_id} not found")
    persona = persona_res.data
    aliases_res = (
        supabase.table("persona_aliases").select("alias").eq("persona_id", persona_id).execute()
    )
    persona["aliases"] = [a["alias"] for a in (aliases_res.data or [])]
    aliases = persona["aliases"]
    if not aliases:
        raise ValueError(f"Persona {persona['name']} has no aliases — cannot match speakers")

    # Transcripts list (with optional folder filter)
    query = supabase.table("transcripts").select("id, name, youtube_url, created_at, folder_id")
    if folder_id:
        folders_res = supabase.table("folders").select("*").execute()
        folders = folders_res.data or []
        folder_ids = get_folder_ids_in_tree(folder_id, folders)
        query = query.in_("folder_id", folder_ids)
    response = query.order("created_at", desc=True).execute()
    transcripts_meta = response.data or []
    if not transcripts_meta:
        raise ValueError(f"No transcripts found for persona {persona['name']}")

    if on_progress:
        on_progress(f"Scanning {len(transcripts_meta)} transcripts...")

    alias_lower = [a.lower() for a in aliases]

    def _speaker_matches(speaker: str) -> bool:
        sl = speaker.lower()
        return any(sl == a or sl.startswith(a) or a in sl for a in alias_lower)

    # Single pass: fetch each transcript once, check alias presence and extract segments
    all_segments: list[dict[str, Any]] = []
    total_transcripts = len(transcripts_meta)
    for i, t_meta in enumerate(transcripts_meta):
        full = (
            supabase.table("transcripts")
            .select("transcript, upload_date")
            .eq("id", t_meta["id"])
            .single()
            .execute()
        )
        if not full.data or not full.data.get("transcript"):
            continue
        text = full.data["transcript"]
        # Quick check: does any alias appear in the transcript text?
        text_lower = text.lower()
        if not any(a in text_lower for a in alias_lower):
            continue
        upload_date = full.data.get("upload_date") or t_meta.get("created_at", "")
        segments = parse_transcript_segments(text)
        for seg in segments:
            if not _speaker_matches(seg["speaker"]):
                continue
            content = seg["content"].strip()
            word_count = len(content.split())
            if word_count < min_word_count:
                continue
            est_tokens = int(word_count * 1.3)
            if est_tokens > max_tokens:
                continue
            all_segments.append({"text": content, "date": upload_date})

        if on_progress and (i + 1) % 10 == 0:
            on_progress(f"Scanned {i + 1}/{total_transcripts} transcripts ({len(all_segments)} segments found)")

    if on_progress:
        on_progress(f"Scanned {total_transcripts}/{total_transcripts} transcripts ({len(all_segments)} segments found)")

    if not all_segments:
        raise ValueError(
            f"No qualifying segments found for {persona['name']} "
            f"(min {min_word_count} words, max {max_tokens} est tokens)"
        )
    all_segments.sort(key=lambda s: s["date"])
    total = len(all_segments)
    train_end = int(total * 0.8)
    valid_end = int(total * 0.9)
    train = all_segments[:train_end]
    valid = all_segments[train_end:valid_end]
    test = all_segments[valid_end:]

    if on_progress:
        on_progress("Writing train/valid/test splits...")

    os.makedirs(output_dir, exist_ok=True)
    paths: dict[str, str] = {}
    for split_name, split_data in [("train", train), ("valid", valid), ("test", test)]:
        path = os.path.join(output_dir, f"{split_name}.jsonl")
        with open(path, "w") as f:
            for seg in split_data:
                f.write(json.dumps({"text": seg["text"]}) + "\n")
        paths[split_name] = path
    return {
        "total_segments": total,
        "train_segments": len(train),
        "valid_segments": len(valid),
        "test_segments": len(test),
        "paths": paths,
        "output_dir": output_dir,
    }


async def prepare_training_data(
    persona_id: str,
    output_dir: str,
    folder_id: str | None = None,
    min_word_count: int = 20,
    max_tokens: int = 480,
    on_progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Extract persona speech segments from transcripts and write train/valid/test JSONL splits.

    Runs the heavy I/O in a thread so the event loop stays responsive (stream + API).
    Returns dict with segment counts and file paths.
    """
    return await asyncio.to_thread(
        _prepare_training_data_sync,
        persona_id,
        output_dir,
        folder_id,
        min_word_count,
        max_tokens,
        on_progress,
    )
