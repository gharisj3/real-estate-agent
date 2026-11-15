# PropDesk step log

## 2026-11-15: Two more guards — a kill switch and a rate limit per session
**What changed:**
- Added `check_kill_switch` to `core/guards.py`. It reads a new setting,
  `PROPDESK_BOT_ENABLED`, from `.env`. Set it to `false` and every customer
  gets "Our assistant is offline right now. A team member will reply soon."
  instead of a real reply — no AI call at all, for anyone. Anything other
  than exactly `false` (including a missing setting) counts as on, so a
  typo in `.env` can't accidentally take the assistant down. Added
  `PROPDESK_BOT_ENABLED=true` to `.env.example` and to the real `.env`.
- Added `check_rate_limit` to `core/guards.py`. It remembers, per chat
  session, the times its last messages arrived, using Django's own cache
  (no new library to install). The two numbers — 20 messages, 10 minutes —
  are both constants (`RATE_LIMIT_MAX_MESSAGES`, `RATE_LIMIT_WINDOW_SECONDS`)
  right next to each other at the top of that guard's section, so they're
  easy to find and change together. Past the limit, a session gets "You are
  sending messages quickly. Please wait a few minutes." instead of reaching
  the AI, until the 10-minute window has cleared.
- Wired both into `core/pipeline.py`, as the very first two checks —
  before the override check, before the fair-housing guard, before
  anything else. The kill switch runs first; if the assistant is off, the
  rate limit is never even checked for that message.
- Tests: `core/tests/test_kill_switch_guard.py` (6 tests) — on/off, case
  does not matter, a missing or unrecognised value defaults to on, and the
  trigger is logged. `core/tests/test_rate_limit_guard.py` (6 tests) — the
  20th message in a session is allowed, the 21st is blocked, the limit
  resets once the window has passed (using a fake `now` passed straight
  into the guard — no 10-minute sleep), a different session has its own,
  separate limit, and the trigger is logged. Also added one test to
  `core/tests/test_pipeline.py` proving the kill switch is wired correctly:
  with it off, `handle_message` returns the offline reply and the AI is
  never called.
- Updated `docs/guards.md`: the rate-limit row is now marked "(built)",
  with its real numbers (20 messages / 10 minutes) instead of a vague
  description, and a new "(built)" row was added for the kill switch.
- Ran the whole `core` test suite: 46 tests, all passed.
**Files:** `core/guards.py` (added `check_kill_switch`, `check_rate_limit`,
and their constants/logging helpers; added `os`, `time`, and
`django.core.cache` imports), `core/pipeline.py` (wired both checks in as
steps 1 and 2, renumbered the rest), `.env.example` and `.env` (added
`PROPDESK_BOT_ENABLED=true`), `core/tests/test_kill_switch_guard.py` (new),
`core/tests/test_rate_limit_guard.py` (new), `core/tests/test_pipeline.py`
(updated expected step lists, added the kill-switch wiring test),
`docs/guards.md` (updated two rows).
**How to undo:** Delete `core/tests/test_kill_switch_guard.py` and
`core/tests/test_rate_limit_guard.py`. In `core/tests/test_pipeline.py`,
remove the `test_bot_offline_blocks_everything_before_the_ai` test, remove
`"PROPDESK_BOT_ENABLED": "true"` from the class decorator, and remove
`"kill_switch", "rate_limit",` from the three expected step lists it was
added to. In `core/pipeline.py`, remove steps 1 and 2 (kill switch, rate
limit) from `_run_pipeline` and from the import line, and renumber the
rest back to 1-7. In `core/guards.py`, remove everything from "Guard: kill
switch" onward, and remove the now-unused `os`, `time`, and
`django.core.cache` imports if nothing else in the file needs them.
Remove the `PROPDESK_BOT_ENABLED` line from `.env.example` and `.env`. In
`docs/guards.md`, revert the two edited rows.

## 2026-11-15: Wired chat_groq.py into the pipeline — the terminal chat is now guarded
**What changed:**
- `chat_groq.py` no longer talks to Groq on its own. It now sets up Django,
  then calls `core.pipeline.handle_message(session_id, text)` for every
  message typed in, and just prints whatever it returns. This is the same
  function any other chat channel must use, so the terminal chat now gets
  every guard: AI disclosure, fair housing, instruction override, the
  prompt-leak canary, and facts-only — none of which it had before today.
