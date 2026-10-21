# PropDesk

An AI assistant for a real estate agency. Customers chat on a web page, ask about properties, and book viewings. Staff manage everything in a web console.

## What exists so far (Stage 1)

- **Property list**: a small database (`data/propdesk.db`) that stores every property.
- **Staff console**: a web page where staff can add, edit and delete properties.

- **Customer chat (basic)**: open http://127.0.0.1:8000/chat.html. It understands bedrooms, budget ("under 2m"), property type and area, and answers from the property list. It only shows available properties. It uses simple rules, not an AI model yet.

- **Viewing bookings**: in the chat, say "book #2" (the number is shown next to each property) and the assistant asks for a day, a time, your name and phone. Viewings are one hour long, 10:00 to 17:00, up to 60 days ahead, and one customer per time slot, so double-booking is not possible. Staff see all bookings at the bottom of the console and can cancel them. A property with upcoming viewings cannot be deleted until they are cancelled.

- **Staff logins**: the console and all staff data are locked behind a login. Customers can still use the chat. Sessions last 8 hours, and 5 wrong passwords in a row blocks that username for 5 minutes. Passwords are stored scrambled (hashed), never as typed.

- **AI assistant (Claude)**: when an Anthropic API key is available, the chat is answered by the Claude AI model instead of the simple rules. It can only look at the real property list, check free viewing times and book viewings, through the same safe rules as before. If there is no key, the limit is reached, or the AI service is down, the chat quietly falls back to the simple rule-based version, so it never goes dead.

- **Email notifications**: when email is set up (see below), the system sends a confirmation to the customer and an alert to your staff address when a viewing is booked, a cancellation notice when staff cancel one, and a reminder to the customer about 24 hours before the viewing. The customer's email is optional; the chat asks for it and they can say "skip". With no email set up, everything else works normally.

Not built yet: text/WhatsApp messages.

## Turning email on

You need an email account that can send through SMTP (the standard way programs send email). For Gmail, create an "app password"; for a business address, ask your email provider for the SMTP details. Set these in the terminal before starting the server (use `$env:NAME = "value"` in PowerShell, `set NAME=value` in Command Prompt). Keep the password out of files and chat.

- `PROPDESK_SMTP_HOST` (for example `smtp.gmail.com`). Email stays off until this is set.
- `PROPDESK_SMTP_PORT` (default 587; 465 also works)
- `PROPDESK_SMTP_USER` and `PROPDESK_SMTP_PASSWORD`
- `PROPDESK_EMAIL_FROM` (optional, defaults to the user)
- `PROPDESK_STAFF_EMAIL`: who gets the alerts, one address or several separated by commas
- `PROPDESK_AGENCY_NAME` (optional, shown in emails; default PropDesk)

Safety limits: at most 3 emails per customer address per day and 200 emails per day in total (`PROPDESK_EMAIL_DAILY_LIMIT`), so nobody can use your booking form to spam others. If email fails, the booking still goes through. Reminders are checked every 10 minutes while the server is running, so the server must stay on. Run only one copy of the server, or reminders may be sent twice.

## Turning the AI on

1. Get an API key from the Anthropic Console (console.anthropic.com). Keep it secret; never paste it into a file in this folder or into the chat.
2. In the terminal, before starting the server, set it for that window only:

```bash
set ANTHROPIC_API_KEY=your-key-here
.venv\Scripts\python -m uvicorn backend.main:app --port 8000
```

(In PowerShell use `$env:ANTHROPIC_API_KEY = "your-key-here"` instead of `set`.)

Settings (all optional, set the same way):
- `PROPDESK_AI=off` switches the AI off and uses the simple chat.
- `PROPDESK_MODEL` picks the Claude model. The default is `claude-opus-5-5`; `claude-sonnet-5-5` or `claude-haiku-5-5` are cheaper.
- `PROPDESK_AI_DAILY_LIMIT` is the most AI replies per day (default 500). Each visitor is also limited to 20 AI replies per 10 minutes. These stop strangers from running up your bill; over the limit, the simple chat takes over.

The AI is paid per use. Check cost and answers on a few real conversations before you put it on your website.

## Creating a staff account

There is no default account. Create the first one yourself (it asks for the password and hides it as you type):

```bash
.venv\Scripts\python -m backend.create_staff yourname
```

Running it again for the same name resets that person's password. Then open http://127.0.0.1:8000 and log in.

## Before putting this on the internet

- Serve it over HTTPS (secure web address) and set the environment variable `PROPDESK_HTTPS=1` so the login cookie is only sent over HTTPS.
- Passwords and sessions are fine for a small team, but there is no "forgot password" page or two-step login yet.

## How to run it

Open a terminal in this folder, then:

```bash
.venv\Scripts\python -m uvicorn backend.main:app --port 8000
```

Then open http://127.0.0.1:8000 in your browser. Press Ctrl+C in the terminal to stop it.

To add three sample properties (only works when the list is empty):

```bash
.venv\Scripts\python -m backend.seed
```

## First-time setup (already done on this computer)

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## What is where

- `backend/` : the behind-the-scenes part. `main.py` handles requests, `database.py` stores data.
- `static/` : the staff console web page (`index.html`, `style.css`, `app.js`).
- `data/` : where the property database file lives.
