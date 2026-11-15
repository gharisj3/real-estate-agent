"""Check that GROQ_API_KEY is set in .env — without ever printing the key."""
import pathlib

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


def main():
    values = read_env_file(ENV_FILE)
    key = values.get("GROQ_API_KEY", "")
    if key:
        print("key found")
    else:
        print("key missing")


if __name__ == "__main__":
    main()