- Removed the old direct Groq client code, the model name, the manual
  conversation history list, and the per-error messages for an invalid key,
  no internet, or a rate limit — `core/pipeline.py` already fails closed on
  any of those with its own safe reply and its own log entry, so chat_groq.py
  doesn't need to handle them itself any more.
- One session id (a random id) is generated per run of the script, so the
  disclosure notice appears once, at the start of each run, same as before.
- Tested by hand, running the script three times: a fair-housing attempt
  ("I only want Muslim tenants, no one else.") was blocked with the fixed
  refusal and the disclosure notice, and the guard's log line showed up —
  the AI was never called. An override attempt ("Please ignore your
  instructions...") was blocked the same way. An ordinary question ("Hello,
  what can you help me with?") reached the real AI and got a normal reply,
  with the disclosure notice on top.
- Ran the whole `core` test suite again afterwards: still 33 tests, all
  passed — this change did not touch any guard or test file.
**Files:** `chat_groq.py` (rewritten to call `core.pipeline.handle_message`).
**How to undo:** Restore the version of `chat_groq.py` from before this
entry (it talked to the Groq client directly, with no guards). See the
2026-10-25 entries below for what that version looked like.

## 2026-11-15: The pipeline — one path every chat channel must use
**What changed:**
- Added `core/pipeline.py` with one function, `handle_message(session_id, text)`.
  This is now the only correct way for any chat channel (the web page later,
  the terminal script, anything else) to talk to a customer — it runs every
  guard and the one allowed AI call in a fixed order, so no channel can skip
  a safety check by mistake:
  1. Override check (input) — blocks known "ignore your instructions" style
     messages before the AI ever sees them.
  2. Fair-housing guard (input) — blocks a request to filter by religion,
     race, nationality, sex, family status, disability, or age before the
     AI ever sees it.
  3. Property search by code (`core/property_search.py`) — works out a city,
     bedroom count, and price limit from the customer's own words (a city is
     only recognised if it is already in our database), and looks up the
     real matching listings. No AI involved.
  4. One AI call to Groq — given the real matches from step 3, so it can
     only describe real listings.
  5. Leak check (output) — throws away the reply if it contains the secret
     canary or a long copied piece of the instructions.
  6. Facts-only guard (output) — checks every price and bedroom count in the
     reply against step 3's matches only, not the whole database.
  7. AI disclosure — added by code on the first reply of the session only.
