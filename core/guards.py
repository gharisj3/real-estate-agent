"""Guards: plain code that decides what the AI assistant is allowed to say.

A guard is not the AI. It runs before or after the AI and can add to,
change, or block a reply. The AI has no say in what this file does — see
docs/guards.md and the rule in CLAUDE.md: "Safety is enforced in code, not
in prompts."

This file has no AI calls in it at all.
"""

import logging
import os
import re
import time
from datetime import datetime, timezone

from django.core.cache import cache

from core.guard_terms import (
    OVERRIDE_ATTEMPT_PHRASES,
    PROTECTED_TRAIT_TERMS,
    STEERING_TERMS,
)

logger = logging.getLogger("propdesk.guards")


# ---------------------------------------------------------------------------
# Guard: AI disclosure
# ---------------------------------------------------------------------------

# Edit this text to change what customers are told. It is shown once, in
# front of the assistant's very first reply in a chat.
DISCLOSURE_NOTICE = (
    "You are chatting with an AI assistant for [AGENCY NAME]. "
    "A team member can take over at any time. "
    "Your messages may be stored to help us serve you."
)


def add_disclosure(reply, history):
    """Put the disclosure notice in front of the first reply of a chat.

    `reply` is the text the AI drafted for this turn.
    `history` is the list of messages sent so far in this chat, using the
    same shape as chat_groq.py: a list of {"role": ..., "content": ...}
    dicts (roles so far can be "system" and "user", but not "assistant"
    yet, if this is really the first reply).

    If none of those messages came from the assistant yet, this is the
    first reply, so the notice is placed in front of it. Any later reply
    is returned unchanged.
    """
    already_replied = any(message.get("role") == "assistant" for message in history)
    if already_replied:
        return reply
    return f"{DISCLOSURE_NOTICE}\n\n{reply}"


# ---------------------------------------------------------------------------
# Guard: fair housing
# ---------------------------------------------------------------------------

# Edit this text to change the fixed refusal shown to customers.
FAIR_HOUSING_REFUSAL = (
    "I'm sorry, but I can't filter or recommend homes based on religion, "
    "race, ethnicity, nationality, sex, family status, disability, or "
    "age — I treat every customer the same way. I'm happy to help you by "
    "budget, size, location, and features instead."
)


def _all_terms(terms_by_script):
    """Flatten a {"english": [...], "urdu_script": [...], ...} dict into
    one list. Not every guard's word list covers every script (the
    override-attempt list below only has English and Roman Urdu), so a
    missing key is treated as an empty list rather than an error."""
    return (
        terms_by_script.get("english", [])
        + terms_by_script.get("urdu_script", [])
        + terms_by_script.get("roman_urdu", [])
    )


def _first_match(text_lower, terms):
    """Return the first term found as a whole word/phrase in `text_lower`,
    or None if none of them appear. A whole-word match stops "no" from
    matching inside "normal", for example."""
    for term in terms:
        term_lower = term.lower()
        pattern = r"\b" + re.escape(term_lower) + r"\b"
        if re.search(pattern, text_lower, flags=re.UNICODE):
            return term
    return None


def check_fair_housing(message, session_id="unknown"):
    """Check a customer's message BEFORE the AI ever sees it, for a
    request to include, exclude, or prefer neighbours or areas by a
    protected trait.

    This looks for two things together, from the word lists in
    core/guard_terms.py: a "steering" word that asks to include, exclude,
    or prefer something ("only", "no", "sirf", ...), and a word naming a
    protected trait (a religion, a nationality, "families", "elderly",
    ...). Both have to be present. A trait word on its own — like "near a
    mosque", or "ground floor for my elderly father" — is a normal,
    allowed question and is left alone.

    Returns a tuple: (blocked, reply).
    - If blocked is True: do NOT call the AI for this turn. `reply` is the
      fixed, polite text to show the customer instead.
    - If blocked is False: `reply` is None, and the message should go to
      the AI as normal.
    """
    text_lower = message.lower()

    steering_hit = _first_match(text_lower, _all_terms(STEERING_TERMS))
    if not steering_hit:
        return False, None

    for category, terms_by_script in PROTECTED_TRAIT_TERMS.items():
        trait_hit = _first_match(text_lower, _all_terms(terms_by_script))
        if trait_hit:
            _log_fair_housing_trigger(session_id, category)
            return True, FAIR_HOUSING_REFUSAL

    return False, None


