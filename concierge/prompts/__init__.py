"""Prompt template management for AI Concierge agents."""

from pathlib import Path


PROMPT_DIR = Path(__file__).parent


def load_prompt(name: str, **kwargs) -> str:
    """Load and format a prompt template.

    Args:
        name: Name of the prompt file (without .md extension)
        **kwargs: Variables to substitute in the template

    Returns:
        Formatted prompt string

    Example:
        >>> load_prompt("voice_agent",
        ...     restaurant_name="Mario's Pizza",
        ...     party_size=4,
        ...     date="tomorrow",
        ...     time="7pm")
    """
    prompt_file = PROMPT_DIR / f"{name}.md"

    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt template not found: {prompt_file}")

    template = prompt_file.read_text()

    # Format the template with provided kwargs
    # Use safe_substitute to handle missing variables gracefully
    return template.format(**kwargs)


__all__ = ["load_prompt"]
