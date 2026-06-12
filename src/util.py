from config import SYSTEM_PROMPT_FILE


def load_system_prompt() -> str:
    """Load the main system prompt"""
    if SYSTEM_PROMPT_FILE:
        return load_prompt(SYSTEM_PROMPT_FILE)

    return None


def load_prompt(prompt_file: str) -> str:
    """Read and return the full contents of a prompt file."""
    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read()
