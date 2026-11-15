"""Chat with Groq in the terminal, through PropDesk's guard pipeline.

Every message typed here goes through core.pipeline.handle_message(),
the same path any other chat channel must use — so this terminal chat
gets the same AI disclosure, fair-housing guard, instruction-override
guard, facts-only guard, and prompt-leak guard as a real customer chat
will. Type 'exit' to stop.
"""
import os
import pathlib
import sys
import uuid

# Make sure special characters (like em dashes) print correctly on Windows.
sys.stdout.reconfigure(encoding="utf-8")

ENV_FILE = pathlib.Path(__file__).resolve().parent / ".env"


def read_env_file(path):
    values = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def load_env_into_os_environ():
    """Copy every setting from .env into the real environment — without
    ever printing a value — so Django's settings and the guard pipeline
    can read them (GROQ_API_KEY, DJANGO_SECRET_KEY, GUARD_CANARY_TOKEN)."""
    for name, value in read_env_file(ENV_FILE).items():
        os.environ.setdefault(name, value)


def main():
    load_env_into_os_environ()

    if not os.environ.get("GROQ_API_KEY"):
        print("Error: no Groq key found. Add GROQ_API_KEY to your .env file.")
        sys.exit(1)

    # Django has to be set up before core.pipeline can be imported, since
    # the pipeline looks properties up in the database.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "propdesk.settings")
    import django

    django.setup()

    from core.pipeline import handle_message

    # One run of this script is one conversation, so one session id for
    # its whole lifetime is enough — this is what makes the AI
    # disclosure show up once, on the very first reply.
    session_id = str(uuid.uuid4())

    print("Chatting with Groq, through PropDesk's guards. Type 'exit' to stop.\n")

    while True:
        user_text = input("You: ").strip()
        if not user_text:
            continue
        if user_text.lower() in ("exit", "quit"):
            print("Bye!")
            break

        reply, steps_run = handle_message(session_id, user_text)
        print(f"Groq: {reply}\n")


if __name__ == "__main__":
    main()