def _log_fair_housing_trigger(session_id, category):
    """Record that the guard fired, without storing anything personal.

    Only the time, the session id, and which category of rule fired are
    recorded — never the customer's message or any other detail.
    """
    logger.warning(
        "guard_triggered rule=fair_housing category=%s session=%s time=%s",
        category,
        session_id,
        datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Guard: instruction override / prompt leak — the INPUT half
# ---------------------------------------------------------------------------

# Edit this text to change the fixed reply shown to customers.
INSTRUCTION_OVERRIDE_REFUSAL = (
    "I can only help with real estate questions, and I can't change how "
    "I work or share my instructions. What can I help you with about a "
    "property or viewing?"
)


def check_instruction_override(message, session_id="unknown"):
    """Check a customer's message BEFORE the AI ever sees it, for a known
    attempt to make the assistant ignore its rules, change what it is, or
    reveal its instructions.

    This only recognises the exact phrases listed in
    core/guard_terms.py (OVERRIDE_ATTEMPT_PHRASES), in English and Roman
    Urdu. See "what these checks cannot stop" for what that means it will
    miss.

    Returns a tuple: (blocked, reply) — same shape as check_fair_housing.
    - If blocked is True: do NOT call the AI for this turn. `reply` is the
      fixed text to show the customer instead.
    - If blocked is False: `reply` is None, and the message should go to
      the AI as normal.
    """
    text_lower = message.lower()
    hit = _first_match(text_lower, _all_terms(OVERRIDE_ATTEMPT_PHRASES))
    if hit:
        _log_override_attempt(session_id, hit)
        return True, INSTRUCTION_OVERRIDE_REFUSAL
    return False, None


def _log_override_attempt(session_id, phrase):
    """Record that the guard fired. `phrase` is one of our own listed
    phrases (never the customer's full message), so nothing personal is
    recorded."""
    logger.warning(
        "guard_triggered rule=instruction_override phrase=%r session=%s time=%s",
        phrase,
        session_id,
        datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Guard: instruction override / prompt leak — the OUTPUT half (the canary)
# ---------------------------------------------------------------------------

# The placeholder written inside prompts/assistant_v1.md. It is replaced
# with the real secret marker at runtime, read from .env — so the prompt
# file itself is safe to commit to git.
CANARY_PLACEHOLDER = "{{CANARY}}"

# Edit this text to change the fixed reply shown when a leak is caught.
OUTPUT_LEAK_SAFE_REPLY = (
    "Sorry, something went wrong with that reply. Let me connect you "
    "with a team member who can help."
)

# How many words in a row from the system prompt, found inside a reply,
# count as "a long piece of the system prompt" rather than a coincidence.
MIN_LEAKED_WORDS = 8


def insert_canary(system_prompt_template, canary):
    """Swap the {{CANARY}} placeholder in the system prompt template for
    the real secret marker.

    `system_prompt_template` is the text read from prompts/assistant_v1.md
    (safe to commit — it only has the placeholder). `canary` is the real
    value, read from GUARD_CANARY_TOKEN in .env (never committed).
    """
    return system_prompt_template.replace(CANARY_PLACEHOLDER, canary)


def _normalize_whitespace(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def _contains_long_excerpt(reply_lower, source_text, min_words=MIN_LEAKED_WORDS):
    """True if `reply_lower` contains `min_words` or more consecutive
    words copied straight from `source_text` (the system prompt)."""
    words = _normalize_whitespace(source_text).split(" ")
    for start in range(len(words) - min_words + 1):
        phrase = " ".join(words[start : start + min_words])
        if phrase and phrase in reply_lower:
            return True
    return False


def check_output_leak(reply, system_prompt_text, canary, session_id="unknown"):
    """Check an AI-drafted reply AFTER it comes back, for a leak of the
    system prompt it was given.

    Looks for two things: the secret canary marker itself, and any long
    run of words copied straight from the system prompt text. Either one
    means the reply must be thrown away before the customer ever sees it
    — the AI already said it, but the customer never will.

    Returns a tuple: (blocked, safe_reply).
    - If blocked is True: do NOT show `reply` to the customer. Show
      `safe_reply` instead.
    - If blocked is False: `safe_reply` is None, show `reply` as normal.
    """
    if not reply:
        return False, None

    reply_lower = reply.lower()

    canary_leaked = bool(canary) and canary.lower() in reply_lower
    excerpt_leaked = _contains_long_excerpt(reply_lower, system_prompt_text)

    if canary_leaked or excerpt_leaked:
        _log_output_leak(session_id, "canary" if canary_leaked else "excerpt")
        return True, OUTPUT_LEAK_SAFE_REPLY

    return False, None


def _log_output_leak(session_id, reason):
    """Record that the guard fired, without storing the leaked text
    itself — only the time, the session id, and whether it was the canary
    or a copied excerpt that gave the leak away."""
    logger.warning(
        "guard_triggered rule=output_leak reason=%s session=%s time=%s",
        reason,
        session_id,
        datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Guard: facts only — prices and details must come from our own database
# ---------------------------------------------------------------------------

# Edit this text to change the fixed reply shown when a reply is discarded.
FACTS_ONLY_SAFE_REPLY = (
    "Sorry, I'm not fully sure about those details. Let me connect you "
    "with a team member who can confirm the exact price and specifications."
)

# A number right before one of these words is read as a bedroom count,
# not a price — e.g. "3 bedrooms" or "3-bed".
_BEDROOM_PATTERN = re.compile(r"(\d+)\s*-?\s*(?:bedrooms?|beds?)\b", re.IGNORECASE)

# A price: either a number with comma groups ("5,350,000") or any bare
# number of 4+ digits ("5350000"). Short numbers (like a bedroom count or
# a floor number) are not treated as prices.
_PRICE_PATTERN = re.compile(r"\b\d{1,3}(?:,\d{3})+\b|\b\d{4,}\b")


def _extract_bedroom_counts(text):
    return {int(match) for match in _BEDROOM_PATTERN.findall(text)}


def _extract_prices(text):
    prices = set()
    for match in _PRICE_PATTERN.findall(text):
        try:
            prices.add(int(match.replace(",", "")))
        except ValueError:
            continue
    return prices


def check_facts_only(reply, properties, session_id="unknown"):
    """Check an AI-drafted reply AFTER it comes back, for a price or
    bedroom count that does not belong to any of the real properties it
    was given.

    `properties` is the list of Property rows (from
    core.property_search.find_matching_properties) that the AI was shown
    for this reply — the only properties it was allowed to describe. Any
    price or bedroom number in the reply that doesn't match one of them
    means a detail was invented or mixed up, so the whole reply is thrown
    away rather than guessing which part is wrong.

    Returns a tuple: (blocked, safe_reply) — same shape as the other
    output guards.
    """
    if not reply:
        return False, None

    valid_prices = {int(prop.price) for prop in properties}
    valid_bedrooms = {prop.bedrooms for prop in properties}

    bad_prices = _extract_prices(reply) - valid_prices
    bad_bedrooms = _extract_bedroom_counts(reply) - valid_bedrooms

    if bad_prices or bad_bedrooms:
        _log_facts_only_mismatch(session_id, len(bad_prices), len(bad_bedrooms))
        return True, FACTS_ONLY_SAFE_REPLY

    return False, None


def _log_facts_only_mismatch(session_id, bad_price_count, bad_bedroom_count):
    """Record that the guard fired — only the time, the session id, and
    how many bad numbers were found, never the reply text itself."""
    logger.warning(
        "guard_triggered rule=facts_only bad_prices=%s bad_bedrooms=%s session=%s time=%s",
        bad_price_count,
        bad_bedroom_count,
        session_id,
        datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Guard: kill switch — a manual off switch for the whole assistant
# ---------------------------------------------------------------------------

# Edit this text to change what customers see while the assistant is off.
BOT_OFFLINE_REPLY = "Our assistant is offline right now. A team member will reply soon."


def check_kill_switch(session_id="unknown"):
    """Check the PROPDESK_BOT_ENABLED setting in .env, before anything
    else runs for this message.

    Set PROPDESK_BOT_ENABLED=false in .env (no restart needed if the
    channel re-reads it, otherwise restart it) to take the assistant
    offline for every customer at once — no code change, no AI call.
    A missing setting, or anything other than exactly "false", counts
    as on, so a typo in .env cannot accidentally take the assistant
    down.

    Returns (blocked, reply) — same shape as the other guards.
    """
    raw_value = os.environ.get("PROPDESK_BOT_ENABLED", "true")
    enabled = raw_value.strip().lower() != "false"
    if enabled:
        return False, None
    _log_kill_switch_triggered(session_id)
    return True, BOT_OFFLINE_REPLY


def _log_kill_switch_triggered(session_id):
    """Record that the guard fired — only the time and the session id."""
    logger.warning(
        "guard_triggered rule=kill_switch session=%s time=%s",
        session_id,
        datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Guard: rate limit — at most a fixed number of messages per session, per
# time window
# ---------------------------------------------------------------------------

# Edit these two numbers to change the limit — they are the only two
# settings this guard has, and they both live here, in one place.
RATE_LIMIT_MAX_MESSAGES = 20
RATE_LIMIT_WINDOW_SECONDS = 600  # 10 minutes

# Edit this text to change what a rate-limited customer sees.
RATE_LIMIT_REPLY = "You are sending messages quickly. Please wait a few minutes."


def _rate_limit_cache_key(session_id):
    return f"propdesk:rate_limit:{session_id}"


def check_rate_limit(session_id="unknown", now=None):
    """Check whether this session has already sent RATE_LIMIT_MAX_MESSAGES
    messages in the last RATE_LIMIT_WINDOW_SECONDS seconds.

    Uses Django's own cache (no new library to install) to remember,
    for each session, the times its recent messages arrived. `now` is
    only for tests, so they do not have to wait 10 real minutes — leave
    it out in real use and the real clock is used.

    This message is counted whether it ends up blocked or not, so a
    visitor cannot get extra tries by sending messages while blocked —
    the limit only clears once the session stops sending messages for
    a whole window.

    Returns (blocked, reply) — same shape as the other guards.
    """
    current_time = time.time() if now is None else now
    key = _rate_limit_cache_key(session_id)
    timestamps = cache.get(key) or []

    window_start = current_time - RATE_LIMIT_WINDOW_SECONDS
    recent = [sent_at for sent_at in timestamps if sent_at > window_start]

    blocked = len(recent) >= RATE_LIMIT_MAX_MESSAGES

    recent.append(current_time)
    cache.set(key, recent, timeout=RATE_LIMIT_WINDOW_SECONDS)

    if blocked:
        _log_rate_limit_triggered(session_id)
        return True, RATE_LIMIT_REPLY

    return False, None


def _log_rate_limit_triggered(session_id):
    """Record that the guard fired — only the time and the session id."""
    logger.warning(
        "guard_triggered rule=rate_limit session=%s time=%s",
        session_id,
        datetime.now(timezone.utc).isoformat(),
    )
