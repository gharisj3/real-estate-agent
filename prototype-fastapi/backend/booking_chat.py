"""Chat that can book a viewing step by step.
The conversation position is kept by the web page and sent back with each message ("state").
Every value in the state is re-checked before a booking is made.
"""
import re
from datetime import date, datetime, timedelta

from .bookings import MAX_DAYS_AHEAD, BookingError, clean_email, clean_phone, create_booking, free_slots
from .chat import search_reply
from .database import get_connection

BOOK_WORDS = re.compile(r"\b(book|booking|viewing|visit|schedule)\b")
STOP_WORDS = ("cancel", "stop", "never mind", "nevermind", "exit", "quit")
SKIP_WORDS = ("skip", "no", "none", "no thanks", "n/a")
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def say(reply: str, state=None) -> dict:
    return {"reply": reply, "properties": [], "state": state}


def find_property(conn, text: str, allow_bare_number: bool = False):
    rows = conn.execute("SELECT * FROM properties WHERE status = 'available'").fetchall()
    match = re.search(r"#\s*(\d+)", text)
    if not match and allow_bare_number:
        match = re.fullmatch(r"\s*(\d+)\s*", text)
    if not match:
        match = re.search(r"\b(?:book|viewing|visit)\s+(?:property\s+)?(\d+)\b", text)
    if match:
        wanted = int(match.group(1))
        return next((r for r in rows if r["id"] == wanted), None)
    return next((r for r in rows if r["title"].lower() in text), None)


def parse_date(text: str):
    today = date.today()
    if "today" in text:
        return today
    if "tomorrow" in text:
        return today + timedelta(days=1)
    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    for i, name in enumerate(WEEKDAYS):
        if name in text:
            return today + timedelta(days=(i - today.weekday()) % 7)
    return None


def parse_hour(text: str):
    match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
    if not match or int(match.group(2) or 0) != 0:
        return None
    hour, suffix = int(match.group(1)), match.group(3)
    if suffix == "pm" and hour < 12:
        hour += 12
    elif suffix == "am" and hour == 12:
        hour = 0
    elif suffix is None and 1 <= hour <= 7:
        hour += 12
    return hour


def start_booking(conn, text: str) -> dict:
    prop = find_property(conn, text)
    if prop is None:
        return say(
            "Which property would you like to view? Tell me its number, for example \"#1\". "
            "Say \"show properties\" to see the list.",
            {"step": "property"},
        )
    return ask_date(prop)


def ask_date(prop) -> dict:
    return say(
        f"Great, let's book a viewing of {prop['title']}. What day would you like? "
        "You can say \"today\", \"tomorrow\", a weekday like \"friday\", or a date like 2026-11-05.",
        {"step": "date", "property_id": prop["id"]},
    )


def handle_step(conn, text: str, state: dict, raw: str) -> dict:
    step = state.get("step")
    property_id = state.get("property_id")

    if step == "property":
        prop = find_property(conn, text, allow_bare_number=True)
        if prop is None:
            return say("I could not find that property. Please give its number, like \"#1\".", state)
        return ask_date(prop)

    if not isinstance(property_id, int):
        return say("Let's start again. " + "Which property would you like to view?", {"step": "property"})
    prop = conn.execute(
        "SELECT * FROM properties WHERE id = ? AND status = 'available'", (property_id,)
    ).fetchone()
    if prop is None:
        return say("Sorry, that property is no longer available. Say \"show properties\" to see others.")

    if step == "date":
        day = parse_date(text)
        if day is None:
            return say("I did not understand the date. Try \"tomorrow\", \"friday\" or 2026-11-05.", state)
        if (day - date.today()).days > MAX_DAYS_AHEAD:
            return say(f"I can only book up to {MAX_DAYS_AHEAD} days ahead. Please pick an earlier day.", state)
        slots = free_slots(conn, property_id, day)
        if not slots:
            return say("There are no free times that day. Please pick another day.", state)
        times = ", ".join(s.strftime("%H:%M") for s in slots)
        return say(
            f"Free times on {day.isoformat()}: {times}. Which time suits you?",
            {"step": "time", "property_id": property_id, "date": day.isoformat()},
        )

    if step == "time":
        try:
            day = date.fromisoformat(str(state.get("date")))
        except ValueError:
            return say("Let's start again. What day would you like?", {"step": "date", "property_id": property_id})
        hour = parse_hour(text)
        slots = free_slots(conn, property_id, day)
        chosen = next((s for s in slots if s.hour == hour), None)
        if chosen is None:
            times = ", ".join(s.strftime("%H:%M") for s in slots) or "none"
            return say(f"That time is not free. Free times: {times}.", state)
        return say(
            "What name should I put the booking under?",
            {"step": "name", "property_id": property_id, "time": chosen.strftime("%Y-%m-%d %H:%M")},
        )

    if step == "name":
        name = " ".join(raw.split())
        if not name or len(name) > 100:
            return say("Please tell me your name (up to 100 characters).", state)
        return say(
            "Thanks. What is your phone number, so our agent can reach you?",
            {**state, "step": "phone", "name": name},
        )

    if step == "phone":
        try:
            phone = clean_phone(raw)
        except BookingError as e:
            return say(e.message, state)
        return say(
            "Last question: what is your email address? We will send a confirmation and a reminder. "
            "Say \"skip\" if you would rather not.",
            {**state, "step": "email", "phone": phone},
        )

    if step == "email":
        email = "" if text in SKIP_WORDS else raw
        try:
            email = clean_email(email)
            when = datetime.strptime(str(state.get("time")), "%Y-%m-%d %H:%M")
            booking = create_booking(conn, property_id, str(state.get("name", "")),
                                     str(state.get("phone", "")), when, email)
        except (BookingError, ValueError) as e:
            message = e.message if isinstance(e, BookingError) else "Something went wrong with the time."
            if isinstance(e, BookingError) and "email" in message.lower():
                return say(message + " Or say \"skip\".", state)
            return say(message + " Say \"book\" to try again.")
        extra = f" A confirmation is on its way to {email}." if email else ""
        return say(
            f"Your viewing is confirmed! {booking['property_title']} on {booking['viewing_time']} "
            f"under the name {booking['customer_name']}. Our agent will contact you on "
            f"{booking['customer_phone']} if anything changes.{extra}"
        )

    return say(search_reply("")["reply"])


def reply_to(message: str, state=None) -> dict:
    text = message.strip().lower()
    conn = get_connection()
    try:
        if isinstance(state, dict) and state.get("step"):
            if any(w in text for w in STOP_WORDS):
                return say("No problem, I have stopped the booking. Is there anything else I can help with?")
            return handle_step(conn, text, state, message.strip())
        if BOOK_WORDS.search(text):
            return start_booking(conn, text)
    finally:
        conn.close()
    result = search_reply(message)
    result["state"] = None
    return result
