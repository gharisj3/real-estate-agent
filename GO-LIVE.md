# PropDesk go-live checklist

Tick each box before real customers use it. "Must" items are blockers. "Should" items can follow in the first weeks.

## 1. Must: the basics that would break or embarrass you

- [ ] **Set the server's clock to Dubai time.** Viewing times use the clock of the computer running PropDesk. Hosting companies usually default to UTC (world standard time), which would put every viewing hours off. Set the server's time zone to Asia/Dubai (on Linux, set the environment variable `TZ=Asia/Dubai`). This computer is currently on US Eastern time, so do not judge times here.
- [ ] **Remove the test data.** The database still holds three sample properties and one cancelled test booking ("Sara Khan"). Delete the samples in the staff console, then add your real listings. Never run the seed command on the live database.
- [ ] **Create real staff accounts** with strong, unique passwords (`python -m backend.create_staff name`). Give each person their own account. There is no "forgot password" page and no two-step login yet. To reset a password, run the same command again.
- [ ] **Use HTTPS** (the padlock, a secure web address). Without it, staff passwords travel readable. Most hosts give this for free. Then set `PROPDESK_HTTPS=1` so the login cookie only travels over HTTPS.
- [ ] **Keep secrets out of files.** The Anthropic key and the email password go into the host's "environment variables" (private settings screen), never into the project folder, the chat, or email.
- [ ] **Run exactly one copy of the server.** Reminders and the spam limits live in the server's memory, so two copies would send reminders twice and count limits separately.

## 2. Must: hosting

- [ ] **Pick a host that runs a Python program all day** (a small rented server such as a VPS, or a service like Render, Railway or Fly.io). Your own Windows PC is not suitable: it sleeps, restarts, and changes address.
- [ ] **The database file needs a permanent disk.** PropDesk keeps everything in `data/propdesk.db`. Some hosts wipe the program's disk on every update. Choose a host with a "persistent volume", or the properties and bookings will vanish.
- [ ] **Behind the host's front door:** if the host's secure front door (called a proxy) is a separate machine, start the server with `--forwarded-allow-ips="*"` only if the host says it is safe, otherwise login lockouts and visitor limits will treat every visitor as one person. Ask the host which setting applies.
- [ ] **Start command:** `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000` (the host will usually tell you which port to use).
- [ ] **Restart automatically** if the program crashes (most hosts do this; check).

## 3. Must: backups

- [ ] **Back up `data/propdesk.db` every day** and keep copies somewhere else (a different service from the host). Test once that a backup actually restores. Without this, one disk failure loses every property and booking.

## 4. Must: the AI

- [ ] **You have not yet seen the AI answer a real question.** Before launch, set the key on a private test copy and hold 15 to 20 realistic conversations: wrong spellings, Arabic, angry customers, "ignore your rules" tricks, booking changes of mind. Read every answer.
- [ ] **Set a spending limit in the Anthropic Console** (your account's billing page) as a second safety net. PropDesk also caps replies (500 a day, 20 per visitor per 10 minutes), but the console limit is the one that protects your card.
- [ ] **Decide which model.** The default is the most capable and costs the most per reply. A cheaper model may be good enough; test both on the same conversations.
- [ ] If the AI is down or the limit is hit, the simple chat takes over. Confirm that works once on the live site.

## 5. Must: email

- [ ] **Send a real test booking** and confirm the customer email, staff alert, cancellation and (with a booking about a day out) reminder all arrive. This has only been tested with a pretend mail server.
- [ ] **Check emails do not land in spam.** Send to a Gmail and an Outlook address. Ask whoever manages your website's address (domain) to set up SPF, DKIM and DMARC (three standard "this email is really from us" records). Send from an address on your own domain, not a free one.
- [ ] Make sure at least one person actually reads the staff alert address.

## 6. Must: privacy and the law (ask a professional, I cannot advise on this)

- [ ] **Tell customers what you keep.** The chat collects names, phone numbers and emails. Add a short notice on the chat page saying what is collected, why, and who to contact to remove it. Customer messages are also sent to Anthropic when the AI is on, so say that too.
- [ ] **Say it is an AI**, so customers know they are not talking to a person.
- [ ] **Check your local data-protection rules** (for the UAE, the personal data protection law and any rules from your real estate regulator) and decide how long you keep old bookings.

## 7. Should: abuse and mistakes to expect

- [ ] **Fake bookings.** Anyone can book through the chat without proving who they are, so a prankster could fill the calendar. Staff can cancel bookings, but there is no per-visitor booking limit and no phone verification yet. Watch the bookings list daily at first, and ask me to add a limit if it happens.
- [ ] **No staff audit trail.** The system does not record who changed or cancelled what.
- [ ] **Properties have no photos yet** (the field exists but is not used). Customers cannot see pictures in the chat.
- [ ] **Staff accounts are managed only by command line.** Whoever manages the server has to add or remove people.
- [ ] **Login lockouts reset** whenever the server restarts.

## 8. Should: putting the chat on your website

- [ ] The chat is a standalone page (`/chat.html`). Link to it from your website, or embed it in a frame, or ask me to build a small chat bubble you paste into any page. Use your own web address (for example `chat.youragency.com`), not the host's default one.
- [ ] Keep the staff console on a web address you do not advertise. It is protected by login, but there is no reason to publish it.

## 9. Should: after launch

- [ ] **Watch it daily for the first two weeks:** read the chat questions that failed, check the bookings list, check the server's log for errors, and check the Anthropic usage page.
- [ ] **Set up an "is it up?" check** (free services such as UptimeRobot ping your site and email you if it stops answering).
- [ ] **Keep the software updated** every month or two (the Python packages in `requirements.txt`).
- [ ] **Write down who does what:** who adds properties, who answers booking alerts, who restores backups, who pays the bills.
