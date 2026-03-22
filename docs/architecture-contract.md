# Architecture Contract

This document defines the current backend shape. It is normative: new code should fit these boundaries unless the contract is updated in the same change.

## Runtime Surfaces
- REST API: [`app/api/api_v1/api.py`](../app/api/api_v1/api.py) wires all versioned routers; [`app/factory.py`](../app/factory.py) mounts the API, websocket routes, share routes, and MCP servers.
- Core marketplace and booking flows live in `app/services/property.py`, `app/services/swipe.py`, `app/services/visit.py`, and `app/services/booking.py`.
- Property Management flows live in `app/services/pm_*.py` and the matching `app/api/api_v1/endpoints/pm_*.py` endpoints.
- Tours and media flows live in `app/services/tour.py`, `app/services/tour_ai.py`, and the tour endpoint modules.
- MCP surfaces live in `app/mcp/user_server.py`, `app/mcp/admin_server.py`, and ChatGPT adapters such as [`app/mcp/chatgpt/visit_tools.py`](../app/mcp/chatgpt/visit_tools.py).
- AI-agent orchestration lives in `app/services/ai_agent/`, especially [`app/services/ai_agent/tool_bridge.py`](../app/services/ai_agent/tool_bridge.py) and `agent_service.py`.
- Vector search and sync live in `app/vector/` and the vector sync scheduler.
- Startup jobs and schedulers are started from `app/factory.py` and currently include blog auto publish, notifications, and vector sync.

## Layer Contracts
- `app/api` depends on `app.schemas`, `app.services`, `app.core`, and dependency modules. It should not own business rules that are needed elsewhere.
- `app/services` depends on `app.models`, `app.schemas`, `app.repositories`, `app.core`, and narrowly-scoped external clients.
- `app/mcp` may depend on `app.services`, `app.schemas`, `app.core`, and serializer/formatter helpers. MCP tools should not create alternate business-rule paths when a service already exists.
- `app/services/ai_agent` may orchestrate models, tool registration, and streaming, but tool execution should prefer shared service-layer behavior over agent-only mutations.
- `app/models` and `app/schemas` are leaf data layers. They should not import endpoint or transport code.

## Approved Extension Points
- Add new REST functionality by creating an endpoint module in `app/api/api_v1/endpoints/`, a service module or service function in `app/services/`, and matching schemas in `app/schemas/`.
- Add new MCP capabilities by extending `app/mcp/user_server.py`, `app/mcp/admin_server.py`, or the ChatGPT wrappers, while reusing existing services for authz and persistence.
- Add new AI-agent capabilities by extending `app/services/ai_agent/tool_bridge.py` or related agent orchestration files, while keeping transport-specific logic out of shared services.
- Add new background automation via dedicated scheduler modules in `app/services/` and explicit startup wiring in `app/factory.py`.

## Known Anti-Patterns To Avoid
- Repeating auth, DB session bootstrapping, or validation logic separately in REST, MCP, and AI-agent flows when the same business action already exists in a shared service.
- Mutating ORM state directly inside endpoint or tool wrappers when an equivalent service abstraction exists or should be added.
- Introducing new public runtime surfaces without updating `AGENTS.md`, this contract, and `docs/repo-contract.json`.
