"""Send one test message to Groq and print the reply."""
import pathlib
import sys

from groq import APIConnectionError, AuthenticationError, Groq, RateLimitError

# Make sure special characters (like em dashes) print correctly on Windows.
sys.stdout.reconfigure(encoding="utf-8")

ENV_FILE = pathlib.Path(__file__).resolve().parent / ".env"
PROMPT_FILE = pathlib.Path(__file__).resolve().parent / "prompts" / "assistant_v1.md"

# No Llama chat model is on Groq's list right now (checked live on 2026-10-25).
# Using this one instead: fast, and good enough for a short customer greeting.
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

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "In one sentence, greet a customer of a real estate agency.",
                },
            ],
        )
    except AuthenticationError:
        print("Error: Groq rejected the key. Check GROQ_API_KEY in .env is correct.")
        sys.exit(1)
    except APIConnectionError:
        print("Error: could not reach Groq. Check your internet connection and try again.")
        sys.exit(1)
    except RateLimitError:
        print("Error: Groq's rate limit was reached. Wait a bit and try again.")
        sys.exit(1)

    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
