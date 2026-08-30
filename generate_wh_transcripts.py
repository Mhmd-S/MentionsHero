#!/usr/bin/env python3
"""
Generate transcripts for White House press briefings directly.
- Fetches recent WH press briefing videos via yt-dlp
- Downloads audio
- Transcribes with Gemini Flash (speaker diarization)
- Saves to Supabase DB
"""

import os, sys, json, subprocess, tempfile, time, re, asyncio
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────
SUPABASE_URL = "https://zzrfputwswchnnjxgeih.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WH_CHANNEL = "https://www.youtube.com/@WhiteHouse"

if not SUPABASE_KEY or not GEMINI_API_KEY:
    print("ERROR: Need SUPABASE_SERVICE_KEY and GEMINI_API_KEY in .env")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Gemini setup ────────────────────────────────────────────────────
import google.generativeai as genai
from google.generativeai.types import File

genai.configure(api_key=GEMINI_API_KEY)

SPEAKER_HINT = (
    "This is a White House press briefing room event. "
    "Key speakers you should identify by name: "
    "Karoline Leavitt (Press Secretary), Donald Trump (President), JD Vance (Vice President), "
    "Susie Wiles (Chief of Staff), Stephen Miller (Deputy Chief of Staff / Senior Advisor), "
    "Marco Rubio (Secretary of State), Scott Bessent (Treasury Secretary), "
    "Pete Hegseth (Defense Secretary), Pam Bondi (AG), Kristi Noem (DHS Secretary), "
    "Howard Lutnick (Commerce Secretary), Mike Waltz (National Security Advisor), "
    "Elon Musk (Senior Advisor), Tulsi Gabbard (DNI), RFK Jr (HHS Secretary). "
    "Reporters should be labeled as 'Reporter' or 'Reporter 1', 'Reporter 2' etc. "
    "Use full names for officials, not title prefixes. "
    "Identify speakers by who is actually speaking."
)

TRANSCRIPTION_PROMPT = f"""Transcribe this audio of a White House event with speaker diarization.
{SPEAKER_HINT}

Return a list of segments with speaker name, timestamp (MM:SS), and content."""

# ── Step 1: Get recent press briefing videos ────────────────────────

def get_channel_videos(channel_url: str, max_videos: int = 50) -> list[dict]:
    """Fetch recent videos from a YouTube channel using yt-dlp."""
    print(f"Fetching videos from {channel_url}...")
    result = subprocess.run(
        [
            "yt-dlp", "--flat-playlist", "--dump-json",
            "--playlist-end", str(max_videos),
            channel_url + "/videos"
        ],
        capture_output=True, text=True, timeout=60
    )

    if result.returncode != 0:
        print(f"yt-dlp error: {result.stderr}")
        return []

    videos = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        try:
            info = json.loads(line)
            videos.append({
                "url": info.get("webpage_url") or f"https://youtube.com/watch?v={info['id']}",
                "title": info.get("title", "Unknown"),
                "duration": info.get("duration", 0),
                "upload_date": info.get("upload_date"),
                "id": info["id"],
            })
        except (json.JSONDecodeError, KeyError):
            continue

    print(f"  Found {len(videos)} videos")
    return videos


# ── Step 2: Get existing transcript URLs from DB ───────────────────

def get_existing_urls() -> set:
    resp = supabase.table("transcripts").select("youtube_url").execute()
    return {r["youtube_url"] for r in (resp.data or [])}


# ── Step 3: Download audio ──────────────────────────────────────────

def download_audio(youtube_url: str, output_dir: str) -> str | None:
    """Download MP3 audio from YouTube."""
    print(f"  Downloading audio: {youtube_url}")
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "-x", "--audio-format", "mp3",
                "--audio-quality", "5",
                "--postprocessor-args", "-ac 1",
                "-o", f"{output_dir}/%(id)s.%(ext)s",
                "--no-playlist",
                youtube_url,
            ],
            capture_output=True, text=True, timeout=300,  # 5 min for download
        )
        if result.returncode != 0:
            print(f"  Download failed: {result.stderr[-200:]}")
            return None

        # Find the output file
        for f in os.listdir(output_dir):
            if f.endswith(".mp3"):
                return os.path.join(output_dir, f)
        return None
    except Exception as e:
        print(f"  Download error: {e}")
        return None


# ── Step 4: Transcribe with Gemini ──────────────────────────────────

def transcribe_audio(audio_path: str, max_retries: int = 3) -> list[dict] | None:
    """Transcribe audio with Gemini Flash, returning segments."""
    file_size = os.path.getsize(audio_path)
    print(f"  Audio size: {file_size / 1024 / 1024:.1f} MB")

    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config={
            "temperature": 0.1,
            "top_p": 0.95,
            "response_mime_type": "application/json",
            "response_schema": {
                "type": "OBJECT",
                "properties": {
                    "segments": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "speaker": {"type": "STRING"},
                                "timestamp": {"type": "STRING"},
                                "content": {"type": "STRING"},
                            },
                            "required": ["speaker", "timestamp", "content"],
                        },
                    }
                },
                "required": ["segments"],
            },
        },
    )

    for attempt in range(max_retries):
        try:
            if file_size < 20 * 1024 * 1024:  # < 20 MB
                with open(audio_path, "rb") as f:
                    audio_data = f.read()
                uploaded = genai.upload_file(audio_path, mime_type="audio/mpeg")
                response = model.generate_content([TRANSCRIPTION_PROMPT, uploaded])
            else:
                uploaded = genai.upload_file(audio_path, mime_type="audio/mpeg")
                print(f"  Uploaded file: {uploaded.name}")
                # Wait for processing
                while uploaded.state.name == "PROCESSING":
                    time.sleep(2)
                    uploaded = genai.get_file(uploaded.name)
                response = model.generate_content([TRANSCRIPTION_PROMPT, uploaded])

            result = json.loads(response.text)
            segments = result.get("segments", [])
            print(f"  Gemini returned {len(segments)} segments")
            return segments

        except Exception as e:
            print(f"  Gemini attempt {attempt+1} failed: {e}")
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"  Retrying in {wait}s...")
                time.sleep(wait)
            else:
                return None

    return None


