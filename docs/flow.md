# PropDesk flow

This is the plan from SPEC.md, drawn as a picture. Solid boxes already exist in some form. Dashed boxes are not built yet.

```mermaid
flowchart TD
    C["Customer types a message"] --> W["Web chat page<br/>Says first: I am an AI assistant"]
    W --> R{"Router<br/>Works out what the customer wants"}

    R -->|"Looking for a property"| H1["Finds matching properties"]
    R -->|"Question about a property"| H2["Answers from the property listing"]
    R -->|"Wants to see a property"| H3["Collects the viewing request"]
    R -->|"Asks for a person, is angry, or raises<br/>price talks, mortgages or legal matters"| H4["Hands the chat to a free Sales Rep"]
    R -->|"Off-topic, owner details, other agencies,<br/>value promises, or unfair filtering"| H5["Politely says no"]

    H1 <--> DB[("Database<br/>Properties, viewing requests, chats")]
    H2 <--> DB
    H3 --> DB
    H4 --> DB

    DB --> S["Safety check by plain code<br/>Fair treatment, refused topics, AI notice"]
    H5 --> S
    S --> A["Reply to the customer"]
    A --> W

    subgraph STAFF["Staff console - needs a login"]
        direction TB
        SR["Sales Rep<br/>Adds properties<br/>Follows up on viewing requests<br/>Confirms the visit time"]
        TO["Takes over a chat handed to them"]
        OA["Owner or admin<br/>Does everything a Sales Rep does, plus:<br/>adds and removes staff, deletes properties,<br/>sees all chats, takes over any chat"]
        RU["Changes the rules for the assistant"]
    end

    SR <--> DB
    OA <--> DB
    TO -->|"Talks to the customer in the same chat"| W
    OA --> TO
    OA --> RU
    RU -->|"Sets what it may and may not say"| R
    RU --> S
    SR -->|"Visit time confirmed"| E["Email to the customer<br/>Confirmation, then a reminder the day before"]
    E --> C

    classDef planned stroke-dasharray: 6 4,stroke:#b45309,fill:#fffbeb,color:#222;
    class R,H4,H5,S,TO,RU planned;
```

## How to read it

- **Solid boxes** exist today in some form: the chat page, finding properties, answering questions, collecting a viewing request, the database, the staff console for properties and bookings, and the emails.
- **Dashed orange boxes** are in SPEC.md but not built yet: the router, the handover to a Sales Rep, the polite refusals enforced in code, the safety check, chat takeover, and editing the assistant's rules.
- **Also not built yet, though drawn as solid:** separate Sales Rep and Owner/admin logins, saving chat history, and a Sales Rep (not the system) confirming the visit time. Today every staff login can do everything, chats are not saved, and a viewing is confirmed instantly.
