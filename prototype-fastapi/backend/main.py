from datetime import date, datetime
from pathlib import Path
from typing import Optional

import os

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel, Field

from .bookings import BookingError, create_booking, free_slots
from .ai_chat import ai_reply
from .notifications import notify_booking_cancelled, start_reminder_loop
from .auth import (COOKIE_NAME, SESSION_SECONDS, check_login, clear_failures, end_session,
                   record_failure, require_staff, start_session, too_many_failures)
from .booking_chat import reply_to
from .database import get_connection, init_db
from .schemas import PropertyIn, PropertyUpdate, PropertyOut, ALLOWED_STATUSES

app = FastAPI(title="PropDesk Staff API")


@app.on_event("startup")
def on_startup():
    init_db()
    start_reminder_loop()


def row_to_property(row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "address": row["address"],
        "property_type": row["property_type"],
        "price": row["price"],
        "bedrooms": row["bedrooms"],
        "bathrooms": row["bathrooms"],
        "description": row["description"],
        "status": row["status"],
        "image_url": row["image_url"],
        "created_at": row["created_at"],
    }


@app.get("/api/properties", response_model=list[PropertyOut], dependencies=[Depends(require_staff)])
def list_properties():
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM properties ORDER BY created_at DESC").fetchall()
        return [row_to_property(r) for r in rows]
    finally:
        conn.close()


@app.get("/api/properties/{property_id}", response_model=PropertyOut, dependencies=[Depends(require_staff)])
def get_property(property_id: int):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM properties WHERE id = ?", (property_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Property not found")
        return row_to_property(row)
    finally:
        conn.close()


@app.post("/api/properties", response_model=PropertyOut, status_code=201, dependencies=[Depends(require_staff)])
def create_property(payload: PropertyIn):
    if payload.status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(ALLOWED_STATUSES)}")
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO properties
                (title, address, property_type, price, bedrooms, bathrooms, description, status, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.title,
                payload.address,
                payload.property_type,
                payload.price,
                payload.bedrooms,
                payload.bathrooms,
                payload.description,
                payload.status,
                payload.image_url,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM properties WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return row_to_property(row)
    finally:
        conn.close()


@app.put("/api/properties/{property_id}", response_model=PropertyOut, dependencies=[Depends(require_staff)])
def update_property(property_id: int, payload: PropertyUpdate):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "status" in updates and updates["status"] not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(ALLOWED_STATUSES)}")
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    conn = get_connection()
    try:
        existing = conn.execute("SELECT * FROM properties WHERE id = ?", (property_id,)).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Property not found")

        set_clause = ", ".join(f"{field} = ?" for field in updates)
        conn.execute(
            f"UPDATE properties SET {set_clause} WHERE id = ?",
            (*updates.values(), property_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM properties WHERE id = ?", (property_id,)).fetchone()
        return row_to_property(row)
    finally:
        conn.close()


@app.delete("/api/properties/{property_id}", status_code=204, dependencies=[Depends(require_staff)])
def delete_property(property_id: int):
    conn = get_connection()
    try:
        existing = conn.execute("SELECT * FROM properties WHERE id = ?", (property_id,)).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Property not found")
        upcoming = conn.execute(
            "SELECT COUNT(*) AS c FROM bookings WHERE property_id = ? "
            "AND status = 'confirmed' AND viewing_time > datetime('now', 'localtime')",
            (property_id,),
        ).fetchone()["c"]
        if upcoming:
            raise HTTPException(
                status_code=409,
                detail=f"This property has {upcoming} upcoming viewing(s). Cancel them first.",
            )
        conn.execute("DELETE FROM properties WHERE id = ?", (property_id,))
        conn.commit()
    finally:
        conn.close()


class LoginIn(BaseModel):
    username: str = Field(max_length=50)
    password: str = Field(max_length=200)


@app.post("/api/login")
def login(payload: LoginIn, request: Request, response: Response):
    key = (request.client.host if request.client else "unknown", payload.username.lower())
    if too_many_failures(key):
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait 5 minutes.")
    staff = check_login(payload.username, payload.password)
    if staff is None:
        record_failure(key)
        raise HTTPException(status_code=401, detail="Wrong username or password.")
    clear_failures(key)
    response.set_cookie(
        COOKIE_NAME,
        start_session(staff["id"]),
        max_age=SESSION_SECONDS,
        httponly=True,
        samesite="lax",
        secure=os.environ.get("PROPDESK_HTTPS") == "1",
    )
    return {"username": staff["username"]}


@app.post("/api/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        end_session(token)
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


class ChatIn(BaseModel):
    message: str = Field(max_length=500)
    state: Optional[dict] = None
    history: list[dict] = Field(default_factory=list, max_length=40)


@app.post("/api/chat")
def chat(payload: ChatIn, request: Request):
    ip = request.client.host if request.client else "unknown"
    result = ai_reply(payload.message, payload.history, ip)
    if result is None:
        result = reply_to(payload.message, payload.state)
        result["mode"] = "basic"
    return result


class BookingIn(BaseModel):
    property_id: int
    customer_name: str = Field(max_length=100)
    customer_phone: str = Field(max_length=30)
    customer_email: str = Field(default="", max_length=254)
    viewing_time: datetime


@app.get("/api/properties/{property_id}/slots")
def get_slots(property_id: int, day: date):
    conn = get_connection()
    try:
        return [s.strftime("%H:%M") for s in free_slots(conn, property_id, day)]
    finally:
        conn.close()


@app.post("/api/bookings", status_code=201)
def create_booking_endpoint(payload: BookingIn):
    conn = get_connection()
    try:
        return create_booking(
            conn, payload.property_id, payload.customer_name,
            payload.customer_phone, payload.viewing_time.replace(tzinfo=None),
            payload.customer_email,
        )
    except BookingError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    finally:
        conn.close()


@app.get("/api/bookings", dependencies=[Depends(require_staff)])
def list_bookings():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT b.*, p.title AS property_title FROM bookings b "
            "JOIN properties p ON p.id = b.property_id ORDER BY b.viewing_time"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.post("/api/bookings/{booking_id}/cancel", dependencies=[Depends(require_staff)])
def cancel_booking(booking_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT b.*, p.title AS property_title, p.address AS property_address "
            "FROM bookings b JOIN properties p ON p.id = b.property_id WHERE b.id = ?",
            (booking_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Booking not found")
        if row["status"] == "confirmed":
            conn.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
            conn.commit()
            notify_booking_cancelled(dict(row))
        return {"id": booking_id, "status": "cancelled"}
    finally:
        conn.close()


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
