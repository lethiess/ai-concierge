import os
from agents import set_default_openai_key

set_default_openai_key(os.getenv("OPENAI_API_KEY"))


def main():
    print("Hello from concierce!")


if __name__ == "__main__":
    main()
