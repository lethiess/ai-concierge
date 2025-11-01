# Project Instructions

## Setup commands
- Install deps: `uv sync --extra dev`
- Start dev server: `python -m concierge`
- Run tests: `pytest`


## Code Style
Use PEP8 standards for all code (indentation, spacing, naming)

Prefer snake_case naming for variables and functions

Use type hints in all function definitions

Write docstrings for classes, methods, and modules using standard Python formats

Organize imports according to PEP8 (standard library, third-party, local)

## Architecture
Structure agents as stateless, modular classes using the OpenAI Agents SDK

Keep business logic separate from agent orchestration or API integration

Prefer dependency injection where possible for configuration and resources

Write unit tests for all agent actions and APIs using pytest or unittest

## General Guidelines
Use logging for debugging and tracing agent actions

Avoid code duplication; refactor to reusable modules if logic repeats

Document agent inputs, outputs, and communications clearly

Follow the single-responsibility principle for agent and utility classes

