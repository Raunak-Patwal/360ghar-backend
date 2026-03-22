# 360Ghar Backend Operating Contract

This repository uses repo-local docs as the source of truth for contributors and agents. The goal is to keep architecture, contribution rules, and test expectations explicit and lightly enforced.

## Operating Docs
- [Architecture Contract](docs/architecture-contract.md)
- [Contribution Contract](docs/contribution-contract.md)
- [Testing Contract](docs/testing-contract.md)
- [Terminology And Ownership](docs/terminology-and-ownership.md)
- [Machine Contract Inventory](docs/repo-contract.json)

## Build And Validation
```bash
docker-compose up -d db redis
python3 run.py
pytest tests/ -v
python3 scripts/validate_docs_contracts.py
```

> **Note:** Dev dependencies (pytest, ruff, mypy) are in the `dev` optional group. Install with `pip install ".[dev]"` or `uv sync --extra dev`.

## Layering Rules
- HTTP endpoints in `app/api/api_v1/endpoints/` validate input, enforce auth through dependencies, and delegate business logic to `app/services/`.
- REST route composition lives in `app/api/api_v1/api.py`; app wiring, middleware, lifespan, and MCP mounts live in `app/factory.py`.
- Business rules belong in `app/services/`. Reuse service functions from REST, MCP, and AI-agent surfaces instead of re-implementing them.
- Persistence models live in `app/models/`; request and response shapes live in `app/schemas/`.
- MCP servers and ChatGPT-specific tool wrappers live in `app/mcp/`. They may format tool responses, but authorization and state changes should still flow through shared services where possible.
- AI-agent orchestration lives in `app/services/ai_agent/`. Tool registration and model streaming belong there, but tool behavior should still call shared service-layer code.
- Cross-cutting infrastructure belongs in `app/core/`, `app/middleware/`, and `app/vector/`.

## Contributor Requirements
- New REST endpoint modules must be routed through `app/api/api_v1/api.py`, covered by tests, and registered in `docs/repo-contract.json`.
- New service modules must follow existing naming conventions, keep I/O async when touching the database, and be registered in `docs/repo-contract.json`.
- New MCP tools, widget bindings, or AI-agent tool bridges must update the architecture and terminology docs when they add a new public surface or execution pattern.
- New background jobs or schedulers must be wired through `app/factory.py` startup and documented in the architecture contract.
- Do not add new dependencies without checking current upstream documentation and compatibility with Python 3.10+, FastAPI, SQLAlchemy 2.x, and Pydantic v2.

## When To Update Docs
- Any new public endpoint or router family
- Any new service module or new nested service package
- Any new MCP tool, widget bundle, or AI-agent tool bridge
- Any new scheduler, background processing flow, or startup job
- Any new top-level runtime directory under `app/`, `tests/`, or `docs/`

## Documentation Drift Checklist
- New public endpoint
- New service domain
- New MCP tool or widget
- New background or scheduler flow
- If any item changed, update the relevant doc in `docs/` and `docs/repo-contract.json`
