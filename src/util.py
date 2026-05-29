import os
from dotenv import load_dotenv

load_dotenv()


def load_system_prompt() -> str:
    """Load the main system prompt from the file configured in the environment."""
    prompt_file = os.getenv("SYSTEM_PROMPT_FILE")

    if prompt_file:
        return load_prompt(prompt_file)

    return None


def load_prompt(prompt_file: str) -> str:
    """Read and return the full contents of a prompt file."""
    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read()
