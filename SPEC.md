# PropDesk: version 1 spec

## What PropDesk does
1. PropDesk is an AI assistant (a computer program that chats like a person) for [AGENCY NAME], which buys, sells and rents property in Pakistan and the UAE.
2. Customers chat on a web page and ask about homes, offices, clinics, commercial buildings and similar, to buy or to rent.
3. The assistant answers only from the agency's own property list, and tells every customer at the start that it is an AI.
4. When a customer wants to see a property, the assistant collects the request, and a Sales Rep confirms the visit time.
5. Staff run everything from a web console (a private management page that needs a login).

## Who uses it

**Customer** (no login)
- Chats with the assistant, asks about properties, and asks for a viewing.
- Can ask for a person at any time.

**Sales Rep** (staff, has a login)
- Adds properties to the list.
- Takes over chats that are handed to them.
- Follows up on viewing requests and confirms the visit time with the customer.

**Owner/admin** (staff, has a login)
- Everything a Sales Rep can do, plus:
- Adds and removes staff.
- Deletes properties.
- Sees all chats.
- Changes the rules for the assistant (what it may and may not say).
- Takes over any chat.

## A customer's journey
1. The customer opens the chat page. The assistant greets them and says it is an AI assistant.
2. The customer says what they want: buy or rent, the kind of property, area, budget, size.
3. The assistant looks through the available properties and shows the ones that match, with plain facts: place, price, size. It never filters, ranks or steers by religion, race, nationality, sex, family status or disability.
4. The customer asks questions about a property. The assistant answers only from the listing. If the answer is not in the listing, it says so and offers a Sales Rep.
5. The customer asks to see a property. The assistant asks for the property, a preferred day and time, their name and phone number, and an email address (optional).
6. The assistant reads the details back. The customer says yes.
7. The assistant records a viewing request marked "waiting for confirmation" and hands the chat to a Sales Rep who is free at that moment.
8. The Sales Rep contacts the customer and confirms the actual visit time.
9. The customer gets a confirmation, and a reminder about a day before the visit (by email, if they gave one).

## What the assistant must refuse or hand to a human

**Hand to a Sales Rep** (whichever rep is free at that moment)
- Anyone who asks for a person.
- Anyone who is angry or upset.
- Questions about price negotiation, mortgages, or legal matters.
- Confirming the time of a site visit.

**Refuse politely, and say what it can help with instead**
- Sharing an owner's personal details.
- Promising that a property will rise in value.
- Discussing other agencies' properties.
- Answering questions that have nothing to do with property.
- Filtering, ranking or steering properties by a customer's religion, race, nationality, sex, family status or disability.

These rules are checked by plain program code, not left to the AI alone. The AI can suggest; the code decides.

## What is NOT in version 1
- Chat in Urdu or Arabic. Version 1 is English only.
- Photos and virtual tours.
- Text or WhatsApp messages.
- Payments or deposits.
- Rental contracts.
- Mortgage calculators.
- A portal for property owners.
- Reports or statistics.
