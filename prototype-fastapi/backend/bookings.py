"""Rules for viewing bookings: one-hour slots, 10:00 to 17:00, one customer per slot."""
import re
import sqlite3
from datetime import date, datetime, timedelta

from . import notifications

OPEN_HOUR = 10
LAST_HOUR = 17
MAX_DAYS_AHEAD = 60
TIME_FORMAT = "%Y-%m-%d %H:%M"


class BookingError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def free_slots(conn, property_id: int, day: date) -> list[datetime]:
    taken = {
        r["viewing_time"]
        for r in conn.execute(
            "SELECT viewing_time FROM bookings "
            "WHERE property_id = ? AND status = 'confirmed' AND viewing_time LIKE ?",
            (property_id, day.isoformat() + "%"),
        )
    }
    now = datetime.now()
    slots = [datetime(day.year, day.month, day.day, h) for h in range(OPEN_HOUR, LAST_HOUR + 1)]
    return [s for s in slots if s > now and s.strftime(TIME_FORMAT) not in taken]


def clean_name(name: str) -> str:
    name = " ".join(name.split())
    if not name or len(name) > 100:
        raise BookingError("Please give a name (up to 100 characters).")
    return name


def clean_phone(phone: str) -> str:
    phone = phone.strip()
    digits = re.sub(r"\D", "", phone)
    if not re.fullmatch(r"[+\d\s\-()]+", phone) or not 7 <= len(digits) <= 15:
        raise BookingError("Please give a valid phone number, for example +971 50 123 4567.")
    return phone


def clean_email(email) -> str:
    email = (email or "").strip()
    if not email:
        return ""
    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise BookingError("Please give a valid email address, or leave it out.")
    return email


def create_booking(conn, property_id: int, name: str, phone: str, when: datetime, email: str = "") -> dict:
    name = clean_name(name)
    phone = clean_phone(phone)
    email = clean_email(email)

    prop = conn.execute("SELECT * FROM properties WHERE id = ?", (property_id,)).fetchone()
    if prop is None:
        raise BookingError("Property not found.", 404)
    if prop["status"] != "available":
        raise BookingError("This property is not available for viewings.", 409)

    if when.minute != 0 or when.second != 0 or not OPEN_HOUR <= when.hour <= LAST_HOUR:
        raise BookingError(f"Viewings run on the hour, {OPEN_HOUR}:00 to {LAST_HOUR}:00.")
    if when <= datetime.now():
        raise BookingError("That time has already passed.")
    if (when.date() - date.today()).days > MAX_DAYS_AHEAD:
        raise BookingError(f"We can only book up to {MAX_DAYS_AHEAD} days ahead.")

    try:
        cursor = conn.execute(
            "INSERT INTO bookings (property_id, customer_name, customer_phone, customer_email, "
            "viewing_time, reminder_sent) VALUES (?, ?, ?, ?, ?, ?)",
            (property_id, name, phone, email, when.strftime(TIME_FORMAT),
             1 if when - datetime.now() < timedelta(hours=24) else 0),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise BookingError("Sorry, that time was just taken. Please pick another.", 409)

    booking = {
        "id": cursor.lastrowid,
        "property_id": property_id,
        "property_title": prop["title"],
        "property_address": prop["address"],
        "customer_name": name,
        "customer_phone": phone,
        "customer_email": email,
        "viewing_time": when.strftime(TIME_FORMAT),
        "status": "confirmed",
    }
    notifications.notify_booking_created(booking)
    return booking
