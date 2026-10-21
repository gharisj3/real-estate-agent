"""Create a staff account, or reset an existing one's password.
Run with: python -m backend.create_staff <username>
"""
import getpass
import sys

from .auth import create_or_update_staff
from .database import init_db


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python -m backend.create_staff <username>")
    username = sys.argv[1]
    password = getpass.getpass("Password (at least 10 characters, hidden as you type): ")
    if password != getpass.getpass("Type it again: "):
        sys.exit("The two passwords did not match. Nothing was changed.")
    init_db()
    try:
        created = create_or_update_staff(username, password)
    except ValueError as e:
        sys.exit(str(e))
    print(f"Account '{username}' created." if created else f"Password for '{username}' reset.")


if __name__ == "__main__":
    main()
