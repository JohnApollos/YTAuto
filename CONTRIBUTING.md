# Contributing to Autonomous Media

As a single-operator project, these guidelines are primarily written to enforce discipline and serve future operators or hires.

## Getting Started

1. Set up your Python environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Start background services using Docker (Postgres, Redis, MinIO):
   ```bash
   docker compose up -d
   ```

3. Initialize the database schema:
   ```bash
   alembic upgrade head
   ```

## Development Workflow

- **Branching**: Use feature branches (`feature/name` or `fix/name`) for any new capability. 
- **Commits**: Write clear, descriptive commit messages. Focus on the *why* rather than just the *what*.
- **Documentation**: If your change affects architecture, create an ADR in `docs/adr/`.

## Running Tests

Tests are executed using `pytest`.
```bash
python -m pytest tests/
```
Ensure all tests pass locally before merging feature branches to `main`.
