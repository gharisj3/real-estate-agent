"""Basic rule-based chat: finds available properties that match what the customer typed.
No AI model yet; this gives reliable answers straight from the property list.
"""
import re

from .database import get_connection

PROPERTY_TYPES = ["apartment", "villa", "townhouse", "office"]
GREETINGS = ("hi", "hello", "hey", "salam", "good morning", "good evening")

HELP_TEXT = (
    "I can help you find a property. Try something like: "
    "\"2 bedroom apartment in Jumeirah under 2m\" or \"show me villas\"."
)


def parse_amount(text: str):
    """Find a budget like 'under 2m', 'below 800k' or 'max 1,500,000'."""
    match = re.search(
        r"(?:under|below|less than|max|up to|budget(?: of)?)\s*(?:aed\s*)?([\d,.]+)\s*(m|million|k|thousand)?",
        text,
    )
    if not match:
        return None
    try:
        value = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    unit = match.group(2)
    if unit in ("m", "million"):
        value *= 1_000_000
    elif unit in ("k", "thousand"):
        value *= 1_000
    return value


def parse_bedrooms(text: str):
    if "studio" in text:
        return 0
    match = re.search(r"(\d+)\s*[- ]?\s*(?:br|bed|beds|bedroom|bedrooms)\b", text)
    return int(match.group(1)) if match else None


def area_names(address: str):
    """'Jumeirah 1, Dubai' -> ['jumeirah', 'dubai']"""
    names = []
    for part in address.split(","):
        name = re.sub(r"\s*\d+\s*$", "", part.strip().lower())
        if name:
            names.append(name)
    return names


def format_price(price: float) -> str:
    return f"AED {price:,.0f}"


def search_reply(message: str) -> dict:
    text = message.strip().lower()
    if not text:
        return {"reply": HELP_TEXT, "properties": []}

    bedrooms = parse_bedrooms(text)
    budget = parse_amount(text)
    wanted_type = next((t for t in PROPERTY_TYPES if t in text or t + "s" in text), None)

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM properties WHERE status = 'available' ORDER BY price"
        ).fetchall()
    finally:
        conn.close()

    wanted_areas = set()
    for row in rows:
        for name in area_names(row["address"]):
            if name in text:
                wanted_areas.add(name)

    has_filter = bedrooms is not None or budget is not None or wanted_type or wanted_areas
    is_browse = any(w in text for w in ("show", "list", "available", "properties", "what do you have", "anything"))

    if not has_filter and not is_browse:
        if text.startswith(GREETINGS):
            return {"reply": "Hello! Welcome to PropDesk. " + HELP_TEXT, "properties": []}
        return {"reply": HELP_TEXT, "properties": []}

    matches = []
    for row in rows:
        if bedrooms is not None and row["bedrooms"] != bedrooms:
            continue
        if budget is not None and row["price"] > budget:
            continue
        if wanted_type and row["property_type"] != wanted_type:
            continue
        if wanted_areas and not (wanted_areas & set(area_names(row["address"]))):
            continue
        matches.append(row)

    if not matches:
        return {
            "reply": "Sorry, I could not find an available property matching that. "
                     "Try a different budget, area or number of bedrooms.",
            "properties": [],
        }

    lines = [
        f"- #{m['id']} {m['title']} ({m['address']}): {format_price(m['price'])}, "
        f"{'studio' if m['bedrooms'] == 0 else str(m['bedrooms']) + ' bed'}, {m['bathrooms']} bath"
        for m in matches
    ]
    noun = "property" if len(matches) == 1 else "properties"
    return {
        "reply": f"I found {len(matches)} available {noun}:\n" + "\n".join(lines)
        + "\n\nTo book a viewing, say \"book #\" and the number, for example \"book #" + str(matches[0]["id"]) + "\".",
        "properties": [
            {"id": m["id"], "title": m["title"], "address": m["address"], "price": m["price"]}
            for m in matches
        ],
    }
