import os
from agents import Agent, function_tool, WebSearchTool, FileSearchTool, set_default_openai_key
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions

set_default_openai_key(os.getenv("OPENAI_API_KEY"))

def main():
    print("Hello from concierce!")


if __name__ == "__main__":
    main()
