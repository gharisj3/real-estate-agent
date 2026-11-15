"""Chat with Groq in the terminal. Type 'exit' to stop."""
import pathlib
import sys

from groq import APIConnectionError, AuthenticationError, Groq, RateLimitError

# Make sure special characters (like em dashes) print correctly on Windows.
sys.stdout.reconfigure(encoding="utf-8")

ENV_FILE = pathlib.Path(__file__).resolve().parent / ".env"
PROMPT_FILE = pathlib.Path(__file__).resolve().parent / "prompts" / "assistant_v1.md"

# No Llama chat model is on Groq's list right now (checked live on 2026-10-25).
MODEL = "openai/gpt-oss-20b"


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


def main():
    api_key = read_env_file(ENV_FILE).get("GROQ_API_KEY", "")
    if not api_key:
        print("Error: no Groq key found. Add GROQ_API_KEY to your .env file.")
        sys.exit(1)

    if not PROMPT_FILE.exists():
        print(f"Error: instructions file not found at {PROMPT_FILE}.")
        sys.exit(1)
    system_prompt = PROMPT_FILE.read_text(encoding="utf-8")

    client = Groq(api_key=api_key)
    history = [{"role": "system", "content": system_prompt}]

    print("Chatting with Groq. Type 'exit' to stop.\n")

    while True:
        user_text = input("You: ").strip()
        if not user_text:
            continue
        if user_text.lower() in ("exit", "quit"):
            print("Bye!")
            break

        history.append({"role": "user", "content": user_text})

        try:
            response = client.chat.completions.create(model=MODEL, messages=history)
        except AuthenticationError:
            print("Error: Groq rejected the key. Check GROQ_API_KEY in .env is correct.")
            break
        except APIConnectionError:
            print("Error: could not reach Groq. Check your internet connection and try again.")
            continue
        except RateLimitError:
            print("Error: Groq's rate limit was reached. Wait a bit and try again.")
            continue

        reply = response.choices[0].message.content
        history.append({"role": "assistant", "content": reply})
        print(f"Groq: {reply}\n")


if __name__ == "__main__":
    main()
