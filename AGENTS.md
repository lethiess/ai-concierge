# AI Concierge Agent Playbook

This document provides instructions for AI agents working on the AI Concierge project.

## Project Overview
AI Concierge is a restaurant reservation system that uses OpenAI Agents SDK and Twilio to make real-time voice calls. It features a multi-agent architecture with an orchestrator and specialized agents for reservation, cancellation, and search.

## Architecture
See [docs/architecture.md](docs/architecture.md) for detailed system architecture and agent flows.

## Development

### Environment Setup
- The project uses `uv` for dependency management.
- Python 3.13+ is required.
- Virtual environment is located in `.venv`.

### Running Tests
Run the test suite to verify agent logic and tool integration:
```bash
uv run pytest
```

### Code Quality
Ensure code style and quality with Ruff. Always run these before committing changes:
```bash
uv run ruff check .
uv run ruff format .
```

## Project Structure
- `src/concierge/agents/`: Agent implementations (Orchestrator, Reservation, Cancellation, Voice).
- `src/concierge/services/`: Core services (Twilio, CallManager, RestaurantService).
- `src/concierge/api.py`: FastAPI server for Twilio webhooks.
- `tests/`: Pytest test suite.
- `docs/`: Documentation and architecture diagrams.

## Key Conventions
- **Agents**: Use `Agent` class from `agents` package.
- **Voice**: Use `RealtimeAgent` for voice capabilities.
- **Tools**: Define tools as standalone functions or methods.
- **Logging**: Use standard `logging` module.
- **Type Hinting**: Use strict type hints for all function signatures.
