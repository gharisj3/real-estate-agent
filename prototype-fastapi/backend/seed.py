"""Adds a few sample properties so the staff console has something to show.
Run with: python -m backend.seed
"""
from .database import get_connection, init_db

SAMPLE_PROPERTIES = [
    ("Sunny 2BR in Jumeirah", "Jumeirah 1, Dubai", "apartment", 1450000, 2, 2,
     "Bright apartment close to the beach, recently renovated.", "available", ""),
    ("Downtown Studio", "Downtown Dubai", "apartment", 780000, 0, 1,
     "Compact studio with Burj Khalifa view.", "available", ""),
    ("Family Villa with Garden", "Arabian Ranches", "villa", 3200000, 4, 5,
     "Spacious villa with private garden and pool.", "booked", ""),
]


def seed():
    init_db()
    conn = get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) AS c FROM properties").fetchone()["c"]
        if count > 0:
            print(f"Database already has {count} properties, skipping seed.")
            return
        conn.executemany(
            """
            INSERT INTO properties
                (title, address, property_type, price, bedrooms, bathrooms, description, status, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            SAMPLE_PROPERTIES,
        )
        conn.commit()
        print(f"Added {len(SAMPLE_PROPERTIES)} sample properties.")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
