"""Email notifications: customer confirmation, staff alert, cancellation, 24-hour reminder.
Email is only sent when PROPDESK_SMTP_HOST is set. Sending never blocks or breaks a booking.
Limits stop the system being used to spam: 3 emails per customer address per day, 200 per day in total.
"""
import logging
import os
import smtplib
import threading
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from email.message import EmailMessage

from .database import get_connection

log = logging.getLogger("propdesk.mail")

PER_RECIPIENT_LIMIT = 3
REMINDER_CHECK_SECONDS = 600
TIME_FORMAT = "%Y-%m-%d %H:%M"

_lock = threading.Lock()
_sent = {"date": None, "total": 0, "per": defaultdict(int)}


def smtp_configured() -> bool:
    return bool(os.environ.get("PROPDESK_SMTP_HOST"))


def agency_name() -> str:
    return os.environ.get("PROPDESK_AGENCY_NAME", "PropDesk")


def staff_addresses() -> list[str]:
    raw = os.environ.get("PROPDESK_STAFF_EMAIL", "")
    return [a.strip() for a in raw.split(",") if a.strip()]


def _reserve(to: str, is_customer: bool) -> bool:
    daily_limit = int(os.environ.get("PROPDESK_EMAIL_DAILY_LIMIT", "200"))
    with _lock:
        today = date.today().isoformat()
        if _sent["date"] != today:
            _sent.update(date=today, total=0, per=defaultdict(int))
        key = to.lower()
        if _sent["total"] >= daily_limit or (is_customer and _sent["per"][key] >= PER_RECIPIENT_LIMIT):
            return False
        _sent["total"] += 1
        _sent["per"][key] += 1
        return True


def send_email(to: str, subject: str, body: str, is_customer: bool = True) -> bool:
    if not smtp_configured() or not to:
        return False
    if not _reserve(to, is_customer):
        log.warning("Email limit reached, not sending")
        return False
    host = os.environ["PROPDESK_SMTP_HOST"]
    port = int(os.environ.get("PROPDESK_SMTP_PORT", "587"))
    user = os.environ.get("PROPDESK_SMTP_USER", "")
    password = os.environ.get("PROPDESK_SMTP_PASSWORD", "")
    sender = os.environ.get("PROPDESK_EMAIL_FROM") or user
    try:
        msg = EmailMessage()
        msg["From"] = f"{agency_name()} <{sender}>"
        msg["To"] = to
        msg["Subject"] = " ".join(subject.split())[:200]
        staff = staff_addresses()
        if staff and is_customer:
            msg["Reply-To"] = staff[0]
        msg.set_content(body)
        smtp_class = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
        with smtp_class(host, port, timeout=15) as smtp:
            if port != 465 and os.environ.get("PROPDESK_SMTP_TLS", "on").lower() != "off":
                smtp.starttls()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
        return True
    except Exception as e:
        log.warning("Email failed (%s)", type(e).__name__)
        return False


def _details(b: dict) -> str:
    return (
        f"Property: {b['property_title']}\n"
        f"Address: {b['property_address']}\n"
        f"When: {b['viewing_time']} (one hour)\n"
    )


def _send_created(b: dict) -> None:
    if b["customer_email"]:
        send_email(
            b["customer_email"],
            f"Your viewing is confirmed: {b['property_title']}",
            f"Hello {b['customer_name']},\n\nYour viewing is confirmed.\n\n{_details(b)}\n"
            f"We will send a reminder the day before. If you need to change the time, "
            f"just reply to this email or call us.\n\n{agency_name()}",
        )
    for address in staff_addresses():
        send_email(
            address,
            f"New viewing: {b['property_title']} on {b['viewing_time']}",
            f"A viewing was booked.\n\n{_details(b)}"
            f"Customer: {b['customer_name']}\nPhone: {b['customer_phone']}\n"
            f"Email: {b['customer_email'] or '(not given)'}\n",
            is_customer=False,
        )


def _send_cancelled(b: dict) -> None:
    if b["customer_email"]:
        send_email(
            b["customer_email"],
            f"Your viewing was cancelled: {b['property_title']}",
            f"Hello {b['customer_name']},\n\nYour viewing has been cancelled.\n\n{_details(b)}\n"
            f"Please contact us if you would like to book another time.\n\n{agency_name()}",
        )
    for address in staff_addresses():
        send_email(
            address,
            f"Viewing cancelled: {b['property_title']} on {b['viewing_time']}",
            f"A viewing was cancelled.\n\n{_details(b)}Customer: {b['customer_name']}\nPhone: {b['customer_phone']}\n",
            is_customer=False,
        )


def _in_background(fn, booking: dict) -> None:
    if not smtp_configured():
        return

    def job():
        try:
            fn(booking)
        except Exception:
            log.exception("Notification job failed")

    threading.Thread(target=job, daemon=True).start()


def notify_booking_created(booking: dict) -> None:
    _in_background(_send_created, booking)


def notify_booking_cancelled(booking: dict) -> None:
    _in_background(_send_cancelled, booking)


def send_due_reminders() -> int:
    """Email customers whose viewing is within the next 24 hours. Returns how many were sent."""
    if not smtp_configured():
        return 0
    now = datetime.now()
    conn = get_connection()
    sent = 0
    try:
        rows = conn.execute(
            "SELECT b.*, p.title AS property_title, p.address AS property_address "
            "FROM bookings b JOIN properties p ON p.id = b.property_id "
            "WHERE b.status = 'confirmed' AND b.reminder_sent = 0 AND b.customer_email != '' "
            "AND b.viewing_time > ? AND b.viewing_time <= ?",
            (now.strftime(TIME_FORMAT), (now + timedelta(hours=24)).strftime(TIME_FORMAT)),
        ).fetchall()
        for r in rows:
            ok = send_email(
                r["customer_email"],
                f"Reminder: viewing of {r['property_title']} at {r['viewing_time']}",
                f"Hello {r['customer_name']},\n\nThis is a reminder of your viewing.\n\n{_details(dict(r))}\n"
                f"If you cannot make it, please reply to this email or call us.\n\n{agency_name()}",
            )
            if ok:
                conn.execute("UPDATE bookings SET reminder_sent = 1 WHERE id = ?", (r["id"],))
                conn.commit()
                sent += 1
    finally:
        conn.close()
    return sent


def _reminder_loop() -> None:
    while True:
        try:
            send_due_reminders()
        except Exception:
            log.exception("Reminder check failed")
        time.sleep(REMINDER_CHECK_SECONDS)


def start_reminder_loop() -> None:
    if smtp_configured():
        threading.Thread(target=_reminder_loop, daemon=True).start()
        log.warning("Email notifications are ON")
    else:
        log.warning("Email notifications are OFF (PROPDESK_SMTP_HOST not set)")
