"""One-off live probe to resolve two uncertainties before the metadata-extraction rewrite.

It answers, against the REAL `gemini-3-flash-preview` model:
  1. Which "minimize thinking" lever the model accepts:
       thinking_level=LOW / MINIMAL   (Gemini-3 style)   vs
       thinking_budget=0              (Gemini-2.5 style)
     ...and how much faster a minimized-thinking structured call is vs the
     current (no thinking control) config.
  2. How Google Search grounding can be combined with structured output:
       (a) google_search + response_schema in ONE call            -> cleanest
       (b) google_search + "JSON only" prompt, then lenient parse  -> one call
       (c) two-step: grounded gather (text) -> structuring call    -> fallback

Run from repo root (framework python):
    python3 -m backend.scripts.probe_thinking_config

This is the ONLY sanctioned live API call in the rewrite. It makes ~8 small
calls (a few are grounded, which is billed per request). Output is a verdict
block that tells the implementer which code paths to wire up.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

# Repo root on sys.path so `python3 backend/scripts/...` works too.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from google import genai
from google.genai import types

from backend.config import get_settings

MODEL = "gemini-3-flash-preview"

# A tiny structured task so latency reflects model overhead, not output size.
PROMPT = (
    "Extract the city and US state from this video title. "
    "Return null if unknown.\n\nTITLE: President Trump Holds a Rally in Phoenix, Arizona"
)

GROUNDED_PROMPT = (
    "Search Google to determine where and when this event happened, then report "
    "the city, US state, and the specific venue/room.\n\n"
    "EVENT: President Trump Participates in the Champion of Coal Event"
)

JSON_ONLY_SUFFIX = (
    "\n\nRespond with ONLY a JSON object of this exact shape, no prose, no code fences:\n"
    '{"city": string|null, "state": string|null, "venue": string|null}'
)


def _schema() -> types.Schema:
    return types.Schema(
        type=types.Type.OBJECT,
        properties={
            "city": types.Schema(type=types.Type.STRING, nullable=True),
            "state": types.Schema(type=types.Type.STRING, nullable=True),
            "venue": types.Schema(type=types.Type.STRING, nullable=True),
        },
    )


def _lenient_json(text: str) -> dict | None:
    """Strip code fences and pull the first balanced {...} object out of text."""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?", "", t).strip()
    t = re.sub(r"```$", "", t).strip()
    start = t.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(t)):
        if t[i] == "{":
            depth += 1
        elif t[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(t[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _grounding_summary(response) -> str:
    try:
        gm = response.candidates[0].grounding_metadata
        if not gm:
            return "no grounding_metadata"
        queries = list(gm.web_search_queries or [])
        chunks = len(gm.grounding_chunks or [])
        return f"queries={queries!r} chunks={chunks}"
    except (AttributeError, IndexError, TypeError):
        return "no grounding_metadata"


def _run(client: genai.Client, label: str, config: types.GenerateContentConfig, prompt: str) -> dict:
    """Run one call; return {ok, secs, text, error, grounding}."""
    t0 = time.perf_counter()
    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=[types.Part.from_text(text=prompt)],
            config=config,
        )
    except Exception as e:  # noqa: BLE001 - probe wants every failure mode
        return {"ok": False, "secs": time.perf_counter() - t0, "error": str(e)[:400]}
    secs = time.perf_counter() - t0
    text = (getattr(resp, "text", None) or "").strip()
    return {
        "ok": True,
        "secs": secs,
        "text": text,
        "grounding": _grounding_summary(resp),
    }


def _print(label: str, r: dict) -> None:
    if r.get("ok"):
        extra = f" | grounding: {r['grounding']}" if "grounding" in r else ""
        preview = (r.get("text") or "")[:120].replace("\n", " ")
        print(f"  [OK  {r['secs']:5.1f}s] {label}{extra}\n              text: {preview}")
    else:
        print(f"  [FAIL {r['secs']:5.1f}s] {label}\n              error: {r['error']}")


def main() -> None:
    settings = get_settings()
    if not settings.gemini_api_key:
        print("ERROR: GEMINI_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    client = genai.Client(api_key=settings.gemini_api_key)
    schema = _schema()

    print(f"\n=== PROBE: {MODEL} ===\n")

    # ---- Part 1: thinking levers on a plain structured call --------------
    print("Part 1 — thinking levers (structured JSON call, no grounding):")
    base = dict(response_mime_type="application/json", response_schema=schema, temperature=0.0)
    thinking_variants = {
        "no-thinking-control (current)": None,
        "thinking_level=LOW": types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
        "thinking_level=MINIMAL": types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
        "thinking_budget=0": types.ThinkingConfig(thinking_budget=0),
    }
    thinking_results: dict[str, dict] = {}
    for label, tc in thinking_variants.items():
        cfg = types.GenerateContentConfig(**base, **({"thinking_config": tc} if tc else {}))
        r = _run(client, label, cfg, PROMPT)
        thinking_results[label] = r
        _print(label, r)

    # ---- Part 2: grounding + structured output paths ---------------------
    print("\nPart 2 — Google Search grounding + structured output:")
    gs_tool = types.Tool(google_search=types.GoogleSearch())

    # (a) grounded + response_schema in one call
    cfg_a = types.GenerateContentConfig(
        tools=[gs_tool],
        response_mime_type="application/json",
        response_schema=schema,
        temperature=0.0,
    )
    ra = _run(client, "(a) google_search + response_schema", cfg_a, GROUNDED_PROMPT)
    _print("(a) google_search + response_schema", ra)
    a_parsed = _lenient_json(ra.get("text", "")) if ra.get("ok") else None
    if ra.get("ok"):
        print(f"              parsed JSON: {a_parsed}")

    # (b) grounded + JSON-only prompt (no schema), lenient parse
    cfg_b = types.GenerateContentConfig(tools=[gs_tool], temperature=0.0)
    rb = _run(client, "(b) google_search + JSON-only prompt", cfg_b, GROUNDED_PROMPT + JSON_ONLY_SUFFIX)
    _print("(b) google_search + JSON-only prompt", rb)
    b_parsed = _lenient_json(rb.get("text", "")) if rb.get("ok") else None
    if rb.get("ok"):
        print(f"              parsed JSON: {b_parsed}")

    # (c) two-step: grounded gather (free text) -> structuring call
    cfg_c1 = types.GenerateContentConfig(tools=[gs_tool], temperature=0.0)
    rc1 = _run(client, "(c1) grounded gather (free text)", cfg_c1, GROUNDED_PROMPT)
    _print("(c1) grounded gather", rc1)
    c_parsed = None
    if rc1.get("ok") and rc1.get("text"):
        cfg_c2 = types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=schema, temperature=0.0
        )
        structure_prompt = (
            "From the notes below, extract city, state, venue as JSON.\n\nNOTES:\n" + rc1["text"]
        )
        rc2 = _run(client, "(c2) structuring call", cfg_c2, structure_prompt)
        _print("(c2) structuring call", rc2)
        c_parsed = _lenient_json(rc2.get("text", "")) if rc2.get("ok") else None
        if rc2.get("ok"):
            print(f"              parsed JSON: {c_parsed}")

    # ---- Verdict ---------------------------------------------------------
    print("\n=== VERDICT ===")
    ok_thinking = [(k, v["secs"]) for k, v in thinking_results.items()
                   if v.get("ok") and k != "no-thinking-control (current)"]
    baseline = thinking_results.get("no-thinking-control (current)", {})
    if ok_thinking:
        fastest = min(ok_thinking, key=lambda kv: kv[1])
        print(f"thinking lever: use `{fastest[0]}` ({fastest[1]:.1f}s", end="")
        if baseline.get("ok"):
            print(f" vs baseline {baseline['secs']:.1f}s)")
        else:
            print(")")
    else:
        print("thinking lever: NONE of the minimized variants worked — keep default thinking.")

    if ra.get("ok") and a_parsed:
        print("grounding path: (a) google_search + response_schema works in ONE call — use it.")
    elif rb.get("ok") and b_parsed:
        print("grounding path: (b) google_search + JSON-only prompt + lenient parse — one call.")
    elif c_parsed:
        print("grounding path: (c) two-step grounded gather -> structuring call.")
    else:
        print("grounding path: NONE produced parseable JSON — inspect output above before wiring.")
    print()


if __name__ == "__main__":
    main()