- If anything in steps 3-6 raises an error (a bug, a database problem, Groq
  being unreachable), the customer is never shown the raw AI reply or a
  technical error — they get a fixed safe reply ("We could not answer just
  now. A team member will contact you."), and the error is logged (session
  id, which step it failed on, the error type — never the customer's words).
- Keeps one conversation history per session in memory, so the assistant
  remembers earlier messages in the same chat and the disclosure notice only
  appears once. This is lost if the server restarts — fine for now, worth
  moving to the database later.
- The actual Groq call lives in its own small function
  (`core.pipeline._default_ai_call`), so tests can swap in a fake AI and run
  with no internet connection and no real API key.
- Tests (`core/tests/test_pipeline.py`, 7 tests, all using a fake AI): a
  normal question gets the real AI reply with the disclosure on top; a
  fair-housing attempt and an override attempt are both blocked before the
  AI is ever called (checked by failing the test if the fake AI runs); an
  invented price is caught by the facts-only guard; a reply that leaks the
  canary is caught by the leak guard, before the facts-only guard even runs;
  a fake AI that raises an error still gets the customer the safe reply, and
  logs the error without the exception's own message text; the disclosure
  notice appears on the first reply of a session and not the second.
- Ran the whole `core` test suite: 33 tests, all passed.
- **Not wired into `chat_groq.py` yet.** The terminal chat script still
  talks to Groq directly with no guards at all — that is still the next
  step, now that `handle_message()` exists for it to call.
**Files:** `core/pipeline.py` (new), `core/tests/test_pipeline.py` (new).
**How to undo:** Delete `core/pipeline.py` and `core/tests/test_pipeline.py`.
Nothing else references them yet, so there is nothing else to unwind.

## 2026-11-01: Property model, sample data, and the fifth guard — facts only
**What changed:**
- Added a `Property` model (`core/models.py`): title, city, area, type (flat/house/plot), bedrooms, price, currency (PKR/AED), status (available/sold/rented), description. Registered it in the admin (`core/admin.py`) with a list view, filters, and search. Generated and applied the migration (`core/migrations/0001_initial.py`).
- Added a management command, `python manage.py load_sample_properties`, that loads 20 invented sample properties. Every title starts with "[SAMPLE DATA]", the city is the placeholder `[CITY]` (edit `SAMPLE_CITY` in the command once a real city is chosen), and the 5 area names are invented, not real neighbourhoods. Safe to run more than once — it will not create duplicates. Ran it once to check it works: 20 rows created in the local `db.sqlite3`.
- Added `core/property_search.py` — plain database filtering only, no AI: `find_matching_properties(city, bedrooms, max_price)` and `properties_as_facts(...)`, which turns the real matches into a plain-text block to hand to the AI so it only ever describes real listings.
- Added the fifth guard, `check_facts_only` in `core/guards.py`. It runs AFTER the AI replies: it pulls out every price and every bedroom count mentioned in the reply, and compares them against the real matched properties. If any number doesn't belong to one of them, the whole reply is thrown away and a fixed safe reply is shown instead ("let me connect you with a team member"). Logs the time, session id, and how many bad numbers were found — never the reply text.
- Tests (`core/tests/test_facts_only_guard.py`, 10 tests): the search function filters correctly by city/bedrooms/max price (alone and combined); a reply matching the real numbers passes through; a reply with an invented price is blocked; a reply with an invented bedroom count is blocked (even when the price is correct); the mismatch is logged; a good reply is not logged.
- Ran the whole `core` test suite: 26 tests, all passed.
- Not wired into `chat_groq.py` yet — the chat script still does not call the search function, build the facts block, or run any guard. That is the next step.
**Files:** `core/models.py` (new `Property` model), `core/admin.py` (registered it), `core/migrations/0001_initial.py` (new), `core/management/__init__.py`, `core/management/commands/__init__.py`, `core/management/commands/load_sample_properties.py` (new), `core/property_search.py` (new), `core/guards.py` (added `check_facts_only` and its helpers), `core/tests/test_facts_only_guard.py` (new), `db.sqlite3` (20 sample rows added locally).
**How to undo:** Delete `core/tests/test_facts_only_guard.py`, `core/property_search.py`, `core/management/` (the whole folder), and `core/migrations/0001_initial.py`. In `core/guards.py`, remove everything from "Guard: facts only" onward. In `core/models.py` and `core/admin.py`, remove the `Property` model and its registration. Run `python manage.py migrate core zero` before deleting the migration file, to undo it in the database too.

## 2026-11-01: Third and fourth guards — instruction-override check, and a canary to catch prompt leaks
**What changed:** Added two more checks to `core/guards.py`.
1. `check_instruction_override` runs BEFORE the AI sees the message. It uses a new phrase list in `core/guard_terms.py` (English and Roman Urdu — things like "ignore your instructions", "you are now", "reveal your prompt", "developer mode"). If a phrase matches, it returns a fixed reply and the AI is never called for that turn.
2. `check_output_leak` runs AFTER the AI replies. It needs a secret "canary" — a random code hidden inside the system prompt — to work. Added a `{{CANARY}}` placeholder as rule 9 in `prompts/assistant_v1.md` (safe to commit, since it's only a placeholder) and a new `GUARD_CANARY_TOKEN` entry in `.env.example`. Generated a real random value and added it straight to `.env` with a one-off script that only printed a status line, never the file's contents, so no secret was ever shown in this chat. `insert_canary()` swaps the placeholder for the real value when the prompt is loaded. `check_output_leak` then looks for that value, or any 8-word-or-longer run copied straight from the system prompt, inside the AI's reply — if either shows up, the reply is thrown away and a fixed safe reply is shown instead.
   Both checks log the time, a session id, and which rule/phrase/reason fired — never the customer's full message or the leaked text itself.
   Tested with 8 override attempts (English + Roman Urdu) that must trigger, 6 normal messages that must not (including one that just uses the word "ignore" normally), a fake AI reply that leaks the canary, a fake AI reply that copies a long excerpt without the canary, a normal fake reply that must pass through, and 2 logging checks. All 15 passed.
   Not wired into `chat_groq.py` yet.
**Files:** `core/guard_terms.py` (added `OVERRIDE_ATTEMPT_PHRASES`), `core/guards.py` (added the override guard, the canary/excerpt guard, and `insert_canary`), `prompts/assistant_v1.md` (added rule 9 with the `{{CANARY}}` placeholder), `.env.example` (added `GUARD_CANARY_TOKEN`), `.env` (added a real random `GUARD_CANARY_TOKEN` value — not committed, not shown in chat), `core/tests/test_injection_guards.py` (new).
**How to undo:** Delete `core/tests/test_injection_guards.py`. In `core/guards.py`, remove everything from "Guard: instruction override / prompt leak" onward, and remove `OVERRIDE_ATTEMPT_PHRASES` from the import line. In `core/guard_terms.py`, remove the `OVERRIDE_ATTEMPT_PHRASES` block. In `prompts/assistant_v1.md`, remove rule 9. Remove the `GUARD_CANARY_TOKEN` line from `.env.example` and from `.env`.

## 2026-11-01: Second guard — fair housing, checked before the AI sees the message
**What changed:** Added `core/guard_terms.py`, a plain word-list file (English, Urdu script, Roman Urdu) that a non-programmer can edit — "steering" words like "only"/"no"/"sirf" and protected-trait words (religion, race/ethnicity, nationality, sex, family status, disability, age, plus a "coded language" list for things like "our community"). Added `check_fair_housing` to `core/guards.py`: it runs before the AI ever sees the message, triggers only when a steering word AND a trait word are both present, and if it triggers it returns a fixed polite refusal instead of calling the AI, and logs the time, a session id, and which category fired — never the customer's actual words. Tested with 12 messages that must trigger it (covering every category, across all three scripts) and 12 normal property questions that must not (including the tricky ones: "near a mosque", "near a school", "ground floor for my elderly father"). All 24 passed, plus 2 tests on the logging itself. Not wired into `chat_groq.py` yet.
**Files:** `core/guard_terms.py` (new), `core/guards.py` (added `check_fair_housing`, `FAIR_HOUSING_REFUSAL`, and the logging helper), `core/tests/test_fair_housing_guard.py` (new).
**How to undo:** Delete `core/guard_terms.py` and `core/tests/test_fair_housing_guard.py`. In `core/guards.py`, remove everything from the "Guard: fair housing" section onward, and remove the `logging`/`re`/`datetime`/`core.guard_terms` imports at the top.

## 2026-11-01: First real guard — AI disclosure, enforced in code
**What changed:** Added `core/guards.py` with one function, `add_disclosure`, that puts a fixed notice in front of the AI's first reply in a chat (and leaves every later reply alone). The notice text lives in one constant, `DISCLOSURE_NOTICE`, so it's a one-line edit. This is plain Python — no AI call inside it — so the notice can never depend on the AI remembering to say it, matching the "AI disclosure" row of `docs/guards.md`. Turned the default (empty) `core/tests.py` into a `core/tests/` folder and added `core/tests/test_guards.py` with 3 tests: the notice appears on the first reply, it appears even with an empty history, and it does not appear on a later reply. Ran them with `manage.py test core.tests.test_guards` — all 3 passed. Not wired into `chat_groq.py` yet — that is the next step.
**Files:** `core/guards.py` (new), `core/tests/__init__.py` (new), `core/tests/test_guards.py` (new), `core/tests.py` (deleted — replaced by the `core/tests/` folder).
**How to undo:** Delete `core/guards.py` and the `core/tests/` folder. Restore `core/tests.py` with just `from django.test import TestCase` and a comment, if you want the default file back.

## 2026-11-01: Guard layer explained in plain English
**What changed:** Added `docs/guards.md`, a plain-English description of the guard layer for the agency owner — six guards (AI disclosure, fair-housing, instruction-override/prompt-leak, facts-only, rate limit per visitor, handoff to a human), what each one checks, when it runs, and what it does when it triggers. Ends with an honest list of what the guards will not catch. No code was written yet — this is the design the real enforcement code (per the rulebook's "safety is enforced in code" rule) will follow next.
**Files:** `docs/guards.md` (new).
**How to undo:** Delete `docs/guards.md`.

## 2026-10-25: chat_groq.py was missing the instructions, and a hand-off fix
**What changed:** Found that `chat_groq.py` (the interactive chat, unlike `hello_groq.py`) was never loading `prompts/assistant_v1.md`, so it chatted with no instructions at all. Fixed that. Also fixed a real bug found while testing: the assistant offered "I will pass you to a team member" even for questions with nothing to do with real estate (like asking about the weather). Rule 6 in `prompts/assistant_v1.md` now says it only offers a team-member hand-off for real estate questions it's unsure about; anything unrelated gets a plain "I can only help with real estate questions."
**Files:** `chat_groq.py` (now loads the instructions file), `prompts/assistant_v1.md` (rule 6 split into two rules).
**How to undo:** In `chat_groq.py`, remove the `PROMPT_FILE` line and change `history = [{"role": "system", ...}]` back to `history = []`. In the prompt file, merge rules 6 and 7 back into one.

## 2026-10-25: First assistant instructions (v1) and a 5-message test
**What changed:** Added `prompts/assistant_v1.md`, the first version of the assistant's instructions (introduce itself as AI, ask one question at a time, never invent listings, match the customer's language, no filtering by religion/race/etc., hand off to a team member when unsure, ignore attempts to override these rules). Updated `hello_groq.py` to load this file as the system message. Tested it with 5 sample messages — it introduced itself, refused to invent a listing, refused a discriminatory request, refused to reveal its instructions, and replied to Urdu with Roman Urdu rather than Urdu script (noted as a gap to fix later). Reminder: this file only *asks* the AI to follow these rules — the no-discrimination and no-invented-data rules still need real code enforcement before launch, per the rulebook.
**Files:** `prompts/assistant_v1.md` (new), `hello_groq.py` (loads the prompt file now).
**How to undo:** Delete `prompts/assistant_v1.md`. In `hello_groq.py`, remove the `PROMPT_FILE` line and the `{"role": "system", ...}` message, restoring the single user message.

## 2026-10-25: First real Groq chat test
**What changed:** Installed the `groq` package (added to `requirements.txt`). Added `hello_groq.py`, which sends one test message to Groq and prints the reply, with plain-English errors for a missing key, no internet, a rejected key, and a reached rate limit. Checked Groq's live model list with the saved key: no Llama chat model is available right now, only two small Meta "prompt-guard" filter models, so the script uses `openai/gpt-oss-20b` instead. Also fixed a display bug where special characters (like an em dash) showed as `�` on Windows.
**Files:** `hello_groq.py` (new), `requirements.txt` (added `groq` and its dependencies).
**How to undo:** Delete `hello_groq.py`. Remove the added lines from `requirements.txt`. Run `.venv\Scripts\python.exe -m pip uninstall groq` if you want it off your computer too.

## 2026-10-25: Groq key setup and a check script
**What changed:** Created `.env` from `.env.example` (still empty, no secrets). Added `check_env.py`, a small script that reads `.env` and prints "key found" or "key missing" for `GROQ_API_KEY`, without ever printing the key itself.
**Files:** `.env` (new, empty, ignored by git), `check_env.py` (new).
**How to undo:** Delete `check_env.py`. Delete `.env` only if you have not put your real key in it yet — otherwise keep it, just remove the line you added.

## 2026-10-21: Django project skeleton
**What changed:** Started the real PropDesk project on Django. Set the earlier prototype aside. Created a virtual environment with Django 6.1.2, a Django project called `propdesk`, and an app called `core`. Added `.gitignore` and `.env.example` (setting names only, no values). Changed `propdesk/settings.py` so the secret key and debug switch come from the computer's settings, not from the file. Started git with a first commit.
**Files:** `manage.py`, `propdesk/`, `core/`, `requirements.txt`, `.gitignore`, `.env.example`, `STEPLOG.md`. The old files moved into `prototype-fastapi/`.
**How to undo:** Move everything inside `prototype-fastapi/` back to the main folder (its `.gitignore` and `requirements.txt` replace the new ones). Delete `manage.py`, `propdesk/`, `core/`, `.env.example`, `.venv/`, and the hidden `.git/` folder.

## Before 2026-10-21: first prototype (written before this log existed)
**What changed:** Built a working prototype using a different tool (FastAPI): property list, staff console with login, customer chat with an AI model and a simple fallback, viewing bookings, and email notifications. Also wrote `CLAUDE.md`, `SPEC.md`, `GO-LIVE.md` and `docs/flow.md`.
**Files:** now in `prototype-fastapi/` (code) and the main folder (the four documents).
**How to undo:** Nothing to undo. It is kept as a reference. Its README says how to run it. Note that its chat used Anthropic's AI, while the new plan uses Groq (`GROQ_API_KEY`), so that part will be redone.