# ── Step 5: Format transcript & extract speakers ───────────────────

def format_transcript(segments: list[dict]) -> tuple[str, set[str]]:
    """Format segments into transcript text and collect speakers."""
    lines = []
    speakers: set[str] = set()

    for seg in segments:
        speaker = seg.get("speaker", "Unknown").strip()
        timestamp = seg.get("timestamp", "00:00").strip()
        content = seg.get("content", "").strip()

        if not content:
            continue

        lines.append(f"[{timestamp}] {speaker}:")
        lines.append(content)
        lines.append("")
        speakers.add(speaker)

    return "\n".join(lines), speakers


# ── Step 6: Save to Supabase ────────────────────────────────────────

def save_transcript(
    youtube_url: str,
    title: str,
    transcript_text: str,
    speakers: set[str],
    folder_id: str | None = None,
    upload_date: str | None = None,
) -> str | None:
    """Save transcript and speakers to Supabase."""
    insert_data = {
        "youtube_url": youtube_url,
        "name": title,
        "transcript": transcript_text,
        "speakers": list(speakers),
        "upload_date": upload_date,
    }
    if folder_id:
        insert_data["folder_id"] = folder_id

    resp = supabase.table("transcripts").insert(insert_data).execute()
    if not resp.data:
        print("  ERROR: Failed to insert transcript")
        return None

    transcript_id = resp.data[0]["id"]
    print(f"  Transcript saved: {transcript_id}")

    # Normalize speakers
    for speaker_name in speakers:
        # Skip generic names
        if speaker_name.lower() in {"reporter", "unknown", "unidentified"}:
            continue
        if re.match(r"^(reporter|speaker)[_\s]?\d*$", speaker_name.lower()):
            continue

        try:
            # Upsert speaker
            sp_resp = supabase.table("speakers").upsert(
                {"name": speaker_name}, on_conflict="name"
            ).execute()
            speaker_id = sp_resp.data[0]["id"] if sp_resp.data else None
            if speaker_id:
                # Count segments for this speaker
                count = sum(1 for s in speakers if s == speaker_name)
                supabase.table("transcript_speakers").insert({
                    "transcript_id": transcript_id,
                    "speaker_id": speaker_id,
                    "segment_count": count,
                }).execute()
        except Exception as e:
            print(f"  Speaker save error ({speaker_name}): {e}")

    return transcript_id


# ── Main ────────────────────────────────────────────────────────────

async def main():
    # Get folder
    folders = supabase.table("folders").select("id, name").eq("name", "White House Briefings").execute()
    folder_id = folders.data[0]["id"] if folders.data else None

    # Get existing URLs
    existing_urls = get_existing_urls()
    print(f"Already have {len(existing_urls)} transcripts")

    # Fetch videos
    videos = get_channel_videos(WH_CHANNEL, max_videos=50)

    # Filter to press briefing / conference type videos
    briefing_keywords = ["press briefing", "press conference", "news conference", "press gaggle", 
                         "remarks by", "statement by", "gaggle", "briefing"]

    briefing_videos = []
    for v in videos:
        title_lower = v["title"].lower()
        if any(kw in title_lower for kw in briefing_keywords):
            briefing_videos.append(v)

    print(f"Filtered to {len(briefing_videos)} briefing videos")

    # Filter out already transcribed
    new_videos = [v for v in briefing_videos if v["url"] not in existing_urls]
    print(f"New to transcribe: {len(new_videos)}")

    if not new_videos:
        print("No new videos to transcribe!")
        return

    # Process up to 5 videos
    to_process = new_videos[:5]
    print(f"\nWill transcribe {len(to_process)} videos:")

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, video in enumerate(to_process):
            print(f"\n── [{i+1}/{len(to_process)}] {video['title'][:80]}")
            print(f"   URL: {video['url']}")

            # Download audio
            audio_path = download_audio(video["url"], tmpdir)
            if not audio_path:
                print("  SKIPPED: Audio download failed")
                continue

            # Transcribe
            segments = transcribe_audio(audio_path)
            if not segments:
                print("  SKIPPED: Transcription failed")
                continue

            # Format
            transcript_text, speaker_set = format_transcript(segments)
            print(f"  Speakers detected: {speaker_set}")

            # Save
            tid = save_transcript(
                video["url"],
                video["title"],
                transcript_text,
                speaker_set,
                folder_id=folder_id,
                upload_date=video.get("upload_date"),
            )

            if tid:
                print(f"  ✓ Done! Transcript ID: {tid}")

            # Clean up audio
            try:
                os.unlink(audio_path)
            except Exception:
                pass

    print("\n── All done ──")
    print(f"Check at: http://localhost:8001/api/transcripts")


if __name__ == "__main__":
    main()