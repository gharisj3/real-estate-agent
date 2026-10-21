# PropDesk rulebook

Read this at the start of every session and follow it.

## About the project
PropDesk is a real estate AI assistant for [AGENCY NAME], which operates in
Pakistan and the UAE. Customers chat with it on a web page, ask about
properties, and book viewings. Staff manage everything in a web console.
See README.md for how to run it and GO-LIVE.md for the launch checklist.

## How to work with the student
- The student is not a programmer. Use short sentences and plain English.
  If a technical word is needed, explain it in brackets.
- Before you write code, say in one or two sentences what you are about to
  do and why.
- After you finish, say how to check that it worked.
- Work in small steps. Never change more than one feature at a time.

## Secrets
- Never put secrets (API keys, passwords) in code or in chat.
- Secrets live only in a file called .env.
- .env must never be committed to git. Keep it listed in .gitignore.

## Safety is enforced in code
- Safety rules are enforced in code, not in prompts.
- The AI can suggest. Plain code decides what is allowed.
- Never rely on an instruction to the AI as the only protection for a rule.

## Fair treatment of customers
- The assistant must never filter, rank or steer properties by a customer's
  religion, race, nationality, sex, family status or disability.
- This covers search results, their order, recommendations, and wording.

## Honesty
- The assistant must tell customers at the start of every chat that it is
  an AI assistant.

## Step log
- Keep a file called STEPLOG.md.
- After each task, add a dated entry: what changed, which files, and how to
  undo it.
