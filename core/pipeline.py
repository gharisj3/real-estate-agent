"""The one path every chat channel must use for a customer message.

A "channel" is anything that talks to a customer — the web chat page,
a WhatsApp bot, or the terminal script. Every one of them must call
handle_message(session_id, text) and send back exactly what it
returns. The guards and the AI are never called any other way, so no
channel can accidentally skip a safety check.

The order below is fixed by the rulebook (CLAUDE.md: "safety is
enforced in code, not in prompts") and must not be changed:

1. Override check (input) — core.guards.check_instruction_override
2. Fair-housing guard (input) — core.guards.check_fair_housing
3. Property search by code, no AI — core.property_search
4. One AI call to Groq, given only the matching properties
5. Leak check (output) — core.guards.check_output_leak
6. Facts-only guard (output), checked against step 3's matches only
7. AI disclosure, added by code on the first reply of the session

If anything in steps 3-6 raises an error (the database, Groq, or a
bug), the customer is never shown the raw AI reply or an error
message — they get a fixed, safe reply instead, and the error is
logged.
"""

import logging
import os
import pathlib
import re
from datetime import datetime, timezone

from groq import Groq

from core.guards import (
    add_disclosure,
    check_facts_only,
    check_fair_housing,
    check_instruction_override,
    check_output_leak,
    insert_canary,
)
from core.models import Property
from core.property_search import find_matching_properties, properties_as_facts

logger = logging.getLogger("propdesk.pipeline")

PROMPT_FILE = pathlib.Path(__file__).resolve().parent.parent / "prompts" / "assistant_v1.md"

# No Llama chat model is on Groq's list right now (checked live on 2026-10-25).
MODEL = "openai/gpt-oss-20b"

# Shown when step 3, 4, 5, or 6 raises an error instead of running
# normally — never the raw AI reply, and never a technical error message.
SAFE_REPLY_ON_ERROR = "We could not answer just now. A team member will contact you."

# One conversation history per session, in memory only — it starts over
# if the server restarts. Each entry is {"role": "user"/"assistant",
# "content": "..."}, the same shape add_disclosure() expects.
_SESSION_HISTORY = {}

# Looks for a bedroom count the customer asked for, e.g. "2 bedroom flat".
_BEDROOM_PATTERN = re.compile(r"(\d+)\s*-?\s*(?:bedrooms?|beds?)\b", re.IGNORECASE)

# Looks for a price limit the customer gave, e.g. "under 10,000,000" or
# "budget of 5000000".
_MAX_PRICE_PATTERN = re.compile(
    r"(?:under|below|max(?:imum)?|budget(?:\s*of)?|up\s*to|less\s*than)\D{0,10}?(\d[\d,]*)",
    re.IGNORECASE,
)


def _extract_search_filters(text):
    """Work out what the customer might be looking for, from their own
    words only — no AI involved. Returns (city, bedrooms, max_price),
    any of which can be None if nothing matched.

    `city` is only recognised if it is already one of the cities in our
    own database — this cannot invent a city that doesn't exist."""
    bedroom_match = _BEDROOM_PATTERN.search(text)
    bedrooms = int(bedroom_match.group(1)) if bedroom_match else None

    price_match = _MAX_PRICE_PATTERN.search(text)
    max_price = int(price_match.group(1).replace(",", "")) if price_match else None

    city = None
    text_lower = text.lower()
    known_cities = Property.objects.values_list("city", flat=True).distinct()
    for known_city in known_cities:
        if known_city and re.search(r"\b" + re.escape(known_city.lower()) + r"\b", text_lower):
            city = known_city
            break

    return city, bedrooms, max_price


def _load_system_prompt():
    """Read the instructions file and swap in the real canary value from
    .env. Returns (system_prompt, canary)."""
    template = PROMPT_FILE.read_text(encoding="utf-8")
    canary = os.environ.get("GUARD_CANARY_TOKEN", "")
    return insert_canary(template, canary), canary


def _default_ai_call(messages):
    """Send the conversation to Groq and return its reply text.

    This is the ONLY function in the whole project that calls the AI.
    It is a separate, small function so tests can swap it for a fake
    AI (see core/tests/test_pipeline.py) and run with no internet
    connection and no real API key."""
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(model=MODEL, messages=messages)
    return response.choices[0].message.content


def handle_message(session_id, text, ai_call=_default_ai_call):
    """Handle one customer message and return (reply, steps_run).

    `session_id` identifies one customer's conversation (any stable
    string the channel already has — a chat widget id, a phone
    number's hash, etc.). `text` is the customer's message as typed.

    `steps_run` is a short list of which steps actually ran, in order
    — useful for tests and for checking in practice that a guard did
    its job (for example, that "ai_call" is missing when a guard
    blocked the message before the AI was ever reached).

    `ai_call` is only meant to be overridden by tests; a real chat
    channel should call handle_message(session_id, text) and leave it
    to use the real Groq call.
    """
    steps_run = []
    history = _SESSION_HISTORY.setdefault(session_id, [])

    try:
        reply = _run_pipeline(session_id, text, ai_call, history, steps_run)
    except Exception as exc:
        logger.error(
            "pipeline_error session=%s last_step=%s error=%s time=%s",
            session_id,
            steps_run[-1] if steps_run else "none",
            type(exc).__name__,
            datetime.now(timezone.utc).isoformat(),
        )
        reply = SAFE_REPLY_ON_ERROR
        steps_run.append("error_fallback")

    disclosed_reply = add_disclosure(reply, history)
    steps_run.append("disclosure")

    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": disclosed_reply})

    return disclosed_reply, steps_run


def _run_pipeline(session_id, text, ai_call, history, steps_run):
    """Run steps 1-6 and return the reply that step 7 (disclosure) will
    wrap. Any exception here is caught by handle_message, not here."""

    # 1. Override check (input) — no AI call if this triggers.
    steps_run.append("override_check")
    blocked, reply = check_instruction_override(text, session_id=session_id)
    if blocked:
        return reply

    # 2. Fair-housing guard (input) — no AI call if this triggers.
    steps_run.append("fair_housing")
    blocked, reply = check_fair_housing(text, session_id=session_id)
    if blocked:
        return reply

    # 3. Property search by code — no AI involved in deciding matches.
    steps_run.append("property_search")
    city, bedrooms, max_price = _extract_search_filters(text)
    matches = find_matching_properties(city=city, bedrooms=bedrooms, max_price=max_price)
    facts = properties_as_facts(matches)

    # 4. One AI call, given only the matching properties from step 3.
    steps_run.append("ai_call")
    system_prompt, canary = _load_system_prompt()
    messages = (
        [{"role": "system", "content": system_prompt}]
        + history
        + [
            {"role": "system", "content": f"Real properties matching this request:\n{facts}"},
            {"role": "user", "content": text},
        ]
    )
    ai_reply = ai_call(messages)

    # 5. Leak check (output).
    steps_run.append("leak_check")
    blocked, safe_reply = check_output_leak(ai_reply, system_prompt, canary, session_id=session_id)
    if blocked:
        return safe_reply

    # 6. Facts-only guard (output) — checked against step 3's matches
    # only, never the whole database.
    steps_run.append("facts_only")
    blocked, safe_reply = check_facts_only(ai_reply, matches, session_id=session_id)
    if blocked:
        return safe_reply

    return ai_reply
