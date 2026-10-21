# PropDesk step log

## 2026-10-21: Django project skeleton
**What changed:** Started the real PropDesk project on Django. Set the earlier prototype aside. Created a virtual environment with Django 6.1.2, a Django project called `propdesk`, and an app called `core`. Added `.gitignore` and `.env.example` (setting names only, no values). Changed `propdesk/settings.py` so the secret key and debug switch come from the computer's settings, not from the file. Started git with a first commit.
**Files:** `manage.py`, `propdesk/`, `core/`, `requirements.txt`, `.gitignore`, `.env.example`, `STEPLOG.md`. The old files moved into `prototype-fastapi/`.
**How to undo:** Move everything inside `prototype-fastapi/` back to the main folder (its `.gitignore` and `requirements.txt` replace the new ones). Delete `manage.py`, `propdesk/`, `core/`, `.env.example`, `.venv/`, and the hidden `.git/` folder.

## Before 2026-10-21: first prototype (written before this log existed)
**What changed:** Built a working prototype using a different tool (FastAPI): property list, staff console with login, customer chat with an AI model and a simple fallback, viewing bookings, and email notifications. Also wrote `CLAUDE.md`, `SPEC.md`, `GO-LIVE.md` and `docs/flow.md`.
**Files:** now in `prototype-fastapi/` (code) and the main folder (the four documents).
**How to undo:** Nothing to undo. It is kept as a reference. Its README says how to run it. Note that its chat used Anthropic's AI, while the new plan uses Groq (`GROQ_API_KEY`), so that part will be redone.
